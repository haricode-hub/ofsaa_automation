"""
BD / ECM / SANC installation router.

Endpoints:
    POST   /start
    GET    /status/{task_id}
    GET    /tasks
    GET    /logs/{task_id}/full
    GET    /logs/{task_id}/tail
    POST   /test-connection
    GET    /rollback
    GET    /checkpoint
    DELETE /checkpoint
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from services.utils import shell_escape

from fastapi import APIRouter, HTTPException

from core.config import InstallationSteps
from core.task_manager import task_manager as tm
from core.dependencies import create_installation_service
from core.prompt_helpers import (
    make_osc_prompt_callback,
    make_envcheck_prompt_callback,
    make_setup_prompt_callback,
)
from schemas.installation import (
    InstallationRequest,
    InstallationResponse,
    InstallationStatus,
)
from services.ssh_service import SSHService

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/start", response_model=InstallationResponse)
async def start_installation(request: InstallationRequest):
    try:
        task_id = str(uuid.uuid4())

        tm.latest_request_cache["request"] = request.dict()
        tm.latest_request_cache["task_id"] = task_id
        tm.latest_request_cache["error"] = None

        tm.register_task(
            task_id,
            InstallationStatus(
                task_id=task_id,
                status="started",
                current_step="Initializing connection",
                current_module="BD_PACK",
                progress=0,
                logs=[
                    f"[INFO] Installation started (task {task_id[:8]})",
                    f"[INFO] Target: {request.host}",
                ],
            ),
        )
        tm.save_task_context(task_id, request=request.dict())

        asyncio_task = asyncio.create_task(run_installation_process(task_id, request))
        tm.register_asyncio_task(task_id, asyncio_task)

        return InstallationResponse(
            task_id=task_id,
            status="started",
            message="Installation process initiated",
        )
    except Exception as exc:
        logger.exception("Failed to start installation")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status/{task_id}", response_model=InstallationStatus)
async def get_installation_status(task_id: str):
    task = tm.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Installation task not found")
    return task


@router.get("/tasks")
async def list_installation_tasks():
    return {"tasks": list(tm.tasks.values())}


@router.get("/logs/{task_id}/full")
async def get_full_logs(task_id: str):
    logs = await tm.logs.read_all_logs(task_id)
    return {"task_id": task_id, "log_lines": logs, "total_lines": len(logs)}


@router.get("/logs/{task_id}/tail")
async def get_tail_logs(task_id: str, n: int = 50):
    logs = await tm.logs.read_last_n_logs(task_id, n)
    return {"task_id": task_id, "log_lines": logs, "total_lines": len(logs), "limit": n}


@router.post("/test-connection")
async def test_connection(request: InstallationRequest):
    ssh_service = SSHService()
    last_result: dict = {"success": False, "error": "SSH connection failed"}
    for attempt in range(1, 4):
        result = await ssh_service.test_connection(request.host, request.username, request.password)
        if result.get("success"):
            return {**result, "attempt": attempt}
        last_result = result
        if attempt < 3:
            await asyncio.sleep(1)
    return {**last_result, "attempt": 3}


@router.get("/rollback")
async def rollback():
    if not tm.latest_request_cache.get("request"):
        raise HTTPException(
            status_code=404,
            detail="No cached request found. No previous installation attempt or cache cleared.",
        )
    return {
        "success": True,
        "cached_request": tm.latest_request_cache["request"],
        "previous_error": tm.latest_request_cache.get("error"),
        "message": "Returning cached request values from previous run. You can modify and resubmit.",
    }


@router.get("/checkpoint")
async def get_checkpoint():
    if not tm.bd_checkpoint.get("completed"):
        raise HTTPException(
            status_code=404,
            detail="No BD Pack checkpoint found. BD Pack has not completed successfully yet.",
        )
    return {
        "success": True,
        "bd_pack_completed": True,
        "host": tm.bd_checkpoint.get("host"),
        "task_id": tm.bd_checkpoint.get("task_id"),
        "timestamp": tm.bd_checkpoint.get("timestamp"),
        "cached_request": tm.bd_checkpoint.get("request"),
        "message": "BD Pack checkpoint is available. You can resume ECM installation using resume_from_checkpoint=true.",
    }


@router.delete("/checkpoint")
async def clear_checkpoint():
    tm.clear_bd_checkpoint()
    return {"success": True, "message": "BD Pack checkpoint cleared."}


@router.delete("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task — kills SSH, stops async worker."""
    task = tm.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    cancelled = await tm.cancel_task(task_id, "Cancelled by user")
    if not cancelled:
        raise HTTPException(status_code=400, detail=f"Task is not running (status={task.status})")
    return {"success": True, "task_id": task_id, "message": "Task cancelled"}


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _ssh_connect(task_id: str, svc, host: str, username: str, password: str) -> bool:
    """Try SSH connection with 3 retries. Returns True on success."""
    for attempt in range(1, 4):
        await tm.append_output(task_id, f"[INFO] SSH connection attempt {attempt}/3")
        connection = await svc.ssh_service.test_connection(host, username, password)
        if connection.get("success"):
            await tm.append_output(task_id, "[OK] SSH connection established")
            return True
        if attempt < 3:
            await tm.append_output(task_id, "[WARN] SSH connection failed. Retrying...")
            await asyncio.sleep(1)
    error_msg = connection.get("error", "SSH connection failed after 3 attempts")
    await tm.append_output(task_id, f"[ERROR] {error_msg}")
    await tm.update_status(task_id, "failed", "SSH connection failed")
    return False


async def _restore_bd_on_ecm_failure(
    task_id: str,
    request: InstallationRequest,
    svc,
    trace,
) -> None:
    """Restore to BD state after ECM failure."""
    await tm.append_output(task_id, "\n[RECOVERY] ==================== ECM FAILURE - RESTORING BD STATE ====================")
    await tm.update_status(task_id, "running", "Restoring to BD state after ECM failure")
    tm.save_task_context(task_id, rollback_status="started", rollback_module="ECM", rollback_target="BD")

    db_sys_pass = request.db_sys_password or getattr(request, "schema_default_password", None)
    db_service = request.schema_jdbc_service or getattr(request, "ecm_schema_jdbc_service", None)

    if not db_sys_pass or not db_service:
        await tm.append_output(task_id, "[RECOVERY] WARNING: db_sys_password or schema_jdbc_service not provided.")
        await tm.append_output(task_id, "[RECOVERY] Cannot auto-restore DB schemas. Manual restore required.")

    manifest_result = await svc.select_restore_manifest(
        request,
        ["BD"],
        on_log=lambda line: tm.append_output(task_id, line),
    )
    if not manifest_result.get("success"):
        await tm.append_output(task_id, "[RECOVERY] ERROR: No valid BD restore manifest found.")
        await tm.append_output(task_id, f"[RECOVERY] {manifest_result.get('error', 'Manifest selection failed')}")
        await trace("BD restore manifest selection failed")
        return

    tm.save_task_context(task_id, restore_manifest_path=manifest_result.get("manifest_path"), restore_target_tag="BD")
    restore_result = await svc.full_restore_from_manifest(
        request.host,
        request.username,
        request.password,
        manifest=manifest_result["manifest"],
        db_sys_password=db_sys_pass or "",
        db_oracle_sid=getattr(request, "oracle_sid", None) or "OFSAADB",
        db_ssh_host=getattr(request, "db_ssh_host", None),
        db_ssh_username=getattr(request, "db_ssh_username", None),
        db_ssh_password=getattr(request, "db_ssh_password", None),
    )
    await tm.append_output(task_id, "\n".join(restore_result.get("logs", [])))

    if restore_result.get("success"):
        tm.save_task_context(task_id, rollback_status="completed", rollback_target="BD")
        await tm.append_output(task_id, "[RECOVERY] BD state restored successfully. You can retry ECM installation.")
        await tm.append_output(task_id, "[RECOVERY] Use resume_from_checkpoint=true to skip BD Pack and retry ECM only.")
    else:
        tm.save_task_context(task_id, rollback_status="failed", rollback_target="BD", rollback_failed_steps=restore_result.get("failed_steps", []))
        failed = restore_result.get("failed_steps", [])
        await tm.append_output(task_id, f"[RECOVERY] WARNING: Some restore steps failed: {', '.join(failed)}")
        await tm.append_output(task_id, "[RECOVERY] Please manually complete the failed steps before retrying ECM.")

    await trace("BD state restore process completed")


