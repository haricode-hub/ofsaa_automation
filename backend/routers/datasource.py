"""
WebLogic Datasource creation router.

Endpoints:
    POST  /create-datasources
    GET   /create-datasources/status/{task_id}
"""

import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException

from core.task_manager import task_manager as tm
from core.dependencies import create_installation_service
from schemas.datasource import (
    DatasourceCreationRequest,
    DatasourceCreationResponse,
)
from schemas.installation import InstallationStatus

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/create-datasources", response_model=DatasourceCreationResponse)
async def create_datasources(request: DatasourceCreationRequest):
    """Create WebLogic datasources via WLST."""
    try:
        if not request.datasources:
            raise HTTPException(400, "At least one datasource is required")

        task_id = str(uuid.uuid4())
        tm.register_task(
            task_id,
            InstallationStatus(
                task_id=task_id,
                status="started",
                current_step="Initializing datasource creation",
                current_module="DATASOURCE_CREATION",
                progress=0,
                logs=[
                    f"[INFO] Datasource creation started (task {task_id[:8]})",
                    f"[INFO] WebLogic: {request.admin_url}",
                    f"[INFO] Datasources: {len(request.datasources)}",
                ],
            ),
        )

        asyncio_task = asyncio.create_task(_execute_datasource_creation(task_id, request))
        tm.register_asyncio_task(task_id, asyncio_task)

        return DatasourceCreationResponse(
            success=True,
            task_id=task_id,
            message=f"Datasource creation started ({len(request.datasources)} datasources)",
            total_datasources=len(request.datasources),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to start datasource creation")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/create-datasources/status/{task_id}")
async def get_datasource_status(task_id: str):
    """Get datasource creation task status."""
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
    raise HTTPException(status_code=404, detail="Datasource creation task not found")


# ── Async worker ─────────────────────────────────────────────────────────────

async def _execute_datasource_creation(
    task_id: str,
    request: DatasourceCreationRequest,
) -> None:
    """Execute datasource creation workflow — single WLST session."""
    tm.register_task(
        task_id,
        InstallationStatus(
            task_id=task_id,
            status="running",
            current_step="Initializing datasource creation",
            current_module="DATASOURCE_CREATION",
            progress=0,
            logs=[f"[INFO] Datasource creation started (task {task_id[:8]})"],
        ),
    )

    try:
        await tm.append_output(task_id, f"[INFO] Target: {request.host}")
        await tm.append_output(task_id, f"[INFO] WebLogic Admin: {request.admin_url}")
        await tm.append_output(task_id, f"[INFO] Total datasources: {len(request.datasources)}")
        await tm.update_status(task_id, "running", "Initializing datasource creation", module="DATASOURCE_CREATION")

        svc = create_installation_service()

        # SSH connection (3 retries)
        if not await _ssh_connect(task_id, svc, request.host, request.username, request.password):
            return

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

        async def on_output(line: str) -> None:
            if line and line.strip():
                await tm.append_output(task_id, line)

        async def on_subtask(message: str) -> None:
            await tm.append_output(task_id, message)

        result = await svc.installer.create_datasources_and_deploy_app(
            host=request.host,
            username=request.username,
            password=request.password,
            admin_url=request.admin_url,
            weblogic_username=request.weblogic_username,
            weblogic_password=request.weblogic_password,
            datasources=ds_list,
            deploy_app_enabled=False,
            wl_home=request.wl_home,
            on_output_callback=on_output,
            on_subtask_callback=on_subtask,
        )
        await tm.append_output(task_id, "\n".join(result.get("logs", [])))

        if not result.get("success"):
            err = result.get("error") or "Datasource creation failed"
            await tm.append_output(task_id, f"[ERROR] {err}")
            await tm.update_status(task_id, "failed", "Datasource creation failed", module="DATASOURCE_CREATION")
        else:
            total = len(request.datasources)
            await tm.append_output(task_id, f"\n[SUCCESS] All {total} datasources created successfully")
            await tm.update_status(task_id, "completed", "All datasources created", module="DATASOURCE_CREATION")

    except (asyncio.CancelledError,):
        logger.info("Datasource task %s was cancelled", task_id)
        task = tm.get_task(task_id)
        if task and task.status not in ("failed",):
            await tm.update_status(task_id, "failed", "Cancelled by user")
    except Exception as exc:
        logger.exception("Datasource creation failed: %s", task_id)
        await tm.append_output(task_id, f"[ERROR] Exception: {exc}")
        await tm.update_status(task_id, "failed", "Datasource creation failed")


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
