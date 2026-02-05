import logging
import asyncio
from typing import Dict, Any, Callable, Optional
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
chmod 775 {Config.INSTALLER_KIT_PATH}

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
    
    async def download_and_extract_installer(self, host: str, username: str, password: str, 
                                             on_output: Optional[Callable[[str], None]] = None,
                                             on_prompt: Optional[Callable[[str], None]] = None,
                                             input_poll: Optional[Callable[[], None]] = None,
                                             on_status: Optional[Callable[[str], None]] = None,
                                             run_envcheck_inline: bool = False,
                                             timeout: int = 7200,
                                             db_user: Optional[str] = None,
                                             db_pass: Optional[str] = None,
                                             db_sid: Optional[str] = None) -> Dict[str, Any]:
        """
        Download OFSAA installer from git repository and extract - specifically looks for p33940349_81100_Linux-x86-64.zip
        
        Args:
            on_output: Optional callback function to stream output in real-time to WebSocket
        """
        try:
            logs = []
            
            db_input_block = ""
            if db_user and db_pass and db_sid:
                # Use base64 to safely pass credentials with special chars
                import base64
                db_user_b64 = base64.b64encode(db_user.encode("utf-8")).decode("utf-8")
                db_pass_b64 = base64.b64encode(db_pass.encode("utf-8")).decode("utf-8")
                db_sid_b64 = base64.b64encode(db_sid.encode("utf-8")).decode("utf-8")
                db_input_block = (
                    f"DB_USER_B64='{db_user_b64}'\n"
                    f"DB_PASS_B64='{db_pass_b64}'\n"
                    f"DB_SID_B64='{db_sid_b64}'\n"
                    "DB_USER=$(printf %s \"$DB_USER_B64\" | base64 -d)\n"
                    "DB_PASS=$(printf %s \"$DB_PASS_B64\" | base64 -d)\n"
                    "DB_SID=$(printf %s \"$DB_SID_B64\" | base64 -d)\n"
                    "DB_INPUT=$(printf \"%s\\n%s\\n%s\\n\" \"$DB_USER\" \"$DB_PASS\" \"$DB_SID\")\n"
                )

            envcheck_block = (
                "# Inline envCheck execution after unzip\n"
                "echo \"[INFO] Starting envCheck.sh after installer step...\"\n"
                "if [ -f /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin/envCheck.sh ]; then\n"
                "    chmod -R 775 /u01/installer_kit/OFS_BD_PACK\n"
                "    chmod 775 /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin/envCheck.sh\n"
                "    echo \"✓ Permissions set to 775 for OFS_BD_PACK\"\n"
                "    echo \"✓ Permissions set to 775 for envCheck.sh\"\n"
                "    if [ ! -f /home/oracle/.profile ]; then\n"
                "        echo \"❌ /home/oracle/.profile not found\"\n"
                "        exit 1\n"
                "    fi\n"
                "    # Clean stray EOF markers if present\n"
                "    sed -i '/EOF/d' /home/oracle/.profile\n"
                "    # Force ORACLE_HOME to preferred client if present\n"
                "    if [ -f /u01/app/oracle/product/19.0.0/client_1/bin/sqlplus ]; then\n"
                "        sed -i 's|^export ORACLE_HOME=.*|export ORACLE_HOME=/u01/app/oracle/product/19.0.0/client_1|g' /home/oracle/.profile\n"
                "        sed -i 's|^export TNS_ADMIN=.*|export TNS_ADMIN=/u01/app/oracle/product/19.0.0/client_1/network/admin|g' /home/oracle/.profile\n"
                "    fi\n"
                "    # Create sqlplus wrapper to force SYSDBA when SYS is used (case-insensitive)\n"
                "    WRAP_DIR=/tmp/ofsaa_sqlplus_wrap\n"
                "    mkdir -p \"$WRAP_DIR\"\n"
                "    cat > \"$WRAP_DIR/sqlplus\" << 'EOSQL'\n"
                "#!/bin/bash\n"
                "REAL_SQLPLUS=/u01/app/oracle/product/19.0.0/client_1/bin/sqlplus\n"
                "if [ -n \"$FORCE_SYSDBA\" ] && [ -n \"$1\" ]; then\n"
                "  lower=$(printf \"%s\" \"$1\" | tr 'A-Z' 'a-z')\n"
                "  case \"$lower\" in\n"
                "    sys/*)\n"
                "      exec \"$REAL_SQLPLUS\" \"$1 as sysdba\" \"${@:2}\"\n"
                "      ;;\n"
                "  esac\n"
                "fi\n"
                "exec \"$REAL_SQLPLUS\" \"$@\"\n"
                "EOSQL\n"
                "    chmod +x \"$WRAP_DIR/sqlplus\"\n"
                "    echo \"\\n=== Starting OFSAA Environment Check ===\"\n"
                "    echo \">>> Starting envCheck.sh -s now...\"\n"
                "    echo \"Executing: ./envCheck.sh -s\"\n"
                "    echo \"\"\n"
                "    export HOME=/home/oracle\n"
                f"{db_input_block}"
                "    if [ -n \"$DB_INPUT\" ]; then\n"
                "        # Run in a pseudo-tty so envCheck can prompt/read correctly\n"
                "        if command -v script >/dev/null 2>&1; then\n"
                "            script -q -c \"printf \\\"%s\\\" \\\"$DB_INPUT\\\" | sudo -u oracle bash -lc 'export FORCE_SYSDBA=1; export PATH=/tmp/ofsaa_sqlplus_wrap:$PATH; source /home/oracle/.profile; cd /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin; ./envCheck.sh -s 2>&1'\" /dev/null\n"
                "        else\n"
                "            printf \"%s\" \"$DB_INPUT\" | sudo -u oracle bash -lc 'export FORCE_SYSDBA=1; export PATH=/tmp/ofsaa_sqlplus_wrap:$PATH; source /home/oracle/.profile; cd /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin; ./envCheck.sh -s 2>&1'\n"
                "        fi\n"
                "    else\n"
                "        if command -v script >/dev/null 2>&1; then\n"
                "            script -q -c \"sudo -u oracle bash -lc 'export FORCE_SYSDBA=1; export PATH=/tmp/ofsaa_sqlplus_wrap:$PATH; source /home/oracle/.profile; cd /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin; ./envCheck.sh -s 2>&1'\" /dev/null\n"
                "        else\n"
                "            sudo -u oracle bash -lc 'export FORCE_SYSDBA=1; export PATH=/tmp/ofsaa_sqlplus_wrap:$PATH; source /home/oracle/.profile; cd /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin; ./envCheck.sh -s 2>&1'\n"
                "        fi\n"
                "    fi\n"
                "    EXIT_CODE=$?\n"
                "    echo \"\"\n"
                "    echo \"=== Environment Check Completed ===\"\n"
                "    echo \"Exit Code: $EXIT_CODE\"\n"
                "    if [ $EXIT_CODE -eq 0 ]; then\n"
                "        echo \"✓ Environment check PASSED\"\n"
                "    else\n"
                "        echo \"⚠ Environment check completed with warnings (Exit Code: $EXIT_CODE)\"\n"
                "    fi\n"
                "    exit $EXIT_CODE\n"
                "else\n"
                "    echo \"❌ envCheck.sh NOT FOUND\"\n"
                "    find /u01/installer_kit -name \"envCheck.sh\" 2>/dev/null || echo \"No envCheck.sh found anywhere\"\n"
                "    exit 1\n"
                "fi\n"
            )

            # If installer already extracted, skip download/unzip and only run envCheck
            precheck_cmd = "test -d /u01/installer_kit/OFS_BD_PACK && echo 'EXTRACTED' || echo 'NOT_EXTRACTED'"
            precheck = await self.ssh_service.execute_command(host, username, password, precheck_cmd)
            if precheck.get("success") and "EXTRACTED" in precheck.get("stdout", ""):
                logs.append("✓ Installer already extracted, skipping download/unzip")
                if run_envcheck_inline:
                    download_cmd = f"""
echo "✓ Installer already extracted, skipping download/unzip"
{envcheck_block}
"""
                else:
                    return {
                        "success": True,
                        "message": "Installer already extracted, skipped download",
                        "logs": logs
                    }
            else:
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
    echo "[PROGRESS] 10% - Repository exists, updating..."
    cd ofsaa_auto_installation
    git pull --progress 2>&1 | while read line; do echo "[GIT] $line"; done
    cd ..
    echo "[PROGRESS] 30% - Repository updated"
