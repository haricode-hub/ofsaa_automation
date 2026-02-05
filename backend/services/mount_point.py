import logging
from typing import Dict, Any
from services.ssh_service import SSHService
from services.validation import ValidationService

logger = logging.getLogger(__name__)

class MountPointService:
    """Service for mount point creation - Step 2"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
        self.validation = ValidationService(ssh_service)
    
    async def create_mount_point(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Create the mount point: /u01
        Enhanced with smart validation
        """
        try:
            logs = []
            
            # Check if /u01 exists
            logs.append("→ Checking for /u01 mount point...")
            u01_check = await self.validation.check_directory_exists(host, username, password, "/u01")
            
            if u01_check.get('exists'):
                logs.append("✓ /u01 mount point already exists")
            else:
                logs.append("Creating /u01 directory...")
                mkdir_cmd = "mkdir -p /u01"
                mkdir_result = await self.ssh_service.execute_command(host, username, password, mkdir_cmd)
                if mkdir_result.get('success') or mkdir_result.get('returncode') == 0:
                    logs.append("✓ /u01 directory created")
                else:
                    logs.append(f"Failed to create /u01: {mkdir_result.get('stderr', '')}")
                    return {"success": False, "error": "Failed to create /u01", "logs": logs}
            
            # Check and create subdirectories
            subdirs = [
                "/u01/OFSAA/FICHOME",
                "/u01/OFSAA/FTPSHARE",
                "/u01/installer_kit"
            ]
            
            all_subdirs_exist = True
            
            for subdir in subdirs:
                subdir_check = await self.validation.check_directory_exists(host, username, password, subdir)
                if subdir_check.get('exists'):
                    logs.append(f"✓ {subdir} already exists")
                else:
                    all_subdirs_exist = False
                    logs.append(f"Creating {subdir}...")
                    create_cmd = f"mkdir -p {subdir}"
                    create_result = await self.ssh_service.execute_command(host, username, password, create_cmd)
                    if create_result.get('success') or create_result.get('returncode') == 0:
                        logs.append(f"✓ {subdir} created")
                    else:
                        logs.append(f"Warning: Could not create {subdir}")
            
            if u01_check.get('exists') and all_subdirs_exist:
                logs.append("✓ All mount point directories already exist, skipping ownership updates")
                logs.append("✓ Mount Point Setup Complete")
                return {
                    "success": True,
                    "message": "Mount point /u01 already configured, skipped",
                    "logs": logs
                }
            
            # Set ownership and permissions
            logs.append("Setting ownership and permissions...")
            chown_cmd = "chown -R oracle:oinstall /u01 && chmod -R 755 /u01"
            chown_result = await self.ssh_service.execute_command(host, username, password, chown_cmd)
            
            if chown_result.get('success') or chown_result.get('returncode') == 0:
                logs.append("✓ Ownership set to oracle:oinstall")
                logs.append("✓ Permissions configured (755)")
            else:
                logs.append("Warning: Could not set all permissions")
            
            logs.append("✓ Mount Point Setup Complete")
            
            return {
                "success": True,
                "message": "Mount point /u01 configured successfully",
                "logs": logs
            }
                
        except Exception as e:
            logger.error(f"Mount point creation failed: {str(e)}")
            return {
                "success": False,
                "error": f"Mount point creation failed: {str(e)}",
                "logs": [f"ERROR: Exception in mount point creation: {str(e)}"]
            }