async def _restore_on_sanc_failure(
    task_id: str,
    request: InstallationRequest,
    svc,
    trace,
) -> None:
    """Restore to ECM (or BD) state after SANC failure.

    Tries ECM backup first; falls back to BD backup if ECM backup not found.
    """
    await tm.append_output(task_id, "\n[RECOVERY] ==================== SANC FAILURE - RESTORING PREVIOUS STATE ====================")
    await tm.update_status(task_id, "running", "Restoring to previous state after SANC failure")
    tm.save_task_context(task_id, rollback_status="started", rollback_module="SANC")

    db_sys_pass = request.db_sys_password or getattr(request, "schema_default_password", None)
    db_service = request.sanc_schema_jdbc_service or request.schema_jdbc_service

    if not db_sys_pass or not db_service:
        await tm.append_output(task_id, "[RECOVERY] WARNING: db_sys_password or schema_jdbc_service not provided.")
        await tm.append_output(task_id, "[RECOVERY] Cannot auto-restore DB schemas. Manual restore required.")

    # Always try ECM first — ECM may have been installed in a prior run even if install_ecm=False now.
    # select_restore_manifest validates each tag and falls back gracefully if no ECM manifest exists.
    restore_tags = ["ECM", "BD"]
    manifest_result = await svc.select_restore_manifest(
        request,
        restore_tags,
        on_log=lambda line: tm.append_output(task_id, line),
    )
    if not manifest_result.get("success"):
        await tm.append_output(task_id, "[RECOVERY] ERROR: No valid restore manifest found for previous state.")
        await tm.append_output(task_id, f"[RECOVERY] {manifest_result.get('error', 'Manifest selection failed')}")
        await trace("Previous-state restore manifest selection failed")
        return

    selected_tag = manifest_result["manifest"].get("tag", "unknown")
    tm.save_task_context(task_id, restore_manifest_path=manifest_result.get("manifest_path"), restore_target_tag=selected_tag)
    restore_result = await svc.full_restore_from_manifest(
        request.host,
        request.username,
        request.password,
        manifest=manifest_result["manifest"],
        db_sys_password=db_sys_pass or "",
        db_oracle_sid=getattr(request, "oracle_sid", None) or "OFSAADB",
        db_ssh_host=getattr(request, "db_ssh_host", None),
        db_ssh_username=getattr(request, "db_ssh_username", None),
        db_ssh_password=getattr(request, "db_ssh_password", None),
    )
    await tm.append_output(task_id, "\n".join(restore_result.get("logs", [])))

    restored_tag = restore_result.get("restored_tag", "unknown")
    if restore_result.get("success"):
        tm.save_task_context(task_id, rollback_status="completed", rollback_target=restored_tag)
        await tm.append_output(task_id, f"[RECOVERY] Restored to {restored_tag} state successfully. You can retry SANC installation.")
    else:
        tm.save_task_context(task_id, rollback_status="failed", rollback_target=restored_tag, rollback_failed_steps=restore_result.get("failed_steps", []))
        failed = restore_result.get("failed_steps", [])
        await tm.append_output(task_id, f"[RECOVERY] WARNING: Some restore steps failed: {', '.join(failed)}")
        await tm.append_output(task_id, "[RECOVERY] Please manually complete the failed steps before retrying SANC.")

    await trace("Previous state restore process completed")


async def _take_backup(
    task_id: str,
    svc,
    request: InstallationRequest,
    tag: str,
    trace,
) -> None:
    """Take application tar + DB schema backup with given tag.

    All schema/DB parameters resolved via build_backup_params(request, tag) —
    the single source of truth.  No schema names are passed as arguments.
    """
    from core.config import build_backup_params
    params = build_backup_params(request, tag)
    app_backup_path: Optional[str] = None

    # Application backup
    await tm.update_status(task_id, "running", f"Taking application backup (tar) [{tag}]")
    app_result = await svc.backup_application(
        params.app_host, params.app_username, params.app_password, backup_tag=tag,
    )
    await tm.append_output(task_id, "\n".join(app_result.get("logs", [])))
    if not app_result.get("success"):
        await tm.append_output(task_id, f"[WARN] {tag} application backup failed.")
    else:
        app_backup_path = app_result.get("backup_path")
        await trace(f"{tag} application backup completed")

    # DB schema backup
    if params.db_sys_password and params.db_service:
        await tm.update_status(task_id, "running", f"Taking DB schema backup [{tag}]")
        db_result = await svc.backup_db_schemas(
            params.app_host, params.app_username, params.app_password,
            db_sys_password=params.db_sys_password,
            db_jdbc_service=params.db_service,
            db_oracle_sid=params.oracle_sid,
            schema_config_schema_name=params.schema_config,
            schema_atomic_schema_name=params.schema_atomic,
            db_ssh_host=params.db_ssh_host,
            db_ssh_username=params.db_ssh_username,
            db_ssh_password=params.db_ssh_password,
        )
        await tm.append_output(task_id, "\n".join(db_result.get("logs", [])))
        if not db_result.get("success"):
            await tm.append_output(task_id, f"[WARN] {tag} DB schema backup failed.")
        else:
            tm.bd_checkpoint["completed"] = True
            tm.bd_checkpoint["request"] = request.dict()
            tm.bd_checkpoint["task_id"] = task_id
            tm.bd_checkpoint["host"] = request.host
            tm.bd_checkpoint["timestamp"] = datetime.now().isoformat()

            if app_backup_path and db_result.get("timestamp") and db_result.get("dump_prefix"):
                manifest_result = svc.record_backup_manifest(
                    request=request,
                    backup_tag=tag,
                    app_backup_path=app_backup_path,
                    dump_prefix=db_result["dump_prefix"],
                    dump_timestamp=db_result["timestamp"],
                    db_service=params.db_service,
                    schemas=params.schemas,
                )
                manifest_path = manifest_result.get("manifest_path")
                if manifest_path:
                    tm.save_task_context(
                        task_id,
                        selected_backup_tag=tag,
                        backup_manifest_path=manifest_path,
                        backup_decision="backup_created",
                    )
                    await tm.append_output(task_id, f"[BACKUP-GOVERNOR] Backup manifest saved: {manifest_path}")
            await trace(f"{tag} DB schema backup completed")
    else:
        await tm.append_output(task_id, f"[WARN] db_sys_password or JDBC service not provided. Skipping {tag} DB schema backup.")


