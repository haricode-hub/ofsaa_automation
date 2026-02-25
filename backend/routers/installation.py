import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException

from core.config import InstallationSteps
from core.websocket_manager import WebSocketManager
from schemas.installation import (
    InstallationRequest,
    InstallationResponse,
    InstallationStatus,
)
from services.installation_service import InstallationService
from services.ssh_service import SSHService


router = APIRouter()
logger = logging.getLogger(__name__)

installation_tasks: dict[str, InstallationStatus] = {}
websocket_manager = WebSocketManager()

# Cache for latest installation request (used for rollback after ENVCHECK failure)
latest_request_cache: dict = {
    "request": None,
    "task_id": None,
    "error": None,
}

# Checkpoint cache for BD Pack completion (used to resume ECM without re-running BD Pack)
# Now repurposed: tracks BD backup state for backup/restore approach
bd_pack_checkpoint: dict = {
    "completed": False,
    "backup_taken": False,
    "request": None,
    "task_id": None,
    "host": None,
    "timestamp": None,
}


@router.post("/start", response_model=InstallationResponse)
async def start_installation(request: InstallationRequest):
    try:
        task_id = str(uuid.uuid4())
        
        # Cache the request for rollback capability
        latest_request_cache["request"] = request.dict()
        latest_request_cache["task_id"] = task_id
        latest_request_cache["error"] = None
        
        installation_tasks[task_id] = InstallationStatus(
            task_id=task_id,
            status="started",
            current_step="Initializing connection",
            progress=0,
            logs=[
                f"[INFO] Installation started (task {task_id[:8]})",
                f"[INFO] Target: {request.host}",
            ],
        )

        asyncio.create_task(run_installation_process(task_id, request))

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
    if task_id not in installation_tasks:
        raise HTTPException(status_code=404, detail="Installation task not found")
    return installation_tasks[task_id]


@router.get("/tasks")
async def list_installation_tasks():
    return {"tasks": list(installation_tasks.values())}


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
    """Return cached installation request for rollback after ENVCHECK failure."""
    if not latest_request_cache.get("request"):
        raise HTTPException(
            status_code=404,
            detail="No cached request found. No previous installation attempt or cache cleared."
        )
    
    return {
        "success": True,
        "cached_request": latest_request_cache["request"],
        "previous_error": latest_request_cache.get("error"),
        "message": "Returning cached request values from previous run. You can modify and resubmit."
    }


@router.get("/checkpoint")
async def get_checkpoint():
    """Get BD Pack backup status. If BD Pack completed and backup taken, ECM can resume from here."""
    if not bd_pack_checkpoint.get("completed"):
        raise HTTPException(
            status_code=404,
            detail="No BD Pack checkpoint found. BD Pack has not completed successfully yet."
        )
    
    return {
        "success": True,
        "bd_pack_completed": True,
        "backup_taken": bd_pack_checkpoint.get("backup_taken", False),
        "host": bd_pack_checkpoint.get("host"),
        "task_id": bd_pack_checkpoint.get("task_id"),
        "timestamp": bd_pack_checkpoint.get("timestamp"),
        "cached_request": bd_pack_checkpoint.get("request"),
        "message": "BD Pack completed with backup. You can resume ECM installation using resume_from_checkpoint=true."
    }


@router.delete("/checkpoint")
async def clear_checkpoint():
    """Clear the BD Pack checkpoint (use after full installation completes or to start fresh)."""
    bd_pack_checkpoint["completed"] = False
    bd_pack_checkpoint["backup_taken"] = False
    bd_pack_checkpoint["request"] = None
    bd_pack_checkpoint["task_id"] = None
    bd_pack_checkpoint["host"] = None
    bd_pack_checkpoint["timestamp"] = None
    return {"success": True, "message": "BD Pack checkpoint cleared."}


async def append_output(task_id: str, text: str) -> None:
    if not text:
        return
    task = installation_tasks.get(task_id)
    if task:
        lines = [line for line in text.splitlines() if line.strip()]
        task.logs.extend(lines)
    await websocket_manager.send_output(task_id, text)


