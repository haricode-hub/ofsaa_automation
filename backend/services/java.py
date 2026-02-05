import logging
from typing import Dict, Any
from services.ssh_service import SSHService

logger = logging.getLogger(__name__)

class JavaInstallationService:
    """Service for Java installation - Step 5"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
    
    async def install_java_from_oracle_kit(self, host: str, username: str, password: str, java_home: str = "/u01/jdk-11.0.16") -> Dict[str, Any]:
        """
        Install Java from Oracle installer kit and configure environment
        """
        try:
            logs = []
            
            # Install Java from installer kit
            java_install_cmd = f'''
# Extract and install Java from kit
cd /u01/installer_kit
if ls jdk-11.0.*.tar.gz 1> /dev/null 2>&1; then
    JAVA_FILE=$(ls jdk-11.0.*.tar.gz | head -1)
    echo "Found Java archive: $JAVA_FILE"
    
    # Extract to target location
    tar -xzf "$JAVA_FILE" -C /u01/
    
    # Find extracted directory and rename/link to standard path
    EXTRACTED_DIR=$(find /u01/ -maxdepth 1 -type d -name "jdk-11.0.*" | head -1)
    
    if [ -d "$EXTRACTED_DIR" ] && [ "$EXTRACTED_DIR" != "{java_home}" ]; then
        # Create symbolic link or rename
        if [ ! -d "{java_home}" ]; then
            ln -s "$EXTRACTED_DIR" {java_home} || mv "$EXTRACTED_DIR" {java_home}
        fi
    fi
    
    echo "Java installation directory: {java_home}"
    
elif ls jdk-11*.rpm 1> /dev/null 2>&1; then
    echo "Found Java RPM package"
    RPM_FILE=$(ls jdk-11*.rpm | head -1)
    rpm -ivh "$RPM_FILE"
    
    # Find RPM installation path and link to standard location
    RPM_JAVA_HOME=$(rpm -ql $(rpm -qa | grep jdk) | grep "/bin/java$" | head -1 | sed 's|/bin/java||')
    if [ -d "$RPM_JAVA_HOME" ] && [ "$RPM_JAVA_HOME" != "{java_home}" ]; then
        ln -s "$RPM_JAVA_HOME" {java_home}
    fi
    
elif ls *jdk*.zip 1> /dev/null 2>&1; then
    echo "Found Java ZIP archive"
    ZIP_FILE=$(ls *jdk*.zip | head -1)
    unzip -q "$ZIP_FILE" -d /u01/
    
    # Find extracted directory
    EXTRACTED_DIR=$(find /u01/ -maxdepth 1 -type d -name "*jdk*" | head -1)
    if [ -d "$EXTRACTED_DIR" ] && [ "$EXTRACTED_DIR" != "{java_home}" ]; then
        ln -s "$EXTRACTED_DIR" {java_home} || mv "$EXTRACTED_DIR" {java_home}
    fi
    
else
    echo "No Java installation files found in kit"
    echo "Available files:"
    ls -la /u01/installer_kit/
    exit 1
fi

# Verify installation
if [ -d "{java_home}" ]; then
    echo "✓ Java installed at {java_home}"
    {java_home}/bin/java -version 2>&1 | head -3
    
    # Set proper ownership
    chown -R oracle:oinstall {java_home}
    chmod +x {java_home}/bin/*
    
    echo "✓ Java installation completed successfully"
else
    echo "✗ Java installation failed"
    exit 1
fi
'''
            
            result = await self.ssh_service.execute_command(host, username, password, java_install_cmd)
            
            if result["success"]:
                logs.extend([
                    "✓ Java Installation from Oracle Kit",
                    "  Java archive extracted and installed",
                    f"  JAVA_HOME: {java_home}",
                    "  Java binaries configured and tested",
                    "  Ownership set to oracle:oinstall",
                    "  Environment ready for OFSAA installation"
                ])
                
                # Update profile with actual Java path
                profile_update = f'''
sed -i 's|export JAVA_HOME=.*|export JAVA_HOME={java_home}|g' /home/oracle/.profile
sed -i 's|export JAVA_BIN=.*|export JAVA_BIN={java_home}/bin|g' /home/oracle/.profile
echo "Java paths updated in profile"
'''
                
                await self.ssh_service.execute_command(host, username, password, profile_update)
                
                return {
                    "success": True,
                    "message": "Java installed successfully from Oracle installer kit",
                    "logs": logs,
                    "java_home": java_home,
                    "java_version": result.get("stdout", ""),
                    "output": result["stdout"]
                }
            else:
                error_msg = f"Java installation failed: {result.get('stderr', 'Unknown error')}"
                logs.append(f"Java installation failed: {error_msg}")
                
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs,
                    "stderr": result.get("stderr", ""),
                    "returncode": result.get("returncode", -1)
                }
                
        except Exception as e:
            logger.error(f"Java installation failed: {str(e)}")
            return {
                "success": False,
                "error": f"Java installation failed: {str(e)}",
                "logs": [f"ERROR: Exception in Java installation: {str(e)}"]
            }
    
    async def create_ofsaa_directories(self, host: str, username: str, password: str, fic_home: str = "/u01/OFSAA/FICHOME") -> Dict[str, Any]:
        """
        Create OFSAA directory structure after Java installation
        """
        try:
            logs = []
            
            # Create OFSAA directory structure
            logs.append("Creating OFSAA directory structure...")
            create_dirs_cmd = f'''
# Create OFSAA directory structure
echo "Creating OFSAA directory structure..."

# Create main OFSAA directories
mkdir -p /u01/OFSAA/FICHOME
mkdir -p /u01/OFSAA/FTPSHARE
mkdir -p /u01/OFSAA/logs
mkdir -p /u01/OFSAA/backup

# Create additional subdirectories for FICHOME
mkdir -p {fic_home}/bin
mkdir -p {fic_home}/conf
mkdir -p {fic_home}/lib
mkdir -p {fic_home}/logs
mkdir -p {fic_home}/temp

# Set proper ownership and permissions
chown -R oracle:oinstall /u01/OFSAA
chmod -R 755 /u01/OFSAA

# Set specific permissions for FTPSHARE
chmod 775 /u01/OFSAA/FTPSHARE

echo "\n=== OFSAA Directory Structure Created ==="
ls -la /u01/OFSAA/
echo "\n=== FICHOME Structure ==="
ls -la {fic_home}/

echo "\n✓ OFSAA directory structure created successfully"
'''
            
            result = await self.ssh_service.execute_command(host, username, password, create_dirs_cmd)
            
            if result["success"]:
                logs.extend([
                    "✓ OFSAA Directory Structure Created",
                    "  /u01/OFSAA/FICHOME (main application directory)",
                    f"    └── {fic_home}/bin (binaries)",
                    f"    └── {fic_home}/conf (configuration)", 
                    f"    └── {fic_home}/lib (libraries)",
                    f"    └── {fic_home}/logs (application logs)",
                    f"    └── {fic_home}/temp (temporary files)",
                    "  /u01/OFSAA/FTPSHARE (FTP share directory)",
                    "  /u01/OFSAA/logs (system logs)",
                    "  /u01/OFSAA/backup (backup directory)",
                    "  Ownership: oracle:oinstall",
                    "  Permissions: 755 (FTPSHARE: 775)"
                ])
                
                # Add command output to logs
                output_lines = result["stdout"].split('\n')
                for line in output_lines:
                    if line.strip():
                        logs.append(f"  {line.strip()}")
                
                return {
                    "success": True,
                    "message": "OFSAA directory structure created successfully",
                    "logs": logs,
                    "directories_created": [
                        "/u01/OFSAA/FICHOME",
                        "/u01/OFSAA/FTPSHARE",
                        "/u01/OFSAA/logs",
                        "/u01/OFSAA/backup",
                        f"{fic_home}/bin",
                        f"{fic_home}/conf",
                        f"{fic_home}/lib",
                        f"{fic_home}/logs",
                        f"{fic_home}/temp"
                    ]
                }
            else:
                error_msg = f"OFSAA directory creation failed: {result.get('stderr', 'Unknown error')}"
                logs.append(f"OFSAA directory creation failed: {error_msg}")
                
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs
                }
                
        except Exception as e:
            logger.error(f"OFSAA directory creation failed: {str(e)}")
            return {
                "success": False,
                "error": f"OFSAA directory creation failed: {str(e)}",
                "logs": [f"ERROR: Exception in OFSAA directory creation: {str(e)}"]
            }