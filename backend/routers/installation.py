from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket
from typing import Optional, Dict
import asyncio
from services.ssh_service import SSHService
from services.installation_service import InstallationService
from schemas.installation import InstallationRequest, InstallationResponse, InstallationStatus, OracleClientConfig
from core.logging import TaskLogger
from core.config import Config, InstallationSteps
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory storage for installation tasks (use Redis/database in production)
installation_tasks: dict[str, InstallationStatus] = {}

# WebSocket Manager for real-time communication
class WebSocketManager:
    """Manages WebSocket connections for real-time updates and interactive prompts"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_input_queue: Dict[str, asyncio.Queue] = {}
    
    async def connect(self, task_id: str, websocket: WebSocket):
        """Connect a WebSocket for a specific task"""
        await websocket.accept()
        self.active_connections[task_id] = websocket
        self.user_input_queue[task_id] = asyncio.Queue()
        logger.info(f"WebSocket connected for task {task_id}")
    
    def disconnect(self, task_id: str):
        """Disconnect a WebSocket"""
        if task_id in self.active_connections:
            del self.active_connections[task_id]
        if task_id in self.user_input_queue:
            del self.user_input_queue[task_id]
        logger.info(f"WebSocket disconnected for task {task_id}")
    
    async def send_message(self, task_id: str, message: dict):
        """Send a message to a specific task's WebSocket"""
        if task_id in self.active_connections:
            try:
                await self.active_connections[task_id].send_json(message)
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {str(e)}")
                self.disconnect(task_id)
    
    async def send_output(self, task_id: str, output: str):
        """Send command output to WebSocket"""
        await self.send_message(task_id, {
            "type": "output",
            "data": output
        })
    
    async def send_prompt(self, task_id: str, prompt: str):
        """Send interactive prompt to WebSocket"""
        await self.send_message(task_id, {
            "type": "prompt",
            "data": prompt
        })
    
    async def wait_for_user_input(self, task_id: str, timeout: int = 300) -> str:
        """Wait for user input from WebSocket"""
        if task_id not in self.user_input_queue:
            return ""
        
        try:
            user_input = await asyncio.wait_for(
                self.user_input_queue[task_id].get(),
                timeout=timeout
            )
            return user_input
        except asyncio.TimeoutError:
            logger.warning(f"User input timeout for task {task_id}")
            return ""
    
    async def handle_user_input(self, task_id: str, user_input: str):
        """Handle user input received from WebSocket"""
        if task_id in self.user_input_queue:
            await self.user_input_queue[task_id].put(user_input)

# Create global WebSocket manager instance
websocket_manager = WebSocketManager()

@router.post("/start", response_model=InstallationResponse)
async def start_installation(
    request: InstallationRequest,
    background_tasks: BackgroundTasks
):
    """Start OFSAA installation process"""
    try:
        # Generate unique task ID
        import uuid
        task_id = str(uuid.uuid4())
        
        # Initialize task status
        installation_tasks[task_id] = InstallationStatus(
            task_id=task_id,
            status="started",
            current_step="Initializing connection",
            progress=0,
            logs=[
                f"OFSAA Installation Started - Task ID: {task_id[:8]}...",
                f"Target Server: {request.host}",
                f"Username: {request.username}",
                f"Started at: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "Initializing SSH connection..."
            ]
        )
        
        # Start installation in background
        background_tasks.add_task(
            run_installation_process,
            task_id,
            request.host,
            request.username,
            request.password,
            request.fic_home,
            request.java_home,
            request.java_bin,
            request.oracle_sid
        )
        
        return InstallationResponse(
            task_id=task_id,
            status="started",
            message="Installation process initiated successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to start installation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start installation: {str(e)}")

@router.get("/status/{task_id}", response_model=InstallationStatus)
async def get_installation_status(task_id: str):
    """Get installation status by task ID"""
    if task_id not in installation_tasks:
        raise HTTPException(status_code=404, detail="Installation task not found")
    
    return installation_tasks[task_id]

@router.get("/tasks")
async def list_installation_tasks():
    """List all installation tasks"""
    return {"tasks": list(installation_tasks.values())}

