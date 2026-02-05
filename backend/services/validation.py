"""Validation service for checking existing installations and configurations"""
import logging
from typing import Optional, Dict, Any
from services.ssh_service import SSHService

logger = logging.getLogger(__name__)

class ValidationService:
    """Service for validating existing installations and configurations"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
    
    async def check_user_exists(self, host: str, username: str, password: str, user_to_check: str) -> Dict[str, Any]:
        """Check if a user exists on the system"""
        try:
            command = f"id {user_to_check}"
            result = await self.ssh_service.execute_command(host, username, password, command)
            
            exists = result.get('success', False) and result.get('returncode') == 0
            
            return {
                "exists": exists,
                "output": result.get('stdout', ''),
                "message": f"User '{user_to_check}' {'exists' if exists else 'does not exist'}"
            }
        except Exception as e:
            logger.error(f"Error checking user existence: {str(e)}")
            return {"exists": False, "error": str(e)}
    
    async def check_group_exists(self, host: str, username: str, password: str, group_name: str) -> Dict[str, Any]:
        """Check if a group exists on the system"""
        try:
            command = f"getent group {group_name}"
            result = await self.ssh_service.execute_command(host, username, password, command)
            
            exists = result.get('success', False) and result.get('returncode') == 0
            
            return {
                "exists": exists,
                "output": result.get('stdout', ''),
                "message": f"Group '{group_name}' {'exists' if exists else 'does not exist'}"
            }
        except Exception as e:
            logger.error(f"Error checking group existence: {str(e)}")
            return {"exists": False, "error": str(e)}
    
    async def check_directory_exists(self, host: str, username: str, password: str, path: str) -> Dict[str, Any]:
        """Check if a directory exists"""
        try:
            command = f"test -d {path} && echo 'EXISTS' || echo 'NOT_EXISTS'"
            result = await self.ssh_service.execute_command(host, username, password, command)
            
            exists = 'EXISTS' in result.get('stdout', '')
            
            return {
                "exists": exists,
                "path": path,
                "message": f"Directory '{path}' {'exists' if exists else 'does not exist'}"
            }
        except Exception as e:
            logger.error(f"Error checking directory existence: {str(e)}")
            return {"exists": False, "error": str(e)}
    
    async def check_file_exists(self, host: str, username: str, password: str, filepath: str) -> Dict[str, Any]:
        """Check if a file exists"""
        try:
            command = f"test -f {filepath} && echo 'EXISTS' || echo 'NOT_EXISTS'"
            result = await self.ssh_service.execute_command(host, username, password, command)
            
            exists = 'EXISTS' in result.get('stdout', '')
            
            return {
                "exists": exists,
                "filepath": filepath,
                "message": f"File '{filepath}' {'exists' if exists else 'does not exist'}"
            }
        except Exception as e:
            logger.error(f"Error checking file existence: {str(e)}")
            return {"exists": False, "error": str(e)}
    
    async def check_package_installed(self, host: str, username: str, password: str, package: str) -> Dict[str, Any]:
        """Check if a package is installed"""
        try:
            # Try multiple methods
            commands = [
                f"which {package}",
                f"rpm -qa | grep -i {package}",
                f"command -v {package}"
            ]
            
            for command in commands:
                result = await self.ssh_service.execute_command(host, username, password, command)
                if result.get('success') and result.get('stdout'):
                    return {
                        "installed": True,
                        "path": result.get('stdout', '').strip(),
                        "message": f"✓ {package} already installed at {result.get('stdout', '').strip()}"
                    }
            
            return {
                "installed": False,
                "message": f"{package} is not installed"
            }
            
        except Exception as e:
            logger.error(f"Error checking package installation: {str(e)}")
            return {"installed": False, "error": str(e)}
    
    async def get_package_version(self, host: str, username: str, password: str, package: str, version_command: str = None) -> Dict[str, Any]:
        """Get installed package version"""
        try:
            if not version_command:
                version_command = f"{package} --version"
            
            result = await self.ssh_service.execute_command(host, username, password, version_command)
            
            if result.get('success'):
                version = result.get('stdout', '').strip()
                return {
                    "success": True,
                    "version": version,
                    "message": f"✓ {package} version: {version}"
                }
            
            return {
                "success": False,
                "message": f"Could not determine {package} version"
            }
            
        except Exception as e:
            logger.error(f"Error getting package version: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def find_oracle_client(self, host: str, username: str, password: str) -> Optional[str]:
        """
        Auto-detect Oracle Client installation path
        
        Returns:
            Oracle Client home path if found, None otherwise
        """
        try:
            # Common Oracle Client locations
            search_paths = [
                "/u01/app/oracle/product/*/client_1",
                "/opt/oracle/product/*/client_*",
                "/u01/oracle/product/*/client_*",
                "/home/oracle/product/*/client_*"
            ]
            
            for search_path in search_paths:
                command = f"ls -d {search_path} 2>/dev/null | head -1"
                result = await self.ssh_service.execute_command(host, username, password, command)
                
                if result.get('success') and result.get('stdout'):
                    oracle_home = result.get('stdout', '').strip()
                    
                    # Verify sqlplus exists
                    sqlplus_check = await self.ssh_service.execute_command(
                        host, username, password, 
                        f"test -f {oracle_home}/bin/sqlplus && echo 'FOUND'"
                    )
                    
                    if 'FOUND' in sqlplus_check.get('stdout', ''):
                        logger.info(f"✓ Oracle Client found at: {oracle_home}")
                        return oracle_home
            
            logger.warning("Oracle Client not found in common locations")
            return None
            
        except Exception as e:
            logger.error(f"Error finding Oracle Client: {str(e)}")
            return None
    
    async def find_java_installation(self, host: str, username: str, password: str) -> Optional[str]:
        """
        Auto-detect Java installation path
        
        Returns:
            JAVA_HOME path if found, None otherwise
        """
        try:
            # Try to find Java in common locations
            search_commands = [
                "ls -d /u01/jdk* 2>/dev/null | head -1",
                "ls -d /usr/lib/jvm/java-11* 2>/dev/null | head -1",
                "ls -d /opt/jdk* 2>/dev/null | head -1"
            ]
            
            for command in search_commands:
                result = await self.ssh_service.execute_command(host, username, password, command)
                
                if result.get('success') and result.get('stdout'):
                    java_home = result.get('stdout', '').strip()
                    
                    # Verify java binary exists
                    java_check = await self.ssh_service.execute_command(
                        host, username, password,
                        f"test -f {java_home}/bin/java && echo 'FOUND'"
                    )
                    
                    if 'FOUND' in java_check.get('stdout', ''):
                        logger.info(f"✓ Java found at: {java_home}")
                        return java_home
            
            logger.warning("Java installation not found in common locations")
            return None
            
        except Exception as e:
            logger.error(f"Error finding Java: {str(e)}")
            return None
    
    async def backup_file(self, host: str, username: str, password: str, filepath: str) -> Dict[str, Any]:
        """Create a timestamped backup of a file"""
        try:
            command = f"cp {filepath} {filepath}.backup.$(date +%Y%m%d_%H%M%S)"
            result = await self.ssh_service.execute_command(host, username, password, command)
            
            if result.get('success'):
                return {
                    "success": True,
                    "message": f"✓ Backed up {filepath}",
                    "backup_created": True
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to backup {filepath}",
                    "error": result.get('stderr', '')
                }
                
        except Exception as e:
            logger.error(f"Error backing up file: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def download_from_git(
        self, 
        host: str, 
        username: str, 
        password: str,
        repo_url: str,
        file_name: str,
        dest_path: str
    ) -> Dict[str, Any]:
        """Download a file from Git repository"""
        try:
            # Construct raw file URL (works for most Git platforms)
            if 'github.com' in repo_url:
                raw_url = repo_url.replace('github.com', 'raw.githubusercontent.com').replace('/tree/', '/')
            else:
                # For custom Git servers, use raw endpoint
                raw_url = f"{repo_url}/raw/master/{file_name}"
            
            # Download using wget or curl
            commands = [
                f"cd {dest_path} && wget --no-check-certificate -q {raw_url}/{file_name}",
                f"cd {dest_path} && curl -k -L -O {raw_url}/{file_name}"
            ]
            
            for command in commands:
                result = await self.ssh_service.execute_command(host, username, password, command, timeout=300)
                
                # Check if file was downloaded
                check_result = await self.check_file_exists(host, username, password, f"{dest_path}/{file_name}")
                
                if check_result.get('exists'):
                    return {
                        "success": True,
                        "message": f"✓ Downloaded {file_name} to {dest_path}",
                        "filepath": f"{dest_path}/{file_name}"
                    }
            
            return {
                "success": False,
                "message": f"Failed to download {file_name}",
                "error": "All download attempts failed"
            }
            
        except Exception as e:
            logger.error(f"Error downloading from Git: {str(e)}")
            return {"success": False, "error": str(e)}
