from typing import Callable, Optional

from services.ssh_service import SSHService
from services.validation import ValidationService
from services.ecm_installer import ECMInstallerService


class ECMInstallationService:
    """Orchestrates the ECM Pack installation workflow."""

    def __init__(self, ssh_service: SSHService) -> None:
        self.ssh_service = ssh_service
        self.validation = ValidationService(ssh_service)
        self.installer = ECMInstallerService(ssh_service, self.validation)

    async def setup_ecm_git_repo(self, host: str, username: str, password: str) -> dict:
        """Set up the Git repository for ECM_PACK."""
        return await self.installer.setup_ecm_git_repo(host, username, password)

    async def download_and_extract_ecm_kit(self, host: str, username: str, password: str) -> dict:
        """Download ECM_PACK zip from Git and extract it to /u01/installer_kit."""
        return await self.installer.download_and_extract_ecm_kit(host, username, password)

    async def backup_ecm_config_files(self, host: str, username: str, password: str) -> dict:
        """Backup existing ECM config files before replacement."""
        return await self.installer.backup_ecm_config_files(host, username, password)

    async def apply_ecm_config_files(
        self,
        host: str,
        username: str,
        password: str,
        *,
        ecm_schema_jdbc_host: Optional[str] = None,
        ecm_schema_jdbc_port: Optional[int] = None,
        ecm_schema_jdbc_service: Optional[str] = None,
        ecm_schema_host: Optional[str] = None,
        ecm_schema_setup_env: Optional[str] = None,
        ecm_schema_apply_same_for_all: Optional[str] = None,
        ecm_schema_default_password: Optional[str] = None,
        ecm_schema_datafile_dir: Optional[str] = None,
        ecm_schema_tablespace_autoextend: Optional[str] = None,
        ecm_schema_external_directory_value: Optional[str] = None,
        ecm_schema_config_schema_name: Optional[str] = None,
        ecm_schema_atomic_schema_name: Optional[str] = None,
        ecm_prop_base_country: Optional[str] = None,
        ecm_prop_default_jurisdiction: Optional[str] = None,
        ecm_prop_web_service_user: Optional[str] = None,
        ecm_prop_web_service_password: Optional[str] = None,
        ecm_aai_webappservertype: Optional[str] = None,
        ecm_aai_dbserver_ip: Optional[str] = None,
        ecm_aai_oracle_service_name: Optional[str] = None,
        ecm_aai_abs_driver_path: Optional[str] = None,
        ecm_aai_web_server_ip: Optional[str] = None,
        ecm_aai_web_server_port: Optional[str] = None,
        ecm_aai_context_name: Optional[str] = None,
    ) -> dict:
        """Apply ECM configuration files from Git repo to the extracted kit."""
        return await self.installer.apply_ecm_config_files(
            host,
            username,
            password,
            ecm_schema_jdbc_host=ecm_schema_jdbc_host,
            ecm_schema_jdbc_port=ecm_schema_jdbc_port,
            ecm_schema_jdbc_service=ecm_schema_jdbc_service,
            ecm_schema_host=ecm_schema_host,
            ecm_schema_setup_env=ecm_schema_setup_env,
            ecm_schema_apply_same_for_all=ecm_schema_apply_same_for_all,
            ecm_schema_default_password=ecm_schema_default_password,
            ecm_schema_datafile_dir=ecm_schema_datafile_dir,
            ecm_schema_tablespace_autoextend=ecm_schema_tablespace_autoextend,
            ecm_schema_external_directory_value=ecm_schema_external_directory_value,
            ecm_schema_config_schema_name=ecm_schema_config_schema_name,
            ecm_schema_atomic_schema_name=ecm_schema_atomic_schema_name,
            ecm_prop_base_country=ecm_prop_base_country,
            ecm_prop_default_jurisdiction=ecm_prop_default_jurisdiction,
            ecm_prop_web_service_user=ecm_prop_web_service_user,
            ecm_prop_web_service_password=ecm_prop_web_service_password,
            ecm_aai_webappservertype=ecm_aai_webappservertype,
            ecm_aai_dbserver_ip=ecm_aai_dbserver_ip,
            ecm_aai_oracle_service_name=ecm_aai_oracle_service_name,
            ecm_aai_abs_driver_path=ecm_aai_abs_driver_path,
            ecm_aai_web_server_ip=ecm_aai_web_server_ip,
            ecm_aai_web_server_port=ecm_aai_web_server_port,
            ecm_aai_context_name=ecm_aai_context_name,
        )

    async def run_ecm_schema_creator(
        self,
        host: str,
        username: str,
        password: str,
        *,
        on_output_callback: Optional[Callable[[str], any]] = None,
        on_prompt_callback: Optional[Callable[[str], any]] = None,
    ) -> dict:
        """Run ECM schema creator (osc.sh -s) with interactive prompts."""
        return await self.installer.run_ecm_schema_creator(
            host,
            username,
            password,
            on_output_callback=on_output_callback,
            on_prompt_callback=on_prompt_callback,
        )

    async def run_ecm_silent_installer(
        self,
        host: str,
        username: str,
        password: str,
        *,
        on_output_callback: Optional[Callable[[str], any]] = None,
        on_prompt_callback: Optional[Callable[[str], any]] = None,
    ) -> dict:
        """Run ECM silent installer (setup.sh SILENT) with interactive prompts."""
        return await self.installer.run_ecm_silent_installer(
            host,
            username,
            password,
            on_output_callback=on_output_callback,
            on_prompt_callback=on_prompt_callback,
        )