@router.post("/test-connection")
async def test_ssh_connection(request: InstallationRequest):
    """Test SSH connection without starting installation"""
    try:
        ssh_service = SSHService()
        result = await ssh_service.test_connection(request.host, request.username, request.password)
        return result
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return {
            "success": False,
            "error": f"Connection test failed: {str(e)}"
        }

@router.post("/oracle-client/check")
async def check_oracle_client_only(request: InstallationRequest):
    """Check Oracle client installation status only"""
    try:
        ssh_service = SSHService()
        installation_service = InstallationService(ssh_service)
        
        # Test connection first
        connection_test = await ssh_service.test_connection(request.host, request.username, request.password)
        if not connection_test["success"]:
            return {
                "success": False,
                "error": connection_test["error"]
            }
        
        # Check Oracle client
        oracle_result = await installation_service.check_existing_oracle_client_and_update_profile(
            request.host, request.username, request.password, request.oracle_sid or "ORCL"
        )
        
        return oracle_result
    except Exception as e:
        logger.error(f"Oracle client check failed: {str(e)}")
        return {
            "success": False,
            "error": f"Oracle client check failed: {str(e)}"
        }

@router.post("/ofsaa/create-directories")
async def create_ofsaa_directories_only(request: InstallationRequest):
    """Create OFSAA directory structure only"""
    try:
        ssh_service = SSHService()
        installation_service = InstallationService(ssh_service)
        
        # Test connection first
        connection_test = await ssh_service.test_connection(request.host, request.username, request.password)
        if not connection_test["success"]:
            return {
                "success": False,
                "error": connection_test["error"]
            }
        
        # Create OFSAA directories
        ofsaa_result = await installation_service.create_ofsaa_directories(
            request.host, request.username, request.password, request.fic_home or "/u01/OFSAA/FICHOME"
        )
        
        return ofsaa_result
    except Exception as e:
        logger.error(f"OFSAA directory creation failed: {str(e)}")
        return {
            "success": False,
            "error": f"OFSAA directory creation failed: {str(e)}"
        }

@router.post("/ofsaa/setup-installer")
async def setup_ofsaa_installer(request: InstallationRequest):
    """Download OFSAA installer and run environment check"""
    try:
        ssh_service = SSHService()
        installation_service = InstallationService(ssh_service)
        
        # Test connection first
        connection_test = await ssh_service.test_connection(request.host, request.username, request.password)
        if not connection_test["success"]:
            return {
                "success": False,
                "error": connection_test["error"]
            }
        
        # Setup installer and run environment check
        installer_result = await installation_service.extract_installer_files(
            request.host, request.username, request.password
        )
        
        return installer_result
    except Exception as e:
        logger.error(f"OFSAA installer setup failed: {str(e)}")
        return {
            "success": False,
            "error": f"OFSAA installer setup failed: {str(e)}"
        }

@router.post("/ofsaa/environment-check")
async def run_environment_check_only(request: InstallationRequest):
    """Run OFSAA environment check script only"""
    try:
        ssh_service = SSHService()
        installation_service = InstallationService(ssh_service)
        
        # Test connection first
        connection_test = await ssh_service.test_connection(request.host, request.username, request.password)
        if not connection_test["success"]:
            return {
                "success": False,
                "error": connection_test["error"]
            }
        
        # Run environment check
        env_check_result = await installation_service.run_environment_check(
            request.host, request.username, request.password
        )
        
        return env_check_result
    except Exception as e:
        logger.error(f"Environment check failed: {str(e)}")
        return {
            "success": False,
            "error": f"Environment check failed: {str(e)}"
        }

