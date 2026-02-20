import asyncio
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException

from core.websocket_manager import WebSocketManager
from schemas.installation import InstallationRequest, InstallationResponse, InstallationStatus
from services.ssh_service import SSHService
from services.ecm_installation_service import ECMInstallationService


router = APIRouter()
logger = logging.getLogger(__name__)

ecm_tasks: dict[str, InstallationStatus] = {}
websocket_manager = WebSocketManager()


@router.post("/start", response_model=InstallationResponse)
async def start_ecm_installation(request: InstallationRequest):
    """Start ECM Pack installation process."""
    try:
        task_id = str(uuid.uuid4())
        
        ecm_tasks[task_id] = InstallationStatus(
            task_id=task_id,
            status="started",
            current_step="Initializing ECM installation",
            progress=0,
            logs=[
                f"[INFO] ECM installation started (task {task_id[:8]})",
                f"[INFO] Target: {request.host}",
            ],
        )

        asyncio.create_task(run_ecm_installation_process(task_id, request))

        return InstallationResponse(
            task_id=task_id,
            status="started",
            message="ECM installation process initiated",
        )
    except Exception as exc:
        logger.exception("Failed to start ECM installation")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status/{task_id}", response_model=InstallationStatus)
async def get_ecm_installation_status(task_id: str):
    """Get the current status of an ECM installation task."""
    if task_id not in ecm_tasks:
        raise HTTPException(status_code=404, detail="ECM installation task not found")
    return ecm_tasks[task_id]


@router.get("/tasks")
async def list_ecm_installation_tasks():
    """List all ECM installation tasks."""
    return {"tasks": list(ecm_tasks.values())}


async def append_output(task_id: str, text: str) -> None:
    """Append output to the task logs and send via WebSocket."""
    if not text:
        return
    task = ecm_tasks.get(task_id)
    if task:
        lines = [line for line in text.splitlines() if line.strip()]
        task.logs.extend(lines)
    await websocket_manager.send_output(task_id, text)


async def update_status(
    task_id: str, status: Optional[str] = None, step: Optional[str] = None, progress: Optional[int] = None
) -> None:
    """Update the task status and send via WebSocket."""
    task = ecm_tasks.get(task_id)
    if task is None:
        return
    if status:
        task.status = status
    if step:
        task.current_step = step
    if progress is not None:
        task.progress = progress
    await websocket_manager.send_status(task_id, task.status, task.current_step, task.progress)


