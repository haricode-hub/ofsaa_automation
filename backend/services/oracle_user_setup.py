import logging
from typing import Dict, Any
from services.ssh_service import SSHService
from services.validation import ValidationService

logger = logging.getLogger(__name__)

class OracleUserSetupService:
    """Service for Oracle user and group setup - Step 1"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
        self.validation = ValidationService(ssh_service)
    
    async def create_oracle_user_and_oinstall_group(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Create the oracle user and map it to the oinstall group
        Enhanced with smart validation
        """
        try:
            logs = []
            
            # Check if oinstall group exists
            logs.append("→ Checking for oinstall group...")
            group_check = await self.validation.check_group_exists(host, username, password, "oinstall")
            
            if group_check.get('exists'):
                logs.append("✓ oinstall group already exists, using existing group")
            else:
                logs.append("Creating oinstall group...")
                # -f makes groupadd succeed even if the group already exists
                group_cmd = "groupadd -f oinstall"
                group_result = await self.ssh_service.execute_command(host, username, password, group_cmd)
                if group_result.get('success'):
                    logs.append("✓ oinstall group created (or already exists)")
                else:
                    stderr_text = (group_result.get('stderr', '') or '').lower()
                    if "already exists" in stderr_text:
                        logs.append("✓ oinstall group already exists, continuing")
                    else:
                        logs.append(f"Failed to create oinstall group: {group_result.get('stderr', '')}")
                        return {
                            "success": False,
                            "error": "Failed to create oinstall group",
                            "logs": logs
                        }
            
            # Check if oracle user exists
            logs.append("→ Checking for oracle user...")
            user_check = await self.validation.check_user_exists(host, username, password, "oracle")
            
            if user_check.get('exists'):
                logs.append("✓ Oracle user already exists, skipping creation")
                logs.append(f"  User info: {user_check.get('output', '')}")
            else:
                logs.append("Creating oracle user and mapping to oinstall group...")
                user_cmd = "useradd -g oinstall oracle"
                user_result = await self.ssh_service.execute_command(host, username, password, user_cmd)
                
                if user_result.get('success') or user_result.get('returncode') == 0:
                    logs.append("✓ Oracle user created and mapped to oinstall group")
                else:
                    # Check if user was created despite error
                    recheck = await self.validation.check_user_exists(host, username, password, "oracle")
                    if recheck.get('exists'):
                        logs.append("✓ Oracle user exists and is configured")
                    else:
                        logs.append(f"Failed to create oracle user: {user_result.get('stderr', '')}")
                        return {
                            "success": False,
                            "error": "Failed to create oracle user",
                            "logs": logs
                        }
            
            logs.append("✓ Oracle User and Group Setup Complete")
            
            return {
                "success": True,
                "message": "Oracle user and oinstall group setup completed",
                "logs": logs
            }
                
        except Exception as e:
            logger.error(f"Oracle user setup failed: {str(e)}")
            return {
                "success": False,
                "error": f"Oracle user setup failed: {str(e)}",
                "logs": [f"ERROR: Exception in Oracle user setup: {str(e)}"]
            }