async def update_status(task_id: str, status: Optional[str] = None, step: Optional[str] = None, progress: Optional[int] = None) -> None:
    task = installation_tasks.get(task_id)
    if task is None:
        return
    if status:
        task.status = status
    if step:
        task.current_step = step
    if progress is not None:
        task.progress = progress
    await websocket_manager.send_status(task_id, task.status, task.current_step, task.progress)


async def _restore_bd_on_ecm_failure(
    task_id: str,
    request: InstallationRequest,
    installation_service: InstallationService,
    trace,
) -> None:
    """Restore to BD state after ECM failure: rm OFSAA -> restore tar -> restore DB schemas.
    This is called when ECM osc.sh or setup.sh fails.
    BD backup acts as the restore point. BD reinstall is NOT required."""
    await append_output(task_id, "\n[RECOVERY] ==================== ECM FAILURE - RESTORING BD STATE ====================")
    await update_status(task_id, "running", "Restoring to BD state after ECM failure", 0)

    db_sys_pass = request.db_sys_password or getattr(request, "schema_default_password", None)
    db_service = (
        request.schema_jdbc_service
        or getattr(request, "ecm_schema_jdbc_service", None)
    )

    if not db_sys_pass or not db_service:
        await append_output(task_id, "[RECOVERY] WARNING: db_sys_password or schema_jdbc_service not provided.")
        await append_output(task_id, "[RECOVERY] Cannot auto-restore DB schemas. Manual restore required:")
        await append_output(task_id, "[RECOVERY]   cd backup_Restore && ./restore_ofs_schemas.sh system <DB_PASS> <SERVICE>")

    # Full restore: rm -rf OFSAA -> tar extract -> restore DB schemas
    restore_result = await installation_service.full_restore_to_bd_state(
        request.host, request.username, request.password,
        db_sys_password=db_sys_pass or "",
        db_jdbc_service=db_service or "",
        db_ssh_host=getattr(request, "db_ssh_host", None),
        db_ssh_username=getattr(request, "db_ssh_username", None),
        db_ssh_password=getattr(request, "db_ssh_password", None),
    )
    await append_output(task_id, "\n".join(restore_result.get("logs", [])))

    if restore_result.get("success"):
        await append_output(task_id, "[RECOVERY] BD state restored successfully. You can retry ECM installation.")
        await append_output(task_id, "[RECOVERY] Use resume_from_checkpoint=true to skip BD Pack and retry ECM only.")
    else:
        failed = restore_result.get("failed_steps", [])
        await append_output(task_id, f"[RECOVERY] WARNING: Some restore steps failed: {', '.join(failed)}")
        await append_output(task_id, "[RECOVERY] Please manually complete the failed steps before retrying ECM.")

    await trace("BD state restore process completed")


