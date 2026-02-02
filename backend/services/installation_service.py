import logging
from typing import Dict, Any, List
from services.ssh_service import SSHService

logger = logging.getLogger(__name__)

class InstallationService:
    """Service for OFSAA installation operations"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
    
    async def setup_oracle_user(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Create oinstall group, oracle user, and required directories
        Equivalent to: sshpass -p {{ROOT_PASS}} ssh -o StrictHostKeyChecking=no {{ROOT_USER}}@{{HOST}} 
        "groupadd -f oinstall; id -u oracle &>/dev/null || useradd -g oinstall oracle; mkdir -p /u01/OFSAA/FICHOME /u01/OFSAA/FTPSHARE /u01/installer_kit; chown -R oracle:oinstall /u01"
        """
        try:
            command = (
                "groupadd -f oinstall; "
                "id -u oracle &>/dev/null || useradd -g oinstall oracle; "
                "mkdir -p /u01/OFSAA/FICHOME /u01/OFSAA/FTPSHARE /u01/installer_kit; "
                "chown -R oracle:oinstall /u01"
            )
            
            result = await self.ssh_service.execute_command(host, username, password, command)
            
            logs = []
            if result["success"]:
                logs.append("Group Management:")
                logs.append("  oinstall group created/verified")
                logs.append("User Management:")
                logs.append("  oracle user created/verified with oinstall group")
                logs.append("Directory Structure:")
                logs.append("  /u01/OFSAA/FICHOME - OFSAA home directory")
                logs.append("  /u01/OFSAA/FTPSHARE - FTP share directory")
                logs.append("  /u01/installer_kit - Installation files directory")
                logs.append("Permissions:")
                logs.append("  Directory ownership set to oracle:oinstall")
                logs.append("System Status:")
                logs.append("  Oracle environment ready for installation")
                
                return {
                    "success": True,
                    "message": "Oracle user and directories setup completed",
                    "logs": logs,
                    "output": result["stdout"]
                }
            else:
                error_msg = f"Setup failed: {result.get('stderr', 'Unknown error')}"
                logs.append(f"ERROR: {error_msg}")
                
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
                "logs": [f"ERROR: Exception: {str(e)}"]
            }
    
    async def install_packages(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Install required packages: ksh, unzip, git
        Equivalent to: sshpass -p {{ROOT_PASS}} ssh -o StrictHostKeyChecking=no {{ROOT_USER}}@{{HOST}} "yum install -y ksh unzip git"
        """
        try:
            command = "yum install -y ksh unzip git"
            
            result = await self.ssh_service.execute_command(host, username, password, command)
            
            logs = []
            if result["success"]:
                logs.append("Package Installation Results:")
                logs.append("  ksh (Korn shell) - Advanced shell for Oracle scripts")
                logs.append("  unzip - Archive extraction utility")
                logs.append("  git - Version control system")
                
                # Parse yum output for more detailed logs
                if result["stdout"]:
                    output_lines = result["stdout"].split('\n')
                    installed_count = 0
                    updated_count = 0
                    already_installed = 0
                    
                    for line in output_lines:
                        if 'Installed:' in line:
                            installed_count += line.count('.')
                        elif 'Updated:' in line:
                            updated_count += line.count('.')
                        elif 'Nothing to do' in line:
                            already_installed += 1
                        elif 'Complete!' in line:
                            logs.append("  YUM transaction completed successfully")
                    
                    if installed_count > 0:
                        logs.append(f"  {installed_count} new packages installed")
                    if updated_count > 0:
                        logs.append(f"  {updated_count} packages updated")
                    if already_installed > 0:
                        logs.append("  Some packages were already installed")
                
                logs.append("Package installation phase completed")
                
                return {
                    "success": True,
                    "message": "Required packages installed successfully",
                    "logs": logs,
                    "output": result["stdout"]
                }
            else:
                error_msg = f"Package installation failed: {result.get('stderr', 'Unknown error')}"
                logs.append(f"ERROR: {error_msg}")
                
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
                "logs": [f"ERROR: Exception: {str(e)}"]
            }
    
    async def extract_installer_files(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Extract installer files as oracle user
        Equivalent to: sshpass -p {{ORACLE_PASS}} ssh -o StrictHostKeyChecking=no {{ORACLE_USER}}@{{HOST}} "cd /u01/installer_kit && unzip -o *.zip"
        
        Note: This assumes the oracle user has the same password as root for simplicity.
        In production, you might want to use sudo or key-based authentication.
        """
        try:
            # Use sudo to run as oracle user instead of separate SSH connection
            command = "sudo -u oracle bash -c 'cd /u01/installer_kit && unzip -o *.zip'"
            
            result = await self.ssh_service.execute_command(host, username, password, command)
            
            logs = []
            if result["success"]:
                logs.append("File Extraction Results:")
                logs.append("  Extraction completed successfully")
                logs.append("  Target: /u01/installer_kit directory")
                logs.append("  User context: oracle")
                
                # Parse unzip output for file details
                if result["stdout"]:
                    output_lines = result["stdout"].split('\n')
                    extracted_files = []
                    archive_count = 0
                    
                    for line in output_lines:
                        if 'inflating:' in line.lower():
                            file_info = line.strip().split()[-1]  # Get filename
                            extracted_files.append(file_info)
                        elif 'extracting:' in line.lower():
                            file_info = line.strip().split()[-1]  # Get filename
                            extracted_files.append(file_info)
                        elif 'archive:' in line.lower() or '.zip' in line.lower():
                            archive_count += 1
                    
                    if archive_count > 0:
                        logs.append(f"  Processed {archive_count} archive file(s)")
                    
                    if extracted_files:
                        logs.append(f"  Extracted {len(extracted_files)} files total")
                        # Show first few files as examples
                        logs.append("  Sample extracted files:")
                        for file in extracted_files[:5]:
                            filename = file.split('/')[-1] if '/' in file else file
                            logs.append(f"    • {filename}")
                        if len(extracted_files) > 5:
                            logs.append(f"    • ... and {len(extracted_files) - 5} more files")
                    
                    logs.append("  Ready for OFSAA installation configuration")
                else:
                    logs.append("  Archive extraction completed (no detailed output)")
                
                logs.append("File extraction phase completed successfully")
                
                return {
                    "success": True,
                    "message": "Installer files extracted successfully",
                    "logs": logs,
                    "output": result["stdout"]
                }
            else:
                error_msg = f"File extraction failed: {result.get('stderr', 'Unknown error')}"
                logs.append(f"ERROR: {error_msg}")
                
                # Check if no zip files found
                if "No such file" in result.get("stderr", "") or "cannot find" in result.get("stderr", ""):
                    logs.append("  → Make sure installer zip files are uploaded to /u01/installer_kit/")
                
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs,
                    "stderr": result.get("stderr", ""),
                    "returncode": result.get("returncode", -1)
                }
                
        except Exception as e:
            logger.error(f"File extraction failed: {str(e)}")
            return {
                "success": False,
                "error": f"File extraction failed: {str(e)}",
                "logs": [f"ERROR: Exception: {str(e)}"]
            }