# ── Main installation worker ─────────────────────────────────────────────────

class TaskCancelledError(Exception):
    """Raised when a task is cancelled by the user."""
    pass


def _check_cancelled(task_id: str) -> None:
    """Raise TaskCancelledError if the task has been cancelled."""
    if tm.is_cancelled(task_id):
        raise TaskCancelledError("Task cancelled by user")


async def run_installation_process(task_id: str, request: InstallationRequest):
    task = tm.get_task(task_id)
    svc = create_installation_service()
    steps = InstallationSteps.STEP_NAMES

    def should_cleanup_failed_fresh() -> bool:
        if (request.installation_mode or "fresh").lower() != "fresh":
            return False
        try:
            return steps.index(task.current_step or "") >= 7
        except ValueError:
            return False

    async def handle_failure(message: str, error: Optional[str] = None) -> None:
        if "Environment check failed" in message:
            tm.latest_request_cache["error"] = f"{message}: {error}" if error else message
        tm.save_task_context(task_id, failure_message=message, failure_error=error)

        if should_cleanup_failed_fresh():
            await tm.append_output(task_id, "[INFO] Fresh installation failed at Step 8+. Starting automatic cleanup...")
            tm.save_task_context(task_id, cleanup_status="started", cleanup_mode="fresh")
            cleanup_result = await svc.cleanup_failed_fresh_installation(
                request.host, request.username, request.password,
            )
            await tm.append_output(task_id, "\n".join(cleanup_result.get("logs", [])))
            verify_result = await svc.verify_fresh_cleanup(request.host, request.username, request.password)
            await tm.append_output(task_id, "\n".join(verify_result.get("logs", [])))
            if verify_result.get("success"):
                tm.save_task_context(task_id, cleanup_status="completed", cleanup_mode="fresh")
            else:
                tm.save_task_context(task_id, cleanup_status="failed", cleanup_mode="fresh", cleanup_failures=verify_result.get("remaining_paths", []))
        task.status = "failed"
        task.error = error or message
        await tm.append_output(task_id, f"[ERROR] {message}")
        if error and error != message:
            await tm.append_output(task_id, f"[ERROR] {error}")
        await tm.update_status(task_id, "failed")

    async def trace(message: str) -> None:
        logger.info("task=%s %s", task_id[:8], message)
        await tm.append_output(task_id, f"[TRACE] {message}")

    async def ensure_valid_backup_before_module(module_name: str) -> bool:
        await tm.append_output(task_id, f"[INFO] Validating backup gate before {module_name}...")
        await tm.update_status(task_id, "running", f"Validating backup before {module_name}")
        result = await svc.ensure_valid_backup_before_module(
            task_id,
            request,
            module_name,
            on_log=lambda line: tm.append_output(task_id, line),
        )
        if result.get("manifest_path"):
            tm.save_task_context(
                task_id,
                selected_backup_tag=result.get("backup_tag"),
                backup_manifest_path=result.get("manifest_path"),
                backup_decision=result.get("decision"),
            )
        if result.get("backup_tag") == "BD" and result.get("success"):
            tm.bd_checkpoint["completed"] = True
            tm.bd_checkpoint["request"] = request.dict()
            tm.bd_checkpoint["task_id"] = task_id
            tm.bd_checkpoint["host"] = request.host
            tm.bd_checkpoint["timestamp"] = datetime.now().isoformat()
        if result.get("success"):
            await trace(
                f"Backup gate passed before {module_name}: {result.get('decision')} ({result.get('backup_tag')})"
            )
            return True
        await tm.append_output(task_id, f"[ERROR] Backup gate failed before {module_name}")
        if result.get("error"):
            await tm.append_output(task_id, f"[ERROR] {result.get('error')}")
        return False

    try:
        await tm.update_status(task_id, "running", task.current_step)

        # SSH connection
        if not await _ssh_connect(task_id, svc, request.host, request.username, request.password):
            await handle_failure("SSH connection failed after 3 attempts")
            return
        await trace("SSH connection established; starting installation workflow")

        # Validate resume_from_checkpoint
        if request.resume_from_checkpoint:
            if not tm.bd_checkpoint.get("completed"):
                await handle_failure("Cannot resume: No BD Pack backup found. Run BD Pack first or disable resume_from_checkpoint.")
                return
            if tm.bd_checkpoint.get("host") != request.host:
                await tm.append_output(task_id, f"[WARN] BD backup was for host {tm.bd_checkpoint.get('host')}, current host is {request.host}")

        # Output callback (shared across all modules)
        async def output_callback(text: str):
            await tm.append_output(task_id, text)

        # ═══════════════════════════════════════════════════════════════════
        # BD PACK
        # ═══════════════════════════════════════════════════════════════════
        if request.install_bdpack and not request.resume_from_checkpoint:
            await tm.update_status(task_id, module="BD_PACK")

            if not request.install_ecm and not request.install_sanc:
                await tm.append_output(task_id, "[INFO] Clearing filesystem caches before BD Pack...")
                await svc.ssh_service.execute_command(request.host, request.username, request.password, "echo 2 | sudo tee /proc/sys/vm/drop_caches")

            # Set open_cursors=2000 on DB server
            db_host_for_cursor = getattr(request, "db_ssh_host", None) or request.host
            db_user_for_cursor = getattr(request, "db_ssh_username", None) or request.username
            db_pass_for_cursor = getattr(request, "db_ssh_password", None) or request.password
            # Must run as oracle user with ORACLE_HOME/ORACLE_SID set for sqlplus OS auth
            cursor_inner = 'source /home/oracle/.profile >/dev/null 2>&1; echo "ALTER SYSTEM SET open_cursors=2000 SCOPE=BOTH;" | sqlplus / as sysdba'
            if db_user_for_cursor == "oracle":
                cursor_cmd = cursor_inner
            else:
                cursor_cmd = (
                    "if command -v sudo >/dev/null 2>&1; then "
                    f"sudo -u oracle bash -c {shell_escape(cursor_inner)}; "
                    "else "
                    f"su - oracle -c {shell_escape(cursor_inner)}; "
                    "fi"
                )
            await tm.append_output(task_id, "[INFO] Setting open_cursors=2000 on DB server...")
            cursor_result = await svc.ssh_service.execute_command(db_host_for_cursor, db_user_for_cursor, db_pass_for_cursor, cursor_cmd)
            cursor_stdout = cursor_result.get("stdout", "")
            if cursor_result.get("success") or "System altered" in cursor_stdout:
                await tm.append_output(task_id, "[OK] open_cursors=2000 set successfully")
            else:
                cursor_err = cursor_result.get("stderr") or cursor_stdout or "unknown error"
                await tm.append_output(task_id, f"[WARN] Failed to set open_cursors: {cursor_err}")

            # Clean old installer kit folders to avoid stale files
            await tm.append_output(task_id, "[INFO] Cleaning old installer kit folders...")
            kit_dirs = [
                "/u01/BD_Installer_Kit", "/u01/bd_installer_kit",
                "/u01/ECM_Installer_Kit", "/u01/ecm_installer_kit",
                "/u01/SANC_Installer_Kit", "/u01/sanc_installer_kit",
                "/u01/Installation_Kit", "/u01/installer_kit",
            ]
            rm_cmd = "sudo rm -rf " + " ".join(kit_dirs)
            await svc.ssh_service.execute_command(request.host, request.username, request.password, rm_cmd)
            await tm.append_output(task_id, "[OK] Old installer kit folders cleaned")

            # Step 1: Oracle user and oinstall group
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", steps[0])
            result = await svc.create_oracle_user_and_oinstall_group(request.host, request.username, request.password)
            await tm.append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("Oracle user setup failed", result.get("error"))
                return

            # Step 2: Mount point /u01
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", steps[1])
            result = await svc.create_mount_point(request.host, request.username, request.password)
            await tm.append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("Mount point creation failed", result.get("error"))
                return

            # Step 3: Install packages
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", steps[2])
            result = await svc.install_ksh_and_git(request.host, request.username, request.password)
            await tm.append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("Package installation failed", result.get("error"))
                return

            # Step 4: Create .profile
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", steps[3])
            result = await svc.create_profile_file(request.host, request.username, request.password)
            await tm.append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("Profile creation failed", result.get("error"))
                return

            # Step 5: Java installation
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", steps[4])
            await trace("Starting Java installation step")
            result = await svc.install_java_from_repo(request.host, request.username, request.password)
            await tm.append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("Java installation failed", result.get("error"))
                return
            await trace("Java installation step completed")

            java_home = result.get("java_home")
            if java_home:
                update_java = await svc.update_java_profile(request.host, request.username, request.password, java_home)
                await tm.append_output(task_id, "\n".join(update_java.get("logs", [])))
                if not update_java.get("success"):
                    await handle_failure("Updating JAVA_HOME failed", update_java.get("error"))
                    return

            # Step 6: OFSAA directories
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", steps[5])
            result = await svc.create_ofsaa_directories(request.host, request.username, request.password)
            await tm.append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("OFSAA directory creation failed", result.get("error"))
                return

            # Step 7: Oracle client check
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", steps[6])
            result = await svc.check_existing_oracle_client_and_update_profile(
                request.host, request.username, request.password, request.oracle_sid,
            )
            await tm.append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("Oracle client detection failed", result.get("error"))
                return

            # Step 8: Installer setup and envCheck
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", steps[7])
            await trace("Starting installer download/extract step")
            result = await svc.download_and_extract_installer(request.host, request.username, request.password)
            await tm.append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("Installer download failed", result.get("error"))
                return
            await trace("Installer download/extract step completed")

            perm_result = await svc.set_installer_permissions(request.host, request.username, request.password)
            await tm.append_output(task_id, "\n".join(perm_result.get("logs", [])))
            if not perm_result.get("success"):
                await handle_failure("Installer permission setup failed", perm_result.get("error"))
                return

            await tm.append_output(task_id, "[INFO] Sourcing /home/oracle/.profile before envCheck")

            bd_db_password = request.db_sys_password or ""
            bd_oracle_sid = request.oracle_sid or "OFSAADB"

            env_result = await svc.run_environment_check(
                request.host, request.username, request.password,
                on_output_callback=output_callback,
                on_prompt_callback=make_envcheck_prompt_callback(tm, task_id, bd_db_password, bd_oracle_sid),
            )
            await tm.append_output(task_id, "\n".join(env_result.get("logs", [])))
            if not env_result.get("success"):
                await handle_failure("Environment check failed", env_result.get("error"))
                return
            await trace("Environment check step completed")

            # Step 9: Apply XML/properties and run osc.sh
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", steps[8])
            await trace("Starting config apply and osc.sh step")
            cfg_result = await svc.apply_installer_config_files(
                request.host, request.username, request.password,
                schema_jdbc_host=request.schema_jdbc_host,
                schema_jdbc_port=request.schema_jdbc_port,
                schema_jdbc_service=request.schema_jdbc_service,
                schema_host=request.schema_host,
                schema_setup_env=request.schema_setup_env,
                schema_apply_same_for_all=request.schema_apply_same_for_all,
                schema_default_password=request.schema_default_password,
                schema_datafile_dir=request.schema_datafile_dir,
                schema_tablespace_autoextend=request.schema_tablespace_autoextend,
                schema_external_directory_value=request.schema_external_directory_value,
                schema_config_schema_name=request.schema_config_schema_name,
                schema_atomic_schema_name=request.schema_atomic_schema_name,
                pack_app_enable=request.pack_app_enable,
                prop_base_country=request.prop_base_country,
                prop_default_jurisdiction=request.prop_default_jurisdiction,
                prop_smtp_host=request.prop_smtp_host,
                prop_partition_date_format=request.prop_partition_date_format,
                prop_datadumpdt_minus_0=request.prop_datadumpdt_minus_0,
                prop_endthisweek_minus_00=request.prop_endthisweek_minus_00,
                prop_startnextmnth_minus_00=request.prop_startnextmnth_minus_00,
                prop_analyst_data_source=request.prop_analyst_data_source,
                prop_miner_data_source=request.prop_miner_data_source,
                prop_web_service_user=request.prop_web_service_user,
                prop_web_service_password=request.prop_web_service_password,
                prop_nls_length_semantics=request.prop_nls_length_semantics,
                prop_configure_obiee=request.prop_configure_obiee,
                prop_obiee_url=request.prop_obiee_url,
                prop_sw_rmiport=request.prop_sw_rmiport,
                prop_big_data_enable=request.prop_big_data_enable,
                prop_sqoop_working_dir=request.prop_sqoop_working_dir,
                prop_ssh_auth_alias=request.prop_ssh_auth_alias,
                prop_ssh_host_name=request.prop_ssh_host_name,
                prop_ssh_port=request.prop_ssh_port,
                prop_cssource=request.prop_cssource,
                prop_csloadtype=request.prop_csloadtype,
                prop_crrsource=request.prop_crrsource,
                prop_crrloadtype=request.prop_crrloadtype,
                prop_fsdf_upload_model=request.prop_fsdf_upload_model,
                aai_webappservertype=request.aai_webappservertype,
                aai_dbserver_ip=request.aai_dbserver_ip,
                aai_oracle_service_name=request.aai_oracle_service_name,
                aai_abs_driver_path=request.aai_abs_driver_path,
                aai_olap_server_implementation=request.aai_olap_server_implementation,
                aai_sftp_enable=request.aai_sftp_enable,
                aai_file_transfer_port=request.aai_file_transfer_port,
                aai_javaport=request.aai_javaport,
                aai_nativeport=request.aai_nativeport,
                aai_agentport=request.aai_agentport,
                aai_iccport=request.aai_iccport,
                aai_iccnativeport=request.aai_iccnativeport,
                aai_olapport=request.aai_olapport,
                aai_msgport=request.aai_msgport,
                aai_routerport=request.aai_routerport,
                aai_amport=request.aai_amport,
                aai_https_enable=request.aai_https_enable,
                aai_web_server_ip=request.aai_web_server_ip,
                aai_web_server_port=request.aai_web_server_port,
                aai_context_name=request.aai_context_name,
                aai_webapp_context_path=request.aai_webapp_context_path,
                aai_web_local_path=request.aai_web_local_path,
                aai_weblogic_domain_home=request.aai_weblogic_domain_home,
                aai_ftspshare_path=request.aai_ftspshare_path,
                aai_sftp_user_id=request.aai_sftp_user_id,
            )
            await tm.append_output(task_id, "\n".join(cfg_result.get("logs", [])))
            if not cfg_result.get("success"):
                await handle_failure("Applying installer config files failed", cfg_result.get("error"))
                return

            osc_result = await svc.run_osc_schema_creator(
                request.host, request.username, request.password,
                on_output_callback=output_callback,
                on_prompt_callback=make_osc_prompt_callback(tm, task_id, bd_db_password),
            )
            await tm.append_output(task_id, "\n".join(osc_result.get("logs", [])))
            if not osc_result.get("success"):
                await tm.append_output(task_id, "\n[RECOVERY] osc.sh execution failed. Starting automatic recovery cleanup...")
                cleanup_result = await svc.cleanup_after_osc_failure(
                    app_host=request.host,
                    app_username=request.username,
                    app_password=request.password,
                    db_host=request.schema_jdbc_host or request.host,
                    db_username=request.username,
                    db_password=request.password,
                    db_sys_password=request.db_sys_password,
                    db_jdbc_host=request.schema_jdbc_host or request.host,
                    db_jdbc_port=request.schema_jdbc_port or 1521,
                    db_jdbc_service=request.schema_jdbc_service,
                    schema_config_schema_name=request.schema_config_schema_name,
                    schema_atomic_schema_name=request.schema_atomic_schema_name,
                    db_ssh_host=getattr(request, "db_ssh_host", None),
                    db_ssh_username=getattr(request, "db_ssh_username", None),
                    db_ssh_password=getattr(request, "db_ssh_password", None),
                )
                await tm.append_output(task_id, "\n".join(cleanup_result.get("logs", [])))
                verify_cleanup = await svc.verify_cleanup_after_osc_failure(
                    app_host=request.host,
                    app_username=request.username,
                    app_password=request.password,
                    db_sys_password=request.db_sys_password,
                    db_jdbc_host=request.schema_jdbc_host or request.host,
                    db_jdbc_port=request.schema_jdbc_port or 1521,
                    db_jdbc_service=request.schema_jdbc_service,
                    schema_config_schema_name=request.schema_config_schema_name,
                    schema_atomic_schema_name=request.schema_atomic_schema_name,
                    db_ssh_host=getattr(request, "db_ssh_host", None),
                    db_ssh_username=getattr(request, "db_ssh_username", None),
                    db_ssh_password=getattr(request, "db_ssh_password", None),
                )
                await tm.append_output(task_id, "\n".join(verify_cleanup.get("logs", [])))
                tm.save_task_context(
                    task_id,
                    cleanup_status="completed" if verify_cleanup.get("success") else "failed",
                    cleanup_mode="osc_failure",
                    cleanup_failures=verify_cleanup.get("failures", []),
                )
                if cleanup_result.get("failed_steps"):
                    await tm.append_output(task_id, f"\n[RECOVERY] The following cleanup steps failed: {', '.join(cleanup_result['failed_steps'])}")
                    await tm.append_output(task_id, "[RECOVERY] Please manually complete the failed steps before retrying installation")
                await handle_failure("osc.sh execution failed - automatic cleanup initiated", osc_result.get("error"))
                return
            await trace("osc.sh step completed")

            # Step 10: setup.sh SILENT
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", steps[9])
            await trace("Starting setup.sh SILENT step")
            setup_result = await svc.run_setup_silent(
                request.host, request.username, request.password,
                on_output_callback=output_callback,
                on_prompt_callback=make_setup_prompt_callback(tm, task_id, sftp_password=request.prop_web_service_password),
                pack_app_enable=request.pack_app_enable,
                installation_mode=request.installation_mode,
                install_sanc=request.install_sanc,
            )
            await tm.append_output(task_id, "\n".join(setup_result.get("logs", [])))
            if not setup_result.get("success"):
                await tm.append_output(task_id, "[RECOVERY] Killing Java processes after setup.sh failure...")
                kill_result = await svc.kill_java_processes(request.host, request.username, request.password)
                await tm.append_output(task_id, "\n".join(kill_result.get("logs", [])))
                await handle_failure("setup.sh SILENT execution failed", setup_result.get("error"))
                return
            await trace("setup.sh SILENT step completed")
            await tm.append_output(task_id, "[OK] BD Pack installation completed")

            # Save BD Pack checkpoint
            tm.bd_checkpoint["completed"] = True
            tm.bd_checkpoint["request"] = request.dict()
            tm.bd_checkpoint["task_id"] = task_id
            tm.bd_checkpoint["host"] = request.host
            tm.bd_checkpoint["timestamp"] = datetime.now().isoformat()

            # BD Pack backup
            await tm.append_output(task_id, "\n[INFO] ==================== BD PACK BACKUP ====================")
            await _take_backup(task_id, svc, request, "BD", trace)
            await tm.append_output(task_id, "[INFO] BD Pack backup phase complete")
            await tm.append_output(task_id, "[CHECKPOINT] BD Pack checkpoint saved. ECM can be restored to this point if it fails.")

            # In force_reinstall mode, BD was wiped and reinstalled from scratch.
            # Purge stale ECM and SANC manifests so the backup gate doesn't mistakenly
            # reuse manifests that no longer represent the current server state.
            if request.installation_mode == "force_reinstall":
                purged = svc.backup_restore_governor.manifests.purge_manifests_for_tags(request.host, ["ECM", "SANC"])
                if purged:
                    await tm.append_output(task_id, f"[BACKUP-GOVERNOR] Force reinstall: purged {len(purged)} stale ECM/SANC manifest(s)")
                    for p in purged:
                        await tm.append_output(task_id, f"[BACKUP-GOVERNOR]   Removed: {p}")
                else:
                    await tm.append_output(task_id, "[BACKUP-GOVERNOR] Force reinstall: no stale ECM/SANC manifests to purge")

        else:
            if request.resume_from_checkpoint and tm.bd_checkpoint.get("completed"):
                await tm.append_output(task_id, "[INFO] Resuming from BD Pack backup - skipping BD Pack installation")
                await tm.append_output(task_id, "[INFO] BD Pack will NOT be reinstalled. Starting ECM from BD backup restore point.")
                await trace("Resuming from BD Pack backup - BD reinstall skipped")
            else:
                await tm.append_output(task_id, "[INFO] Skipping BD Pack installation as per request")
                await trace("Skipping BD Pack installation")

        # ═══════════════════════════════════════════════════════════════════
        # ECM PACK
        # ═══════════════════════════════════════════════════════════════════
        if request.install_ecm:
            await tm.update_status(task_id, module="ECM_PACK")
            await tm.append_output(task_id, "\n[INFO] ==================== ECM MODULE INSTALLATION ====================")

            await tm.append_output(task_id, "[INFO] Clearing filesystem caches before ECM Pack...")
            await svc.ssh_service.execute_command(request.host, request.username, request.password, "echo 2 | sudo tee /proc/sys/vm/drop_caches")

            if not await ensure_valid_backup_before_module("ECM"):
                await handle_failure("ECM backup validation failed", "Could not verify or create a proper BD backup before ECM")
                return

            # ECM Step 1: Download and extract
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", "Downloading and extracting ECM installer kit")
            await trace("Starting ECM installer download/extract step")
            ecm_download_result = await svc.download_and_extract_ecm_installer(request.host, request.username, request.password)
            await tm.append_output(task_id, "\n".join(ecm_download_result.get("logs", [])))
            if not ecm_download_result.get("success"):
                await tm.append_output(task_id, "\n[RECOVERY] ECM download failed. Initiating restore to BD state...")
                await _restore_bd_on_ecm_failure(task_id, request, svc, trace)
                await handle_failure("ECM installer download failed - restored to BD state", ecm_download_result.get("error"))
                return
            await trace("ECM installer download/extract step completed")

            # ECM Step 2: Set permissions
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", "Setting ECM kit permissions")
            ecm_perm_result = await svc.set_ecm_permissions(request.host, request.username, request.password)
            await tm.append_output(task_id, "\n".join(ecm_perm_result.get("logs", [])))
            if not ecm_perm_result.get("success"):
                await tm.append_output(task_id, "\n[RECOVERY] ECM permissions failed. Initiating restore to BD state...")
                await _restore_bd_on_ecm_failure(task_id, request, svc, trace)
                await handle_failure("ECM permission setup failed - restored to BD state", ecm_perm_result.get("error"))
                return

            # ECM Step 3: Apply config files
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", "Applying ECM configuration files")
            await trace("Starting ECM config apply step")
            ecm_cfg_result = await svc.apply_ecm_config_files(
                request.host, request.username, request.password,
                ecm_schema_jdbc_host=request.ecm_schema_jdbc_host,
                ecm_schema_jdbc_port=request.ecm_schema_jdbc_port,
                ecm_schema_jdbc_service=request.ecm_schema_jdbc_service,
                ecm_schema_host=request.ecm_schema_host,
                ecm_schema_setup_env=request.ecm_schema_setup_env,
                ecm_schema_prefix_schema_name=request.ecm_schema_prefix_schema_name,
                ecm_schema_apply_same_for_all=request.ecm_schema_apply_same_for_all,
                ecm_schema_default_password=request.ecm_schema_default_password,
                ecm_schema_datafile_dir=request.ecm_schema_datafile_dir,
                ecm_schema_config_schema_name=request.ecm_schema_config_schema_name,
                ecm_schema_atomic_schema_name=request.ecm_schema_atomic_schema_name,
                ecm_prop_base_country=request.ecm_prop_base_country,
                ecm_prop_default_jurisdiction=request.ecm_prop_default_jurisdiction,
                ecm_prop_smtp_host=request.ecm_prop_smtp_host,
                ecm_prop_web_service_user=request.ecm_prop_web_service_user,
                ecm_prop_web_service_password=request.ecm_prop_web_service_password,
                ecm_prop_nls_length_semantics=request.ecm_prop_nls_length_semantics,
                ecm_prop_analyst_data_source=request.ecm_prop_analyst_data_source,
                ecm_prop_miner_data_source=request.ecm_prop_miner_data_source,
                ecm_prop_configure_obiee=request.ecm_prop_configure_obiee,
                ecm_prop_fsdf_upload_model=request.ecm_prop_fsdf_upload_model,
                ecm_prop_amlsource=request.ecm_prop_amlsource,
                ecm_prop_kycsource=request.ecm_prop_kycsource,
                ecm_prop_cssource=request.ecm_prop_cssource,
                ecm_prop_externalsystemsource=request.ecm_prop_externalsystemsource,
                ecm_prop_tbamlsource=request.ecm_prop_tbamlsource,
                ecm_prop_fatcasource=request.ecm_prop_fatcasource,
                ecm_prop_ofsecm_datasrcname=request.ecm_prop_ofsecm_datasrcname,
                ecm_prop_comn_gateway_ds=request.ecm_prop_comn_gateway_ds,
                ecm_prop_t2jurl=request.ecm_prop_t2jurl,
                ecm_prop_j2turl=request.ecm_prop_j2turl,
                ecm_prop_cmngtwyurl=request.ecm_prop_cmngtwyurl,
                ecm_prop_bdurl=request.ecm_prop_bdurl,
                ecm_prop_ofss_wls_url=request.ecm_prop_ofss_wls_url,
                ecm_prop_aai_url=request.ecm_prop_aai_url,
                ecm_prop_cs_url=request.ecm_prop_cs_url,
                ecm_prop_arachnys_nns_service_url=request.ecm_prop_arachnys_nns_service_url,
                ecm_aai_webappservertype=request.ecm_aai_webappservertype,
                ecm_aai_dbserver_ip=request.ecm_aai_dbserver_ip,
                ecm_aai_oracle_service_name=request.ecm_aai_oracle_service_name,
                ecm_aai_abs_driver_path=request.ecm_aai_abs_driver_path,
                ecm_aai_olap_server_implementation=request.ecm_aai_olap_server_implementation,
                ecm_aai_sftp_enable=request.ecm_aai_sftp_enable,
                ecm_aai_file_transfer_port=request.ecm_aai_file_transfer_port,
                ecm_aai_javaport=request.ecm_aai_javaport,
                ecm_aai_nativeport=request.ecm_aai_nativeport,
                ecm_aai_agentport=request.ecm_aai_agentport,
                ecm_aai_iccport=request.ecm_aai_iccport,
                ecm_aai_iccnativeport=request.ecm_aai_iccnativeport,
                ecm_aai_olapport=request.ecm_aai_olapport,
                ecm_aai_msgport=request.ecm_aai_msgport,
                ecm_aai_routerport=request.ecm_aai_routerport,
                ecm_aai_amport=request.ecm_aai_amport,
                ecm_aai_https_enable=request.ecm_aai_https_enable,
                ecm_aai_web_server_ip=request.ecm_aai_web_server_ip,
                ecm_aai_web_server_port=request.ecm_aai_web_server_port,
                ecm_aai_context_name=request.ecm_aai_context_name,
                ecm_aai_webapp_context_path=request.ecm_aai_webapp_context_path,
                ecm_aai_web_local_path=request.ecm_aai_web_local_path,
                ecm_aai_weblogic_domain_home=request.ecm_aai_weblogic_domain_home,
                ecm_aai_ftspshare_path=request.ecm_aai_ftspshare_path,
                ecm_aai_sftp_user_id=request.ecm_aai_sftp_user_id,
            )
            await tm.append_output(task_id, "\n".join(ecm_cfg_result.get("logs", [])))
            if not ecm_cfg_result.get("success"):
                await tm.append_output(task_id, "\n[RECOVERY] ECM config apply failed. Initiating restore to BD state...")
                await _restore_bd_on_ecm_failure(task_id, request, svc, trace)
                await handle_failure("ECM config files apply failed - restored to BD state", ecm_cfg_result.get("error"))
                return
            await trace("ECM config apply step completed")

            # ECM Step 4a: Run ECM osc.sh
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", "Running ECM schema creator (osc.sh)")
            await trace("Starting ECM osc.sh step")
            ecm_db_password = request.db_sys_password or ""

            ecm_osc_result = await svc.run_ecm_osc_schema_creator(
                request.host, request.username, request.password,
                on_output_callback=output_callback,
                on_prompt_callback=make_osc_prompt_callback(tm, task_id, ecm_db_password),
            )
            await tm.append_output(task_id, "\n".join(ecm_osc_result.get("logs", [])))
            if not ecm_osc_result.get("success"):
                await tm.append_output(task_id, "\n[RECOVERY] ECM osc.sh failed. Initiating restore to BD state...")
                await _restore_bd_on_ecm_failure(task_id, request, svc, trace)
                await handle_failure("ECM osc.sh execution failed - restored to BD state", ecm_osc_result.get("error"))
                return
            await trace("ECM osc.sh step completed")

            # ECM Step 4b: Run ECM setup.sh SILENT
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", "Running ECM setup (setup.sh SILENT)")
            await trace("Starting ECM setup.sh SILENT step")
            ecm_setup_result = await svc.run_ecm_setup_silent(
                request.host, request.username, request.password,
                on_output_callback=output_callback,
                on_prompt_callback=make_setup_prompt_callback(tm, task_id),
            )
            await tm.append_output(task_id, "\n".join(ecm_setup_result.get("logs", [])))
            if not ecm_setup_result.get("success"):
                await tm.append_output(task_id, "\n[RECOVERY] ECM setup.sh failed. Initiating restore to BD state...")
                await _restore_bd_on_ecm_failure(task_id, request, svc, trace)
                await handle_failure("ECM setup.sh SILENT execution failed - restored to BD state", ecm_setup_result.get("error"))
                return
            await trace("ECM setup.sh SILENT step completed")
            await tm.append_output(task_id, "[OK] ECM Module installation completed")

            # ECM success backup
            await tm.append_output(task_id, "\n[INFO] ==================== ECM SUCCESS BACKUP ====================")
            await _take_backup(task_id, svc, request, "ECM", trace)
            await tm.append_output(task_id, "[INFO] ECM backup phase complete")

            # Clear BD checkpoint after successful ECM
            if tm.bd_checkpoint.get("completed"):
                tm.clear_bd_checkpoint()
                await tm.append_output(task_id, "[CHECKPOINT] BD Pack checkpoint cleared after successful ECM completion.")

        # ═══════════════════════════════════════════════════════════════════
        # SANC PACK
        # ═══════════════════════════════════════════════════════════════════
        if request.install_sanc:
            await tm.update_status(task_id, module="SANC_PACK")
            await tm.append_output(task_id, "\n[INFO] ==================== SANC MODULE INSTALLATION ====================")

            await tm.append_output(task_id, "[INFO] Clearing filesystem caches before SANC Pack...")
            await svc.ssh_service.execute_command(request.host, request.username, request.password, "echo 2 | sudo tee /proc/sys/vm/drop_caches")

            if not await ensure_valid_backup_before_module("SANC"):
                await handle_failure("SANC backup validation failed", "Could not verify or create a proper backup before SANC")
                return

            # SANC Step 1: Download and extract
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", "Downloading and extracting SANC installer kit")
            await trace("Starting SANC installer download/extract step")
            sanc_download_result = await svc.download_and_extract_sanc_installer(request.host, request.username, request.password)
            await tm.append_output(task_id, "\n".join(sanc_download_result.get("logs", [])))
            if not sanc_download_result.get("success"):
                await tm.append_output(task_id, "\n[RECOVERY] SANC download failed. Initiating restore to previous state...")
                await _restore_on_sanc_failure(task_id, request, svc, trace)
                await handle_failure("SANC installer download failed - restored to previous state", sanc_download_result.get("error"))
                return
            await trace("SANC installer download/extract step completed")

            # SANC Step 2: Set permissions
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", "Setting SANC kit permissions")
            sanc_perm_result = await svc.set_sanc_permissions(request.host, request.username, request.password)
            await tm.append_output(task_id, "\n".join(sanc_perm_result.get("logs", [])))
            if not sanc_perm_result.get("success"):
                await tm.append_output(task_id, "\n[RECOVERY] SANC permissions failed. Initiating restore to previous state...")
                await _restore_on_sanc_failure(task_id, request, svc, trace)
                await handle_failure("SANC permission setup failed - restored to previous state", sanc_perm_result.get("error"))
                return

            # SANC Step 3: Apply config files
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", "Applying SANC configuration files")
            await trace("Starting SANC config apply step")
            sanc_cfg_result = await svc.apply_sanc_config_files(
                request.host, request.username, request.password,
                sanc_schema_jdbc_host=request.sanc_schema_jdbc_host,
                sanc_schema_jdbc_port=request.sanc_schema_jdbc_port,
                sanc_schema_jdbc_service=request.sanc_schema_jdbc_service,
                sanc_schema_host=request.sanc_schema_host,
                sanc_schema_setup_env=request.sanc_schema_setup_env,
                sanc_schema_apply_same_for_all=request.sanc_schema_apply_same_for_all,
                sanc_schema_default_password=request.sanc_schema_default_password,
                sanc_schema_datafile_dir=request.sanc_schema_datafile_dir,
                sanc_schema_tablespace_autoextend=request.sanc_schema_tablespace_autoextend,
                sanc_schema_external_directory_value=request.sanc_schema_external_directory_value,
                sanc_schema_config_schema_name=request.sanc_schema_config_schema_name,
                sanc_schema_atomic_schema_name=request.sanc_schema_atomic_schema_name,
                sanc_cs_swiftinfo=request.sanc_cs_swiftinfo,
                sanc_tflt_swiftinfo=request.sanc_tflt_swiftinfo,
                aai_webappservertype=request.aai_webappservertype,
                aai_dbserver_ip=request.aai_dbserver_ip,
                aai_oracle_service_name=request.aai_oracle_service_name,
                aai_abs_driver_path=request.aai_abs_driver_path,
                aai_olap_server_implementation=request.aai_olap_server_implementation,
                aai_sftp_enable=request.aai_sftp_enable,
                aai_file_transfer_port=request.aai_file_transfer_port,
                aai_javaport=request.aai_javaport,
                aai_nativeport=request.aai_nativeport,
                aai_agentport=request.aai_agentport,
                aai_iccport=request.aai_iccport,
                aai_iccnativeport=request.aai_iccnativeport,
                aai_olapport=request.aai_olapport,
                aai_msgport=request.aai_msgport,
                aai_routerport=request.aai_routerport,
                aai_amport=request.aai_amport,
                aai_https_enable=request.aai_https_enable,
                aai_web_server_ip=request.aai_web_server_ip,
                aai_web_server_port=request.aai_web_server_port,
                aai_context_name=request.aai_context_name,
                aai_webapp_context_path=request.aai_webapp_context_path,
                aai_web_local_path=request.aai_web_local_path,
                aai_weblogic_domain_home=request.aai_weblogic_domain_home,
                aai_ftspshare_path=request.aai_ftspshare_path,
                aai_sftp_user_id=request.aai_sftp_user_id,
            )
            await tm.append_output(task_id, "\n".join(sanc_cfg_result.get("logs", [])))
            if not sanc_cfg_result.get("success"):
                await tm.append_output(task_id, "\n[RECOVERY] SANC config apply failed. Initiating restore to previous state...")
                await _restore_on_sanc_failure(task_id, request, svc, trace)
                await handle_failure("SANC config files apply failed - restored to previous state", sanc_cfg_result.get("error"))
                return
            await trace("SANC config apply step completed")

            # SANC Step 4a: Run SANC osc.sh
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", "Running SANC schema creator (osc.sh)")
            await trace("Starting SANC osc.sh step")
            sanc_db_password = request.db_sys_password or ""

            sanc_osc_result = await svc.run_sanc_osc_schema_creator(
                request.host, request.username, request.password,
                on_output_callback=output_callback,
                on_prompt_callback=make_osc_prompt_callback(tm, task_id, sanc_db_password),
            )
            await tm.append_output(task_id, "\n".join(sanc_osc_result.get("logs", [])))
            if not sanc_osc_result.get("success"):
                await tm.append_output(task_id, "\n[RECOVERY] SANC osc.sh failed. Initiating restore to previous state...")
                await _restore_on_sanc_failure(task_id, request, svc, trace)
                await handle_failure("SANC osc.sh execution failed - restored to previous state", sanc_osc_result.get("error"))
                return
            await trace("SANC osc.sh step completed")

            # SANC Step 4b: Run SANC setup.sh SILENT
            _check_cancelled(task_id)
            await tm.update_status(task_id, "running", "Running SANC setup (setup.sh SILENT)")
            await trace("Starting SANC setup.sh SILENT step")
            sanc_setup_result = await svc.run_sanc_setup_silent(
                request.host, request.username, request.password,
                on_output_callback=output_callback,
                on_prompt_callback=make_setup_prompt_callback(tm, task_id),
            )
            await tm.append_output(task_id, "\n".join(sanc_setup_result.get("logs", [])))
            if not sanc_setup_result.get("success"):
                await tm.append_output(task_id, "\n[RECOVERY] SANC setup.sh failed. Initiating restore to previous state...")
                await _restore_on_sanc_failure(task_id, request, svc, trace)
                await handle_failure("SANC setup.sh SILENT execution failed - restored to previous state", sanc_setup_result.get("error"))
                return
            await trace("SANC setup.sh SILENT step completed")
            await tm.append_output(task_id, "[OK] SANC Module installation completed")

            # SANC success backup
            await tm.append_output(task_id, "\n[INFO] ==================== SANC SUCCESS BACKUP ====================")
            await _take_backup(task_id, svc, request, "SANC", trace)
            await tm.append_output(task_id, "[INFO] SANC Pack backup phase complete")

        # ═══════════════════════════════════════════════════════════════════
        # COMPLETION
        # ═══════════════════════════════════════════════════════════════════
        task.status = "completed"
        task.progress = 100
        await tm.update_status(task_id, "completed", steps[9])
        await tm.append_output(task_id, "[OK] Installation completed successfully")
        return

    except asyncio.TimeoutError as exc:
        await handle_failure("Installation timed out", str(exc))
    except (TaskCancelledError, asyncio.CancelledError):
        logger.info("Installation task %s was cancelled", task_id)
        await tm.append_output(task_id, "\n[CANCEL] ==================== TASK CANCELLED BY USER ====================")

        # Module-based restore on cancel
        current_module = getattr(task, "current_module", None)
        try:
            if current_module == "SANC_PACK":
                await tm.append_output(task_id, "[CANCEL] Cancelled during SANC Pack. Restoring to previous state...")
                await _restore_on_sanc_failure(task_id, request, svc, trace)
            elif current_module == "ECM_PACK":
                await tm.append_output(task_id, "[CANCEL] Cancelled during ECM Pack. Restoring to BD state...")
                await _restore_bd_on_ecm_failure(task_id, request, svc, trace)
            elif current_module == "BD_PACK":
                await tm.append_output(task_id, "[CANCEL] Cancelled during BD Pack. Cleaning up partial installation...")
                if should_cleanup_failed_fresh():
                    cleanup = await svc.cleanup_failed_fresh_installation(
                        request.host, request.username, request.password,
                    )
                    await tm.append_output(task_id, "\n".join(cleanup.get("logs", [])))
                    verify_cleanup = await svc.verify_fresh_cleanup(request.host, request.username, request.password)
                    await tm.append_output(task_id, "\n".join(verify_cleanup.get("logs", [])))
                    tm.save_task_context(
                        task_id,
                        cleanup_status="completed" if verify_cleanup.get("success") else "failed",
                        cleanup_mode="fresh-cancel",
                        cleanup_failures=verify_cleanup.get("remaining_paths", []),
                    )
                else:
                    await tm.append_output(task_id, "[CANCEL] BD Pack cancel — no automatic cleanup for non-fresh installs.")
        except Exception as restore_exc:
            logger.exception("Restore on cancel failed for task %s", task_id)
            await tm.append_output(task_id, f"[CANCEL] WARNING: Restore after cancel failed: {restore_exc}")

        if task.status not in ("failed",):
            await tm.update_status(task_id, "failed", "Cancelled by user")
    except Exception as exc:
        logger.exception("Installation process failed")
        await handle_failure("Installation failed", str(exc))