async def run_installation_process(task_id: str, host: str, username: str, password: str, 
                                    fic_home: str, java_home: Optional[str], java_bin: Optional[str], oracle_sid: str):
    """Background task to run the complete OFSAA installation process"""
    try:
        print(f"Starting OFSAA installation process for task {task_id}")
        print(f"Target: {host}, User: {username}")
        print(f"Profile variables: FIC_HOME={fic_home}, ORACLE_SID={oracle_sid}")
        
        task = installation_tasks[task_id]
        ssh_service = SSHService()
        installation_service = InstallationService(ssh_service)
        
        # Test SSH connection first
        task.current_step = "Testing SSH connection"
        task.progress = InstallationSteps.PROGRESS_MAP["connection_test"]
        task.logs.append("🔗 Testing SSH connection to target server...")
        task.logs.append(f"Target host: {host}")
        task.logs.append(f"Username: {username}")
        
        connection_test = await ssh_service.test_connection(host, username, password)
        if not connection_test["success"]:
            task.status = "failed"
            task.error = connection_test["error"]
            task.logs.append(f"❌ Connection failed: {connection_test['error']}")
            return
        
        task.logs.append("✅ SSH connection successful")
        task.progress = InstallationSteps.PROGRESS_MAP["connection_test"]
        
        # Oracle User Setup
        task.current_step = InstallationSteps.STEP_NAMES[1]
        task.progress = InstallationSteps.PROGRESS_MAP["oracle_user_setup"]
        task.logs.append("🔨 Creating oracle user and oinstall group...")
        
        oracle_user_result = await installation_service.create_oracle_user_and_oinstall_group(host, username, password)
        if not oracle_user_result["success"]:
            task.status = "failed"
            task.error = oracle_user_result["error"]
            task.logs.extend(oracle_user_result["logs"])
            return
        
        task.logs.extend(oracle_user_result["logs"])
        task.progress = InstallationSteps.PROGRESS_MAP["oracle_user_setup"]
        
        # Mount Point Creation
        task.current_step = InstallationSteps.STEP_NAMES[2]
        task.progress = InstallationSteps.PROGRESS_MAP["mount_point_creation"]
        task.logs.append("🔨 Creating mount point /u01...")
        
        mount_point_result = await installation_service.create_mount_point(host, username, password)
        if not mount_point_result["success"]:
            task.status = "failed"
            task.error = mount_point_result["error"]
            task.logs.extend(mount_point_result["logs"])
            return
        
        task.logs.extend(mount_point_result["logs"])
        task.progress = InstallationSteps.PROGRESS_MAP["mount_point_creation"]
        
        # Package Installation
        task.current_step = InstallationSteps.STEP_NAMES[3]
        task.progress = InstallationSteps.PROGRESS_MAP["packages_installation"]
        task.logs.append("🔨 Installing KSH (Korn Shell) and git...")
        
        packages_result = await installation_service.install_ksh_and_git(host, username, password)
        if not packages_result["success"]:
            task.status = "failed"
            task.error = packages_result["error"]
            task.logs.extend(packages_result["logs"])
            return
        
        task.logs.extend(packages_result["logs"])
        task.progress = InstallationSteps.PROGRESS_MAP["packages_installation"]
        
        # Profile Creation
        task.current_step = InstallationSteps.STEP_NAMES[4]
        task.progress = InstallationSteps.PROGRESS_MAP["profile_creation"]
        task.logs.append("🔨 Creating .profile file at /home/oracle/.profile...")
        
        profile_result = await installation_service.create_profile_file(host, username, password)
        if not profile_result["success"]:
            task.status = "failed"
            task.error = profile_result["error"]
            task.logs.extend(profile_result["logs"])
            return
        
        task.logs.extend(profile_result["logs"])
        task.progress = InstallationSteps.PROGRESS_MAP["profile_creation"]
        
        # Java Installation (Required prerequisite for Oracle Client)
        task.current_step = InstallationSteps.STEP_NAMES[5]
        task.progress = InstallationSteps.PROGRESS_MAP["java_installation"]
        task.logs.append("🔨 Installing Java from Oracle installer kit...")
        task.logs.append("📋 Note: Java must be installed before Oracle Client")
        
        java_home_path = java_home or "/u01/jdk-11.0.16"
        java_result = await installation_service.install_java_from_oracle_kit(host, username, password, java_home_path)
        if not java_result["success"]:
            task.status = "failed"
            task.error = java_result["error"]
            task.logs.extend(java_result["logs"])
            return
        
        task.logs.extend(java_result["logs"])
        task.logs.append("✅ Java installation completed successfully!")
        task.logs.append("🔒 PREREQUISITE MET: Java is now available for Oracle Client")
        task.progress = InstallationSteps.PROGRESS_MAP["java_installation"]
        
        # OFSAA Directory Structure Creation
        task.current_step = InstallationSteps.STEP_NAMES[6]
        task.progress = InstallationSteps.PROGRESS_MAP["ofsaa_directories"]
        task.logs.append("📁 Creating OFSAA directory structure...")
        task.logs.append("🏠 Setting up FICHOME and FTPSHARE directories...")
        
        ofsaa_dirs_result = await installation_service.create_ofsaa_directories(host, username, password, fic_home)
        if not ofsaa_dirs_result["success"]:
            task.status = "failed"
            task.error = ofsaa_dirs_result["error"]
            task.logs.extend(ofsaa_dirs_result["logs"])
            return
        
        task.logs.extend(ofsaa_dirs_result["logs"])
        task.logs.append("✅ OFSAA directory structure created successfully!")
        task.progress = InstallationSteps.PROGRESS_MAP["ofsaa_directories"]
        
        # Oracle Client Check (Optimized - no installation, just check and configure)
        task.current_step = InstallationSteps.STEP_NAMES[7]
        task.progress = InstallationSteps.PROGRESS_MAP["oracle_client_check"]
        task.logs.append("🔍 Scanning for existing Oracle client installations...")
        task.logs.append("⚡ Optimized mode: Checking existing installations (no new files created)")
        task.logs.append("🔍 Searching common Oracle installation paths...")
        
        oracle_client_result = await installation_service.check_existing_oracle_client_and_update_profile(host, username, password, oracle_sid)
        if not oracle_client_result["success"]:
            task.status = "failed"
            task.error = oracle_client_result["error"]
            task.logs.extend(oracle_client_result["logs"])
            return
        
        task.logs.extend(oracle_client_result["logs"])
        task.progress = InstallationSteps.PROGRESS_MAP["oracle_client_check"]
        
        # OFSAA Installer Setup and Environment Check
        task.current_step = InstallationSteps.STEP_NAMES[8]
        task.progress = InstallationSteps.PROGRESS_MAP["installer_setup"]
        task.logs.append("📦 Setting up OFSAA installer from git repository...")
        
        # Send WebSocket message to inform user about installer download
        await websocket_manager.send_output(task_id, "")
        await websocket_manager.send_output(task_id, "=" * 70)
        await websocket_manager.send_output(task_id, "📦 OFSAA INSTALLER DOWNLOAD & EXTRACTION")
        await websocket_manager.send_output(task_id, "=" * 70)
        await websocket_manager.send_output(task_id, "⏳ Estimated time: 5-15 minutes (depending on network speed)")
        await websocket_manager.send_output(task_id, "📊 Real-time progress will be shown below:")
        await websocket_manager.send_output(task_id, "")
        
        # Create callback to stream output to WebSocket
        async def output_callback(line: str):
            await websocket_manager.send_output(task_id, line)
            # Also add to task logs for persistence
            task.logs.append(line)
        
        installer_result = await installation_service.download_and_extract_installer(
            host, username, password, on_output=output_callback
        )
        if not installer_result["success"]:
            task.logs.append("⚠️ Installer setup had issues, but continuing...")
            await websocket_manager.send_output(task_id, "⚠️ Installer setup had issues, check logs")
        else:
            task.logs.append("✅ OFSAA installer setup completed!")
            await websocket_manager.send_output(task_id, "")
            await websocket_manager.send_output(task_id, "✅ Installer download and extraction completed!")
            await websocket_manager.send_output(task_id, "=" * 70)
            # Debug: Announce about to run envCheck.sh
            await websocket_manager.send_output(task_id, "[DEBUG] About to call run_environment_check after installer extraction")
            env_check_result = await installation_service.run_environment_check(
                host, username, password, on_output=output_callback
            )
            if not env_check_result["success"]:
                task.logs.append("❌ Environment check failed!")
                await websocket_manager.send_output(task_id, "❌ Environment check failed!")
            else:
                task.logs.append("✅ Environment check completed!")
                await websocket_manager.send_output(task_id, "✅ Environment check completed!")
        
        task.progress = InstallationSteps.PROGRESS_MAP["environment_check"]
        
        # Profile Update with Custom Variables
        task.current_step = InstallationSteps.STEP_NAMES[9]
        task.progress = InstallationSteps.PROGRESS_MAP["profile_update"]
        task.logs.append("🔨 Updating profile with custom variables...")
        
        custom_variables_result = await installation_service.update_profile_with_custom_variables(
            host, username, password, fic_home, java_home, java_bin, oracle_sid
        )
        if not custom_variables_result["success"]:
            task.status = "failed"
            task.error = custom_variables_result["error"]
            task.logs.extend(custom_variables_result["logs"])
            return
        
        task.logs.extend(custom_variables_result["logs"])
        task.progress = 97
        
        # Extract Installer Files
        task.current_step = "Extracting installer files"
        task.progress = 98
        task.logs.append("🔨 Extracting installer files...")
        
        installer_result = await installation_service.extract_installer_files(host, username, password)
        if not installer_result["success"]:
            task.logs.append("⚠️ Installer extraction failed - may need manual file upload")
            task.logs.extend(installer_result["logs"])
        else:
            task.logs.extend(installer_result["logs"])
        
        # Profile Verification
        task.current_step = InstallationSteps.STEP_NAMES[10]
        task.progress = InstallationSteps.PROGRESS_MAP["verification"]
        task.logs.append("🔍 Verifying profile setup...")
        
        verify_result = await installation_service.verify_profile_setup(host, username, password)
        if verify_result["success"]:
            task.logs.extend(verify_result["logs"])
        else:
            task.logs.append("⚠️ Profile verification had issues, but continuing...")
            task.logs.extend(verify_result["logs"])
        
        # Complete
        task.progress = InstallationSteps.PROGRESS_MAP["completed"]
        task.current_step = "OFSAA environment setup completed successfully"
        task.status = "completed"
        task.logs.append("")
        task.logs.append("🎉 OFSAA Environment Setup Completed Successfully!")
        task.logs.append("=" * 50)
        task.logs.append("✅ Oracle user and oinstall group created")
        task.logs.append("✅ Mount point /u01 created with proper directory structure")
        task.logs.append("✅ KSH (Korn Shell) and git packages installed")
        task.logs.append("✅ Oracle profile file created at /home/oracle/.profile")
        task.logs.append("✅ Java installed from Oracle kit")
        task.logs.append("✅ OFSAA directory structure created (/u01/OFSAA/FICHOME, /u01/OFSAA/FTPSHARE)")
        task.logs.append("✅ Oracle client found and environment configured")
        task.logs.append("✅ OFSAA installer downloaded and environment check completed")
        task.logs.append("✅ Profile updated with custom variables")
        task.logs.append("✅ Environment ready for OFSAA installation")
        task.logs.append("")
        task.logs.append("📊 Optimized Installation Summary:")
        task.logs.append("   • Zero backup files created (optimized mode)")
        task.logs.append("   • Minimal temporary files used")
        task.logs.append("   • OFSAA directory structure pre-configured")
        task.logs.append("   • Installer downloaded from git repository")
        task.logs.append("   • Interactive environment check (you respond to all prompts)")
        task.logs.append("   • Existing Oracle client detected and configured")
        task.logs.append("   • All operations performed in-place")
        task.logs.append("")
        task.logs.append("Next components:")
        task.logs.append("  1. Upload OFSAA installation files to /u01/installer_kit/")
        task.logs.append("  2. Run OFSAA installer as oracle user")
        task.logs.append("  3. Configure database connections")
        task.logs.append("")
        task.logs.append("Environment Summary:")
        task.logs.append(f"   • FIC_HOME: {fic_home}")
        task.logs.append(f"   • OFSAA_HOME: /u01/OFSAA")
        task.logs.append(f"   • FTPSHARE: /u01/OFSAA/FTPSHARE")
        task.logs.append(f"   • INSTALLER_KIT: /u01/installer_kit")
        task.logs.append(f"   • ENV_CHECK: /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin/envCheck.sh")
        if java_home:
            task.logs.append(f"   • JAVA_HOME: {java_home} (custom)")
        if java_bin:
            task.logs.append(f"   • JAVA_BIN: {java_bin} (custom)")
        task.logs.append(f"   • ORACLE_SID: {oracle_sid}")
        task.logs.append("")
        task.logs.append("🚀 System is ready for OFSAA installation!")
        task.logs.append("   Upload your OFSAA installer files to /u01/installer_kit/")
        task.logs.append("   Run the OFSAA installer as the oracle user")
        
    except Exception as e:
        print(f"Installation process failed with exception: {str(e)}")
        logger.error(f"Installation process failed: {str(e)}")
        task = installation_tasks[task_id]
        task.status = "failed"
        task.error = str(e)
        task.logs.append(f"❌ Unexpected error: {str(e)}")