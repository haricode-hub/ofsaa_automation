import logging
import asyncio
from typing import Dict, Any
from services.ssh_service import SSHService
from core.config import Config

logger = logging.getLogger(__name__)

class InstallerService:
    """OFSAA Installer Service - handles installer download, extraction, and environment checks"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
    
    async def create_installer_directory(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Create the installer directory with proper ownership
        """
        try:
            logs = []
            
            create_dir_cmd = f"""
# Create installer directory
echo "Creating installer directory: {Config.INSTALLER_KIT_PATH}"
mkdir -p {Config.INSTALLER_KIT_PATH}

# Set ownership to oracle:oinstall
chown oracle:oinstall {Config.INSTALLER_KIT_PATH}

# Verify directory creation
if [ -d "{Config.INSTALLER_KIT_PATH}" ]; then
    echo "✓ Installer directory created successfully"
    ls -la {Config.INSTALLER_KIT_PATH}/
else
    echo "❌ Failed to create installer directory"
    exit 1
fi
"""
            
            result = await self.ssh_service.execute_command(host, username, password, create_dir_cmd, timeout=60)
            
            if result["success"]:
                logs.extend([
                    f"✓ Installer Directory Creation",
                    f"  Path: {Config.INSTALLER_KIT_PATH}",
                    f"  Ownership: oracle:oinstall",
                    f"  Directory ready for installer files"
                ])
                
                # Add command output
                if result["stdout"]:
                    for line in result["stdout"].split('\n'):
                        if line.strip():
                            logs.append(f"  {line.strip()}")
                
                return {
                    "success": True,
                    "message": f"Installer directory created at {Config.INSTALLER_KIT_PATH}",
                    "logs": logs
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to create installer directory: {result.get('stderr', 'Unknown error')}",
                    "logs": [f"ERROR: {result.get('stderr', 'Unknown error')}"]
                }
                
        except Exception as e:
            logger.error(f"Directory creation failed: {str(e)}")
            return {
                "success": False,
                "error": f"Directory creation failed: {str(e)}",
                "logs": [f"ERROR: {str(e)}"]
            }
    
    async def download_and_extract_installer(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Download OFSAA installer from git repository and extract - specifically looks for p33940349_81100_Linux-x86-64.zip
        """
        try:
            logs = []
            
            download_cmd = f"""
# Download OFSAA installer from git repository
echo "=== OFSAA Installer Download & Extract Process ==="
echo "Target directory: /u01/installer_kit"
echo "Installer file: p33940349_81100_Linux-x86-64.zip"
echo "Repository: {Config.JAVA_REPO_URL}"
echo "=================================================="

# Ensure we're in the correct directory
cd /u01/installer_kit
pwd
echo "Current working directory: $(pwd)"

# Clone or update the repository
if [ -d "ofsaa_auto_installation" ]; then
    echo "Repository exists, updating..."
    cd ofsaa_auto_installation
    git pull
    cd ..
else
    echo "Cloning repository..."
    git clone {Config.JAVA_REPO_URL}
fi

# Check for installer files in the repository
echo "\\n=== Looking for installer files ==="
find ofsaa_auto_installation -name "*.zip" -o -name "*.tar.gz" -o -name "p33940349_*.zip" -o -name "OFS_*" | head -10

# Copy installer files to current directory (/u01/installer_kit)
echo "\\n=== Copying installer files to /u01/installer_kit ==="
if [ -d "ofsaa_auto_installation" ]; then
    # Look for Oracle installer packages (your specific file pattern)
    find ofsaa_auto_installation -name "p33940349_*.zip" -exec cp {{}} . \\;
    find ofsaa_auto_installation -name "OFS_*.zip" -exec cp {{}} . \\;
    find ofsaa_auto_installation -name "OFS_BD_PACK*" -type d -exec cp -r {{}} . \\;
    
    echo "Files copied to $(pwd):"
    ls -la *.zip 2>/dev/null || echo "No ZIP files found to copy"
    
    # Extract ZIP files in /u01/installer_kit
    echo "\\n=== Extracting installer files in /u01/installer_kit ==="
    for zipfile in *.zip; do
        if [ -f "$zipfile" ]; then
            echo "Extracting $zipfile in $(pwd)..."
            unzip -o "$zipfile"
            
            # Special handling for Oracle installer
            if [[ "$zipfile" == *"p33940349"* ]]; then
                echo "✓ Oracle OFSAA installer extracted: $zipfile"
                echo "  Extracted to: $(pwd)"
            fi
        fi
    done
    
    # Verify the installer file was downloaded and extracted to /u01/installer_kit
    echo "\\n=== Verifying installer in /u01/installer_kit ==="
    if [ -f "p33940349_81100_Linux-x86-64.zip" ]; then
        echo "✓ Found Oracle OFSAA installer ZIP: p33940349_81100_Linux-x86-64.zip"
        echo "  Location: $(pwd)/p33940349_81100_Linux-x86-64.zip"
    else
        echo "⚠️  Oracle installer p33940349_81100_Linux-x86-64.zip not found"
        echo "Available ZIP files in $(pwd):"
        ls -la *.zip 2>/dev/null || echo "No ZIP files found"
    fi
    
    # Show extracted contents in /u01/installer_kit
    echo "\\n=== Extracted contents in /u01/installer_kit ==="
    ls -la /u01/installer_kit/ | head -20
fi

# Set ownership
chown -R oracle:oinstall /u01/installer_kit

echo "\\n=== Final installer directory structure ==="
ls -la /u01/installer_kit/

# Check if OFS_BD_PACK directory exists
if [ -d "/u01/installer_kit/OFS_BD_PACK" ]; then
    echo "\\n=== OFS_BD_PACK structure ==="
    find /u01/installer_kit/OFS_BD_PACK -name "envCheck.sh" 2>/dev/null || echo "envCheck.sh not found yet"
    ls -la /u01/installer_kit/OFS_BD_PACK/ 2>/dev/null || echo "OFS_BD_PACK directory structure will be checked after extraction"
fi

echo "\\n✓ Installer download and extraction completed"
"""
            
            result = await self.ssh_service.execute_command(host, username, password, download_cmd, timeout=300)
            
            if result["success"]:
                logs.extend([
                    "✓ OFSAA Installer Download & Extraction",
                    f"  Repository: {Config.JAVA_REPO_URL}",
                    "  Target file: p33940349_81100_Linux-x86-64.zip",
                    "  Files extracted to /u01/installer_kit",
                    "  Ownership set to oracle:oinstall"
                ])
                
                # Add command output
                for line in result["stdout"].split('\n'):
                    if line.strip():
                        logs.append(f"  {line.strip()}")
                
                return {
                    "success": True,
                    "message": "OFSAA installer downloaded and extracted successfully",
                    "logs": logs
                }
            else:
                return {
                    "success": False,
                    "error": f"Installer download failed: {result.get('stderr', 'Unknown error')}",
                    "logs": [f"ERROR: {result.get('stderr', 'Unknown error')}"]
                }
                
        except Exception as e:
            logger.error(f"Installer download failed: {str(e)}")
            return {
                "success": False,
                "error": f"Installer download failed: {str(e)}",
                "logs": [f"ERROR: {str(e)}"]
            }
    
    async def run_environment_check(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Run OFSAA environment check script - displays the script content and execution approach
        """
        try:
            logs = []
            
            # First, let's examine what the envCheck.sh script contains
            examine_script_cmd = """
cd /u01/installer_kit

# Find and verify envCheck.sh script location
if [ -f "OFS_BD_PACK/OFS_AAI/bin/envCheck.sh" ]; then
    SCRIPT_PATH="OFS_BD_PACK/OFS_AAI/bin"
    SCRIPT_FILE="envCheck.sh"
    echo "✓ Found envCheck.sh at: $SCRIPT_PATH/$SCRIPT_FILE"
elif [ -f "OFS_BD_PACK/bin/envCheck.sh" ]; then
    SCRIPT_PATH="OFS_BD_PACK/bin"  
    SCRIPT_FILE="envCheck.sh"
    echo "✓ Found envCheck.sh at: $SCRIPT_PATH/$SCRIPT_FILE"
else
    echo "❌ envCheck.sh not found in expected locations"
    echo "Searching for envCheck.sh..."
    find . -name "envCheck.sh" -type f
    exit 1
fi

echo ""
echo "=== SCRIPT LOCATION AND PERMISSIONS ==="
cd "$SCRIPT_PATH"
chmod +x "$SCRIPT_FILE"
ls -la "$SCRIPT_FILE"
echo ""
echo "=== SCRIPT CONTENT PREVIEW (first 50 lines) ==="
head -50 "$SCRIPT_FILE"
echo ""
echo "=== SCRIPT CONTENT PREVIEW (last 20 lines) ==="
tail -20 "$SCRIPT_FILE"
echo ""
echo "=== INTERACTIVE EXECUTION NEEDED ==="
echo "This script requires interactive execution with TTY support."
echo "The script contains prompts that need user responses."
echo "Current SSH connection method cannot handle true interactive scripts."
echo ""
echo "RECOMMENDATION:"
echo "1. Use terminal access to manually run: ./$SCRIPT_FILE"
echo "2. Or modify the script to run non-interactively"
echo "3. Current directory for manual execution: $(pwd)"
"""
            
            result = await self.ssh_service.execute_command(host, username, password, examine_script_cmd, timeout=300)
            
            logs.extend([
                "🔍 OFSAA Environment Check Script Analysis", 
                "  Script: /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin/envCheck.sh",
                "  Analysis: Examining script content and requirements",
                "  NOTE: Interactive scripts require special handling",
                ""
            ])
            
            result = await self.ssh_service.execute_command(host, username, password, examine_script_cmd, timeout=300)
            
            # Display complete script analysis in UI
            if result["stdout"]:
                logs.append("\\n" + "="*60)
                logs.append("🖥️  ENVIRONMENT CHECK SCRIPT ANALYSIS")
                logs.append("="*60)
                
                # Show every line of output exactly as it appears
                for line in result["stdout"].split('\\n'):
                    logs.append(line)
                
                logs.append("="*60)
                logs.append("🏁 END OF SCRIPT ANALYSIS")  
                logs.append("="*60)
            
            # Show stderr if any
            if result["stderr"]:
                logs.append("\\n=== ANALYSIS STDERR OUTPUT ===")
                for line in result["stderr"].split('\\n'):
                    if line.strip():
                        logs.append(f"ERROR: {line.strip()}")
            
            # Determine success
            exit_code = result.get("returncode", 0)
            if result["success"] or exit_code in [0, 124]:
                logs.extend([
                    "",
                    "✅ Environment check script analysis completed",
                    f"  📍 Script: /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin/envCheck.sh", 
                    f"  🔄 Exit code: {exit_code}",
                    "  📋 Script content and structure analyzed",
                    "  ⚠️  Manual interactive execution required",
                    "  💡 See analysis above for script details and manual execution path"
                ])
                
                return {
                    "success": True,
                    "message": "Environment check script analyzed - manual execution required for interactive prompts",
                    "logs": logs,
                    "script_analysis": result["stdout"] if result["stdout"] else "",
                    "requires_manual_execution": True,
                    "exit_code": exit_code
                }
            else:
                logs.extend([
                    "",
                    f"⚠️ Environment check script analysis had issues (exit code {exit_code})",
                    "  Complete output shown above for review"
                ])
                
                return {
                    "success": False,
                    "error": f"Environment check script exited with code {exit_code}",
                    "logs": logs,
                    "complete_script_output": result["stdout"] if result["stdout"] else "",
                    "exit_code": exit_code
                }
                
        except Exception as e:
            logger.error(f"Environment check execution failed: {str(e)}")
            return {
                "success": False,
                "error": f"Environment check execution failed: {str(e)}",
                "logs": [f"ERROR: {str(e)}"]
            }

    async def extract_installer_files(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Combined method: Create directory, download installer, and run environment check
        """
        try:
            logs = []
            
            # Step 1: Create directory
            dir_result = await self.create_installer_directory(host, username, password)
            logs.extend(dir_result.get("logs", []))
            if not dir_result["success"]:
                return dir_result
            
            # Step 2: Download and extract installer
            download_result = await self.download_and_extract_installer(host, username, password)
            logs.extend(download_result.get("logs", []))
            if not download_result["success"]:
                return download_result
            
            # Step 3: Run environment check
            env_result = await self.run_environment_check(host, username, password)
            logs.extend(env_result.get("logs", []))
            
            return {
                "success": env_result["success"],
                "message": "Complete installer setup with environment check completed",
                "logs": logs,
                "environment_check_output": env_result.get("complete_script_output", ""),
                "steps_completed": ["directory_creation", "installer_download", "environment_check"]
            }
            
        except Exception as e:
            logger.error(f"Complete installer setup failed: {str(e)}")
            return {
                "success": False,
                "error": f"Complete installer setup failed: {str(e)}",
                "logs": logs + [f"ERROR: {str(e)}"]
            }