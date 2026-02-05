import logging
from typing import Dict, Any
from services.ssh_service import SSHService

logger = logging.getLogger(__name__)

class MountPointService:
    """Service for mount point creation - Step 2"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
    
    async def create_mount_point(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Create the mount point: /u01
        """
        try:
            command = (
                "mkdir -p /u01/OFSAA/FICHOME /u01/OFSAA/FTPSHARE /u01/installer_kit && "
                "chown -R oracle:oinstall /u01 && "
                "chmod -R 755 /u01 && "
                "echo 'Mount point /u01 created and configured'"
            )
            
            result = await self.ssh_service.execute_command(host, username, password, command)
            
            logs = []
            if result["success"]:
                logs.append("✓ Mount Point Creation")
                logs.append("  /u01 directory structure created")
                logs.append("  /u01/OFSAA/FICHOME (OFSAA home directory)")
                logs.append("  /u01/OFSAA/FTPSHARE (FTP share directory)")
                logs.append("  /u01/installer_kit (Installation files)")
                logs.append("  Ownership set to oracle:oinstall")
                logs.append("  Permissions configured (755)")
                
                return {
                    "success": True,
                    "message": "Mount point /u01 created successfully",
                    "logs": logs,
                    "output": result["stdout"]
                }
            else:
                error_msg = f"Mount point creation failed: {result.get('stderr', 'Unknown error')}"
                logs.append(f"Mount point creation failed: {error_msg}")
                
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs,
                    "stderr": result.get("stderr", ""),
                    "returncode": result.get("returncode", -1)
                }
                
        except Exception as e:
            logger.error(f"Mount point creation failed: {str(e)}")
            return {
                "success": False,
                "error": f"Mount point creation failed: {str(e)}",
                "logs": [f"ERROR: Exception in mount point creation: {str(e)}"]
            }