async def run_ecm_installation_process(task_id: str, request: InstallationRequest):
    """Run the ECM installation workflow."""
    task = ecm_tasks[task_id]
    ssh_service = SSHService()
    ecm_service = ECMInstallationService(ssh_service)
    
    ecm_steps = [
        "SSH Connection",
        "Git Repository Setup",
        "Download & Extract ECM Kit",
        "Backup Config Files",
        "Replace Config Files",
        "Run Schema Creator (osc.sh)",
        "Run Silent Installer (setup.sh)",
    ]

    def step_progress(index: int) -> int:
        """Calculate progress percentage for step index."""
        return int((index / len(ecm_steps)) * 100)

    async def handle_failure(message: str, error: Optional[str] = None) -> None:
        """Handle installation failure."""
        task.status = "failed"
        task.error = error or message
        await append_output(task_id, f"[ERROR] {message}")
        if error and error != message:
            await append_output(task_id, f"[ERROR] {error}")
        await update_status(task_id, "failed")

    async def trace(message: str) -> None:
        """Log a trace message."""
        logger.info("ecm_task=%s %s", task_id[:8], message)
        await append_output(task_id, f"[TRACE] {message}")

    try:
        await update_status(task_id, "running", ecm_steps[0], step_progress(0))

        # Step 1: SSH Connection
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
        await trace("SSH connection established; starting ECM installation workflow")

        # Step 2: Git Repository Setup
        await update_status(task_id, "running", ecm_steps[1], step_progress(1))
        await trace("Setting up Git repository")
        git_result = await ecm_service.setup_ecm_git_repo(request.host, request.username, request.password)
        await append_output(task_id, "\n".join(git_result.get("logs", [])))
        if not git_result.get("success"):
            await handle_failure("Git repository setup failed", git_result.get("error"))
            return
        await trace("Git repository setup completed")

        # Step 3: Download & Extract ECM Kit
        await update_status(task_id, "running", ecm_steps[2], step_progress(2))
        await trace("Downloading and extracting ECM kit")
        extract_result = await ecm_service.download_and_extract_ecm_kit(request.host, request.username, request.password)
        await append_output(task_id, "\n".join(extract_result.get("logs", [])))
        if not extract_result.get("success"):
            await handle_failure("ECM kit extraction failed", extract_result.get("error"))
            return
        await trace("ECM kit extraction completed")

        # Step 4: Backup Config Files
        await update_status(task_id, "running", ecm_steps[3], step_progress(3))
        await trace("Backing up existing ECM config files")
        backup_result = await ecm_service.backup_ecm_config_files(request.host, request.username, request.password)
        await append_output(task_id, "\n".join(backup_result.get("logs", [])))
        if not backup_result.get("success"):
            await handle_failure("Config file backup failed", backup_result.get("error"))
            return
        await trace("Config file backup completed")

        # Step 5: Replace Config Files
        await update_status(task_id, "running", ecm_steps[4], step_progress(4))
        await trace("Replacing ECM config files from Git")
        
        async def output_callback(text: str):
            await append_output(task_id, text)

        config_result = await ecm_service.apply_ecm_config_files(
            request.host,
            request.username,
            request.password,
            ecm_schema_jdbc_host=request.ecm_schema_jdbc_host,
            ecm_schema_jdbc_port=request.ecm_schema_jdbc_port,
            ecm_schema_jdbc_service=request.ecm_schema_jdbc_service,
            ecm_schema_host=request.ecm_schema_host,
            ecm_schema_setup_env=request.ecm_schema_setup_env,
            ecm_schema_apply_same_for_all=request.ecm_schema_apply_same_for_all,
            ecm_schema_default_password=request.ecm_schema_default_password,
            ecm_schema_datafile_dir=request.ecm_schema_datafile_dir,
            ecm_schema_tablespace_autoextend=request.ecm_schema_tablespace_autoextend,
            ecm_schema_external_directory_value=request.ecm_schema_external_directory_value,
            ecm_schema_config_schema_name=request.ecm_schema_config_schema_name,
            ecm_schema_atomic_schema_name=request.ecm_schema_atomic_schema_name,
            ecm_prop_base_country=request.ecm_prop_base_country,
            ecm_prop_default_jurisdiction=request.ecm_prop_default_jurisdiction,
            ecm_prop_web_service_user=request.ecm_prop_web_service_user,
            ecm_prop_web_service_password=request.ecm_prop_web_service_password,
            ecm_aai_webappservertype=request.ecm_aai_webappservertype,
            ecm_aai_dbserver_ip=request.ecm_aai_dbserver_ip,
            ecm_aai_oracle_service_name=request.ecm_aai_oracle_service_name,
            ecm_aai_abs_driver_path=request.ecm_aai_abs_driver_path,
            ecm_aai_web_server_ip=request.ecm_aai_web_server_ip,
            ecm_aai_web_server_port=request.ecm_aai_web_server_port,
            ecm_aai_context_name=request.ecm_aai_context_name,
        )
        await append_output(task_id, "\n".join(config_result.get("logs", [])))
        if not config_result.get("success"):
            await handle_failure("Config file replacement failed", config_result.get("error"))
            return
        await trace("Config files replaced successfully")

        # Step 6: Run Schema Creator (osc.sh -s)
        await update_status(task_id, "running", ecm_steps[5], step_progress(5))
        await trace("Starting ECM schema creator (osc.sh -s)")
        await append_output(task_id, "[INFO] Running schema creator...")

        async def prompt_callback(prompt: str) -> str:
            """Handle interactive prompts during schema creation."""
            await append_output(task_id, f"[PROMPT] {prompt}")
            await websocket_manager.send_prompt(task_id, prompt)
            await update_status(task_id, "waiting_input", ecm_steps[5], step_progress(5))
            response = await websocket_manager.wait_for_user_input(task_id, timeout=3600)
            await update_status(task_id, "running", ecm_steps[5], step_progress(5))
            return response

        osc_result = await ecm_service.run_ecm_schema_creator(
            request.host,
            request.username,
            request.password,
            on_output_callback=output_callback,
            on_prompt_callback=prompt_callback,
        )
        await append_output(task_id, "\n".join(osc_result.get("logs", [])))
        if not osc_result.get("success"):
            await handle_failure("Schema creator (osc.sh) failed", osc_result.get("error"))
            return
        await trace("Schema creator step completed successfully")

        # Step 7: Run Silent Installer (setup.sh SILENT)
        await update_status(task_id, "running", ecm_steps[6], step_progress(6))
        await trace("Starting ECM silent installer (setup.sh SILENT)")
        await append_output(task_id, "[INFO] Running silent installer...")

        async def auto_yes_callback(prompt: str) -> str:
            """Automatically answer Y to prompts during silent installation."""
            await append_output(task_id, f"[AUTO-ANSWER Y] {prompt}")
            return "Y"

        setup_result = await ecm_service.run_ecm_silent_installer(
            request.host,
            request.username,
            request.password,
            on_output_callback=output_callback,
            on_prompt_callback=auto_yes_callback,
        )
        await append_output(task_id, "\n".join(setup_result.get("logs", [])))
        if not setup_result.get("success"):
            await handle_failure("Silent installer (setup.sh) failed", setup_result.get("error"))
            return
        await trace("Silent installer step completed successfully")

        # Success
        task.status = "completed"
        task.progress = 100
        await update_status(task_id, "completed", "ECM Installation Complete", 100)
        await append_output(task_id, "[OK] ECM installation completed successfully!")
        logger.info("ecm_task=%s ECM installation completed successfully", task_id[:8])

    except asyncio.CancelledError:
        task.status = "cancelled"
        await append_output(task_id, "[WARN] ECM installation was cancelled")
        await update_status(task_id, "cancelled")
        logger.warning("ecm_task=%s ECM installation cancelled", task_id[:8])
    except Exception as exc:
        logger.exception("ecm_task=%s Unexpected error during ECM installation", task_id[:8])
        await handle_failure("Unexpected error during ECM installation", str(exc))
