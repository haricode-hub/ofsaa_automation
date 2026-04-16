"""
FICHOME Deployment router — EAR creation, datasource + app deployment.

Endpoints:
    POST  /deploy-fichome
    GET   /deploy-fichome/status/{task_id}
"""

import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException

from core.task_manager import task_manager as tm
from core.dependencies import create_installation_service
from schemas.installation import (
    FichomeDeploymentRequest,
    FichomeDeploymentResponse,
    InstallationStatus,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/deploy-fichome", response_model=FichomeDeploymentResponse)
async def deploy_fichome(request: FichomeDeploymentRequest):
    """Start EAR Creation & Exploding workflow."""
    try:
        if not request.db_sys_password:
            raise HTTPException(400, "db_sys_password is required")
        if not request.config_schema_name:
            raise HTTPException(400, "config_schema_name is required")
        if not request.atomic_schema_name:
            raise HTTPException(400, "atomic_schema_name is required")
        if not request.db_jdbc_service:
            raise HTTPException(400, "db_jdbc_service is required")
        if not request.weblogic_domain_home:
            raise HTTPException(400, "weblogic_domain_home is required")

        task_id = str(uuid.uuid4())
        tm.register_task(
            task_id,
            InstallationStatus(
                task_id=task_id,
                status="started",
                current_step="Initializing EAR creation & exploding",
                current_module="EAR_CREATION",
                progress=0,
                logs=[
                    f"[INFO] EAR creation & exploding started (task {task_id[:8]})",
                    f"[INFO] Database: {request.db_jdbc_service}",
                ],
            ),
        )

        asyncio.create_task(_execute_fichome_deployment(task_id, request))

        return FichomeDeploymentResponse(
            success=True,
            task_id=task_id,
            message="EAR creation & exploding started",
            estimated_duration="15 minutes",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to start EAR creation & exploding")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/deploy-fichome/status/{task_id}")
async def get_fichome_status(task_id: str):
    """Get EAR creation & exploding task status."""
    task = tm.get_task(task_id)
    if task:
        return {
            "success": True,
            "task_id": task_id,
            "status": task.status,
            "current_step": task.current_step,
            "progress": task.progress,
            "logs": task.logs[-50:],
        }
    raise HTTPException(status_code=404, detail="EAR creation task not found")


# ── Async worker ─────────────────────────────────────────────────────────────

async def _execute_fichome_deployment(
    task_id: str,
    request: FichomeDeploymentRequest,
) -> None:
    """Execute EAR Creation & Exploding workflow asynchronously."""
    tm.register_task(
        task_id,
        InstallationStatus(
            task_id=task_id,
            status="running",
            current_step="Initializing EAR creation & exploding",
            current_module="EAR_CREATION",
            progress=0,
            logs=[f"[INFO] EAR creation & exploding started (task {task_id[:8]})"],
        ),
    )

    try:
        await tm.append_output(task_id, f"[INFO] Target: {request.host}")
        await tm.append_output(task_id, f"[INFO] WebLogic Domain: {request.weblogic_domain_home}")
        await tm.update_status(task_id, "running", "Initializing EAR creation & exploding", 0)

        svc = create_installation_service()

        # SSH connection (3 retries)
        connection = await _ssh_connect(task_id, svc, request.host, request.username, request.password)
        if not connection:
            return

        # Callbacks
        async def on_subtask(message: str) -> None:
            await tm.append_output(task_id, message)
            if "Granting database privileges" in message:
                await tm.update_status(task_id, "running", "Granting database privileges", 10)
            elif "Running EAR creation & exploding script" in message:
                await tm.update_status(task_id, "running", "Running EAR creation & exploding script", 30)
            elif "Running startofsaa.sh" in message:
                await tm.update_status(task_id, "running", "Running startofsaa.sh", 70)
            elif "Running checkofsaa.sh" in message:
                await tm.update_status(task_id, "running", "Running checkofsaa.sh", 80)
            elif "Deploying application to WebLogic" in message:
                await tm.update_status(task_id, "running", "Deploying application to WebLogic", 85)

        async def on_output(line: str) -> None:
            if line and line.strip():
                await tm.append_output(task_id, line)

        # EAR creation
        result = await svc.installer.deploy_fichome(
            host=request.host,
            username=request.username,
            password=request.password,
            on_subtask_callback=on_subtask,
            on_output_callback=on_output,
            db_sys_password=request.db_sys_password,
            db_jdbc_host=request.db_jdbc_host or request.host,
            db_jdbc_port=request.db_jdbc_port,
            db_jdbc_service=request.db_jdbc_service,
            config_schema_name=request.config_schema_name,
            atomic_schema_name=request.atomic_schema_name,
            weblogic_domain_home=request.weblogic_domain_home,
        )
        await tm.append_output(task_id, "\n".join(result.get("logs", [])))

        if not result.get("success"):
            error_msg = result.get("error") or "EAR creation & exploding failed"
            await tm.append_output(task_id, f"[ERROR] {error_msg}")
            await tm.update_status(task_id, "failed", "EAR creation & exploding failed")
            return

        await tm.append_output(task_id, "[SUCCESS] EAR creation & exploding completed successfully")

        # Combined datasource creation + app deployment (single WLST session)
        has_ds = request.ds_enabled and request.datasources
        has_deploy = request.deploy_app_enabled

        if has_ds or has_deploy:
            ds_list = []
            if has_ds:
                ds_list = [
                    {
                        "ds_name": ds.ds_name,
                        "jndi_name": ds.jndi_name,
                        "db_url": ds.db_url,
                        "db_user": ds.db_user,
                        "db_password": ds.db_password,
                        "targets": ds.targets,
                    }
                    for ds in request.datasources
                ]

            section_label = (
                "Datasources + App Deployment"
                if (has_ds and has_deploy)
                else ("Datasource Creation" if has_ds else "App Deployment")
            )
            await tm.append_output(task_id, f"\n[INFO] ===== {section_label.upper()} (SINGLE WLST SESSION) =====")
            if has_ds:
                await tm.append_output(task_id, f"[INFO] Datasources: {len(ds_list)}")
            if has_deploy:
                await tm.append_output(task_id, f"[INFO] Deploy: FICHOME -> {request.deploy_app_target_server}")
            await tm.update_status(task_id, "running", "Datasources + App Deployment", 88)

            combined_result = await svc.installer.create_datasources_and_deploy_app(
                host=request.host,
                username=request.username,
                password=request.password,
                admin_url=request.admin_url,
                weblogic_username=request.weblogic_username,
                weblogic_password=request.weblogic_password,
                datasources=ds_list if has_ds else None,
                deploy_app_enabled=has_deploy,
                deploy_app_path=request.deploy_app_path,
                deploy_app_target_server=request.deploy_app_target_server,
                wl_home=request.wl_home,
                on_output_callback=on_output,
                on_subtask_callback=on_subtask,
            )
            await tm.append_output(task_id, "\n".join(combined_result.get("logs", [])))

            if not combined_result.get("success"):
                err = combined_result.get("error") or f"{section_label} failed"
                await tm.append_output(task_id, f"[ERROR] {err}")
                await tm.update_status(task_id, "failed", f"EAR OK but {section_label} failed", 100)
            else:
                await tm.append_output(task_id, f"[SUCCESS] {section_label} completed successfully")
                await tm.update_status(task_id, "completed", "Deployment completed", 100)
        else:
            await tm.update_status(task_id, "completed", "Deployment completed", 100)

    except Exception as exc:
        logger.exception("EAR creation & exploding failed: %s", task_id)
        await tm.append_output(task_id, f"[ERROR] Exception: {exc}")
        await tm.update_status(task_id, "failed", "EAR creation & exploding failed")


# ── Shared SSH helper ────────────────────────────────────────────────────────

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
