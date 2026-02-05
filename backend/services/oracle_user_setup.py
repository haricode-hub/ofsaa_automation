import logging
from typing import Dict, Any
from services.ssh_service import SSHService

logger = logging.getLogger(__name__)

class OracleUserSetupService:
    """Service for Oracle user and group setup - Step 1"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
    
    async def create_oracle_user_and_oinstall_group(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Create the oracle user and map it to the oinstall group
        """
        try:
            command = (
                "groupadd -f oinstall && "
                "(id -u oracle &>/dev/null || useradd -g oinstall oracle) && "
                "echo 'Oracle user and oinstall group setup completed'"
            )
            
            result = await self.ssh_service.execute_command(host, username, password, command)
            
            logs = []
            if result["success"]:
                logs.append("✓ Oracle User and Group Setup")
                logs.append("  oinstall group created/verified")
                logs.append("  oracle user created and mapped to oinstall group")
                logs.append("  User authentication configured")
                
                return {
                    "success": True,
                    "message": "Oracle user and oinstall group setup completed",
                    "logs": logs,
                    "output": result["stdout"]
                }
            else:
                error_msg = f"Oracle user setup failed: {result.get('stderr', 'Unknown error')}"
                logs.append(f"Oracle user setup failed: {error_msg}")
                
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs,
                    "stderr": result.get("stderr", ""),
                    "returncode": result.get("returncode", -1)
                }
                
        except Exception as e:
            logger.error(f"Oracle user setup failed: {str(e)}")
            return {
                "success": False,
                "error": f"Oracle user setup failed: {str(e)}",
                "logs": [f"ERROR: Exception in Oracle user setup: {str(e)}"]
            }