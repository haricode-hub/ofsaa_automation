from typing import Optional

from services.ssh_service import SSHService
from services.validation import ValidationService
from services.oracle_user_setup import OracleUserSetupService
from services.mount_point import MountPointService
from services.packages import PackageService
from services.profile import ProfileService
from services.java import JavaService
from services.oracle_client import OracleClientService
from services.installer import InstallerService


class InstallationService:
    """Orchestrates the OFSAA installation workflow."""

    def __init__(self, ssh_service: SSHService) -> None:
        self.ssh_service = ssh_service
        self.validation = ValidationService(ssh_service)

        self.oracle_user_setup = OracleUserSetupService(ssh_service, self.validation)
        self.mount_point = MountPointService(ssh_service, self.validation)
        self.packages = PackageService(ssh_service, self.validation)
        self.profile = ProfileService(ssh_service, self.validation)
        self.java = JavaService(ssh_service, self.validation)
        self.oracle_client = OracleClientService(ssh_service, self.validation, self.profile)
        self.installer = InstallerService(ssh_service, self.validation)

    async def create_oracle_user_and_oinstall_group(self, host: str, username: str, password: str) -> dict:
        return await self.oracle_user_setup.ensure_oracle_user(host, username, password)

    async def create_mount_point(self, host: str, username: str, password: str) -> dict:
        return await self.mount_point.ensure_mount_point(host, username, password)

    async def install_ksh_and_git(self, host: str, username: str, password: str) -> dict:
        return await self.packages.ensure_packages(host, username, password, ["ksh", "git", "unzip"])

    async def create_profile_file(self, host: str, username: str, password: str) -> dict:
        return await self.profile.create_profile_file(host, username, password)

    async def install_java_from_repo(self, host: str, username: str, password: str) -> dict:
        return await self.java.install_java_from_repo(host, username, password)

    async def create_ofsaa_directories(self, host: str, username: str, password: str) -> dict:
        return await self.java.create_ofsaa_directories(host, username, password)

    async def check_existing_oracle_client_and_update_profile(
        self,
        host: str,
        username: str,
        password: str,
        oracle_sid: Optional[str],
    ) -> dict:
        return await self.oracle_client.check_existing_oracle_client_and_update_profile(
            host, username, password, oracle_sid
        )

    async def download_and_extract_installer(self, host: str, username: str, password: str) -> dict:
        return await self.installer.download_and_extract_installer(host, username, password)

    async def set_installer_permissions(self, host: str, username: str, password: str) -> dict:
        return await self.installer.set_permissions(host, username, password)

    async def run_environment_check(self, host: str, username: str, password: str, **kwargs) -> dict:
        return await self.installer.run_environment_check(host, username, password, **kwargs)

    async def update_profile_with_custom_variables(
        self,
        host: str,
        username: str,
        password: str,
        fic_home: Optional[str],
        java_home: Optional[str],
        java_bin: Optional[str],
        oracle_sid: Optional[str],
    ) -> dict:
        return await self.profile.update_profile_with_custom_variables(
            host, username, password, fic_home, java_home, java_bin, oracle_sid
        )

    async def update_java_profile(self, host: str, username: str, password: str, java_home: str) -> dict:
        java_bin = f"{java_home}/bin"
        result = await self.profile.update_profile_variable(host, username, password, "JAVA_HOME", java_home)
        if not result["success"]:
            return result
        result = await self.profile.update_profile_variable(host, username, password, "JAVA_BIN", java_bin)
        if not result["success"]:
            return result
        return {"success": True, "logs": [f"[OK] Updated JAVA_HOME/JAVA_BIN to {java_home}"]}

    async def verify_profile_setup(self, host: str, username: str, password: str) -> dict:
        return await self.profile.verify_profile_setup(host, username, password)