async def recover_interrupted_tasks() -> None:
    restored = tm.restore_persisted_tasks()
    for payload in restored:
        task_id = payload.get("task_id")
        task = tm.get_task(task_id) if task_id else None
        context = payload.get("context", {})
        request_payload = context.get("request")
        if not task_id or not task or task.status != "interrupted" or not isinstance(request_payload, dict):
            continue

        request = InstallationRequest(**request_payload)
        svc = create_installation_service()

        async def trace(message: str) -> None:
            logger.info("recovery task=%s %s", task_id[:8], message)
            await tm.append_output(task_id, f"[TRACE] {message}")

        await tm.append_output(task_id, "[RECOVERY] Backend restart detected. Starting automatic recovery for interrupted task.")
        try:
            if task.current_module == "SANC_PACK":
                await _restore_on_sanc_failure(task_id, request, svc, trace)
                task.error = "Recovered after backend restart; retry SANC if needed"
                await tm.update_status(task_id, "failed", "Recovered after backend restart; retry SANC if needed")
            elif task.current_module == "ECM_PACK":
                await _restore_bd_on_ecm_failure(task_id, request, svc, trace)
                task.error = "Recovered after backend restart; retry ECM if needed"
                await tm.update_status(task_id, "failed", "Recovered after backend restart; retry ECM if needed")
            elif task.current_module == "BD_PACK":
                if (request.installation_mode or "fresh").lower() == "fresh":
                    cleanup = await svc.cleanup_failed_fresh_installation(request.host, request.username, request.password)
                    await tm.append_output(task_id, "\n".join(cleanup.get("logs", [])))
                    verify = await svc.verify_fresh_cleanup(request.host, request.username, request.password)
                    await tm.append_output(task_id, "\n".join(verify.get("logs", [])))
                    tm.save_task_context(
                        task_id,
                        cleanup_status="completed" if verify.get("success") else "failed",
                        cleanup_mode="restart-recovery",
                        cleanup_failures=verify.get("remaining_paths", []),
                    )
                    task.error = "Recovered after backend restart; retry BD if needed"
                    await tm.update_status(task_id, "failed", "Recovered after backend restart; retry BD if needed")
                else:
                    task.error = "Backend restarted during BD task; no auto-cleanup for non-fresh install"
                    await tm.update_status(task_id, "failed", "Backend restarted during BD task; no auto-cleanup for non-fresh install")
            else:
                task.error = "Backend restarted during task; manual retry required"
                await tm.update_status(task_id, "failed", "Backend restarted during task; manual retry required")
        except Exception as exc:
            logger.exception("Automatic interrupted-task recovery failed for %s", task_id)
            await tm.append_output(task_id, f"[RECOVERY] Automatic recovery failed: {exc}")
            task.error = "Automatic recovery failed after backend restart"
            await tm.update_status(task_id, "failed", "Automatic recovery failed after backend restart")
