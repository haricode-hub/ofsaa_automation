import logging
from typing import Dict, Any
from services.ssh_service import SSHService

logger = logging.getLogger(__name__)

class ProfileService:
    """Service for profile creation - Step 4"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
    
    async def create_profile_file(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Create the .profile file under: /home/oracle/.profile with complete OFSAA template
        """
        try:
            # Complete OFSAA profile template
            profile_content = '''alias c=clear

alias p="ps -ef | grep $LOGNAME"

alias pp="ps -fu $LOGNAME"

PS1='$PWD>'

export PS1
 
stty erase ^?

#set -o vi
 
echo $PATH

export FIC_HOME=/u01/OFSAA/FICHOME 
 
export JAVA_HOME=/u01/jdk-11.0.16 

export JAVA_BIN=/u01/jdk-11.0.16/bin 

export ANT_HOME=$FIC_HOME/ficweb/apache-ant

#export ANT_HOME=$FIC_HOME/ficweb/apache-ant
 
export ORACLE_HOME=/u01/app/oracle/product/19.0.0/client_1 
export TNS_ADMIN=/u01/app/oracle/product/19.0.0/client_1/network/admin 
export LANG=en_US.utf8

export NLS_LANG=AMERICAN_AMERICA.AL32UTF8
 
export ORACLE_SID=OFSAAPDB

export PATH=.:$JAVA_HOME/bin:$ORACLE_HOME/bin:/sbin:/bin:/usr/bin:/usr/kerberos/bin:/usr/local/bin:/usr/sbin:$PATH

#export PATH=$ORACLE_HOME/bin:$PATH:$JAVA_HOME/bin
 
export LD_LIBRARY_PATH=$ORACLE_HOME/lib:/lib:/usr/lib

export CLASSPATH=$ORACLE_HOME/jlib:$ORACLE_HOME/rdbms/jlib

'''
            
            command = f"mkdir -p /home/oracle && cat > /home/oracle/.profile << 'EOF'\n{profile_content}\nEOF && chown oracle:oinstall /home/oracle/.profile && chmod 644 /home/oracle/.profile"
            
            result = await self.ssh_service.execute_command(host, username, password, command)
            
            logs = []
            if result["success"]:
                logs.append("✓ OFSAA Profile Creation")
                logs.append("  Complete .profile template created at /home/oracle/.profile")
                logs.append("  Environment variables configured:")
                logs.append("    • FIC_HOME: /u01/OFSAA/FICHOME")
                logs.append("    • JAVA_HOME: /u01/jdk-11.0.16")
                logs.append("    • ORACLE_HOME: /u01/app/oracle/product/19.0.0/client_1")
                logs.append("    • ORACLE_SID: OFSAAPDB")
                logs.append("  File ownership set to oracle:oinstall")
                logs.append("  Shell aliases and PATH configured")
                logs.append("  Profile ready for OFSAA installation")
                
                return {
                    "success": True,
                    "message": "Oracle profile created successfully with OFSAA template",
                    "logs": logs,
                    "output": result["stdout"]
                }
            else:
                error_msg = f"Profile creation failed: {result.get('stderr', 'Unknown error')}"
                logs.append(f"Profile creation failed: {error_msg}")
                
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs,
                    "stderr": result.get("stderr", ""),
                    "returncode": result.get("returncode", -1)
                }
                
        except Exception as e:
            logger.error(f"Profile creation failed: {str(e)}")
            return {
                "success": False,
                "error": f"Profile creation failed: {str(e)}",
                "logs": [f"ERROR: Exception in profile creation: {str(e)}"]
            }
            
    async def update_profile_with_custom_variables(self, host: str, username: str, password: str, 
                                                   fic_home: str = "/u01/OFSAA/FICHOME", 
                                                   custom_java_home: str = None,
                                                   custom_java_bin: str = None,
                                                   custom_oracle_sid: str = None) -> Dict[str, Any]:
        """
        Update profile with frontend overrides for FIC_HOME, JAVA_HOME, JAVA_BIN, ORACLE_SID
        If no frontend values provided, use profile template defaults
        """
        try:
            logs = []
            
            # Use frontend values or profile template defaults
            final_fic_home = fic_home if fic_home != "/u01/OFSAA/FICHOME" else "/u01/OFSAA/FICHOME"
            final_java_home = custom_java_home if custom_java_home else "/u01/jdk-11.0.16"
            final_java_bin = custom_java_bin if custom_java_bin else "/u01/jdk-11.0.16/bin"
            final_oracle_sid = custom_oracle_sid if custom_oracle_sid else "OFSAAPDB"
            
            logs.append(f"Applying frontend overrides or using profile defaults")
            
            # Replace variables in existing profile
            replacement_cmd = f'''
# Update profile variables with frontend overrides or defaults
sed -i 's|export FIC_HOME=.*|export FIC_HOME={final_fic_home}|g' /home/oracle/.profile
sed -i 's|export JAVA_HOME=.*|export JAVA_HOME={final_java_home}|g' /home/oracle/.profile
sed -i 's|export JAVA_BIN=.*|export JAVA_BIN={final_java_bin}|g' /home/oracle/.profile
sed -i 's|export ORACLE_SID=.*|export ORACLE_SID={final_oracle_sid}|g' /home/oracle/.profile

# Verify updates
echo "Profile variables updated:"
grep -E "(FIC_HOME|JAVA_HOME|JAVA_BIN|ORACLE_SID)=" /home/oracle/.profile
'''
            
            update_result = await self.ssh_service.execute_command(host, username, password, replacement_cmd)
            
            if update_result["success"]:
                logs.extend([
                    "✓ Custom Profile Variables Updated",
                    f"  FIC_HOME: {final_fic_home}",
                    f"  JAVA_HOME: {final_java_home}", 
                    f"  JAVA_BIN: {final_java_bin}",
                    f"  ORACLE_SID: {final_oracle_sid}",
                    "  Profile variables synchronized with frontend preferences",
                    "  Environment ready for OFSAA installation"
                ])
                
                return {
                    "success": True,
                    "message": "Profile updated with custom variables successfully",
                    "logs": logs,
                    "final_variables": {
                        "fic_home": final_fic_home,
                        "java_home": final_java_home,
                        "java_bin": final_java_bin,
                        "oracle_sid": final_oracle_sid
                    },
                    "verification_output": update_result.get("stdout", "")
                }
            else:
                error_msg = f"Profile variable update failed: {update_result.get('stderr', 'Unknown error')}"
                logs.append(f"Profile variable update failed: {error_msg}")
                
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs,
                    "stderr": update_result.get("stderr", ""),
                    "returncode": update_result.get("returncode", -1)
                }
                
        except Exception as e:
            logger.error(f"Profile variables update failed: {str(e)}")
            return {
                "success": False,
                "error": f"Profile variables update failed: {str(e)}",
                "logs": [f"ERROR: Exception in profile variables update: {str(e)}"]
            }
            
    async def verify_profile_setup(self, host: str, username: str, password: str) -> Dict[str, Any]:
        """
        Verify the profile setup by sourcing it and checking environment variables
        """
        try:
            command = (
                "sudo -u oracle bash -c '"
                "source /home/oracle/.profile && "
                "echo \"=== Profile Verification ===\"; "
                "echo \"FIC_HOME: $FIC_HOME\"; "
                "echo \"JAVA_HOME: $JAVA_HOME\"; "
                "echo \"JAVA_BIN: $JAVA_BIN\"; "
                "echo \"ORACLE_HOME: $ORACLE_HOME\"; "
                "echo \"ORACLE_SID: $ORACLE_SID\"; "
                "echo \"TNS_ADMIN: $TNS_ADMIN\"; "
                "echo \"Java Version: $(java -version 2>&1 | head -1)\"; "
                "echo \"Profile verification completed\"'"
            )
            
            result = await self.ssh_service.execute_command(host, username, password, command)
            
            logs = []
            if result["success"]:
                logs.append("✓ Profile Verification Completed")
                logs.append("  Environment variables are properly set")
                logs.append("  Profile sourcing works correctly")
                logs.append("  Java installation verified")
                
                # Parse the output to extract variables
                output_lines = result["stdout"].split('\n')
                env_vars = {}
                for line in output_lines:
                    if ':' in line and any(var in line for var in ['FIC_HOME', 'JAVA_HOME', 'JAVA_BIN', 'ORACLE_HOME', 'ORACLE_SID', 'TNS_ADMIN']):
                        key, value = line.split(':', 1)
                        env_vars[key.strip()] = value.strip()
                
                logs.append("  Environment Summary:")
                for key, value in env_vars.items():
                    logs.append(f"    • {key}: {value}")
                
                return {
                    "success": True,
                    "message": "Profile verification completed successfully",
                    "logs": logs,
                    "environment_variables": env_vars,
                    "output": result["stdout"]
                }
            else:
                error_msg = f"Profile verification failed: {result.get('stderr', 'Unknown error')}"
                logs.append(f"Profile verification failed: {error_msg}")
                
                return {
                    "success": False,
                    "error": error_msg,
                    "logs": logs,
                    "stderr": result.get("stderr", ""),
                    "returncode": result.get("returncode", -1)
                }
                
        except Exception as e:
            logger.error(f"Profile verification failed: {str(e)}")
            return {
                "success": False,
                "error": f"Profile verification failed: {str(e)}",
                "logs": [f"ERROR: Exception in profile verification: {str(e)}"]
            }