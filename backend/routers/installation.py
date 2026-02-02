from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional
import asyncio
from services.ssh_service import SSHService
from services.installation_service import InstallationService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class InstallationRequest(BaseModel):
    host: str = Field(..., description="Target host IP address or hostname")
    username: str = Field(..., description="Root username for SSH connection")
    password: str = Field(..., description="Root password for SSH connection")

class InstallationResponse(BaseModel):
    task_id: str
    status: str
    message: str

class InstallationStatus(BaseModel):
    task_id: str
    status: str
    current_step: Optional[str] = None
    progress: int = 0
    logs: list[str] = []
    error: Optional[str] = None

# In-memory storage for installation tasks (use Redis/database in production)
installation_tasks: dict[str, InstallationStatus] = {}

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
            request.password
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

async def run_installation_process(task_id: str, host: str, username: str, password: str):
    """Background task to run the complete installation process"""
    try:
        print(f"🚀 Starting installation process for task {task_id}")
        print(f"📋 Target: {host}, User: {username}")
        
        task = installation_tasks[task_id]
        ssh_service = SSHService()
        installation_service = InstallationService(ssh_service)
        
        # Step 1: Test SSH connection with multiple username formats
        print(f"Testing SSH connection to {host}...")
        task.current_step = "Testing SSH connection"
        task.progress = 10
        task.logs.append(f"Initiating SSH connection to {host}")
        task.logs.append(f"Trying username variations for: {username}")
        task.logs.append(f"Target host: {host}")
        
        # Try different username formats
        username_variations = [
            username,  # Original
            username.lower(),  # Lowercase
            username.capitalize(),  # First letter capitalized
        ]
        
        connection_test = None
        successful_username = None
        
        for test_username in username_variations:
            if test_username != username_variations[0]:  # Skip if same as original
                if test_username == username:
                    continue
            
            print(f"Trying username: '{test_username}'")
            task.logs.append(f"Attempting connection with username: {test_username}")
            
            connection_test = await ssh_service.test_connection(host, test_username, password)
            print(f"Connection test result for '{test_username}': {connection_test}")
            
            if connection_test["success"]:
                successful_username = test_username
                print(f"Connection successful with username: '{test_username}'")
                task.logs.append(f"Connection successful with username: {test_username}")
                break
            else:
                task.logs.append(f"Failed with '{test_username}': {connection_test['error']}")
        
        if not connection_test or not connection_test["success"]:
            print(f"All connection attempts failed")
            task.status = "failed"
            task.error = connection_test["error"] if connection_test else "No connection attempts succeeded"
            task.logs.append("All username variations failed")
            task.logs.append("Check: Host reachable, SSH service running, credentials correct")
            return
        
        task.logs.append(f"SSH connection established successfully as '{successful_username}'")
        task.logs.append(f"Connected to {host} - Authentication verified")
        task.progress = 20
        
        # Step 2: Create Oracle user and directories
        task.current_step = "Setting up Oracle user and directories"
        task.progress = 30
        task.logs.append("Starting Oracle environment setup")
        task.logs.append("Creating oinstall group and oracle user")
        task.logs.append("Creating OFSAA directory structure")
        
        setup_result = await installation_service.setup_oracle_user(host, username, password)
        if not setup_result["success"]:
            task.status = "failed"
            task.error = setup_result["error"]
            task.logs.append(f"User setup failed: {setup_result['error']}")
            task.logs.append("Check: Root privileges, filesystem permissions")
            return
        
        task.logs.extend(setup_result["logs"])
        task.logs.append("Oracle environment setup completed")
        task.progress = 50
        
        # Step 3: Install required packages
        task.current_step = "Installing required packages"
        task.progress = 60
        task.logs.append("Starting package installation")
        task.logs.append("Installing: ksh (Korn shell)")
        task.logs.append("Installing: unzip (Archive utility)")
        task.logs.append("Installing: git (Version control)")
        
        packages_result = await installation_service.install_packages(host, username, password)
        if not packages_result["success"]:
            task.status = "failed"
            task.error = packages_result["error"]
            task.logs.append(f"Package installation failed: {packages_result['error']}")
            task.logs.append("Check: Internet connection, yum repositories, disk space")
            return
        
        task.logs.extend(packages_result["logs"])
        task.logs.append("All required packages installed successfully")
        task.progress = 80
        
        # Step 4: Extract installer files
        task.current_step = "Extracting installer files"
        task.progress = 90
        task.logs.append("Starting installer file extraction")
        task.logs.append("Target directory: /u01/installer_kit")
        task.logs.append("Running as oracle user")
        task.logs.append("Searching for *.zip files...")
        
        extract_result = await installation_service.extract_installer_files(host, username, password)
        if not extract_result["success"]:
            task.status = "failed"
            task.error = extract_result["error"]
            task.logs.append(f"File extraction failed: {extract_result['error']}")
            task.logs.append("Check: Zip files present, oracle user permissions, disk space")
            return
        
        task.logs.extend(extract_result["logs"])
        task.progress = 100
        task.current_step = "System preparation completed successfully"
        task.status = "completed"
        task.logs.append("OFSAA system preparation completed successfully")
        task.logs.append("Environment configured and installer files extracted")
        task.logs.append("Next step: Run OFSAA installer manually or configure automated installation")
        task.logs.append("System is now ready for OFSAA application installation")
        
    except Exception as e:
        print(f"Installation process failed with exception: {str(e)}")
        logger.error(f"Installation process failed: {str(e)}")
        task = installation_tasks[task_id]
        task.status = "failed"
        task.error = str(e)
        task.logs.append(f"Unexpected error: {str(e)}")