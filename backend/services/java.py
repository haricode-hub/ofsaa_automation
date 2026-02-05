import logging
from typing import Dict, Any
from services.ssh_service import SSHService
from services.validation import ValidationService

logger = logging.getLogger(__name__)

class JavaInstallationService:
    """Service for Java installation - Step 5"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
        self.validation = ValidationService(ssh_service)
    
    async def install_java_from_oracle_kit(self, host: str, username: str, password: str, java_home: str = "/u01/jdk-11.0.16") -> Dict[str, Any]:
        """
        Install Java from Git repository and configure environment
        Enhanced with smart validation and Git download
        """
        try:
            logs = []
            
            # Step 1: Ensure /u01/installer_kit exists
            logs.append("→ Checking /u01/installer_kit directory...")
            installer_kit_check = await self.validation.check_directory_exists(host, username, password, "/u01/installer_kit")
            
            if not installer_kit_check.get('exists'):
                logs.append("Creating /u01/installer_kit directory...")
                mkdir_cmd = "mkdir -p /u01/installer_kit && chown oracle:oinstall /u01/installer_kit && chmod 755 /u01/installer_kit"
                mkdir_result = await self.ssh_service.execute_command(host, username, password, mkdir_cmd)
                if mkdir_result.get('success'):
                    logs.append("✓ /u01/installer_kit directory created")
                else:
                    return {
                        "success": False,
                        "error": "Failed to create /u01/installer_kit directory",
                        "logs": logs
                    }
            else:
                logs.append("✓ /u01/installer_kit directory already exists")
            
            # Step 2: Check if Java is already installed
            logs.append(f"→ Checking for Java at {java_home}...")
            java_check = await self.validation.check_directory_exists(host, username, password, java_home)
            
            if java_check.get('exists'):
                # Verify it's a working Java installation
                verify_cmd = f"test -f {java_home}/bin/java && {java_home}/bin/java -version 2>&1 | head -1"
                verify_result = await self.ssh_service.execute_command(host, username, password, verify_cmd)
                
                if verify_result.get('success') and 'java version' in verify_result.get('stdout', '').lower():
                    logs.append(f"✓ Java already installed at {java_home}")
                    logs.append(f"  Version: {verify_result.get('stdout', '').strip()}")
                    
                    # Update profile with existing Java path
                    profile_update = f'''
sed -i 's|export JAVA_HOME=.*|export JAVA_HOME={java_home}|g' /home/oracle/.profile
sed -i 's|export JAVA_BIN=.*|export JAVA_BIN={java_home}/bin|g' /home/oracle/.profile
'''
                    await self.ssh_service.execute_command(host, username, password, profile_update)
                    logs.append("✓ Profile updated with Java paths")
                    
                    return {
                        "success": True,
                        "message": "Java already installed, skipping download",
                        "logs": logs,
                        "java_home": java_home
                    }
            
            # Step 3: Download Java from Git repository
            logs.append("Java not found, downloading from Git repository...")
            logs.append("Repository: https://infrarepo.jmrinfotech.com:8443/ofsaa_agentic/ofsaa_auto_installation")
            logs.append("File: jdk-11.0.16_linux-x64_bin__1_.tar.gz")
            
            download_cmd = f'''
cd /u01/installer_kit

# Download Java from Git repository using git archive or wget
# Try git clone with sparse checkout for specific file
if command -v git &> /dev/null; then
    echo "Using git to download..."
    
    # Clone repository (shallow clone for speed)
    if [ ! -d "ofsaa_auto_installation" ]; then
        git clone --depth 1 https://infrarepo.jmrinfotech.com:8443/ofsaa_agentic/ofsaa_auto_installation 2>/dev/null || \\
        GIT_SSL_NO_VERIFY=true git clone --depth 1 https://infrarepo.jmrinfotech.com:8443/ofsaa_agentic/ofsaa_auto_installation
    fi
    
    # Copy Java file if found
    if [ -f "ofsaa_auto_installation/jdk-11.0.16_linux-x64_bin__1_.tar.gz" ]; then
        cp ofsaa_auto_installation/jdk-11.0.16_linux-x64_bin__1_.tar.gz .
        echo "✓ Java file copied from repository"
    fi
fi

# Alternative: Try direct download with wget/curl
if [ ! -f "jdk-11.0.16_linux-x64_bin__1_.tar.gz" ]; then
    echo "Trying direct download..."
    
    # Try wget
    if command -v wget &> /dev/null; then
        wget --no-check-certificate https://infrarepo.jmrinfotech.com:8443/ofsaa_agentic/ofsaa_auto_installation/raw/master/jdk-11.0.16_linux-x64_bin__1_.tar.gz || \\
        wget --no-check-certificate https://infrarepo.jmrinfotech.com:8443/ofsaa_agentic/ofsaa_auto_installation/raw/main/jdk-11.0.16_linux-x64_bin__1_.tar.gz
    elif command -v curl &> /dev/null; then
        curl -k -L -O https://infrarepo.jmrinfotech.com:8443/ofsaa_agentic/ofsaa_auto_installation/raw/master/jdk-11.0.16_linux-x64_bin__1_.tar.gz || \\
        curl -k -L -O https://infrarepo.jmrinfotech.com:8443/ofsaa_agentic/ofsaa_auto_installation/raw/main/jdk-11.0.16_linux-x64_bin__1_.tar.gz
    fi
fi

# Verify download
if [ -f "jdk-11.0.16_linux-x64_bin__1_.tar.gz" ]; then
    ls -lh jdk-11.0.16_linux-x64_bin__1_.tar.gz
    echo "✓ Java archive downloaded successfully"
else
    echo "✗ Failed to download Java archive"
    echo "Available files in /u01/installer_kit:"
    ls -la
    exit 1
fi
'''
            
            download_result = await self.ssh_service.execute_command(host, username, password, download_cmd, timeout=600)
            
            if not download_result.get('success'):
                logs.append(f"Failed to download Java: {download_result.get('stderr', '')}")
                return {
                    "success": False,
                    "error": "Failed to download Java from Git repository",
                    "logs": logs,
                    "stderr": download_result.get('stderr', '')
                }
            
            logs.append("✓ Java archive downloaded successfully")
            
            # Step 4: Extract and install Java
            logs.append("✓ Java archive downloaded successfully")
            
            # Step 4: Extract and install Java
            logs.append("Extracting Java archive...")
            java_install_cmd = f'''
cd /u01/installer_kit

# Extract Java archive
echo "Extracting jdk-11.0.16_linux-x64_bin__1_.tar.gz..."
tar -xzf jdk-11.0.16_linux-x64_bin__1_.tar.gz -C /u01/

# Find extracted directory
EXTRACTED_DIR=$(find /u01/ -maxdepth 1 -type d -name "jdk-11.0.*" -o -name "jdk1.11.*" | head -1)

if [ -n "$EXTRACTED_DIR" ]; then
    echo "Found extracted directory: $EXTRACTED_DIR"
    
    # If extracted dir is not the target java_home, create link or rename
    if [ "$EXTRACTED_DIR" != "{java_home}" ]; then
        if [ ! -d "{java_home}" ]; then
            mv "$EXTRACTED_DIR" {java_home} 2>/dev/null || ln -s "$EXTRACTED_DIR" {java_home}
        fi
    fi
fi

# Verify installation
if [ -d "{java_home}" ] && [ -f "{java_home}/bin/java" ]; then
    echo "✓ Java installed at {java_home}"
    {java_home}/bin/java -version 2>&1 | head -3
    
    # Set proper ownership
    chown -R oracle:oinstall {java_home}
    chmod +x {java_home}/bin/*
    
    echo "✓ Java installation completed successfully"
else
    echo "✗ Java installation failed - directory or binary not found"
    ls -la /u01/ | grep jdk
    exit 1
fi
'''
            
            install_result = await self.ssh_service.execute_command(host, username, password, java_install_cmd, timeout=300)
            
            if not install_result.get('success'):
                logs.append(f"Java extraction failed: {install_result.get('stderr', '')}")
                return {
                    "success": False,
                    "error": "Failed to extract and install Java",
                    "logs": logs,
                    "stderr": install_result.get('stderr', '')
                }
            
            logs.append("✓ Java extracted and installed")
            
            # Step 5: Update profile with Java paths
            logs.append("Updating .profile with Java paths...")
            profile_update = f'''
sed -i 's|export JAVA_HOME=.*|export JAVA_HOME={java_home}|g' /home/oracle/.profile
sed -i 's|export JAVA_BIN=.*|export JAVA_BIN={java_home}/bin|g' /home/oracle/.profile

# Verify updates
echo "Profile updated:"
grep -E "(JAVA_HOME|JAVA_BIN)" /home/oracle/.profile
'''
            
            profile_result = await self.ssh_service.execute_command(host, username, password, profile_update)
            
            if profile_result.get('success'):
                logs.append("✓ Profile updated with Java paths")
                logs.append(f"  JAVA_HOME={java_home}")
                logs.append(f"  JAVA_BIN={java_home}/bin")
            
            logs.append("✓ Java Installation Complete")
            
            return {
                "success": True,
                "message": "Java installed successfully from Git repository",
                "logs": logs,
                "java_home": java_home,
                "output": install_result.get("stdout", "")
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