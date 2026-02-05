import logging
import asyncio
from typing import Dict, Any
from services.ssh_service import SSHService

logger = logging.getLogger(__name__)

class OracleClientService:
    """Service for Oracle Client installation via Terraform - Step 6"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
    
    async def check_existing_oracle_client_and_update_profile(self, host: str, username: str, password: str, oracle_sid: str = "ORCL") -> Dict[str, Any]:
        """
        Check for existing Oracle Client installation and update profile with environment variables
        """
        try:
            logs = []
            
            # Step 1: Check for existing Oracle installations
            logs.append("Checking for existing Oracle client installations...")
            check_oracle_cmd = '''
# Check common Oracle installation locations
echo "=== Checking for Oracle installations ==="

# Common Oracle installation paths
ORACLE_PATHS=(
    "/u01/app/oracle/product/*/client*"
    "/opt/oracle/*/client*" 
    "/home/oracle/*/client*"
    "/usr/lib/oracle/*/client*"
    "/oracle/*/client*"
)

FOUND_INSTALLATIONS=()

for path in "${ORACLE_PATHS[@]}"; do
    if [ -d "$path" ] 2>/dev/null; then
        for dir in $path; do
            if [ -d "$dir" ]; then
                FOUND_INSTALLATIONS+=("$dir")
                echo "Found Oracle installation: $dir"
            fi
        done
    fi
done

# Also check for oracle binary in PATH
if command -v oracle >/dev/null 2>&1; then
    oracle_path=$(which oracle)
    echo "Oracle binary found in PATH: $oracle_path"
fi

# Check for sqlplus
if command -v sqlplus >/dev/null 2>&1; then
    sqlplus_path=$(which sqlplus)
    echo "SQL*Plus found: $sqlplus_path"
    # Try to determine ORACLE_HOME from sqlplus location
    if [[ "$sqlplus_path" == */bin/sqlplus ]]; then
        potential_home="${sqlplus_path%/bin/sqlplus}"
        echo "Potential ORACLE_HOME from sqlplus: $potential_home"
        FOUND_INSTALLATIONS+=("$potential_home")
    fi
fi

# Check for existing ORACLE_HOME in environment or profiles
echo ""
echo "=== Checking existing environment variables ==="
if [ -n "$ORACLE_HOME" ]; then
    echo "Current ORACLE_HOME: $ORACLE_HOME"
    FOUND_INSTALLATIONS+=("$ORACLE_HOME")
fi

# Check oracle user's profile
if [ -f "/home/oracle/.profile" ]; then
    echo "Checking /home/oracle/.profile for Oracle settings..."
    grep -E "ORACLE_HOME|TNS_ADMIN|ORACLE_SID" /home/oracle/.profile || echo "No Oracle settings in profile"
fi

# Check bash profile
if [ -f "/home/oracle/.bash_profile" ]; then
    echo "Checking /home/oracle/.bash_profile for Oracle settings..."
    grep -E "ORACLE_HOME|TNS_ADMIN|ORACLE_SID" /home/oracle/.bash_profile || echo "No Oracle settings in bash profile"
fi

# Final summary
echo ""
echo "=== Summary of Oracle installations ==="
if [ ${#FOUND_INSTALLATIONS[@]} -eq 0 ]; then
    echo "No Oracle installations found"
    exit 1
else
    echo "Found ${#FOUND_INSTALLATIONS[@]} Oracle installation(s):"
    for install in "${!FOUND_INSTALLATIONS[@]}"; do
        echo "  $((install+1)). ${FOUND_INSTALLATIONS[$install]}"
    done
    
    # Use the first found installation as default
    DEFAULT_ORACLE_HOME="${FOUND_INSTALLATIONS[0]}"
    echo ""
    echo "Using ORACLE_HOME: $DEFAULT_ORACLE_HOME"
    
    # Verify it's a valid Oracle installation
    if [ -f "$DEFAULT_ORACLE_HOME/bin/sqlplus" ]; then
        echo "✓ Valid Oracle installation - sqlplus found"
    elif [ -f "$DEFAULT_ORACLE_HOME/bin/oracle" ]; then
        echo "✓ Valid Oracle installation - oracle binary found"
    else
        echo "⚠ Warning: No Oracle binaries found in $DEFAULT_ORACLE_HOME/bin/"
    fi
    
    # Output the selected installation for parsing
    echo "SELECTED_ORACLE_HOME=$DEFAULT_ORACLE_HOME"
fi
'''
            
            check_result = await self.ssh_service.execute_command(host, username, password, check_oracle_cmd)
            
            if not check_result["success"]:
                logs.append("❌ No existing Oracle client installations found")
                return {
                    "success": False,
                    "error": "No existing Oracle client installations found. Please install Oracle client first.",
                    "logs": logs
                }
            
            stdout = check_result.get("stdout", "")
            logs.append("Oracle installation check completed:")
            for line in stdout.split('\n'):
                if line.strip():
                    logs.append(f"  {line.strip()}")
            
            # Extract the selected ORACLE_HOME
            oracle_home = None
            for line in stdout.split('\n'):
                if line.startswith('SELECTED_ORACLE_HOME='):
                    oracle_home = line.split('=', 1)[1].strip()
                    break
            
            if not oracle_home:
                logs.append("❌ Could not determine ORACLE_HOME from existing installation")
                return {
                    "success": False,
                    "error": "Could not determine ORACLE_HOME from existing Oracle installation",
                    "logs": logs
                }
            
            logs.append(f"✅ Using ORACLE_HOME: {oracle_home}")
            
            # Step 2: Determine TNS_ADMIN location
            tns_admin = f"{oracle_home}/network/admin"
            logs.append(f"Setting TNS_ADMIN: {tns_admin}")
            
            # Step 3: Verify TNS_ADMIN directory exists, create if needed
            verify_tns_cmd = f'''
echo "Verifying TNS_ADMIN directory: {tns_admin}"
if [ ! -d "{tns_admin}" ]; then
    echo "TNS_ADMIN directory does not exist, creating..."
    sudo mkdir -p "{tns_admin}"
    sudo chown oracle:oinstall "{tns_admin}"
    echo "✓ Created TNS_ADMIN directory: {tns_admin}"
else
    echo "✓ TNS_ADMIN directory already exists: {tns_admin}"
fi

# Check for tnsnames.ora
if [ -f "{tns_admin}/tnsnames.ora" ]; then
    echo "✓ tnsnames.ora found in TNS_ADMIN"
else
    echo "⚠ tnsnames.ora not found in TNS_ADMIN (will need to be created later)"
fi
'''
            
            verify_result = await self.ssh_service.execute_command(host, username, password, verify_tns_cmd)
            if verify_result["success"]:
                logs.extend([f"  {line.strip()}" for line in verify_result["stdout"].split('\n') if line.strip()])
            
            # Step 4: Update .profile with Oracle environment variables (optimized - no backup files)
            logs.append("Updating .profile with Oracle environment variables...")
            profile_update = f'''
# Update Oracle environment variables in .profile (in-place, no backup)
echo "Updating Oracle environment variables in .profile..."

# Create or update profile with Oracle settings atomically
cat > /tmp/oracle_env_temp << 'EOF'
# Oracle Client Environment Variables
export ORACLE_HOME={oracle_home}
export TNS_ADMIN={tns_admin}
export ORACLE_SID={oracle_sid}
export PATH=$ORACLE_HOME/bin:$PATH
export LD_LIBRARY_PATH=$ORACLE_HOME/lib:$LD_LIBRARY_PATH
EOF

# Remove existing Oracle variables and append new ones
if [ -f "/home/oracle/.profile" ]; then
    # Remove old Oracle settings in-place
    sed -i '/^# Oracle Client Environment Variables/,/^export LD_LIBRARY_PATH.*ORACLE_HOME/d' /home/oracle/.profile 2>/dev/null
    sed -i '/^export ORACLE_HOME=/d; /^export TNS_ADMIN=/d; /^export ORACLE_SID=/d' /home/oracle/.profile 2>/dev/null
else
    # Create new profile if it doesn't exist
    touch /home/oracle/.profile
    chown oracle:oinstall /home/oracle/.profile
fi

# Append Oracle environment variables
echo "" >> /home/oracle/.profile
cat /tmp/oracle_env_temp >> /home/oracle/.profile
rm -f /tmp/oracle_env_temp

echo "✓ Oracle environment variables updated in .profile"

# Verify and test Oracle environment
echo "\n=== Oracle Environment Verification ==="
source /home/oracle/.profile 2>/dev/null
echo "ORACLE_HOME: {oracle_home}"
echo "TNS_ADMIN: {tns_admin}"
echo "ORACLE_SID: {oracle_sid}"

# Quick Oracle client validation
if [ -f "{oracle_home}/bin/sqlplus" ]; then
    echo "✓ SQL*Plus found and accessible"
    # Test version without creating temp files
    {oracle_home}/bin/sqlplus -V 2>/dev/null | head -1 || echo "⚠ Version check failed"
else
    echo "⚠ SQL*Plus not found at {oracle_home}/bin/sqlplus"
fi
'''
            
            profile_result = await self.ssh_service.execute_command(host, username, password, profile_update)
            if not profile_result["success"]:
                logs.append("❌ Failed to update .profile with Oracle environment")
                return {
                    "success": False,
                    "error": "Failed to update .profile with Oracle environment variables",
                    "logs": logs
                }
            
            # Add profile update results to logs
            profile_output = profile_result.get("stdout", "")
            logs.append("Profile update completed:")
            for line in profile_output.split('\n'):
                if line.strip():
                    logs.append(f"  {line.strip()}")
            
            # Final summary
            logs.extend([
                "",
                "✅ Oracle Client Environment Setup Complete",
                "=" * 50,
                f"  ORACLE_HOME: {oracle_home}",
                f"  TNS_ADMIN: {tns_admin}",
                f"  ORACLE_SID: {oracle_sid}",
                "  Environment variables added to /home/oracle/.profile",
                "  Oracle client ready for OFSAA installation"
            ])
            
            return {
                "success": True,
                "message": "Oracle client environment configured successfully",
                "logs": logs,
                "oracle_home": oracle_home,
                "tns_admin": tns_admin,
                "oracle_sid": oracle_sid
            }
        
        except Exception as e:
            logger.error(f"Oracle client check and profile update failed: {str(e)}")
            return {
                "success": False,
                "error": f"Oracle client check and profile update failed: {str(e)}",
                "logs": [f"ERROR: Exception in Oracle client check: {str(e)}"]
            }
    
    async def install_oracle_client_and_update_profile(self, host: str, username: str, password: str, oracle_sid: str = "ORCL") -> Dict[str, Any]:
        """
        Install Oracle Client using terraform repository - simplified approach
        """
        try:
            logs = []
            
            # Step 1: Install terraform prerequisites
            logs.append("Installing terraform prerequisites")
            terraform_setup = '''
# Install terraform if not exists - RHEL/CentOS version
if ! command -v terraform &> /dev/null; then
    sudo yum install -y yum-utils
    sudo yum-config-manager --add-repo https://rpm.releases.hashicorp.com/RHEL/hashicorp.repo
    sudo yum -y install terraform
    echo "Terraform installed successfully"
else
    echo "Terraform already installed"
fi
'''
            
            terraform_result = await self.ssh_service.execute_command(host, username, password, terraform_setup)
            if not terraform_result["success"]:
                error_msg = f"Terraform installation failed: {terraform_result.get('stderr', 'Unknown error')}"
                logs.append(f"Terraform setup failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs
                }
            
            logs.append("✓ Terraform prerequisites installed")
            
            # Step 2: Clone Oracle client repository
            logs.append("Cloning Oracle client repository")
            clone_cmd = '''
cd /tmp && rm -rf oracle_db19c_client_oel7-8-9 2>/dev/null
git clone https://infrarepo.jmrinfotech.com:8443/infra_build_tf/oracle_db19c_client_oel7-8-9.git
cd oracle_db19c_client_oel7-8-9
'''
            
            clone_result = await self.ssh_service.execute_command(host, username, password, clone_cmd)
            if not clone_result["success"]:
                error_msg = f"Repository clone failed: {clone_result.get('stderr', 'Unknown error')}"
                logs.append(f"Repository clone failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs
                }
            
            logs.append("✓ Oracle client repository cloned")
            
            # Step 3: Optimize terraform configuration (minimize file operations)
            logs.append("Configuring terraform with optimized settings")
            inspect_and_fix = f'''
cd /tmp/oracle_db19c_client_oel7-8-9

# Quick terraform files check
echo "=== Terraform Configuration Setup ==="
[ -f terraform.tfvars ] && echo "Original terraform.tfvars found" || echo "No original terraform.tfvars"

# Setup SSH keys efficiently (reuse if exists)
if [ ! -f /root/.ssh/id_rsa ]; then
    mkdir -p /root/.ssh
    ssh-keygen -t rsa -f /root/.ssh/id_rsa -N "" -q >/dev/null 2>&1
    echo "✓ SSH key generated"
else
    echo "✓ SSH key already exists"
fi

# Ensure jenkins directory and copy key
mkdir -p /var/lib/jenkins/.ssh
cp /root/.ssh/id_rsa /var/lib/jenkins/.ssh/id_ed25519 2>/dev/null

# Create optimized terraform.tfvars (single write operation)
cat > terraform.tfvars << EOF
target_host_ip = "{host}"
ssh_user = "root"
ssh_password = "{password}"
private_key_path = "/var/lib/jenkins/.ssh/id_ed25519"
oracle_base = "/u01/app/oracle"
oracle_home = "/u01/app/oracle/product/19.0.0/client_1"
oracle_inventory = "/u01/app/oraInventory"
oracle_user = "oracle"
oracle_group = "oinstall"
EOF

echo "✓ Terraform configuration ready"
'''
            
            inspect_result = await self.ssh_service.execute_command(host, username, password, inspect_and_fix)
            if not inspect_result["success"]:
                error_msg = f"Terraform configuration fix failed: {inspect_result.get('stderr', 'Unknown error')}"
                logs.append(f"Terraform config fix failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs
                }
            
            logs.append("✓ Terraform configuration fixed - SSH keys created, terraform.tfvars updated")
            
            # Step 4: Initialize terraform
            logs.append("Initializing terraform")
            terraform_init = '''
cd /tmp/oracle_db19c_client_oel7-8-9
terraform init
'''
            
            init_result = await self.ssh_service.execute_command(host, username, password, terraform_init)
            if not init_result["success"]:
                error_msg = f"Terraform init failed: {init_result.get('stderr', 'Unknown error')}"
                logs.append(f"Terraform init failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs
                }
            
            logs.append("✓ Terraform initialized")
            
            # Step 5: Run terraform apply -auto-approve with better error handling
            logs.append("Running terraform apply -auto-approve")
            terraform_apply = '''
cd /tmp/oracle_db19c_client_oel7-8-9

# First attempt with current configuration
echo "Starting terraform apply..."
terraform apply -auto-approve

# Check if it succeeded
if [ $? -eq 0 ]; then
    echo "✓ Terraform apply completed successfully"
else
    echo "✗ Terraform apply failed, checking for SSH key issues..."
    
    # Check if the error is related to SSH keys
    if terraform apply -auto-approve 2>&1 | grep -q "private_key_path\\|ssh\\|authentication"; then
        echo "Detected SSH authentication issue, attempting workaround..."
        
        # Try to modify terraform configuration to use password auth
        if [ -f variables.tf ]; then
            # Add password authentication variables if they don't exist
            grep -q "ssh_password" variables.tf || echo 'variable "ssh_password" { type = string }' >> variables.tf
            grep -q "use_password_auth" variables.tf || echo 'variable "use_password_auth" { type = bool, default = true }' >> variables.tf
        fi
        
        # Retry terraform apply
        echo "Retrying terraform apply with enhanced configuration..."
        terraform apply -auto-approve
    else
        # If it's not SSH related, show the actual error
        echo "Non-SSH related terraform error detected"
        terraform apply -auto-approve
    fi
fi
'''
            
            apply_result = await self.ssh_service.execute_command(host, username, password, terraform_apply, timeout=3600)
            if not apply_result["success"]:
                # Enhanced error handling for specific issues
                stderr = apply_result.get('stderr', '')
                stdout = apply_result.get('stdout', '')
                
                if 'private_key_path' in stderr or 'ssh' in stderr.lower():
                    error_msg = "SSH authentication failed - private key not found. Please ensure SSH keys are properly configured."
                    logs.append("✗ SSH Authentication Error:")
                    logs.append("  Private key file not found at expected location")
                    logs.append("  Try generating SSH keys manually or use password authentication")
                elif 'connection' in stderr.lower():
                    error_msg = f"Connection failed to target host {host}. Please verify host accessibility and credentials."
                    logs.append("✗ Connection Error:")
                    logs.append(f"  Unable to connect to {host}")
                    logs.append("  Verify host IP, SSH service, and network connectivity")
                else:
                    error_msg = f"Terraform apply failed: {stderr[:500] if stderr else 'Unknown error'}"
                    logs.append(f"✗ Terraform apply failed:")
                    if stdout:
                        for line in stdout.split('\n')[-10:]:  # Show last 10 lines
                            if line.strip():
                                logs.append(f"  {line.strip()}")
                
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs,
                    "stderr": stderr,
                    "stdout": stdout
                }
            
            logs.append("✓ Terraform apply completed successfully")
            
            # Step 7: Update profile with Oracle environment
            logs.append("Updating .profile with Oracle environment")
            oracle_home = "/u01/app/oracle/product/19.0.0/client_1"
            tns_admin = "/u01/app/oracle/product/19.0.0/client_1/network/admin"
            
            # Update the existing profile template with correct Oracle settings
            profile_update = f'''
# Update existing profile with Oracle client settings
sed -i 's|export ORACLE_HOME=.*|export ORACLE_HOME={oracle_home}|g' /home/oracle/.profile
sed -i 's|export TNS_ADMIN=.*|export TNS_ADMIN={tns_admin}|g' /home/oracle/.profile
sed -i 's|export ORACLE_SID=.*|export ORACLE_SID={oracle_sid}|g' /home/oracle/.profile

# Verify profile updates
echo "Updated Oracle environment in .profile:"
grep -E "ORACLE_HOME|TNS_ADMIN|ORACLE_SID" /home/oracle/.profile
'''
            
            profile_result = await self.ssh_service.execute_command(host, username, password, profile_update)
            if not profile_result["success"]:
                logs.append("⚠ Warning: Could not update profile (non-critical)")
            else:
                logs.append("✓ Oracle environment updated in .profile")
            
            # Final summary
            logs.extend([
                "✓ Oracle Client Installation Complete",
                "  Repository cloned from infrarepo.jmrinfotech.com",
                f"  terraform.tfvars edited with target_host_ip: {host}",
                "  terraform apply -auto-approve executed",
                f"  ORACLE_HOME: {oracle_home}",
                f"  TNS_ADMIN: {tns_admin}",
                f"  ORACLE_SID: {oracle_sid}",
                "  Oracle client ready for OFSAA installation"
            ])
            
            return {
                "success": True,
                "message": "Oracle client installed successfully using terraform",
                "logs": logs,
                "oracle_home": oracle_home,
                "tns_admin": tns_admin,
                "oracle_sid": oracle_sid,
                "terraform_output": apply_result.get("stdout", "")
            }
                
        except Exception as e:
            logger.error(f"Oracle client installation failed: {str(e)}")
            return {
                "success": False,
                "error": f"Oracle client installation failed: {str(e)}",
                "logs": [f"ERROR: Exception in Oracle client installation: {str(e)}"]
            }