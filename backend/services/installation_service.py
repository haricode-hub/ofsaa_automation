import logging
import asyncio
from typing import Dict, Any, List
from services.ssh_service import SSHService

# Import all service modules
from services.oracle_user_setup import OracleUserSetupService
from services.mount_point import MountPointService
from services.packages import PackageInstallationService
from services.profile import ProfileService
from services.java import JavaInstallationService
from services.oracle_client import OracleClientService
from services.installer import InstallerService

logger = logging.getLogger(__name__)

class InstallationService:
    """Main OFSAA Installation Service - orchestrates all installation components"""
    
    def __init__(self, ssh_service: SSHService):
        self.ssh_service = ssh_service
        
        # Initialize all step services
        self.oracle_user_service = OracleUserSetupService(ssh_service)
        self.mount_point_service = MountPointService(ssh_service)
        self.packages_service = PackageInstallationService(ssh_service)
        self.profile_service = ProfileService(ssh_service)
        self.java_service = JavaInstallationService(ssh_service)
        self.oracle_client_service = OracleClientService(ssh_service)
        self.installer_service = InstallerService(ssh_service)
    
    # Oracle User Setup
    async def create_oracle_user_and_oinstall_group(self, host: str, username: str, password: str) -> Dict[str, Any]:
        return await self.oracle_user_service.create_oracle_user_and_oinstall_group(host, username, password)
    
    # Mount Point Creation
    async def create_mount_point(self, host: str, username: str, password: str) -> Dict[str, Any]:
        return await self.mount_point_service.create_mount_point(host, username, password)
    
    # Package Installation
    async def install_ksh_and_git(self, host: str, username: str, password: str) -> Dict[str, Any]:
        return await self.packages_service.install_ksh_and_git(host, username, password)
    
    # Profile Setup
    async def create_profile_file(self, host: str, username: str, password: str) -> Dict[str, Any]:
        return await self.profile_service.create_profile_file(host, username, password)
    
    async def update_profile_with_custom_variables(self, host: str, username: str, password: str, 
                                                   fic_home: str = "/u01/OFSAA/FICHOME", 
                                                   custom_java_home: str = None,
                                                   custom_java_bin: str = None,
                                                   custom_oracle_sid: str = None) -> Dict[str, Any]:
        return await self.profile_service.update_profile_with_custom_variables(
            host, username, password, fic_home, custom_java_home, custom_java_bin, custom_oracle_sid)
    
    async def verify_profile_setup(self, host: str, username: str, password: str) -> Dict[str, Any]:
        return await self.profile_service.verify_profile_setup(host, username, password)
    
    # Java Installation
    async def install_java_from_oracle_kit(self, host: str, username: str, password: str, java_home: str = "/u01/jdk-11.0.16") -> Dict[str, Any]:
        return await self.java_service.install_java_from_oracle_kit(host, username, password, java_home)
    
    # OFSAA Directory Creation
    async def create_ofsaa_directories(self, host: str, username: str, password: str, fic_home: str = "/u01/OFSAA/FICHOME") -> Dict[str, Any]:
        return await self.java_service.create_ofsaa_directories(host, username, password, fic_home)
    
    # Oracle Client Installation
    async def install_oracle_client_and_update_profile(self, host: str, username: str, password: str, oracle_sid: str = "ORCL") -> Dict[str, Any]:
        return await self.oracle_client_service.install_oracle_client_and_update_profile(host, username, password, oracle_sid)
    
    # Oracle Client Check (for existing installations)
    async def check_existing_oracle_client_and_update_profile(self, host: str, username: str, password: str, oracle_sid: str = "ORCL") -> Dict[str, Any]:
        return await self.oracle_client_service.check_existing_oracle_client_and_update_profile(host, username, password, oracle_sid)
    
    # Installer Files
    async def extract_installer_files(self, host: str, username: str, password: str) -> Dict[str, Any]:
        return await self.installer_service.extract_installer_files(host, username, password)
    
    async def download_and_extract_installer(self, host: str, username: str, password: str, 
                                             on_output=None, on_prompt=None, input_poll=None, on_status=None,
                                             run_envcheck_inline: bool = False, timeout: int = 7200,
                                             db_user: str = None, db_pass: str = None, db_sid: str = None) -> Dict[str, Any]:
        return await self.installer_service.download_and_extract_installer(
            host, username, password,
            on_output=on_output,
            on_prompt=on_prompt,
            input_poll=input_poll,
            on_status=on_status,
            run_envcheck_inline=run_envcheck_inline,
            timeout=timeout,
            db_user=db_user,
            db_pass=db_pass,
            db_sid=db_sid
        )
        
    async def run_environment_check(self, host: str, username: str, password: str,
                                    on_output=None, on_prompt=None, input_poll=None, on_status=None,
                                    timeout: int = 7200) -> Dict[str, Any]:
        return await self.installer_service.run_environment_check(
            host, username, password,
            on_output=on_output,
            on_prompt=on_prompt,
            input_poll=input_poll,
            on_status=on_status,
            timeout=timeout
        )
    
    # Complete Installation Workflow
    async def run_complete_installation(self, host: str, username: str, password: str, 
                                      fic_home: str = "/u01/OFSAA/FICHOME",
                                      custom_java_home: str = None,
                                      custom_java_bin: str = None,
                                      custom_oracle_sid: str = None) -> Dict[str, Any]:
        """
        Run the complete OFSAA installation workflow
        """
        try:
            all_logs = []
            installation_results = {}
            
            # Step 1: Oracle User Setup
            step1_result = await self.create_oracle_user_and_oinstall_group(host, username, password)
            all_logs.extend(step1_result.get("logs", []))
            installation_results["step1_oracle_user"] = step1_result
            if not step1_result["success"]:
                return {"success": False, "error": "Step 1 failed", "logs": all_logs, "results": installation_results}
            
            # Step 2: Mount Point Creation
            step2_result = await self.create_mount_point(host, username, password)
            all_logs.extend(step2_result.get("logs", []))
            installation_results["step2_mount_point"] = step2_result
            if not step2_result["success"]:
                return {"success": False, "error": "Step 2 failed", "logs": all_logs, "results": installation_results}
            
            # Step 3: Package Installation
            step3_result = await self.install_ksh_and_git(host, username, password)
            all_logs.extend(step3_result.get("logs", []))
            installation_results["step3_packages"] = step3_result
            if not step3_result["success"]:
                return {"success": False, "error": "Step 3 failed", "logs": all_logs, "results": installation_results}
            
            # Step 4: Profile Creation
            step4_result = await self.create_profile_file(host, username, password)
            all_logs.extend(step4_result.get("logs", []))
            installation_results["step4_profile"] = step4_result
            if not step4_result["success"]:
                return {"success": False, "error": "Step 4 failed", "logs": all_logs, "results": installation_results}
            
            # Step 5: Java Installation (Required before Oracle Client)
            java_home = custom_java_home or "/u01/jdk-11.0.16"
            step5_result = await self.install_java_from_oracle_kit(host, username, password, java_home)
            all_logs.extend(step5_result.get("logs", []))
            installation_results["step5_java"] = step5_result
            if not step5_result["success"]:
                return {"success": False, "error": "Step 5 (Java) failed", "logs": all_logs, "results": installation_results}
            
            # Oracle Client Installation (Must be immediately after Java installation)
            # DEPENDENCY: Java must be installed first for Oracle Client to work properly
            oracle_sid = custom_oracle_sid or "ORCL"
            oracle_client_result = await self.install_oracle_client_and_update_profile(host, username, password, oracle_sid)
            all_logs.extend(oracle_client_result.get("logs", []))
            installation_results["oracle_client"] = oracle_client_result
            if not oracle_client_result["success"]:
                return {"success": False, "error": "Oracle Client installation failed", "logs": all_logs, "results": installation_results}
            
            # Update Profile with Custom Variables
            profile_update_result = await self.update_profile_with_custom_variables(
                host, username, password, fic_home, custom_java_home, custom_java_bin, custom_oracle_sid)
            all_logs.extend(profile_update_result.get("logs", []))
            installation_results["profile_update"] = profile_update_result
            if not profile_update_result["success"]:
                return {"success": False, "error": "Profile update failed", "logs": all_logs, "results": installation_results}
            
            # Extract Installer Files
            installer_result = await self.extract_installer_files(host, username, password)
            all_logs.extend(installer_result.get("logs", []))
            installation_results["installer"] = installer_result
            if not installer_result["success"]:
                return {"success": False, "error": "Installer extraction failed", "logs": all_logs, "results": installation_results}
            
            # Final Profile Verification
            verification_result = await self.verify_profile_setup(host, username, password)
            all_logs.extend(verification_result.get("logs", []))
            installation_results["verification"] = verification_result
            
            # Final summary
            all_logs.extend([
                "",
                "🎉 OFSAA Installation Complete! 🎉",
                "================================",
                "✅ All installation components completed successfully",
                "✅ Oracle user and environment configured",
                "✅ Java and Oracle client installed",
                "✅ OFSAA environment ready for use",
                "",
                "Next components:",
                "  1. Upload OFSAA installation files to /u01/installer_kit/",
                "  2. Run OFSAA installer as oracle user",
                "  3. Configure database connections",
                ""
            ])
            
            return {
                "success": True,
                "message": "Complete OFSAA installation finished successfully",
                "logs": all_logs,
                "results": installation_results,
                "summary": {
                    "total_components": len(installation_results),
                    "successful_components": len([r for r in installation_results.values() if r.get("success", False)]),
                    "host": host,
                    "java_home": java_home,
                    "oracle_sid": oracle_sid,
                    "fic_home": fic_home
                }
            }
            
        except Exception as e:
            logger.error(f"Complete installation failed: {str(e)}")
            return {
                "success": False,
                "error": f"Complete installation failed: {str(e)}",
                "logs": all_logs + [f"ERROR: Exception in complete installation: {str(e)}"],
                "results": installation_results
            }
