import asyncio
import logging
import uuid
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

        async def output_callback(text: str):
            await append_output(task_id, text)

        async def prompt_callback(prompt: str) -> str:
            await append_output(task_id, f"[PROMPT] {prompt}")
            await websocket_manager.send_prompt(task_id, prompt)
            await update_status(task_id, "waiting_input", steps[7], InstallationSteps.progress_for_index(7))
            response = await websocket_manager.wait_for_user_input(task_id, timeout=3600)
            await update_status(task_id, "running", steps[7], InstallationSteps.progress_for_index(7))
            return response

        async def auto_yes_callback(prompt: str) -> str:
            """Automatically answer Y to any Y/N prompts during setup.sh SILENT.
            setup.sh is invoked with SILENT flag but some prompts are not suppressed.
            Blocking on WebSocket input here would cause the process to hang for hours.
            """
            await append_output(task_id, f"[AUTO-ANSWER Y] {prompt}")
            return "Y"

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
            prop_ecmsource=request.prop_ecmsource,
            prop_ecmloadtype=request.prop_ecmloadtype,
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

        task.status = "completed"
        task.progress = 100
        await update_status(task_id, "completed", steps[9], 100)
        await append_output(task_id, "[OK] osc.sh completed")
        await append_output(task_id, "[OK] setup.sh SILENT completed")
        await append_output(task_id, "[OK] Schema creation completed")
        return

    except asyncio.TimeoutError as exc:
        await handle_failure("Installation timed out", str(exc))
    except Exception as exc:
        logger.exception("Installation process failed")
        await handle_failure("Installation failed", str(exc))
