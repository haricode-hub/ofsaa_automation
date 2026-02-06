from typing import Any, Callable, Optional
import os
import re
import time

from core.config import Config
from .ssh_service import SSHService
from .validation import ValidationService
from .utils import shell_escape


class InstallerService:
    """Download installer kit and run envCheck."""

    def __init__(self, ssh_service: SSHService, validation: ValidationService) -> None:
        self.ssh_service = ssh_service
        self.validation = validation

    async def download_and_extract_installer(self, host: str, username: str, password: str) -> dict:
        logs: list[str] = []
        target_dir = "/u01/installer_kit"
        repo_dir = Config.REPO_DIR
        safe_dir_cfg = f"-c safe.directory={repo_dir}"

        # If already extracted, skip repo pull/clone and unzip. Proceed directly to scripts.
        await self.ssh_service.execute_command(host, username, password, f"mkdir -p {target_dir}", get_pty=True)
        check_existing = await self.validation.check_directory_exists(host, username, password, f"{target_dir}/OFS_BD_PACK")
        if check_existing.get("exists"):
            logs.append("[OK] Installer kit already extracted")
            return {"success": True, "logs": logs}

        cmd_prepare = (
            f"if [ -d {repo_dir}/.git ]; then "
            f"cd {repo_dir} && "
            f"(git -c http.sslVerify=false {safe_dir_cfg} pull --ff-only || "
            f"(git config --global --add safe.directory {repo_dir} && git -c http.sslVerify=false {safe_dir_cfg} pull --ff-only)); "
            f"else git -c http.sslVerify=false clone {Config.REPO_URL} {repo_dir}; fi"
        )
        result = await self.ssh_service.execute_command(host, username, password, cmd_prepare, timeout=1800, get_pty=True)
        if not result["success"]:
            if result.get("stdout"):
                logs.append(result["stdout"])
            if result.get("stderr"):
                logs.append(result["stderr"])
            return {"success": False, "logs": logs, "error": result.get("stderr") or "Failed to prepare installer repo"}
        logs.append("[OK] Repository ready for installer kit")

        find_zip_cmd = (
            f"installer_zip=$(find {repo_dir} -maxdepth 1 -type f -name '{Config.INSTALLER_ZIP_NAME}' -print | head -n 1); "
            "if [ -z \"$installer_zip\" ]; then echo 'INSTALLER_ZIP_NOT_FOUND'; exit 1; fi; "
            "echo $installer_zip"
        )
        zip_result = await self.ssh_service.execute_command(host, username, password, find_zip_cmd)
        if not zip_result["success"] or "INSTALLER_ZIP_NOT_FOUND" in zip_result.get("stdout", ""):
            return {"success": False, "logs": logs, "error": "Installer kit zip not found in repo"}

        zip_path = zip_result.get("stdout", "").splitlines()[0].strip()
        logs.append(f"[INFO] Installer zip found: {zip_path}")

        unzip_cmd = f"unzip -o {zip_path} -d {target_dir}"
        unzip_result = await self.ssh_service.execute_command(
            host, username, password, unzip_cmd, timeout=1800, get_pty=True
        )
        if not unzip_result["success"]:
            return {
                "success": False,
                "logs": logs,
                "error": unzip_result.get("stderr") or "Failed to unzip installer kit",
            }
        logs.append("[OK] Installer kit extracted")
        return {"success": True, "logs": logs}

    async def set_permissions(self, host: str, username: str, password: str) -> dict:
        cmd = "chmod -R 775 /u01/installer_kit/OFS_BD_PACK"
        result = await self.ssh_service.execute_command(host, username, password, cmd, get_pty=True)
        if not result["success"]:
            return {"success": False, "logs": [], "error": result.get("stderr") or "Failed to set permissions"}
        return {"success": True, "logs": ["[OK] Permissions set on OFS_BD_PACK"]}

    async def apply_config_files_from_repo(
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
        prop_web_service_user: Optional[str] = None,
        prop_web_service_password: Optional[str] = None,
        prop_configure_obiee: Optional[str] = None,
        prop_obiee_url: Optional[str] = None,
        prop_sw_rmiport: Optional[str] = None,
        prop_big_data_enable: Optional[str] = None,
        prop_sqoop_working_dir: Optional[str] = None,
        prop_ssh_auth_alias: Optional[str] = None,
        prop_ssh_host_name: Optional[str] = None,
        prop_ssh_port: Optional[str] = None,
        prop_ecmsource: Optional[str] = None,
        prop_ecmloadtype: Optional[str] = None,
        prop_cssource: Optional[str] = None,
        prop_csloadtype: Optional[str] = None,
        prop_crrsource: Optional[str] = None,
        prop_crrloadtype: Optional[str] = None,
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
        """
        Fetch required XML/properties from the git repo and place them into the extracted kit locations.
        """
        logs: list[str] = []
        repo_dir = Config.REPO_DIR
        kit_dir = "/u01/installer_kit/OFS_BD_PACK"
        safe_dir_cfg = f"-c safe.directory={repo_dir}"

        # Ensure repo is present and up-to-date before copying config files
        cmd_prepare_repo = (
            "mkdir -p /u01/installer_kit && "
            f"if [ -d {repo_dir}/.git ]; then "
            f"cd {repo_dir} && "
            f"(git -c http.sslVerify=false {safe_dir_cfg} pull --ff-only || "
            f"(git config --global --add safe.directory {repo_dir} && git -c http.sslVerify=false {safe_dir_cfg} pull --ff-only)); "
            f"else git -c http.sslVerify=false clone {Config.REPO_URL} {repo_dir}; fi"
        )
        repo_result = await self.ssh_service.execute_command(
            host, username, password, cmd_prepare_repo, timeout=1800, get_pty=True
        )
        if not repo_result["success"]:
            if repo_result.get("stdout"):
                logs.append(repo_result["stdout"])
            if repo_result.get("stderr"):
                logs.append(repo_result["stderr"])
            return {"success": False, "logs": logs, "error": repo_result.get("stderr") or "Failed to prepare repo"}
        logs.append("[OK] Repo updated for config file fetch")

        mappings = [
            ("OFS_BD_SCHEMA_IN.xml", f"{kit_dir}/schema_creator/conf/OFS_BD_SCHEMA_IN.xml"),
            ("OFS_BD_PACK.xml", f"{kit_dir}/conf/OFS_BD_PACK.xml"),
            ("default.properties", f"{kit_dir}/OFS_AML/conf/default.properties"),
            ("OFSAAI_InstallConfig.xml", f"{kit_dir}/OFS_AAI/conf/OFSAAI_InstallConfig.xml"),
        ]

        # Sanity checks
        check_repo = await self.ssh_service.execute_command(host, username, password, f"test -d {repo_dir}")
        if not check_repo["success"]:
            return {"success": False, "logs": logs, "error": f"Repo dir not found: {repo_dir}"}
        check_kit = await self.ssh_service.execute_command(host, username, password, f"test -d {kit_dir}")
        if not check_kit["success"]:
            return {"success": False, "logs": logs, "error": f"Installer kit not found: {kit_dir}"}

        # If user provided schema inputs, patch the repo copy of OFS_BD_SCHEMA_IN.xml before copying into the kit.
        user_wants_schema_patch = any(
            v is not None and str(v) != ""
            for v in [
                schema_jdbc_host,
                schema_jdbc_service,
                schema_host,
                schema_setup_env,
                schema_default_password,
                schema_datafile_dir,
                schema_tablespace_autoextend,
                schema_external_directory_value,
                schema_config_schema_name,
                schema_atomic_schema_name,
            ]
        )
        if user_wants_schema_patch:
            patch_result = await self._patch_ofs_bd_schema_in_repo(
                host,
                username,
                password,
                repo_dir=repo_dir,
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
            )
            logs.extend(patch_result.get("logs", []))
            if not patch_result.get("success"):
                return {"success": False, "logs": logs, "error": patch_result.get("error") or "Failed to patch schema XML"}

        if pack_app_enable:
            pack_patch = await self._patch_ofs_bd_pack_xml_repo(
                host,
                username,
                password,
                repo_dir=repo_dir,
                pack_app_enable=pack_app_enable,
            )
            logs.extend(pack_patch.get("logs", []))
            if not pack_patch.get("success"):
                return {"success": False, "logs": logs, "error": pack_patch.get("error") or "Failed to patch pack XML"}

        silent_props = {
            "BASE_COUNTRY": prop_base_country,
            "DEFAULT_JURISDICTION": prop_default_jurisdiction,
            "SMTP_HOST": prop_smtp_host,
            "PARTITION_DATE_FORMAT": prop_partition_date_format,
            "WEB_SERVICE_USER": prop_web_service_user,
            "WEB_SERVICE_PASSWORD": prop_web_service_password,
            "CONFIGURE_OBIEE": prop_configure_obiee,
            "OBIEE_URL": prop_obiee_url,
            "SW_RMIPORT": prop_sw_rmiport,
            "BIG_DATA_ENABLE": prop_big_data_enable,
        }
        if any(v is not None for v in silent_props.values()):
            props_patch = await self._patch_default_properties_repo(
                host, username, password, repo_dir=repo_dir, updates=silent_props
            )
            logs.extend(props_patch.get("logs", []))
            if not props_patch.get("success"):
                return {"success": False, "logs": logs, "error": props_patch.get("error") or "Failed to patch default.properties"}

        aai_updates = {
            "WEBAPPSERVERTYPE": aai_webappservertype,
            "DBSERVER_IP": aai_dbserver_ip,
            "ORACLE_SID/SERVICE_NAME": aai_oracle_service_name,
            "ABS_DRIVER_PATH": aai_abs_driver_path,
            "OLAP_SERVER_IMPLEMENTATION": aai_olap_server_implementation,
            "SFTP_ENABLE": aai_sftp_enable,
            "FILE_TRANSFER_PORT": aai_file_transfer_port,
            "JAVAPORT": aai_javaport,
            "NATIVEPORT": aai_nativeport,
            "AGENTPORT": aai_agentport,
            "ICCPORT": aai_iccport,
            "ICCNATIVEPORT": aai_iccnativeport,
            "OLAPPORT": aai_olapport,
            "MSGPORT": aai_msgport,
            "ROUTERPORT": aai_routerport,
            "AMPORT": aai_amport,
            "HTTPS_ENABLE": aai_https_enable,
            "WEB_SERVER_IP": aai_web_server_ip,
            "WEB_SERVER_PORT": aai_web_server_port,
            "CONTEXT_NAME": aai_context_name,
            "WEBAPP_CONTEXT_PATH": aai_webapp_context_path,
            "WEB_LOCAL_PATH": aai_web_local_path,
            "WEBLOGIC_DOMAIN_HOME": aai_weblogic_domain_home,
            "OFSAAI_FTPSHARE_PATH": aai_ftspshare_path,
            "OFSAAI_SFTP_USER_ID": aai_sftp_user_id,
        }
        if any(v is not None for v in aai_updates.values()):
            aai_patch = await self._patch_ofsaai_install_config_repo(
                host, username, password, repo_dir=repo_dir, updates=aai_updates
            )
            logs.extend(aai_patch.get("logs", []))
            if not aai_patch.get("success"):
                return {"success": False, "logs": logs, "error": aai_patch.get("error") or "Failed to patch OFSAAI_InstallConfig.xml"}

        for filename, dest_path in mappings:
            find_cmd = (
                f"src=$(find {repo_dir} -type f -name '{filename}' "
                "! -name '*_BEFORE*' -print | head -n 1); "
                "if [ -z \"$src\" ]; then echo 'NOT_FOUND'; exit 2; fi; "
                "echo $src"
            )
            src_result = await self.ssh_service.execute_command(host, username, password, find_cmd)
            if not src_result["success"] or "NOT_FOUND" in (src_result.get("stdout") or ""):
                return {"success": False, "logs": logs, "error": f"File not found in repo: {filename}"}

            src_path = (src_result.get("stdout") or "").splitlines()[0].strip()
            logs.append(f"[INFO] Using {filename} from repo: {src_path}")

            copy_cmd = (
                f"mkdir -p $(dirname {dest_path}) && "
                f"cp -f {src_path} {dest_path} && "
                f"chown oracle:oinstall {dest_path} && "
                f"chmod 664 {dest_path}"
            )
            copy_result = await self.ssh_service.execute_command(host, username, password, copy_cmd, get_pty=True)
            if not copy_result["success"]:
                return {
                    "success": False,
                    "logs": logs,
                    "error": copy_result.get("stderr") or f"Failed to copy {filename} to kit",
                }
            logs.append(f"[OK] Updated kit file: {dest_path}")

        return {"success": True, "logs": logs}

    async def _read_remote_file(self, host: str, username: str, password: str, path: str) -> dict:
        result = await self.ssh_service.execute_command(host, username, password, f"cat {path}")
        if not result.get("success"):
            return {"success": False, "error": result.get("stderr") or f"Failed to read {path}"}
        return {"success": True, "content": result.get("stdout", "")}

    async def _write_remote_file(self, host: str, username: str, password: str, path: str, content: str) -> dict:
        cmd = f"cat <<'EOF' > {path}\n{content}\nEOF"
        result = await self.ssh_service.execute_command(host, username, password, cmd, get_pty=True)
        if not result.get("success"):
            return {"success": False, "error": result.get("stderr") or f"Failed to write {path}"}
        return {"success": True}

    def _patch_ofs_bd_schema_in_content(
        self,
        content: str,
        *,
        schema_jdbc_host: Optional[str],
        schema_jdbc_port: Optional[int],
        schema_jdbc_service: Optional[str],
        schema_host: Optional[str],
        schema_setup_env: Optional[str],
        schema_apply_same_for_all: Optional[str],
        schema_default_password: Optional[str],
        schema_datafile_dir: Optional[str],
        schema_tablespace_autoextend: Optional[str],
        schema_external_directory_value: Optional[str],
        schema_config_schema_name: Optional[str],
        schema_atomic_schema_name: Optional[str],
    ) -> str:
        updated = content

        if schema_jdbc_host and schema_jdbc_port and schema_jdbc_service:
            jdbc_url = f"jdbc:oracle:thin:@//{schema_jdbc_host}:{schema_jdbc_port}/{schema_jdbc_service}"
            updated = re.sub(
                r"<JDBC_URL>.*?</JDBC_URL>",
                f"<JDBC_URL>{jdbc_url}</JDBC_URL>",
                updated,
                flags=re.DOTALL,
            )

        if schema_host:
            updated = re.sub(r"<HOST>.*?</HOST>", f"<HOST>{schema_host}</HOST>", updated, flags=re.DOTALL)

        if schema_setup_env:
            updated = re.sub(
                r'(<SETUPINFO\b[^>]*\bNAME=")[^"]*(")',
                rf"\g<1>{schema_setup_env}\g<2>",
                updated,
            )

        if schema_apply_same_for_all:
            updated = re.sub(
                r'(<PASSWORD\b[^>]*\bAPPLYSAMEFORALL=")[^"]*(")',
                rf"\g<1>{schema_apply_same_for_all}\g<2>",
                updated,
            )

        if schema_default_password is not None:
            updated = re.sub(
                r'(<PASSWORD\b[^>]*\bDEFAULT=")[^"]*(")',
                rf"\g<1>{schema_default_password}\g<2>",
                updated,
            )

        if schema_tablespace_autoextend:
            updated = re.sub(
                r'(\bAUTOEXTEND=")[^"]*(")',
                rf"\g<1>{schema_tablespace_autoextend}\g<2>",
                updated,
            )

        if schema_datafile_dir:
            base_dir = schema_datafile_dir.rstrip("/")

            def _repl_datafile(m: re.Match) -> str:
                prefix, path, suffix = m.group(1), m.group(2), m.group(3)
                filename = os.path.basename(path)
                return f'{prefix}{base_dir}/{filename}{suffix}'

            updated = re.sub(r'(\bDATAFILE=")([^"]+)(")', _repl_datafile, updated)

        if schema_external_directory_value:
            updated = re.sub(
                r'(<DIRECTORY\b[^>]*\bID="OFS_BD_PACK_EXTERNAL_DIRECTORY_1"[^>]*\bVALUE=")[^"]*(")',
                rf"\g<1>{schema_external_directory_value}\g<2>",
                updated,
            )

        if schema_config_schema_name:
            updated = re.sub(
                r'(<SCHEMA\b[^>]*\bTYPE="CONFIG"[^>]*\bNAME=")[^"]*(")',
                rf"\g<1>{schema_config_schema_name}\g<2>",
                updated,
            )

        if schema_atomic_schema_name:
            updated = re.sub(
                r'(<SCHEMA\b[^>]*\bTYPE="ATOMIC"[^>]*\bNAME=")[^"]*(")',
                rf"\g<1>{schema_atomic_schema_name}\g<2>",
                updated,
            )

        return updated

    async def _patch_ofs_bd_schema_in_repo(
        self,
        host: str,
        username: str,
        password: str,
        *,
        repo_dir: str,
        schema_jdbc_host: Optional[str],
        schema_jdbc_port: Optional[int],
        schema_jdbc_service: Optional[str],
        schema_host: Optional[str],
        schema_setup_env: Optional[str],
        schema_apply_same_for_all: Optional[str],
        schema_default_password: Optional[str],
        schema_datafile_dir: Optional[str],
        schema_tablespace_autoextend: Optional[str],
        schema_external_directory_value: Optional[str],
        schema_config_schema_name: Optional[str],
        schema_atomic_schema_name: Optional[str],
    ) -> dict:
        logs: list[str] = []

        # locate file within repo
        find_cmd = (
            f"src=$(find {repo_dir} -type f -name 'OFS_BD_SCHEMA_IN.xml' ! -name '*_BEFORE*' -print | head -n 1); "
            "if [ -z \"$src\" ]; then echo 'NOT_FOUND'; exit 2; fi; "
            "echo $src"
        )
        src_result = await self.ssh_service.execute_command(host, username, password, find_cmd)
        if not src_result.get("success") or "NOT_FOUND" in (src_result.get("stdout") or ""):
            return {"success": False, "logs": logs, "error": "OFS_BD_SCHEMA_IN.xml not found in repo"}

        src_path = (src_result.get("stdout") or "").splitlines()[0].strip()
        logs.append(f"[INFO] Patching repo XML: {src_path}")

        read = await self._read_remote_file(host, username, password, src_path)
        if not read.get("success"):
            return {"success": False, "logs": logs, "error": read.get("error")}

        original = read.get("content", "")
        patched = self._patch_ofs_bd_schema_in_content(
            original,
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
        )

        if patched == original:
            logs.append("[INFO] No changes needed for OFS_BD_SCHEMA_IN.xml")
            return {"success": True, "logs": logs}

        ts = time.strftime("%Y%m%d_%H%M%S")
        backup_cmd = f"cp -f {src_path} {src_path}.backup.{ts}"
        await self.ssh_service.execute_command(host, username, password, backup_cmd, get_pty=True)
        write = await self._write_remote_file(host, username, password, src_path, patched)
        if not write.get("success"):
            return {"success": False, "logs": logs, "error": write.get("error")}

        logs.append("[OK] Updated OFS_BD_SCHEMA_IN.xml in repo (local clone)")
        return {"success": True, "logs": logs}

    def _patch_ofs_bd_pack_xml_content(self, content: str, *, pack_app_enable: dict[str, bool]) -> str:
        updated = content

        def _set_enable_for_app(app_id: str, enable: bool, text: str) -> str:
            value = "YES" if enable else ""

            # Preferred: update ENABLE="..." in place
            pat = re.compile(
                r'(<APP_ID\\b[^>]*\\bENABLE=\")([^\"]*)(\"[^>]*>\\s*' + re.escape(app_id) + r'\\s*</APP_ID>)',
                flags=re.IGNORECASE,
            )
            if pat.search(text):
                return pat.sub(rf"\\1{value}\\3", text)

            # Fallback: inject ENABLE attr if missing
            pat2 = re.compile(
                r'(<APP_ID\\b)([^>]*>\\s*' + re.escape(app_id) + r'\\s*</APP_ID>)',
                flags=re.IGNORECASE,
            )
            return pat2.sub(rf"\\1 ENABLE=\"{value}\"\\2", text)

        for app_id, enabled in pack_app_enable.items():
            updated = _set_enable_for_app(app_id, bool(enabled), updated)

        return updated

    async def _patch_ofs_bd_pack_xml_repo(
        self,
        host: str,
        username: str,
        password: str,
        *,
        repo_dir: str,
        pack_app_enable: dict[str, bool],
    ) -> dict:
        logs: list[str] = []
        find_cmd = (
            f"src=$(find {repo_dir} -type f -name 'OFS_BD_PACK.xml' ! -name '*_BEFORE*' -print | head -n 1); "
            "if [ -z \"$src\" ]; then echo 'NOT_FOUND'; exit 2; fi; "
            "echo $src"
        )
        src_result = await self.ssh_service.execute_command(host, username, password, find_cmd)
        if not src_result.get("success") or "NOT_FOUND" in (src_result.get("stdout") or ""):
            return {"success": False, "logs": logs, "error": "OFS_BD_PACK.xml not found in repo"}

        src_path = (src_result.get("stdout") or "").splitlines()[0].strip()
        logs.append(f"[INFO] Patching repo XML: {src_path}")

        read = await self._read_remote_file(host, username, password, src_path)
        if not read.get("success"):
            return {"success": False, "logs": logs, "error": read.get("error")}

        original = read.get("content", "")
        patched = self._patch_ofs_bd_pack_xml_content(original, pack_app_enable=pack_app_enable)

        if patched == original:
            logs.append("[INFO] No changes needed for OFS_BD_PACK.xml")
            return {"success": True, "logs": logs}

        ts = time.strftime("%Y%m%d_%H%M%S")
        await self.ssh_service.execute_command(host, username, password, f"cp -f {src_path} {src_path}.backup.{ts}", get_pty=True)
        write = await self._write_remote_file(host, username, password, src_path, patched)
        if not write.get("success"):
            return {"success": False, "logs": logs, "error": write.get("error")}

        logs.append("[OK] Updated OFS_BD_PACK.xml in repo (local clone)")
        return {"success": True, "logs": logs}

    def _patch_default_properties_content(self, content: str, *, updates: dict[str, Optional[str]]) -> str:
        lines = content.splitlines()

        start_idx = None
        end_idx = None
        for i, line in enumerate(lines):
            if "##Start: User input required for silent installer" in line:
                start_idx = i
            if "## End: User input required for silent installer" in line:
                end_idx = i
                break

        # If markers are not found, fall back to whole-file key replacement.
        if start_idx is None or end_idx is None or start_idx >= end_idx:
            start_idx = 0
            end_idx = len(lines)

        stop_idx = end_idx
        for i in range(start_idx, end_idx):
            if lines[i].strip().startswith("FSDF_UPLOAD_MODEL="):
                stop_idx = i  # do not modify beyond this
                break

        key_to_index: dict[str, int] = {}
        for i in range(start_idx, stop_idx):
            raw = lines[i]
            if raw.lstrip().startswith("#") or "=" not in raw:
                continue
            key = raw.split("=", 1)[0].strip()
            if key:
                key_to_index[key] = i

        insert_at = stop_idx
        for key, value in updates.items():
            if value is None:
                continue  # not provided, do not change
            new_line = f"{key}={value}"
            if key in key_to_index:
                lines[key_to_index[key]] = new_line
            else:
                lines.insert(insert_at, new_line)
                insert_at += 1

        # Preserve trailing newline behavior (most kits don't care).
        return "\n".join(lines) + "\n"

    async def _patch_default_properties_repo(
        self,
        host: str,
        username: str,
        password: str,
        *,
        repo_dir: str,
        updates: dict[str, Optional[str]],
    ) -> dict:
        logs: list[str] = []
        find_cmd = (
            f"src=$(find {repo_dir} -type f -name 'default.properties' ! -name '*_BEFORE*' -print | head -n 1); "
            "if [ -z \"$src\" ]; then echo 'NOT_FOUND'; exit 2; fi; "
            "echo $src"
        )
        src_result = await self.ssh_service.execute_command(host, username, password, find_cmd)
        if not src_result.get("success") or "NOT_FOUND" in (src_result.get("stdout") or ""):
            return {"success": False, "logs": logs, "error": "default.properties not found in repo"}

        src_path = (src_result.get("stdout") or "").splitlines()[0].strip()
        logs.append(f"[INFO] Patching repo properties: {src_path}")

        read = await self._read_remote_file(host, username, password, src_path)
        if not read.get("success"):
            return {"success": False, "logs": logs, "error": read.get("error")}

        original = read.get("content", "")
        patched = self._patch_default_properties_content(original, updates=updates)

        if patched == original:
            logs.append("[INFO] No changes needed for default.properties")
            return {"success": True, "logs": logs}

        ts = time.strftime("%Y%m%d_%H%M%S")
        await self.ssh_service.execute_command(host, username, password, f"cp -f {src_path} {src_path}.backup.{ts}", get_pty=True)
        write = await self._write_remote_file(host, username, password, src_path, patched)
        if not write.get("success"):
            return {"success": False, "logs": logs, "error": write.get("error")}

        logs.append("[OK] Updated default.properties in repo (local clone)")
        return {"success": True, "logs": logs}

    def _patch_ofsaai_install_config_content(self, content: str, *, updates: dict[str, Optional[str]]) -> tuple[str, list[str]]:
        updated = content
        warnings: list[str] = []

        for name, value in updates.items():
            if value is None:
                continue
            pat = re.compile(
                rf'(<InteractionVariable\\s+name=\"{re.escape(name)}\"\\s*>)(.*?)(</InteractionVariable>)',
                flags=re.DOTALL,
            )
            if not pat.search(updated):
                warnings.append(f"[WARN] InteractionVariable not found: {name}")
                continue
            updated = pat.sub(rf"\\1{value}\\3", updated)

        return updated, warnings

    async def _patch_ofsaai_install_config_repo(
        self,
        host: str,
        username: str,
        password: str,
        *,
        repo_dir: str,
        updates: dict[str, Optional[str]],
    ) -> dict:
        logs: list[str] = []
        find_cmd = (
            f"src=$(find {repo_dir} -type f -name 'OFSAAI_InstallConfig.xml' ! -name '*_BEFORE*' -print | head -n 1); "
            "if [ -z \"$src\" ]; then echo 'NOT_FOUND'; exit 2; fi; "
            "echo $src"
        )
        src_result = await self.ssh_service.execute_command(host, username, password, find_cmd)
        if not src_result.get("success") or "NOT_FOUND" in (src_result.get("stdout") or ""):
            return {"success": False, "logs": logs, "error": "OFSAAI_InstallConfig.xml not found in repo"}

        src_path = (src_result.get("stdout") or "").splitlines()[0].strip()
        logs.append(f"[INFO] Patching repo XML: {src_path}")

        read = await self._read_remote_file(host, username, password, src_path)
        if not read.get("success"):
            return {"success": False, "logs": logs, "error": read.get("error")}

        original = read.get("content", "")
        patched, warnings = self._patch_ofsaai_install_config_content(original, updates=updates)
        logs.extend(warnings)

        if patched == original:
            logs.append("[INFO] No changes needed for OFSAAI_InstallConfig.xml")
            return {"success": True, "logs": logs}

        ts = time.strftime("%Y%m%d_%H%M%S")
        await self.ssh_service.execute_command(host, username, password, f"cp -f {src_path} {src_path}.backup.{ts}", get_pty=True)
        write = await self._write_remote_file(host, username, password, src_path, patched)
        if not write.get("success"):
            return {"success": False, "logs": logs, "error": write.get("error")}

        logs.append("[OK] Updated OFSAAI_InstallConfig.xml in repo (local clone)")
        return {"success": True, "logs": logs}

    async def run_osc_schema_creator(
        self,
        host: str,
        username: str,
        password: str,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_prompt_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        # Support both directory spellings used in environments
        # (seen in docs): /u01/installer_kit and /u01/Installation_Kit
        osc_candidates = [
            "/u01/installer_kit/OFS_BD_PACK/schema_creator/bin/osc.sh",
            "/u01/Installation_Kit/OFS_BD_PACK/schema_creator/bin/osc.sh",
        ]
        osc_path = None
        for candidate in osc_candidates:
            check = await self.ssh_service.execute_command(host, username, password, f"test -x {candidate}")
            if check["success"]:
                osc_path = candidate
                break
        if osc_path is None:
            return {"success": False, "logs": [], "error": "osc.sh not found or not executable in expected locations"}

        # User requirement: run from schema_creator/bin and use lowercase -s
        # Some kits also accept -S; if -s fails, we retry with -S.
        inner_cmd = (
            "source /home/oracle/.profile >/dev/null 2>&1; "
            f"cd $(dirname {osc_path}) && "
            "(./osc.sh -s || ./osc.sh -S)"
        )
        if username == "oracle":
            command = f"bash -lc {shell_escape(inner_cmd)}"
        else:
            command = (
                "if command -v sudo >/dev/null 2>&1; then "
                f"sudo -u oracle bash -lc {shell_escape(inner_cmd)}; "
                "else "
                f"su - oracle -c {shell_escape('bash -lc ' + shell_escape(inner_cmd))}; "
                "fi"
            )

        result = await self.ssh_service.execute_interactive_command(
            host,
            username,
            password,
            command,
            on_output_callback=on_output_callback,
            on_prompt_callback=on_prompt_callback,
            timeout=3600,
        )
        if not result.get("success"):
            return {"success": False, "logs": [], "error": "osc.sh failed"}
        return {"success": True, "logs": ["[OK] osc.sh completed"]}

    async def run_environment_check(
        self,
        host: str,
        username: str,
        password: str,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_prompt_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        bin_dir = "/u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin"
        envcheck_path = f"{bin_dir}/envCheck.sh"
        verinfo_path = f"{bin_dir}/VerInfo.txt"

        check_cmd = f"test -x {envcheck_path}"
        check = await self.ssh_service.execute_command(host, username, password, check_cmd)
        if not check["success"]:
            return {"success": False, "logs": [], "error": "envCheck.sh not found or not executable"}

        # envCheck expects VerInfo.txt in the *current folder* (observed error: "VerInfo.txt file not present in current folder.")
        # Also, some kits ship with Linux_VERSION limited to 7,8; patch it to 7,8,9 to support OEL/RHEL 9 environments.
        # Note: envCheck commonly parses VerInfo with `cut -d'=' -f2`, so this must be a single '=' (not '==').
        preflight_cmd = (
            f"cd {bin_dir} || exit 1; "
            f"if [ -f {verinfo_path} ]; then "
            "echo '[INFO] VerInfo Linux_VERSION (before):'; "
            f"grep -n 'Linux_VERSION' {verinfo_path} || true; "
            f"if grep -Eq '^[[:space:]]*Linux_VERSION' {verinfo_path}; then "
            f"sed -i -E 's/^[[:space:]]*Linux_VERSION.*$/Linux_VERSION=7,8,9/' {verinfo_path}; "
            "else "
            f"echo 'Linux_VERSION=7,8,9' >> {verinfo_path}; "
            "fi; "
            "echo '[INFO] VerInfo Linux_VERSION (after):'; "
            f"grep -n 'Linux_VERSION' {verinfo_path} || true; "
            "else echo '[WARN] VerInfo.txt not found at expected path'; fi"
        )

        inner_cmd = (
            "source /home/oracle/.profile >/dev/null 2>&1; "
            f"{preflight_cmd}; "
            f"cd {bin_dir} && ./envCheck.sh -s"
        )
        if username == "oracle":
            command = f"bash -lc {shell_escape(inner_cmd)}"
        else:
            command = (
                "if command -v sudo >/dev/null 2>&1; then "
                f"sudo -u oracle bash -lc {shell_escape(inner_cmd)}; "
                "else "
                f"su - oracle -c {shell_escape('bash -lc ' + shell_escape(inner_cmd))}; "
                "fi"
            )

        result = await self.ssh_service.execute_interactive_command(
            host,
            username,
            password,
            command,
            on_output_callback=on_output_callback,
            on_prompt_callback=on_prompt_callback,
            timeout=3600,
        )
        if not result.get("success"):
            return {"success": False, "logs": [], "error": "envCheck.sh failed"}
        return {"success": True, "logs": ["[OK] envCheck completed"]}
