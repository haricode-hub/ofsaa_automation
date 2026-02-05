import logging
from typing import Dict, Any
from services.ssh_service import SSHService
from services.validation import ValidationService

logger = logging.getLogger(__name__)

class PackageInstallationService:
    """Service for package installation - Step 3"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
        self.validation = ValidationService(ssh_service)
    
    async def install_ksh_and_git(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Install KSH (KORN SHELL) and git with smart validation
        """
        try:
            logs = []
            packages_to_install = []
            
            # Check KSH
            logs.append("→ Checking for KSH (Korn Shell)...")
            ksh_check = await self.validation.check_package_installed(host, username, password, "ksh")
            
            if ksh_check.get('installed'):
                logs.append(ksh_check.get('message', '✓ KSH already installed'))
            else:
                logs.append("KSH not found, will install")
                packages_to_install.append("ksh")
            
            # Check git
            logs.append("→ Checking for git...")
            git_check = await self.validation.check_package_installed(host, username, password, "git")
            
            if git_check.get('installed'):
                git_version = await self.validation.get_package_version(host, username, password, "git")
                logs.append(git_version.get('message', '✓ Git already installed'))
            else:
                logs.append("Git not found, will install")
                packages_to_install.append("git")
            
            # Check unzip
            logs.append("→ Checking for unzip...")
            unzip_check = await self.validation.check_package_installed(host, username, password, "unzip")
            
            if unzip_check.get('installed'):
                logs.append("✓ Unzip already installed")
            else:
                logs.append("Unzip not found, will install")
                packages_to_install.append("unzip")
            
            # Install missing packages
            if packages_to_install:
                logs.append(f"Installing packages: {', '.join(packages_to_install)}")
                command = f"yum install -y {' '.join(packages_to_install)}"
                result = await self.ssh_service.execute_command(host, username, password, command, timeout=300)
                
                if result.get('success') or result.get('returncode') == 0:
                    logs.append(f"✓ Packages installed successfully: {', '.join(packages_to_install)}")
                else:
                    logs.append(f"Warning: Package installation may have had issues")
                    logs.append(f"  {result.get('stderr', '')[:200]}")
            else:
                logs.append("✓ All required packages already installed")
            
            logs.append("✓ Package Installation Complete")
            
            return {
                "success": True,
                "message": "Package installation completed",
                "logs": logs
            }
                
        except Exception as e:
            logger.error(f"Package installation failed: {str(e)}")
            return {
                "success": False,
                "error": f"Package installation failed: {str(e)}",
                "logs": [f"ERROR: Exception in package installation: {str(e)}"]
            }