async def run_installation_process(task_id: str, request: InstallationRequest):
    task = installation_tasks[task_id]
    ssh_service = SSHService()
    installation_service = InstallationService(ssh_service)
    steps = InstallationSteps.STEP_NAMES

    def should_cleanup_failed_fresh() -> bool:
        if (request.installation_mode or "fresh").lower() != "fresh":
            return False
        try:
            return steps.index(task.current_step or "") >= 7
        except ValueError:
            return False

    async def handle_failure(message: str, error: Optional[str] = None) -> None:
        # Cache the error for rollback capability
        if "Environment check failed" in message:
            latest_request_cache["error"] = f"{message}: {error}" if error else message
        
        if should_cleanup_failed_fresh():
            await append_output(task_id, "[INFO] Fresh installation failed at Step 8+. Starting automatic cleanup...")
            cleanup_result = await installation_service.cleanup_failed_fresh_installation(
                request.host, request.username, request.password
            )
            await append_output(task_id, "\n".join(cleanup_result.get("logs", [])))
        task.status = "failed"
        task.error = error or message
        await append_output(task_id, f"[ERROR] {message}")
        if error and error != message:
            await append_output(task_id, f"[ERROR] {error}")
        await update_status(task_id, "failed")

    async def trace(message: str) -> None:
        logger.info("task=%s %s", task_id[:8], message)
        await append_output(task_id, f"[TRACE] {message}")

    try:
        await update_status(task_id, "running", task.current_step, 0)

        connection: dict = {"success": False, "error": "SSH connection failed"}
        for attempt in range(1, 4):
            await append_output(task_id, f"[INFO] SSH connection attempt {attempt}/3")
            connection = await ssh_service.test_connection(request.host, request.username, request.password)
            if connection.get("success"):
                break
            if attempt < 3:
                await append_output(task_id, "[WARN] SSH connection failed. Retrying...")
                await asyncio.sleep(1)

        if not connection.get("success"):
            await handle_failure("SSH connection failed after 3 attempts", connection.get("error"))
            return
        await append_output(task_id, "[OK] SSH connection established")
        await trace("SSH connection established; starting installation workflow")

        # Validate resume_from_checkpoint (resume ECM from BD backup)
        if request.resume_from_checkpoint:
            if not bd_pack_checkpoint.get("completed"):
                await handle_failure("Cannot resume: No BD Pack backup found. Run BD Pack first or disable resume_from_checkpoint.")
                return
            if not bd_pack_checkpoint.get("backup_taken"):
                await append_output(task_id, "[WARN] BD Pack completed but backup was not taken. ECM restore capability may be limited.")
            if bd_pack_checkpoint.get("host") != request.host:
                await append_output(task_id, f"[WARN] BD backup was for host {bd_pack_checkpoint.get('host')}, current host is {request.host}")

        # Define callbacks for interactive commands (available for both BD Pack and ECM)
        async def output_callback(text: str):
            await append_output(task_id, text)

        async def prompt_callback(prompt: str) -> str:
            """Wait for user input via WebSocket for interactive prompts."""
            await append_output(task_id, f"[PROMPT] {prompt}")
            await websocket_manager.send_prompt(task_id, prompt)
            await update_status(task_id, "waiting_input", task.current_step, task.progress)
            response = await websocket_manager.wait_for_user_input(task_id, timeout=3600)
            await update_status(task_id, "running", task.current_step, task.progress)
            return response

        async def auto_yes_callback(prompt: str) -> str:
            """Automatically answer Y only for Y/N confirmation prompts.
            For other prompts (passwords, usernames, etc.), wait for user input.
            """
            prompt_lower = prompt.lower()
            # Detect Y/N confirmation patterns (all lowercase since we check against prompt_lower)
            yn_patterns = [
                # Parenthesized patterns (lowercase versions)
                "(y/n)", "(y/y)", "(n/n)", "(n/y)",
                "(y)", "(n)",
                # Slash patterns without parens
                "y/y", "n/n", "y/n", "n/y",
                # Enter patterns
                "enter (y", "enter (n", "enter y", "enter n",
                # Proceed patterns  
                "to proceed",
                # Other confirmation patterns
                "y to", "n to",
                "y or n", "yes or no",
                "(yes/no)", "yes/no",
                # Selection change patterns
                "to change the selection",
            ]
            is_yn_prompt = any(pattern in prompt_lower for pattern in yn_patterns)
            
            if is_yn_prompt:
                await append_output(task_id, f"[AUTO-ANSWER Y] {prompt}")
                return "Y"
            else:
                # Not a Y/N prompt - wait for user input
                await append_output(task_id, f"[PROMPT] {prompt}")
                await websocket_manager.send_prompt(task_id, prompt)
                await update_status(task_id, "waiting_input", task.current_step, task.progress)
                response = await websocket_manager.wait_for_user_input(task_id, timeout=3600)
                await update_status(task_id, "running", task.current_step, task.progress)
                return response

        # Run BD Pack only if selected AND not resuming from checkpoint
        if request.install_bdpack and not request.resume_from_checkpoint:
            # Step 1: Oracle user and oinstall group
            await update_status(task_id, "running", steps[0], InstallationSteps.progress_for_index(0))
            result = await installation_service.create_oracle_user_and_oinstall_group(request.host, request.username, request.password)
            await append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("Oracle user setup failed", result.get("error"))
                return

            # Step 2: Mount point /u01
            await update_status(task_id, "running", steps[1], InstallationSteps.progress_for_index(1))
            result = await installation_service.create_mount_point(request.host, request.username, request.password)
            await append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("Mount point creation failed", result.get("error"))
                return

            # Step 3: Install packages
            await update_status(task_id, "running", steps[2], InstallationSteps.progress_for_index(2))
            result = await installation_service.install_ksh_and_git(request.host, request.username, request.password)
            await append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("Package installation failed", result.get("error"))
                return

            # Step 4: Create .profile
            await update_status(task_id, "running", steps[3], InstallationSteps.progress_for_index(3))
            result = await installation_service.create_profile_file(request.host, request.username, request.password)
            await append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("Profile creation failed", result.get("error"))
                return

            # Step 5: Java installation
            await update_status(task_id, "running", steps[4], InstallationSteps.progress_for_index(4))
            await trace("Starting Java installation step")
            result = await installation_service.install_java_from_repo(request.host, request.username, request.password)
            await append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("Java installation failed", result.get("error"))
                return
            await trace("Java installation step completed")

            java_home = result.get("java_home")
            if java_home:
                update_java = await installation_service.update_java_profile(
                    request.host, request.username, request.password, java_home
                )
                await append_output(task_id, "\n".join(update_java.get("logs", [])))
                if not update_java.get("success"):
                    await handle_failure("Updating JAVA_HOME failed", update_java.get("error"))
                    return

            # Step 6: OFSAA directories
            await update_status(task_id, "running", steps[5], InstallationSteps.progress_for_index(5))
            result = await installation_service.create_ofsaa_directories(request.host, request.username, request.password)
            await append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("OFSAA directory creation failed", result.get("error"))
                return

            # Step 7: Oracle client check
            await update_status(task_id, "running", steps[6], InstallationSteps.progress_for_index(6))
            result = await installation_service.check_existing_oracle_client_and_update_profile(
                request.host, request.username, request.password, request.oracle_sid
            )
            await append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("Oracle client detection failed", result.get("error"))
                return

            # Step 8: Installer setup and envCheck
            await update_status(task_id, "running", steps[7], InstallationSteps.progress_for_index(7))
            await trace("Starting installer download/extract step")
            result = await installation_service.download_and_extract_installer(request.host, request.username, request.password)
            await append_output(task_id, "\n".join(result.get("logs", [])))
            if not result.get("success"):
                await handle_failure("Installer download failed", result.get("error"))
                return
            await trace("Installer download/extract step completed")

            perm_result = await installation_service.set_installer_permissions(request.host, request.username, request.password)
            await append_output(task_id, "\n".join(perm_result.get("logs", [])))
            if not perm_result.get("success"):
                await handle_failure("Installer permission setup failed", perm_result.get("error"))
                return

            await append_output(task_id, "[INFO] Sourcing /home/oracle/.profile before envCheck")

            env_result = await installation_service.run_environment_check(
                request.host,
                request.username,
                request.password,
                on_output_callback=output_callback,
                on_prompt_callback=prompt_callback,
            )
            await append_output(task_id, "\n".join(env_result.get("logs", [])))
            if not env_result.get("success"):
                await handle_failure("Environment check failed", env_result.get("error"))
                return
            await trace("Environment check step completed")

            # Step 9: Apply XML/properties and run schema creator (osc.sh)
            await update_status(task_id, "running", steps[8], InstallationSteps.progress_for_index(8))
            await trace("Starting config apply and osc.sh step")
            cfg_result = await installation_service.apply_installer_config_files(
                request.host,
                request.username,
                request.password,
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
            await append_output(task_id, "\n".join(cfg_result.get("logs", [])))
            if not cfg_result.get("success"):
                await handle_failure("Applying installer config files failed", cfg_result.get("error"))
                return

            osc_result = await installation_service.run_osc_schema_creator(
                request.host,
                request.username,
                request.password,
                on_output_callback=output_callback,
                on_prompt_callback=prompt_callback,
            )
            await append_output(task_id, "\n".join(osc_result.get("logs", [])))
            if not osc_result.get("success"):
                # Auto-cleanup on osc.sh failure
                await append_output(task_id, "\n[RECOVERY] osc.sh execution failed. Starting automatic recovery cleanup...")
                cleanup_result = await installation_service.cleanup_after_osc_failure(
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
                    db_ssh_host=getattr(request, "db_ssh_host", None),
                    db_ssh_username=getattr(request, "db_ssh_username", None),
                    db_ssh_password=getattr(request, "db_ssh_password", None),
                )
                await append_output(task_id, "\n".join(cleanup_result.get("logs", [])))
                if cleanup_result.get("failed_steps"):
                    await append_output(task_id, f"\n[RECOVERY] The following cleanup steps failed: {', '.join(cleanup_result['failed_steps'])}")
                    await append_output(task_id, "[RECOVERY] Please manually complete the failed steps before retrying installation")
                
                await handle_failure("osc.sh execution failed - automatic cleanup initiated", osc_result.get("error"))
                return
            await trace("osc.sh step completed")

            # Step 10: setup.sh SILENT
            await update_status(task_id, "running", steps[9], InstallationSteps.progress_for_index(9))
            await trace("Starting setup.sh SILENT step")
            setup_result = await installation_service.run_setup_silent(
                request.host,
                request.username,
                request.password,
                on_output_callback=output_callback,
                on_prompt_callback=auto_yes_callback,
                pack_app_enable=request.pack_app_enable,
                installation_mode=request.installation_mode,
                install_sanc=request.install_sanc,
            )
            await append_output(task_id, "\n".join(setup_result.get("logs", [])))
            if not setup_result.get("success"):
                await handle_failure("setup.sh SILENT execution failed", setup_result.get("error"))
                return
            await trace("setup.sh SILENT step completed")
            await append_output(task_id, "[OK] BD Pack installation completed")
            
            # Save BD Pack checkpoint
            bd_pack_checkpoint["completed"] = True
            bd_pack_checkpoint["request"] = request.dict()
            bd_pack_checkpoint["task_id"] = task_id
            bd_pack_checkpoint["host"] = request.host
            bd_pack_checkpoint["timestamp"] = datetime.now().isoformat()

            # ===== AUTOMATIC BACKUP AFTER BD PACK SUCCESS =====
            # Always take backup after BD success (required for ECM restore capability)
            await append_output(task_id, "\n[INFO] ==================== BD PACK BACKUP ====================")
            
            # Ensure backup/restore scripts from Git repo are available
            await update_status(task_id, "running", "Verifying backup/restore scripts", 76)
            scripts_result = await installation_service.ensure_backup_restore_scripts(
                request.host, request.username, request.password
            )
            await append_output(task_id, "\n".join(scripts_result.get("logs", [])))
            if not scripts_result.get("success"):
                await append_output(task_id, "[WARN] Backup scripts not found in Git repo. Backup may fail for DB schemas.")

            # Application Backup: tar -cvf OFSAA_BKP.tar.gz OFSAA
            await update_status(task_id, "running", "Taking application backup (tar)", 77)
            await trace("Starting application backup after BD Pack success")
            app_backup_result = await installation_service.backup_application(
                request.host, request.username, request.password
            )
            await append_output(task_id, "\n".join(app_backup_result.get("logs", [])))
            if not app_backup_result.get("success"):
                await append_output(task_id, "[WARN] Application backup failed. ECM restore capability may be limited.")
            else:
                await trace("Application backup completed")

            # DB Schema Backup: backup_ofs_schemas.sh system <DB_PASS> <SERVICE>
            db_sys_pass = request.db_sys_password
            db_service = request.schema_jdbc_service
            if db_sys_pass and db_service:
                await update_status(task_id, "running", "Taking DB schema backup", 79)
                await trace("Starting DB schema backup after BD Pack success")
                db_backup_result = await installation_service.backup_db_schemas(
                    request.host, request.username, request.password,
                    db_sys_password=db_sys_pass,
                    db_jdbc_service=db_service,
                        db_ssh_host=getattr(request, "db_ssh_host", None),
                        db_ssh_username=getattr(request, "db_ssh_username", None),
                        db_ssh_password=getattr(request, "db_ssh_password", None),
                )
                await append_output(task_id, "\n".join(db_backup_result.get("logs", [])))
                if not db_backup_result.get("success"):
                    await append_output(task_id, "[WARN] DB schema backup failed. ECM restore capability may be limited.")
                else:
                    bd_pack_checkpoint["backup_taken"] = True
                    await trace("DB schema backup completed")
            else:
                await append_output(task_id, "[WARN] db_sys_password or schema_jdbc_service not provided. Skipping DB schema backup.")

            await append_output(task_id, "[INFO] BD Pack backup phase complete")
            if bd_pack_checkpoint.get("backup_taken"):
                await append_output(task_id, "[CHECKPOINT] BD Pack backup saved. ECM can be restored to this point if it fails.")
        else:
            # Check if we're resuming from BD backup or just skipping BD Pack
            if request.resume_from_checkpoint and bd_pack_checkpoint.get("completed"):
                await append_output(task_id, "[INFO] Resuming from BD Pack backup - skipping BD Pack installation")
                await append_output(task_id, "[INFO] BD Pack will NOT be reinstalled. Starting ECM from BD backup restore point.")
                await trace("Resuming from BD Pack backup - BD reinstall skipped")
            else:
                    await append_output(task_id, "[INFO] Skipping BD Pack installation as per request")
                    await trace("Skipping BD Pack installation")

            # If user requested ECM-only but wants a BD app+DB backup before ECM starts,
            # perform the same backup steps we take after a BD Pack success so ECM can
            # be restored to this point on failure.
            if (not request.install_bdpack) and getattr(request, "ecm_take_bd_backup", False):
                await append_output(task_id, "\n[INFO] ECM-only run: taking BD application + DB schema backup before ECM start as requested")
                await update_status(task_id, "running", "Preparing BD backup before ECM", 80)

                scripts_result = await installation_service.ensure_backup_restore_scripts(
                    request.host, request.username, request.password
                )
                await append_output(task_id, "\n".join(scripts_result.get("logs", [])))
                if not scripts_result.get("success"):
                    await append_output(task_id, "[WARN] Backup scripts not found in Git repo. Backup may fail for DB schemas.")

                await update_status(task_id, "running", "Taking application backup (tar)", 81)
                app_backup_result = await installation_service.backup_application(
                    request.host, request.username, request.password
                )
                await append_output(task_id, "\n".join(app_backup_result.get("logs", [])))
                if not app_backup_result.get("success"):
                    await append_output(task_id, "[WARN] Application backup failed. ECM restore capability may be limited.")
                else:
                    await trace("Application backup completed (pre-ECM)")

                db_sys_pass = request.db_sys_password
                db_service = request.schema_jdbc_service
                if db_sys_pass and db_service:
                    await update_status(task_id, "running", "Taking DB schema backup", 82)
                    db_backup_result = await installation_service.backup_db_schemas(
                        request.host, request.username, request.password,
                        db_sys_password=db_sys_pass,
                        db_jdbc_service=db_service,
                        db_ssh_host=getattr(request, "db_ssh_host", None),
                        db_ssh_username=getattr(request, "db_ssh_username", None),
                        db_ssh_password=getattr(request, "db_ssh_password", None),
                    )
                    await append_output(task_id, "\n".join(db_backup_result.get("logs", [])))
                    if not db_backup_result.get("success"):
                        await append_output(task_id, "[WARN] DB schema backup failed. ECM restore capability may be limited.")
                    else:
                        bd_pack_checkpoint["completed"] = True
                        bd_pack_checkpoint["backup_taken"] = True
                        bd_pack_checkpoint["request"] = request.dict()
                        bd_pack_checkpoint["task_id"] = task_id
                        bd_pack_checkpoint["host"] = request.host
                        bd_pack_checkpoint["timestamp"] = datetime.now().isoformat()
                        await trace("DB schema backup completed (pre-ECM) and checkpoint saved")
                else:
                    await append_output(task_id, "[WARN] db_sys_password or schema_jdbc_service not provided. Skipping DB schema backup.")


        # ============== ECM MODULE INSTALLATION ==============
        if request.install_ecm:
            await append_output(task_id, "\n[INFO] ==================== ECM MODULE INSTALLATION ====================")
            
            # ECM Step 1: Download and extract ECM installer kit
            await update_status(task_id, "running", "Downloading and extracting ECM installer kit", 82)
            await trace("Starting ECM installer download/extract step")
            ecm_download_result = await installation_service.download_and_extract_ecm_installer(
                request.host, request.username, request.password
            )
            await append_output(task_id, "\n".join(ecm_download_result.get("logs", [])))
            if not ecm_download_result.get("success"):
                await handle_failure("ECM installer download failed", ecm_download_result.get("error"))
                return
            await trace("ECM installer download/extract step completed")

            # ECM Step 2: Set permissions
            await update_status(task_id, "running", "Setting ECM kit permissions", 85)
            ecm_perm_result = await installation_service.set_ecm_permissions(
                request.host, request.username, request.password
            )
            await append_output(task_id, "\n".join(ecm_perm_result.get("logs", [])))
            if not ecm_perm_result.get("success"):
                await handle_failure("ECM permission setup failed", ecm_perm_result.get("error"))
                return

            # ECM Step 3: Apply ECM config files
            await update_status(task_id, "running", "Applying ECM configuration files", 88)
            await trace("Starting ECM config apply step")
            ecm_cfg_result = await installation_service.apply_ecm_config_files(
                request.host,
                request.username,
                request.password,
                # OFS_ECM_SCHEMA_IN.xml params
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
                # ECM default.properties params
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
                # ECM OFSAAI_InstallConfig.xml params
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
            await append_output(task_id, "\n".join(ecm_cfg_result.get("logs", [])))
            if not ecm_cfg_result.get("success"):
                await handle_failure("ECM config files apply failed", ecm_cfg_result.get("error"))
                return
            await trace("ECM config apply step completed")

            # ECM Step 4a: Run ECM osc.sh -s
            await update_status(task_id, "running", "Running ECM schema creator (osc.sh)", 92)
            await trace("Starting ECM osc.sh step")
            ecm_osc_result = await installation_service.run_ecm_osc_schema_creator(
                request.host,
                request.username,
                request.password,
                on_output_callback=output_callback,
                on_prompt_callback=prompt_callback,
            )
            await append_output(task_id, "\n".join(ecm_osc_result.get("logs", [])))
            if not ecm_osc_result.get("success"):
                # ECM osc.sh failed → Restore to BD state
                await append_output(task_id, "\n[RECOVERY] ECM osc.sh failed. Initiating restore to BD state...")
                await _restore_bd_on_ecm_failure(task_id, request, installation_service, trace)
                await handle_failure("ECM osc.sh execution failed - restored to BD state", ecm_osc_result.get("error"))
                return
            await trace("ECM osc.sh step completed")

            # ECM Step 4b: Run ECM setup.sh SILENT
            await update_status(task_id, "running", "Running ECM setup (setup.sh SILENT)", 96)
            await trace("Starting ECM setup.sh SILENT step")
            ecm_setup_result = await installation_service.run_ecm_setup_silent(
                request.host,
                request.username,
                request.password,
                on_output_callback=output_callback,
                on_prompt_callback=auto_yes_callback,
            )
            await append_output(task_id, "\n".join(ecm_setup_result.get("logs", [])))
            if not ecm_setup_result.get("success"):
                # ECM setup.sh failed → Restore to BD state
                await append_output(task_id, "\n[RECOVERY] ECM setup.sh failed. Initiating restore to BD state...")
                await _restore_bd_on_ecm_failure(task_id, request, installation_service, trace)
                await handle_failure("ECM setup.sh SILENT execution failed - restored to BD state", ecm_setup_result.get("error"))
                return
            await trace("ECM setup.sh SILENT step completed")
            await append_output(task_id, "[OK] ECM Module installation completed")
            
            # Clear BD Pack checkpoint after successful ECM completion
            if bd_pack_checkpoint.get("completed"):
                bd_pack_checkpoint["completed"] = False
                bd_pack_checkpoint["backup_taken"] = False
                bd_pack_checkpoint["request"] = None
                bd_pack_checkpoint["task_id"] = None
                bd_pack_checkpoint["host"] = None
                bd_pack_checkpoint["timestamp"] = None
                await append_output(task_id, "[CHECKPOINT] BD Pack checkpoint cleared after successful ECM completion.")

        task.status = "completed"
        task.progress = 100
        await update_status(task_id, "completed", steps[9], 100)
        await append_output(task_id, "[OK] Installation completed successfully")
        return

    except asyncio.TimeoutError as exc:
        await handle_failure("Installation timed out", str(exc))
    except Exception as exc:
        logger.exception("Installation process failed")
        await handle_failure("Installation failed", str(exc))
