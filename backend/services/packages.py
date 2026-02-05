import logging
from typing import Dict, Any
from services.ssh_service import SSHService

logger = logging.getLogger(__name__)

class PackageInstallationService:
    """Service for package installation - Step 3"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
    
    async def install_ksh_and_git(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Install KSH (KORN SHELL) and git
        """
        try:
            command = "yum install -y ksh git unzip"
            
            result = await self.ssh_service.execute_command(host, username, password, command)
            
            logs = []
            if result["success"]:
                logs.append("✓ Package Installation")
                logs.append("  ksh (Korn Shell) - Advanced shell for Oracle scripts")
                logs.append("  git - Version control system")
                logs.append("  unzip - Archive extraction utility")
                logs.append("  Package installation completed successfully")
                
                return {
                    "success": True,
                    "message": "KSH, git, and unzip installed successfully",
                    "logs": logs,
                    "output": result["stdout"]
                }
            else:
                error_msg = f"Package installation failed: {result.get('stderr', 'Unknown error')}"
                logs.append(f"Package installation failed: {error_msg}")
                
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs,
                    "stderr": result.get("stderr", ""),
                    "returncode": result.get("returncode", -1)
                }
                
        except Exception as e:
            logger.error(f"Package installation failed: {str(e)}")
            return {
                "success": False,
                "error": f"Package installation failed: {str(e)}",
                "logs": [f"ERROR: Exception in package installation: {str(e)}"]
            }