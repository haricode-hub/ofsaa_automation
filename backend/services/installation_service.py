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
from services.recovery_service import RecoveryService


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
        self.recovery = RecoveryService(ssh_service)

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

    async def apply_installer_config_files(
        self,
        host: str,
        username: str,
        password: str,
        *,
        schema_jdbc_host: Optional[str] = None,
        schema_jdbc_port: Optional[int] = None,
        schema_jdbc_service: Optional[str] = None,
        schema_host: Optional[str] = None,
        schema_setup_env: Optional[str] = None,
        schema_apply_same_for_all: Optional[str] = None,
        schema_default_password: Optional[str] = None,
        schema_datafile_dir: Optional[str] = None,
        schema_tablespace_autoextend: Optional[str] = None,
        schema_external_directory_value: Optional[str] = None,
        schema_config_schema_name: Optional[str] = None,
        schema_atomic_schema_name: Optional[str] = None,
        pack_app_enable: Optional[dict[str, bool]] = None,
        prop_base_country: Optional[str] = None,
        prop_default_jurisdiction: Optional[str] = None,
        prop_smtp_host: Optional[str] = None,
        prop_partition_date_format: Optional[str] = None,
        prop_datadumpdt_minus_0: Optional[str] = None,
        prop_endthisweek_minus_00: Optional[str] = None,
        prop_startnextmnth_minus_00: Optional[str] = None,
        prop_analyst_data_source: Optional[str] = None,
        prop_miner_data_source: Optional[str] = None,
        prop_web_service_user: Optional[str] = None,
        prop_web_service_password: Optional[str] = None,
        prop_nls_length_semantics: Optional[str] = None,
        prop_configure_obiee: Optional[str] = None,
        prop_obiee_url: Optional[str] = None,
        prop_sw_rmiport: Optional[str] = None,
        prop_big_data_enable: Optional[str] = None,
        prop_sqoop_working_dir: Optional[str] = None,
        prop_ssh_auth_alias: Optional[str] = None,
        prop_ssh_host_name: Optional[str] = None,
        prop_ssh_port: Optional[str] = None,
        prop_cssource: Optional[str] = None,
        prop_csloadtype: Optional[str] = None,
        prop_crrsource: Optional[str] = None,
        prop_crrloadtype: Optional[str] = None,
        prop_fsdf_upload_model: Optional[str] = None,
        aai_webappservertype: Optional[str] = None,
        aai_dbserver_ip: Optional[str] = None,
        aai_oracle_service_name: Optional[str] = None,
        aai_abs_driver_path: Optional[str] = None,
        aai_olap_server_implementation: Optional[str] = None,
        aai_sftp_enable: Optional[str] = None,
        aai_file_transfer_port: Optional[str] = None,
        aai_javaport: Optional[str] = None,
        aai_nativeport: Optional[str] = None,
        aai_agentport: Optional[str] = None,
        aai_iccport: Optional[str] = None,
        aai_iccnativeport: Optional[str] = None,
        aai_olapport: Optional[str] = None,
        aai_msgport: Optional[str] = None,
        aai_routerport: Optional[str] = None,
        aai_amport: Optional[str] = None,
        aai_https_enable: Optional[str] = None,
        aai_web_server_ip: Optional[str] = None,
        aai_web_server_port: Optional[str] = None,
        aai_context_name: Optional[str] = None,
        aai_webapp_context_path: Optional[str] = None,
        aai_web_local_path: Optional[str] = None,
        aai_weblogic_domain_home: Optional[str] = None,
        aai_ftspshare_path: Optional[str] = None,
        aai_sftp_user_id: Optional[str] = None,
    ) -> dict:
        return await self.installer.apply_config_files_from_repo(
            host,
            username,
            password,
            schema_jdbc_host=schema_jdbc_host,
            schema_jdbc_port=schema_jdbc_port,
            schema_jdbc_service=schema_jdbc_service,
            schema_host=schema_host,
            schema_setup_env=schema_setup_env,
            schema_apply_same_for_all=schema_apply_same_for_all,
            schema_default_password=schema_default_password,
            schema_datafile_dir=schema_datafile_dir,
            schema_tablespace_autoextend=schema_tablespace_autoextend,
            schema_external_directory_value=schema_external_directory_value,
            schema_config_schema_name=schema_config_schema_name,
            schema_atomic_schema_name=schema_atomic_schema_name,
            pack_app_enable=pack_app_enable,
            prop_base_country=prop_base_country,
            prop_default_jurisdiction=prop_default_jurisdiction,
            prop_smtp_host=prop_smtp_host,
            prop_partition_date_format=prop_partition_date_format,
            prop_datadumpdt_minus_0=prop_datadumpdt_minus_0,
            prop_endthisweek_minus_00=prop_endthisweek_minus_00,
            prop_startnextmnth_minus_00=prop_startnextmnth_minus_00,
            prop_analyst_data_source=prop_analyst_data_source,
            prop_miner_data_source=prop_miner_data_source,
            prop_web_service_user=prop_web_service_user,
            prop_web_service_password=prop_web_service_password,
            prop_nls_length_semantics=prop_nls_length_semantics,
            prop_configure_obiee=prop_configure_obiee,
            prop_obiee_url=prop_obiee_url,
            prop_sw_rmiport=prop_sw_rmiport,
            prop_big_data_enable=prop_big_data_enable,
            prop_sqoop_working_dir=prop_sqoop_working_dir,
            prop_ssh_auth_alias=prop_ssh_auth_alias,
            prop_ssh_host_name=prop_ssh_host_name,
            prop_ssh_port=prop_ssh_port,
            prop_cssource=prop_cssource,
            prop_csloadtype=prop_csloadtype,
            prop_crrsource=prop_crrsource,
            prop_crrloadtype=prop_crrloadtype,
            prop_fsdf_upload_model=prop_fsdf_upload_model,
            aai_webappservertype=aai_webappservertype,
            aai_dbserver_ip=aai_dbserver_ip,
            aai_oracle_service_name=aai_oracle_service_name,
            aai_abs_driver_path=aai_abs_driver_path,
            aai_olap_server_implementation=aai_olap_server_implementation,
            aai_sftp_enable=aai_sftp_enable,
            aai_file_transfer_port=aai_file_transfer_port,
            aai_javaport=aai_javaport,
            aai_nativeport=aai_nativeport,
            aai_agentport=aai_agentport,
            aai_iccport=aai_iccport,
            aai_iccnativeport=aai_iccnativeport,
            aai_olapport=aai_olapport,
            aai_msgport=aai_msgport,
            aai_routerport=aai_routerport,
            aai_amport=aai_amport,
            aai_https_enable=aai_https_enable,
            aai_web_server_ip=aai_web_server_ip,
            aai_web_server_port=aai_web_server_port,
            aai_context_name=aai_context_name,
            aai_webapp_context_path=aai_webapp_context_path,
            aai_web_local_path=aai_web_local_path,
            aai_weblogic_domain_home=aai_weblogic_domain_home,
            aai_ftspshare_path=aai_ftspshare_path,
            aai_sftp_user_id=aai_sftp_user_id,
        )

    async def run_osc_schema_creator(self, host: str, username: str, password: str, **kwargs) -> dict:
        return await self.installer.run_osc_schema_creator(host, username, password, **kwargs)

    async def run_setup_silent(self, host: str, username: str, password: str, **kwargs) -> dict:
        return await self.installer.run_setup_silent(host, username, password, **kwargs)

    async def run_environment_check(self, host: str, username: str, password: str, **kwargs) -> dict:
        return await self.installer.run_environment_check(host, username, password, **kwargs)

    async def cleanup_failed_fresh_installation(self, host: str, username: str, password: str) -> dict:
        return await self.installer.cleanup_failed_fresh_installation(host, username, password)

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

    async def cleanup_after_osc_failure(
        self,
        app_host: str,
        app_username: str,
        app_password: str,
        db_host: str,
        db_username: str,
        db_password: str,
        *,
        db_sys_password: Optional[str] = None,
        db_jdbc_host: Optional[str] = None,
        db_jdbc_port: int = 1521,
        db_jdbc_service: Optional[str] = None,
        db_ssh_host: Optional[str] = None,
        db_ssh_username: Optional[str] = None,
        db_ssh_password: Optional[str] = None,
    ) -> dict:
        """Execute cleanup after osc.sh failure: kill Java, drop schema, clear cache."""
        return await self.recovery.cleanup_after_osc_failure(
            app_host, app_username, app_password,
            db_host, db_username, db_password,
            db_sys_password=db_sys_password,
            db_jdbc_host=db_jdbc_host,
            db_jdbc_port=db_jdbc_port,
            db_jdbc_service=db_jdbc_service,
            db_ssh_host=db_ssh_host,
            db_ssh_username=db_ssh_username,
            db_ssh_password=db_ssh_password,
        )

    # ============== BACKUP / RESTORE METHODS ==============

    async def ensure_backup_restore_scripts(self, host: str, username: str, password: str) -> dict:
        """Ensure Git-controlled backup/restore scripts exist on target."""
        return await self.recovery.ensure_backup_restore_scripts(host, username, password)

    async def backup_application(self, host: str, username: str, password: str) -> dict:
        """Create application tar backup."""
        return await self.recovery.backup_application(host, username, password)

    async def backup_db_schemas(
        self, host: str, username: str, password: str,
        *, db_sys_password: str, db_jdbc_service: str,
        db_ssh_host: Optional[str] = None, db_ssh_username: Optional[str] = None, db_ssh_password: Optional[str] = None,
    ) -> dict:
        """Run DB schema backup using Git-controlled script."""
        return await self.recovery.backup_db_schemas(
            host, username, password,
            db_sys_password=db_sys_password,
            db_jdbc_service=db_jdbc_service,
            db_ssh_host=db_ssh_host,
            db_ssh_username=db_ssh_username,
            db_ssh_password=db_ssh_password,
        )

    async def restore_application(self, host: str, username: str, password: str) -> dict:
        """Restore application from tar backup."""
        return await self.recovery.restore_application(host, username, password)

    async def restore_db_schemas(
        self, host: str, username: str, password: str,
        *, db_sys_password: str, db_jdbc_service: str,
        db_ssh_host: Optional[str] = None, db_ssh_username: Optional[str] = None, db_ssh_password: Optional[str] = None,
    ) -> dict:
        """Restore DB schemas using Git-controlled script."""
        return await self.recovery.restore_db_schemas(
            host, username, password,
            db_sys_password=db_sys_password,
            db_jdbc_service=db_jdbc_service,
            db_ssh_host=db_ssh_host,
            db_ssh_username=db_ssh_username,
            db_ssh_password=db_ssh_password,
        )

    async def full_restore_to_bd_state(
        self, host: str, username: str, password: str,
        *, db_sys_password: str, db_jdbc_service: str,
        db_ssh_host: Optional[str] = None, db_ssh_username: Optional[str] = None, db_ssh_password: Optional[str] = None,
    ) -> dict:
        """Full restore to BD state: rm OFSAA -> restore tar -> restore DB schemas."""
        # recovery.full_restore_to_bd_state currently restores app then calls restore_db_schemas
        # which accepts db_ssh_* args; pass them through
        return await self.recovery.full_restore_to_bd_state(
            host, username, password,
            db_sys_password=db_sys_password,
            db_jdbc_service=db_jdbc_service,
            db_ssh_host=db_ssh_host,
            db_ssh_username=db_ssh_username,
            db_ssh_password=db_ssh_password,
        )

    # ============== ECM MODULE METHODS ==============

    async def download_and_extract_ecm_installer(self, host: str, username: str, password: str) -> dict:
        """Download and extract ECM installer kit."""
        return await self.installer.download_and_extract_ecm_installer(host, username, password)

    async def set_ecm_permissions(self, host: str, username: str, password: str) -> dict:
        """Set permissions on ECM kit directory."""
        return await self.installer.set_ecm_permissions(host, username, password)

    async def apply_ecm_config_files(
        self,
        host: str,
        username: str,
        password: str,
        *,
        # OFS_ECM_SCHEMA_IN.xml params
        ecm_schema_jdbc_host: Optional[str] = None,
        ecm_schema_jdbc_port: Optional[int] = None,
        ecm_schema_jdbc_service: Optional[str] = None,
        ecm_schema_host: Optional[str] = None,
        ecm_schema_setup_env: Optional[str] = None,
        ecm_schema_prefix_schema_name: Optional[str] = None,
        ecm_schema_apply_same_for_all: Optional[str] = None,
        ecm_schema_default_password: Optional[str] = None,
        ecm_schema_datafile_dir: Optional[str] = None,
        ecm_schema_config_schema_name: Optional[str] = None,
        ecm_schema_atomic_schema_name: Optional[str] = None,
        # ECM default.properties params
        ecm_prop_base_country: Optional[str] = None,
        ecm_prop_default_jurisdiction: Optional[str] = None,
        ecm_prop_smtp_host: Optional[str] = None,
        ecm_prop_web_service_user: Optional[str] = None,
        ecm_prop_web_service_password: Optional[str] = None,
        ecm_prop_nls_length_semantics: Optional[str] = None,
        ecm_prop_analyst_data_source: Optional[str] = None,
        ecm_prop_miner_data_source: Optional[str] = None,
        ecm_prop_configure_obiee: Optional[str] = None,
        ecm_prop_fsdf_upload_model: Optional[str] = None,
        ecm_prop_amlsource: Optional[str] = None,
        ecm_prop_kycsource: Optional[str] = None,
        ecm_prop_cssource: Optional[str] = None,
        ecm_prop_externalsystemsource: Optional[str] = None,
        ecm_prop_tbamlsource: Optional[str] = None,
        ecm_prop_fatcasource: Optional[str] = None,
        ecm_prop_ofsecm_datasrcname: Optional[str] = None,
        ecm_prop_comn_gateway_ds: Optional[str] = None,
        ecm_prop_t2jurl: Optional[str] = None,
        ecm_prop_j2turl: Optional[str] = None,
        ecm_prop_cmngtwyurl: Optional[str] = None,
        ecm_prop_bdurl: Optional[str] = None,
        ecm_prop_ofss_wls_url: Optional[str] = None,
        ecm_prop_aai_url: Optional[str] = None,
        ecm_prop_cs_url: Optional[str] = None,
        ecm_prop_arachnys_nns_service_url: Optional[str] = None,
        # ECM OFSAAI_InstallConfig.xml params
        ecm_aai_webappservertype: Optional[str] = None,
        ecm_aai_dbserver_ip: Optional[str] = None,
        ecm_aai_oracle_service_name: Optional[str] = None,
        ecm_aai_abs_driver_path: Optional[str] = None,
        ecm_aai_olap_server_implementation: Optional[str] = None,
        ecm_aai_sftp_enable: Optional[str] = None,
        ecm_aai_file_transfer_port: Optional[str] = None,
        ecm_aai_javaport: Optional[str] = None,
        ecm_aai_nativeport: Optional[str] = None,
        ecm_aai_agentport: Optional[str] = None,
        ecm_aai_iccport: Optional[str] = None,
        ecm_aai_iccnativeport: Optional[str] = None,
        ecm_aai_olapport: Optional[str] = None,
        ecm_aai_msgport: Optional[str] = None,
        ecm_aai_routerport: Optional[str] = None,
        ecm_aai_amport: Optional[str] = None,
        ecm_aai_https_enable: Optional[str] = None,
        ecm_aai_web_server_ip: Optional[str] = None,
        ecm_aai_web_server_port: Optional[str] = None,
        ecm_aai_context_name: Optional[str] = None,
        ecm_aai_webapp_context_path: Optional[str] = None,
        ecm_aai_web_local_path: Optional[str] = None,
        ecm_aai_weblogic_domain_home: Optional[str] = None,
        ecm_aai_ftspshare_path: Optional[str] = None,
        ecm_aai_sftp_user_id: Optional[str] = None,
    ) -> dict:
        """Apply ECM config files from repo."""
        return await self.installer.apply_ecm_config_files_from_repo(
            host, username, password,
            ecm_schema_jdbc_host=ecm_schema_jdbc_host,
            ecm_schema_jdbc_port=ecm_schema_jdbc_port,
            ecm_schema_jdbc_service=ecm_schema_jdbc_service,
            ecm_schema_host=ecm_schema_host,
            ecm_schema_setup_env=ecm_schema_setup_env,
            ecm_schema_prefix_schema_name=ecm_schema_prefix_schema_name,
            ecm_schema_apply_same_for_all=ecm_schema_apply_same_for_all,
            ecm_schema_default_password=ecm_schema_default_password,
            ecm_schema_datafile_dir=ecm_schema_datafile_dir,
            ecm_schema_config_schema_name=ecm_schema_config_schema_name,
            ecm_schema_atomic_schema_name=ecm_schema_atomic_schema_name,
            ecm_prop_base_country=ecm_prop_base_country,
            ecm_prop_default_jurisdiction=ecm_prop_default_jurisdiction,
            ecm_prop_smtp_host=ecm_prop_smtp_host,
            ecm_prop_web_service_user=ecm_prop_web_service_user,
            ecm_prop_web_service_password=ecm_prop_web_service_password,
            ecm_prop_nls_length_semantics=ecm_prop_nls_length_semantics,
            ecm_prop_analyst_data_source=ecm_prop_analyst_data_source,
            ecm_prop_miner_data_source=ecm_prop_miner_data_source,
            ecm_prop_configure_obiee=ecm_prop_configure_obiee,
            ecm_prop_fsdf_upload_model=ecm_prop_fsdf_upload_model,
            ecm_prop_amlsource=ecm_prop_amlsource,
            ecm_prop_kycsource=ecm_prop_kycsource,
            ecm_prop_cssource=ecm_prop_cssource,
            ecm_prop_externalsystemsource=ecm_prop_externalsystemsource,
            ecm_prop_tbamlsource=ecm_prop_tbamlsource,
            ecm_prop_fatcasource=ecm_prop_fatcasource,
            ecm_prop_ofsecm_datasrcname=ecm_prop_ofsecm_datasrcname,
            ecm_prop_comn_gateway_ds=ecm_prop_comn_gateway_ds,
            ecm_prop_t2jurl=ecm_prop_t2jurl,
            ecm_prop_j2turl=ecm_prop_j2turl,
            ecm_prop_cmngtwyurl=ecm_prop_cmngtwyurl,
            ecm_prop_bdurl=ecm_prop_bdurl,
            ecm_prop_ofss_wls_url=ecm_prop_ofss_wls_url,
            ecm_prop_aai_url=ecm_prop_aai_url,
            ecm_prop_cs_url=ecm_prop_cs_url,
            ecm_prop_arachnys_nns_service_url=ecm_prop_arachnys_nns_service_url,
            ecm_aai_webappservertype=ecm_aai_webappservertype,
            ecm_aai_dbserver_ip=ecm_aai_dbserver_ip,
            ecm_aai_oracle_service_name=ecm_aai_oracle_service_name,
            ecm_aai_abs_driver_path=ecm_aai_abs_driver_path,
            ecm_aai_olap_server_implementation=ecm_aai_olap_server_implementation,
            ecm_aai_sftp_enable=ecm_aai_sftp_enable,
            ecm_aai_file_transfer_port=ecm_aai_file_transfer_port,
            ecm_aai_javaport=ecm_aai_javaport,
            ecm_aai_nativeport=ecm_aai_nativeport,
            ecm_aai_agentport=ecm_aai_agentport,
            ecm_aai_iccport=ecm_aai_iccport,
            ecm_aai_iccnativeport=ecm_aai_iccnativeport,
            ecm_aai_olapport=ecm_aai_olapport,
            ecm_aai_msgport=ecm_aai_msgport,
            ecm_aai_routerport=ecm_aai_routerport,
            ecm_aai_amport=ecm_aai_amport,
            ecm_aai_https_enable=ecm_aai_https_enable,
            ecm_aai_web_server_ip=ecm_aai_web_server_ip,
            ecm_aai_web_server_port=ecm_aai_web_server_port,
            ecm_aai_context_name=ecm_aai_context_name,
            ecm_aai_webapp_context_path=ecm_aai_webapp_context_path,
            ecm_aai_web_local_path=ecm_aai_web_local_path,
            ecm_aai_weblogic_domain_home=ecm_aai_weblogic_domain_home,
            ecm_aai_ftspshare_path=ecm_aai_ftspshare_path,
            ecm_aai_sftp_user_id=ecm_aai_sftp_user_id,
        )

    async def run_ecm_osc_schema_creator(self, host: str, username: str, password: str, **kwargs) -> dict:
        """Run ECM schema creator osc.sh."""
        return await self.installer.run_ecm_osc_schema_creator(host, username, password, **kwargs)

    async def run_ecm_setup_silent(self, host: str, username: str, password: str, **kwargs) -> dict:
        """Run ECM setup.sh SILENT."""
        return await self.installer.run_ecm_setup_silent(host, username, password, **kwargs)