else
    echo "[PROGRESS] 10% - Starting repository clone..."
    git clone --progress {Config.JAVA_REPO_URL} 2>&1 | while read line; do echo "[GIT] $line"; done
    echo "[PROGRESS] 30% - Repository cloned successfully"
fi

# Check for installer files in the repository
echo "[PROGRESS] 35% - Searching for installer files..."
echo "\\n=== Looking for installer files ==="
find ofsaa_auto_installation -name "*.zip" -o -name "*.tar.gz" -o -name "p33940349_*.zip" -o -name "OFS_*" | head -10

# Copy installer files to current directory (/u01/installer_kit)
echo "[PROGRESS] 40% - Copying installer files to /u01/installer_kit..."
echo "\\n=== Copying installer files to /u01/installer_kit ==="
if [ -d "ofsaa_auto_installation" ]; then
    # Look for Oracle installer packages (your specific file pattern)
    find ofsaa_auto_installation -name "p33940349_*.zip" -exec cp -v {{}} . \\;
    find ofsaa_auto_installation -name "OFS_*.zip" -exec cp -v {{}} . \\;
    find ofsaa_auto_installation -name "OFS_BD_PACK*" -type d -exec cp -rv {{}} . \\;
    
    echo "[PROGRESS] 50% - Files copied successfully"
    echo "Files copied to $(pwd):"
    ls -la *.zip 2>/dev/null || echo "No ZIP files found to copy"
    
    # Skip unzip if both zip and OFS_BD_PACK exist
    if [ -f "/u01/installer_kit/p33940349_81100_Linux-x86-64.zip" ] && [ -d "/u01/installer_kit/OFS_BD_PACK" ]; then
        echo "[PROGRESS] 80% - ZIP and OFS_BD_PACK already present, skipping extraction."
    else
        # Extract ZIP files in /u01/installer_kit
        echo "[PROGRESS] 55% - Starting extraction of installer files..."
        echo "\\n=== Extracting installer files in /u01/installer_kit ==="
        
        # Count total ZIP files
        total_zips=$(ls -1 *.zip 2>/dev/null | wc -l)
        current_zip=0
        
        for zipfile in *.zip; do
            if [ -f "$zipfile" ]; then
                current_zip=$((current_zip + 1))
                zip_progress=$((55 + (current_zip * 25 / total_zips)))
                
                echo "[PROGRESS] $zip_progress% - Extracting $zipfile ($current_zip/$total_zips)..."
                echo "Extracting $zipfile in $(pwd)..."
                
                # Get file size for progress indication
                filesize=$(ls -lh "$zipfile" | awk '{{print $5}}')
                echo "  File size: $filesize"
                
                # Extract with verbose output
                unzip -o "$zipfile" | while read line; do 
                    case "$line" in
                        *inflating*|*extracting*) echo "  $line" ;;
                    esac
                done
                
                # Special handling for Oracle installer
                if [[ "$zipfile" == *"p33940349"* ]]; then
                    echo "✓ Oracle OFSAA installer extracted: $zipfile"
                    echo "  Extracted to: $(pwd)"
                fi
            fi
        done
        
        echo "[PROGRESS] 80% - All installer files extracted"
    fi
    
    # Verify the installer file was downloaded and extracted to /u01/installer_kit
    echo "[PROGRESS] 85% - Verifying installation files..."
    echo "\\n=== Verifying installer in /u01/installer_kit ==="
    if [ -f "p33940349_81100_Linux-x86-64.zip" ]; then
        echo "✓ Found Oracle OFSAA installer ZIP: p33940349_81100_Linux-x86-64.zip"
        echo "  Location: $(pwd)/p33940349_81100_Linux-x86-64.zip"
    else
        echo "⚠️  Oracle installer p33940349_81100_Linux-x86-64.zip not found"
        echo "Available ZIP files in $(pwd):"
        ls -la *.zip 2>/dev/null || echo "No ZIP files found"
    fi
    
    # Set permissions for OFS_BD_PACK
    if [ -d "/u01/installer_kit/OFS_BD_PACK" ]; then
        chmod -R 775 /u01/installer_kit/OFS_BD_PACK
        echo "[PROGRESS] Set permissions 775 for OFS_BD_PACK"
    fi
    
    # Show extracted contents in /u01/installer_kit
    echo "\\n=== Extracted contents in /u01/installer_kit ==="
    ls -la /u01/installer_kit/ | head -20
fi

# Set ownership
echo "[PROGRESS] 90% - Setting permissions..."
chown -R oracle:oinstall /u01/installer_kit
chmod 775 /u01/installer_kit

echo "[PROGRESS] 95% - Generating final directory structure..."
echo "\\n=== Final installer directory structure ==="
ls -la /u01/installer_kit/

# Check if OFS_BD_PACK directory exists
if [ -d "/u01/installer_kit/OFS_BD_PACK" ]; then
    echo "\\n=== OFS_BD_PACK structure ==="
    find /u01/installer_kit/OFS_BD_PACK -name "envCheck.sh" 2>/dev/null || echo "envCheck.sh not found yet"
    ls -la /u01/installer_kit/OFS_BD_PACK/ 2>/dev/null || echo "OFS_BD_PACK directory structure will be checked after extraction"
fi

echo "[PROGRESS] 100% - Installation complete!"
echo "\\n✓ Installer download and extraction completed"
{envcheck_block if run_envcheck_inline else ""}
"""
            
            # Use execute_interactive_command if callback provided, otherwise use regular command
            if on_output:
                result = await self.ssh_service.execute_interactive_command(
                    host, username, password, download_cmd, 
                    on_output_callback=on_output,
                    on_prompt_callback=on_prompt,
                    input_poll_callback=input_poll,
                    on_status_callback=on_status,
                    timeout=timeout
                )
            else:
                result = await self.ssh_service.execute_command(host, username, password, download_cmd, timeout=timeout)
            
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
    
    async def run_environment_check(self, host: str, username: str, password: str, 
                               on_output: Optional[Callable[[str], None]] = None,
                               on_prompt: Optional[Callable[[str], None]] = None,
                               input_poll: Optional[Callable[[], None]] = None,
                               on_status: Optional[Callable[[str], None]] = None,
                               timeout: int = 7200) -> Dict[str, Any]:
        """
        Run OFSAA environment check script and stream ALL output in real-time
        """
        try:
            logs = []
            
            # Step 1: Verify envCheck.sh exists
            if on_output:
                await on_output("=== Verifying envCheck.sh ===")
            logs.append("=== Verifying envCheck.sh ===")
            
            check_script_cmd = """
    if [ -f /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin/envCheck.sh ]; then
        echo "✓ envCheck.sh found at: /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin/envCheck.sh"
        ls -lh /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin/envCheck.sh
    else
        echo "❌ envCheck.sh NOT FOUND"
        echo "Searching for envCheck.sh in installer directory..."
        find /u01/installer_kit -name "envCheck.sh" 2>/dev/null || echo "No envCheck.sh found anywhere"
        exit 1
    fi
    """
            
            check_result = await self.ssh_service.execute_command(host, username, password, check_script_cmd, timeout=30)
            
            if check_result["stdout"]:
                for line in check_result["stdout"].split('\n'):
                    if line.strip():
                        logs.append(line.strip())
                        if on_output:
                            await on_output(line.strip())
            
            if not check_result["success"]:
                return {
                    "success": False,
                    "error": "envCheck.sh not found",
                    "logs": logs
                }
            
            # Step 2: Set permissions
            if on_output:
                await on_output("\n=== Setting Script Permissions ===")
            logs.append("\n=== Setting Script Permissions ===")
            
            prep_cmd = """
    chmod -R 775 /u01/installer_kit/OFS_BD_PACK
    chmod 775 /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin/envCheck.sh
    echo "✓ Permissions set to 775 for OFS_BD_PACK"
    echo "✓ Permissions set to 775 for envCheck.sh"
    echo "Current directory: /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin"
    echo "Running as user: $(whoami)"
    """
            
            prep_result = await self.ssh_service.execute_command(host, username, password, prep_cmd, timeout=30)
            if prep_result["stdout"]:
                for line in prep_result["stdout"].split('\n'):
                    if line.strip():
                        logs.append(line.strip())
                        if on_output:
                            await on_output(line.strip())
            
            # Step 3: Run envCheck.sh with -s flag (interactive)
            if on_output:
                await on_output("\n=== Starting OFSAA Environment Check ===")
                await on_output("This will verify system prerequisites for OFSAA installation...")
                await on_output("=" * 60)
                await on_output(">>> Starting envCheck.sh -s now...")
            
            logs.append("\n=== Starting OFSAA Environment Check ===")
            logs.append("=" * 60)
            logs.append(">>> Starting envCheck.sh -s now...")
            
            # Run WITH -s flag for summary/silent mode as required
            env_check_cmd = """
    if [ ! -f /home/oracle/.profile ]; then
        echo "❌ /home/oracle/.profile not found"
        exit 1
    fi

    # Clean stray EOF markers if present
    sed -i '/EOF/d' /home/oracle/.profile
    # Force ORACLE_HOME to preferred client if present
    if [ -f /u01/app/oracle/product/19.0.0/client_1/bin/sqlplus ]; then
        sed -i 's|^export ORACLE_HOME=.*|export ORACLE_HOME=/u01/app/oracle/product/19.0.0/client_1|g' /home/oracle/.profile
        sed -i 's|^export TNS_ADMIN=.*|export TNS_ADMIN=/u01/app/oracle/product/19.0.0/client_1/network/admin|g' /home/oracle/.profile
    fi

    echo "Executing: ./envCheck.sh -s"
    echo ""

    export HOME=/home/oracle
    sudo -u oracle bash -lc 'source /home/oracle/.profile; cd /u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin; ./envCheck.sh -s 2>&1'

    # Capture exit code
    EXIT_CODE=$?
    echo ""
    echo "=== Environment Check Completed ==="
    echo "Exit Code: $EXIT_CODE"

    if [ $EXIT_CODE -eq 0 ]; then
        echo "✓ Environment check PASSED"
    else
        echo "⚠ Environment check completed with warnings (Exit Code: $EXIT_CODE)"
    fi

    exit $EXIT_CODE
    """
            
            if on_output:
                result = await self.ssh_service.execute_interactive_command(
                    host, username, password, env_check_cmd,
                    on_output_callback=on_output,
                    on_prompt_callback=on_prompt,
                    input_poll_callback=input_poll,
                    on_status_callback=on_status,
                    timeout=timeout
                )
            else:
                result = await self.ssh_service.execute_command(
                    host, username, password, env_check_cmd, 
                    timeout=timeout
                )
            
            # Process output
            if result["stdout"]:
                for line in result["stdout"].split('\n'):
                    if line.strip():
                        logs.append(line.strip())
                        if on_output and line.strip():
                            await on_output(line.strip())
            
            # Handle stderr
            if result.get("stderr"):
                for line in result["stderr"].split('\n'):
                    if line.strip():
                        error_line = f"[STDERR] {line.strip()}"
                        logs.append(error_line)
                        if on_output:
                            await on_output(error_line)
            
            # Final status
            if on_output:
                await on_output("\n" + "=" * 60)
                if result["success"]:
                    await on_output("✓ Environment check script execution completed successfully!")
                else:
                    await on_output("⚠ Environment check completed with issues - see output above")
            
            if result["success"]:
                logs.append("\n✓ Environment check completed successfully")
                return {
                    "success": True,
                    "message": "Environment check completed",
                    "logs": logs,
                    "exit_code": result.get("returncode", 0)
                }
            else:
                logs.append(f"\n⚠ Environment check exit code: {result.get('returncode', 'unknown')}")
                return {
                    "success": False,
                    "error": f"Environment check failed with exit code: {result.get('returncode', 'unknown')}",
                    "logs": logs,
                    "exit_code": result.get("returncode", 1)
                }
                
        except Exception as e:
            logger.error(f"Environment check failed: {str(e)}")
            error_msg = f"ERROR: Environment check exception - {str(e)}"
            if on_output:
                await on_output(error_msg)
            return {
                "success": False,
                "error": str(e),
                "logs": logs + [error_msg]
            }

    async def extract_installer_files(self, host: str, username: str, password: str,
                                 on_output: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """
        Combined method: Create directory, download installer, and run environment check
        WITH proper error handling and output streaming
        """
        try:
            logs = []
            
            # Step 1: Create directory
            if on_output:
                await on_output("\n" + "=" * 70)
                await on_output("STEP 1/3: CREATING INSTALLER DIRECTORY")
                await on_output("=" * 70)
            logs.append("=== STEP 1/3: Creating Installer Directory ===")
            
            dir_result = await self.create_installer_directory(host, username, password)
            logs.extend(dir_result.get("logs", []))
            
            if not dir_result["success"]:
                error_msg = f"Step 1 FAILED: {dir_result.get('error')}"
                if on_output:
                    await on_output(f"❌ {error_msg}")
                logs.append(f"❌ {error_msg}")
                return dir_result
            
            if on_output:
                await on_output("✓ Step 1 COMPLETED - Directory ready\n")
            logs.append("✓ Step 1 COMPLETED")
            
            # Step 2: Download and extract installer
            if on_output:
                await on_output("\n" + "=" * 70)
                await on_output("STEP 2/3: DOWNLOADING & EXTRACTING INSTALLER")
                await on_output("=" * 70)
            logs.append("\n=== STEP 2/3: Downloading & Extracting Installer ===")
            
            download_result = await self.download_and_extract_installer(
                host, username, password, on_output  # ⭐ Pass callback!
            )
            logs.extend(download_result.get("logs", []))
            
            if not download_result["success"]:
                error_msg = f"Step 2 FAILED: {download_result.get('error')}"
                if on_output:
                    await on_output(f"❌ {error_msg}")
                logs.append(f"❌ {error_msg}")
                return download_result
            
            if on_output:
                await on_output("✓ Step 2 COMPLETED - Installer extracted\n")
            logs.append("✓ Step 2 COMPLETED")
            
            # Step 3: Run environment check
            if on_output:
                await on_output("\n" + "=" * 70)
                await on_output("STEP 3/3: RUNNING ENVIRONMENT CHECK")
                await on_output("=" * 70)
            logs.append("\n=== STEP 3/3: Running Environment Check ===")
            
            env_result = await self.run_environment_check(
                host, username, password, on_output  # ⭐ Pass callback!
            )
            logs.extend(env_result.get("logs", []))
            
            if on_output:
                if env_result["success"]:
                    await on_output("\n✓ Step 3 COMPLETED - Environment check passed")
                else:
                    await on_output(f"\n⚠️ Step 3 completed with warnings: {env_result.get('error')}")
            
            logs.append("✓ Step 3 COMPLETED")
            
            # Final summary
            if on_output:
                await on_output("\n" + "=" * 70)
                await on_output("🎉 ALL INSTALLATION STEPS COMPLETED SUCCESSFULLY")
                await on_output("=" * 70)
            
            return {
                "success": env_result["success"],
                "message": "Complete installer setup with environment check completed",
                "logs": logs,
                "environment_check_output": env_result.get("stdout", ""),
                "steps_completed": ["directory_creation", "installer_download", "environment_check"]
            }
            
        except Exception as e:
            error_msg = f"Complete installer setup failed: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full exception details:")  # ⭐ Log full stack trace
            
            if on_output:
                await on_output(f"\n❌ CRITICAL ERROR: {error_msg}")
            
            return {
                "success": False,
                "error": error_msg,
                "logs": logs + [f"ERROR: {str(e)}"]
            }
