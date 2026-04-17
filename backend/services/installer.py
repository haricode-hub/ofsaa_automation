from typing import Any, Callable, Optional
import asyncio
import inspect
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

    async def download_and_extract_installer(
        self,
        host: str,
        username: str,
        password: str,
    ) -> dict:
        logs: list[str] = []
        target_dir = "/u01/Installation_Kit/BD_PACK_INSTALLATION_KIT"
        repo_dir = Config.REPO_DIR
        safe_dir_cfg = f"-c safe.directory={repo_dir}"

        # If already extracted, skip repo pull/clone and unzip. Proceed directly to scripts.
        await self.ssh_service.execute_command(host, username, password, f"mkdir -p {target_dir}", get_pty=True)
        check_existing = await self.validation.check_directory_exists(host, username, password, f"{target_dir}/OFS_BD_PACK")
        if check_existing.get("exists"):
            logs.append("[OK] Installer kit already extracted")
            return {"success": True, "logs": logs}

        git_auth_setup = self._git_auth_setup_cmd()
        cmd_prepare = (
            f"{git_auth_setup}"
            f"if [ -d {repo_dir}/.git ]; then "
            f"cd {repo_dir} && "
            f"(git -c http.sslVerify=false -c protocol.version=2 {safe_dir_cfg} pull --ff-only --no-tags || "
            f"(git config --global --add safe.directory {repo_dir} && git -c http.sslVerify=false -c protocol.version=2 {safe_dir_cfg} pull --ff-only --no-tags)); "
            f"else git -c http.sslVerify=false -c protocol.version=2 clone --depth 1 --single-branch --no-tags {Config.REPO_URL} {repo_dir}; fi"
        )
        result = await self.ssh_service.execute_command(host, username, password, cmd_prepare, timeout=1800, get_pty=True)
        if not result["success"]:
            if result.get("stdout"):
                logs.append(result["stdout"])
            if result.get("stderr"):
                logs.append(result["stderr"])
            return {"success": False, "logs": logs, "error": result.get("stderr") or "Failed to prepare installer repo"}
        logs.append("[OK] Repository ready for installer kit")

        zip_name = (Config.INSTALLER_ZIP_NAME or "").strip()
        if zip_name:
            find_zip_cmd = (
                f"installer_zip=$(find {repo_dir}/BD_PACK -maxdepth 1 -type f -name {shell_escape(zip_name)} -print | head -n 1); "
                "if [ -z \"$installer_zip\" ]; then echo 'INSTALLER_ZIP_NOT_FOUND'; exit 1; fi; "
                "echo $installer_zip"
            )
        else:
            find_zip_cmd = (
                f"installer_zip=$(ls -1t {repo_dir}/BD_PACK/*.zip 2>/dev/null | head -n 1); "
                "if [ -z \"$installer_zip\" ]; then echo 'INSTALLER_ZIP_NOT_FOUND'; exit 1; fi; "
                "echo $installer_zip"
            )
        zip_result = await self.ssh_service.execute_command(host, username, password, find_zip_cmd)
        if not zip_result["success"] or "INSTALLER_ZIP_NOT_FOUND" in zip_result.get("stdout", ""):
            return {"success": False, "logs": logs, "error": "Installer kit zip not found in repo"}

        zip_path = zip_result.get("stdout", "").splitlines()[0].strip()
        logs.append(f"[INFO] Installer zip found: {zip_path}")

        # Requirement: extraction must be performed as the 'oracle' OS user.
        unzip_cmd = (
            "if command -v bsdtar >/dev/null 2>&1; then "
            f"bsdtar -xf {shell_escape(zip_path)} -C {target_dir}; "
            "else "
            f"unzip -oq {shell_escape(zip_path)} -d {target_dir}; "
            "fi"
        )
        unzip_cmd_shell = f"bash -lc {shell_escape(unzip_cmd)}"
        if username == "oracle":
            unzip_as_oracle_cmd = f"mkdir -p {target_dir} && {unzip_cmd_shell}"
        else:
            # Ensure target dir is writable by oracle; prefer sudo when available.
            # Note: if the connected user is neither root nor sudo-capable, this will likely fail.
            unzip_as_oracle_cmd = (
                "if command -v sudo >/dev/null 2>&1; then "
                f"sudo mkdir -p {target_dir} && "
                f"sudo chown -R oracle:oinstall {target_dir} && "
                f"sudo chmod -R 775 {target_dir} && "
                f"(sudo chmod a+r {shell_escape(zip_path)} 2>/dev/null || true) && "
                f"sudo -u oracle {unzip_cmd_shell}; "
                "else "
                f"mkdir -p {target_dir} && "
                f"chown -R oracle:oinstall {target_dir} && "
                f"chmod -R 775 {target_dir} && "
                f"(chmod a+r {shell_escape(zip_path)} 2>/dev/null || true) && "
                f"su - oracle -c {shell_escape(unzip_cmd_shell)}; "
                "fi"
            )

        unzip_result = await self.ssh_service.execute_command(
            host, username, password, unzip_as_oracle_cmd, timeout=1800, get_pty=True
        )
        if not unzip_result["success"]:
            if unzip_result.get("stdout"):
                logs.append(unzip_result["stdout"])
            if unzip_result.get("stderr"):
                logs.append(unzip_result["stderr"])
            rc = unzip_result.get("returncode")
            return {
                "success": False,
                "logs": logs,
                "error": unzip_result.get("stderr")
                or unzip_result.get("stdout")
                or (f"Failed to unzip installer kit (rc={rc})" if rc is not None else "Failed to unzip installer kit"),
            }
        logs.append("[OK] Installer kit extracted")
        return {"success": True, "logs": logs}

    async def set_permissions(self, host: str, username: str, password: str) -> dict:
        cmd = "chmod -R 775 /u01/Installation_Kit/BD_PACK_INSTALLATION_KIT/OFS_BD_PACK"
        result = await self.ssh_service.execute_command(host, username, password, cmd, get_pty=True)
        if not result["success"]:
            return {"success": False, "logs": [], "error": result.get("stderr") or "Failed to set permissions"}
        return {"success": True, "logs": ["[OK] Permissions set on OFS_BD_PACK"]}

    async def cleanup_failed_fresh_installation(self, host: str, username: str, password: str) -> dict:
        logs: list[str] = []
        updated_repo_pathspecs: set[str] = set()

        # Kill all Java processes first to release file locks and ports
        logs.append("[CLEANUP] Killing all Java processes before cleanup...")
        kill_cmd = "pkill -9 -f java; killall -9 java 2>/dev/null; true"
        await self.ssh_service.execute_command(host, username, password, kill_cmd)
        import asyncio
        await asyncio.sleep(2)
        await self.ssh_service.execute_command(host, username, password, kill_cmd)
        logs.append("[CLEANUP] All Java processes killed")

        dirs = [
            # Only clean OFSAA runtime directories — keep installer kits intact
            "/u01/OFSAA/FICHOME",
            "/u01/OFSAA/FTPSHARE",
        ]
        dir_list = " ".join(shell_escape(d) for d in dirs)
        remove_cmd = (
            "if command -v sudo >/dev/null 2>&1; then "
            f"sudo rm -rf {dir_list}; "
            "else "
            f"rm -rf {dir_list}; "
            "fi"
        )
        remove_result = await self.ssh_service.execute_command(host, username, password, remove_cmd, timeout=1800, get_pty=True)
        if remove_result.get("success"):
            logs.append("[OK] Cleanup removed installation directories")
        else:
            if remove_result.get("stdout"):
                logs.append(remove_result["stdout"])
            if remove_result.get("stderr"):
                logs.append(remove_result["stderr"])
            logs.append("[WARN] Directory cleanup had errors")

        drop_inner = (
            "source /home/oracle/.profile >/dev/null 2>&1; "
            "cd /u01 || exit 1; "
            "if [ -f ./drop_ofsaa_objects.sh ]; then "
            "chmod +x ./drop_ofsaa_objects.sh 2>/dev/null || true; "
            "./drop_ofsaa_objects.sh; "
            "else "
            "echo 'DROP_SCRIPT_NOT_FOUND'; "
            "exit 0; "
            "fi"
        )
        if username == "oracle":
            drop_cmd = f"bash -lc {shell_escape(drop_inner)}"
        else:
            drop_cmd = (
                "if command -v sudo >/dev/null 2>&1; then "
                f"sudo -u oracle bash -lc {shell_escape(drop_inner)}; "
                "else "
                f"su - oracle -c {shell_escape('bash -lc ' + shell_escape(drop_inner))}; "
                "fi"
            )

        drop_result = await self.ssh_service.execute_command(host, username, password, drop_cmd, timeout=1800, get_pty=True)
        out = (drop_result.get("stdout") or "").strip()
        err = (drop_result.get("stderr") or "").strip()
        if "DROP_SCRIPT_NOT_FOUND" in out:
            logs.append("[WARN] /u01/drop_ofsaa_objects.sh not found; schema drop skipped")
        elif drop_result.get("success"):
            logs.append("[OK] Schema cleanup script executed: /u01/drop_ofsaa_objects.sh")
        else:
            if out:
                logs.append(out)
            if err:
                logs.append(err)
            logs.append("[WARN] Schema cleanup script failed")

        return {"success": True, "logs": logs}

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
        """
        Fetch required XML/properties from the git repo and place them into the extracted kit locations.
        """
        logs: list[str] = []
        updated_repo_pathspecs: set[str] = set()
        repo_dir = Config.REPO_DIR
        kit_dir = "/u01/Installation_Kit/BD_PACK_INSTALLATION_KIT/OFS_BD_PACK"
        safe_dir_cfg = f"-c safe.directory={repo_dir}"
        fast_config_apply = str(Config.FAST_CONFIG_APPLY).strip().lower() in {"1", "true", "yes", "y"}
        enable_config_push = str(Config.ENABLE_CONFIG_PUSH).strip().lower() in {"1", "true", "yes", "y"}

        # Ensure repo is present. In fast mode we skip pull to reduce startup delay for osc.sh step.
        git_auth_setup = self._git_auth_setup_cmd()
        if fast_config_apply:
            cmd_prepare_repo = (
                "mkdir -p /u01/Installation_Kit/BD_PACK_INSTALLATION_KIT && "
                f"{git_auth_setup}"
                f"if [ -d {repo_dir}/.git ]; then "
                "echo 'REPO_READY_FAST'; "
                f"else git -c http.sslVerify=false -c protocol.version=2 clone --depth 1 --single-branch --no-tags {Config.REPO_URL} {repo_dir}; fi"
            )
        else:
            cmd_prepare_repo = (
                "mkdir -p /u01/Installation_Kit/BD_PACK_INSTALLATION_KIT && "
                f"{git_auth_setup}"
                f"if [ -d {repo_dir}/.git ]; then "
                f"cd {repo_dir} && "
                f"(git -c http.sslVerify=false -c protocol.version=2 {safe_dir_cfg} pull --ff-only --no-tags || "
                f"(git config --global --add safe.directory {repo_dir} && git -c http.sslVerify=false -c protocol.version=2 {safe_dir_cfg} pull --ff-only --no-tags)); "
                f"else git -c http.sslVerify=false -c protocol.version=2 clone --depth 1 --single-branch --no-tags {Config.REPO_URL} {repo_dir}; fi"
            )
        repo_result = await self.ssh_service.execute_command(
            host, username, password, cmd_prepare_repo, timeout=1800, get_pty=True
        )
        if not repo_result["success"]:
            if repo_result.get("stdout"):
                logs.append(repo_result["stdout"])
            if repo_result.get("stderr"):
                logs.append(repo_result["stderr"])
            # Attempt a conservative fallback: fetch + hard reset to origin/<branch>
            try:
                fallback_cmd = (
                    f"cd {repo_dir} && git fetch origin && "
                    "BRANCH=$(git rev-parse --abbrev-ref HEAD) && "
                    "git reset --hard origin/$BRANCH"
                )
                fallback_result = await self.ssh_service.execute_command(host, username, password, fallback_cmd, timeout=120)
                if fallback_result.get("success"):
                    logs.append("[INFO] Repo fallback reset to origin/<branch> succeeded")
                else:
                    if fallback_result.get("stdout"):
                        logs.append(fallback_result.get("stdout"))
                    if fallback_result.get("stderr"):
                        logs.append(fallback_result.get("stderr"))
                    return {"success": False, "logs": logs, "error": repo_result.get("stderr") or "Failed to prepare repo"}
            except Exception:
                return {"success": False, "logs": logs, "error": repo_result.get("stderr") or "Failed to prepare repo"}
        logs.append("[OK] Repo prepared for config file fetch")
        if fast_config_apply:
            logs.append("[INFO] Fast config apply mode enabled: skipped git pull")

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

        # Always run patchers so UI values are deterministically synchronized into repo files.
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
        schema_changed = bool(patch_result.get("changed"))
        schema_src = patch_result.get("source_path")
        if isinstance(schema_src, str) and schema_src:
            updated_repo_pathspecs.add(self._repo_rel_path(repo_dir, schema_src))

        pack_changed = False
        if pack_app_enable is not None:
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
            pack_changed = bool(pack_patch.get("changed"))
            pack_src = pack_patch.get("source_path")
            if isinstance(pack_src, str) and pack_src:
                updated_repo_pathspecs.add(self._repo_rel_path(repo_dir, pack_src))

        silent_props = {
            "BASE_COUNTRY": prop_base_country,
            "DEFAULT_JURISDICTION": prop_default_jurisdiction,
            "SMTP_HOST": prop_smtp_host,
            "PARTITION_DATE_FORMAT": prop_partition_date_format,
            "DATADUMPDT_MINUS_0": prop_datadumpdt_minus_0,
            "ENDTHISWEEK_MINUS_00": prop_endthisweek_minus_00,
            "STARTNEXTMNTH_MINUS_00": prop_startnextmnth_minus_00,
            "ANALYST_DATA_SOURCE": prop_analyst_data_source,
            "MINER_DATA_SOURCE": prop_miner_data_source,
            "WEB_SERVICE_USER": prop_web_service_user,
            "WEB_SERVICE_PASSWORD": prop_web_service_password,
            "NLS_LENGTH_SEMANTICS": prop_nls_length_semantics,
            "CONFIGURE_OBIEE": prop_configure_obiee,
            "OBIEE_URL": prop_obiee_url,
            "SW_RMIPORT": prop_sw_rmiport,
            "BIG_DATA_ENABLE": prop_big_data_enable,
            "SQOOP_WORKING_DIR": prop_sqoop_working_dir,
            "SSH_AUTH_ALIAS": prop_ssh_auth_alias,
            "SSH_HOST_NAME": prop_ssh_host_name,
            "SSH_PORT": prop_ssh_port,

            "CSSOURCE": prop_cssource,
            "CSLOADTYPE": prop_csloadtype,
            "CRRSOURCE": prop_crrsource,
            "CRRLOADTYPE": prop_crrloadtype,
            "FSDF_UPLOAD_MODEL": prop_fsdf_upload_model,
        }
        props_patch = await self._patch_default_properties_repo(
            host, username, password, repo_dir=repo_dir, updates=silent_props
        )
        logs.extend(props_patch.get("logs", []))
        if not props_patch.get("success"):
            return {"success": False, "logs": logs, "error": props_patch.get("error") or "Failed to patch default.properties"}
        props_changed = bool(props_patch.get("changed"))
        props_src = props_patch.get("source_path")
        if isinstance(props_src, str) and props_src:
            updated_repo_pathspecs.add(self._repo_rel_path(repo_dir, props_src))

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
        aai_patch = await self._patch_ofsaai_install_config_repo(
            host, username, password, repo_dir=repo_dir, updates=aai_updates
        )
        logs.extend(aai_patch.get("logs", []))
        if not aai_patch.get("success"):
            return {"success": False, "logs": logs, "error": aai_patch.get("error") or "Failed to patch OFSAAI_InstallConfig.xml"}
        aai_changed = bool(aai_patch.get("changed"))
        aai_src = aai_patch.get("source_path")
        if isinstance(aai_src, str) and aai_src:
            updated_repo_pathspecs.add(self._repo_rel_path(repo_dir, aai_src))
        logs.append(
            "[INFO] UI sync summary: "
            f"OFS_BD_SCHEMA_IN.xml={'UPDATED' if schema_changed else 'UNCHANGED'}, "
            f"OFS_BD_PACK.xml={'UPDATED' if pack_changed else 'UNCHANGED'}, "
            f"default.properties={'UPDATED' if props_changed else 'UNCHANGED'}, "
            f"OFSAAI_InstallConfig.xml={'UPDATED' if aai_changed else 'UNCHANGED'}"
        )

        for filename, dest_path in mappings:
            src_path = await self._resolve_repo_bd_pack_file_path(
                host, username, password, repo_dir=repo_dir, filename=filename
            )
            if not src_path:
                return {"success": False, "logs": logs, "error": f"File not found in repo: {filename}"}
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

        if enable_config_push:
            push_result = await self._commit_and_push_repo_changes(
                host,
                username,
                password,
                repo_dir=repo_dir,
                commit_message="Update OFSAA installer configs from UI inputs",
                pathspecs=sorted(updated_repo_pathspecs) if updated_repo_pathspecs else ["BD_PACK"],
            )
            logs.extend(push_result.get("logs", []))
        else:
            logs.append("[INFO] Config push skipped (OFSAA_ENABLE_CONFIG_PUSH is disabled)")

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

    async def _resolve_repo_bd_pack_file_path(
        self,
        host: str,
        username: str,
        password: str,
        *,
        repo_dir: str,
        filename: str,
    ) -> Optional[str]:
        preferred_path = f"{repo_dir}/BD_PACK/{filename}"
        preferred_check = await self.ssh_service.execute_command(
            host, username, password, f"test -f {shell_escape(preferred_path)} && echo FOUND"
        )
        if preferred_check.get("success") and "FOUND" in (preferred_check.get("stdout") or ""):
            return preferred_path

        fallback_cmd = (
            f"src=$(find {repo_dir} -type f -name '{filename}' ! -name '*_BEFORE*' -print | head -n 1); "
            "if [ -z \"$src\" ]; then echo 'NOT_FOUND'; exit 0; fi; "
            "echo $src"
        )
        fallback_result = await self.ssh_service.execute_command(host, username, password, fallback_cmd)
        src_lines = (fallback_result.get("stdout") or "").splitlines()
        if not src_lines:
            return None
        first = src_lines[0].strip()
        if not first or first == "NOT_FOUND":
            return None
        return first

    async def _commit_and_push_repo_changes(
        self,
        host: str,
        username: str,
        password: str,
        *,
        repo_dir: str,
        commit_message: str,
        pathspecs: Optional[list[str]] = None,
    ) -> dict:
        logs: list[str] = []
        safe_dir_cfg = f"-c safe.directory={repo_dir}"
        git_auth_setup = self._git_auth_setup_cmd()
        pathspec_items = pathspecs or ["BD_PACK"]
        pathspec_str = " ".join(pathspec_items)
        cmd = (
            f"cd {repo_dir} >/dev/null 2>&1 || exit 1; "
            f"(git config --global --add safe.directory {repo_dir} >/dev/null 2>&1 || true); "
            f"if ! git {safe_dir_cfg} rev-parse --is-inside-work-tree >/dev/null 2>&1; then "
            "echo 'NOT_A_GIT_REPO'; exit 0; "
            "fi; "
            f"changes=$(git {safe_dir_cfg} status --porcelain -- {pathspec_str} 2>/dev/null | wc -l); "
            "if [ \"$changes\" = \"0\" ]; then echo 'NO_CHANGES'; exit 0; fi; "
            f"if ! git {safe_dir_cfg} remote get-url origin >/dev/null 2>&1; then echo 'NO_ORIGIN_REMOTE'; exit 0; fi; "
            f"{git_auth_setup}"
            "export GIT_TERMINAL_PROMPT=0; "
            f"git {safe_dir_cfg} add -u -- {pathspec_str} && "
            f"git {safe_dir_cfg} -c user.name='ofsaa-ui' -c user.email='ofsaa-ui@local' "
            f"commit -m {shell_escape(commit_message)} >/dev/null 2>&1 || true; "
            f"git -c http.sslVerify=false {safe_dir_cfg} push"
        )

        result = await self.ssh_service.execute_command(host, username, password, cmd, timeout=1800, get_pty=True)
        out = (result.get('stdout') or '').strip()
        err = (result.get('stderr') or '').strip()

        if "NOT_A_GIT_REPO" in out:
            logs.append("[INFO] Repo push skipped: not a git repo")
            return {"success": True, "logs": logs}
        if "NO_CHANGES" in out:
            logs.append("[INFO] Repo push skipped: no config changes")
            return {"success": True, "logs": logs}
        if "NO_ORIGIN_REMOTE" in out:
            logs.append("[INFO] Repo push skipped: origin remote not set")
            return {"success": True, "logs": logs}

        if not result.get("success"):
            if out:
                logs.append(out)
            if err:
                logs.append(err)
            logs.append("[WARN] Repo push failed; changes applied locally on the target host only")
            return {"success": True, "logs": logs}

        logs.append("[OK] Repo updated: pushed XML/properties changes to origin")
        return {"success": True, "logs": logs}

    def _repo_rel_path(self, repo_dir: str, src_path: str) -> str:
        base = repo_dir.rstrip("/")
        prefix = f"{base}/"
        if src_path.startswith(prefix):
            return src_path[len(prefix):]
        return src_path

    def _git_auth_setup_cmd(self) -> str:
        git_username = Config.GIT_USERNAME
        git_password = Config.GIT_PASSWORD
        if not git_username or not git_password:
            return ""

        safe_user = shell_escape(git_username)
        safe_pass = shell_escape(git_password)
        return (
            f"export OFSAA_GIT_USERNAME={safe_user}; "
            f"export OFSAA_GIT_PASSWORD={safe_pass}; "
            "askpass=$(mktemp) || exit 1; "
            "trap 'rm -f \"$askpass\"' EXIT; "
            "cat >\"$askpass\" <<'EOF'\n"
            "#!/bin/sh\n"
            "case \"$1\" in\n"
            "*Username*|*username*) printf '%s\\n' \"$OFSAA_GIT_USERNAME\";;\n"
            "*Password*|*password*) printf '%s\\n' \"$OFSAA_GIT_PASSWORD\";;\n"
            "*) printf '\\n';;\n"
            "esac\n"
            "EOF\n"
            "chmod 700 \"$askpass\"; "
            "export GIT_ASKPASS=\"$askpass\"; "
            "export GIT_TERMINAL_PROMPT=0; "
        )

        return updated

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

        if schema_jdbc_host is not None and schema_jdbc_port is not None and schema_jdbc_service is not None:
            jdbc_url = f"jdbc:oracle:thin:@//{schema_jdbc_host}:{schema_jdbc_port}/{schema_jdbc_service}"
            updated = re.sub(
                r"<JDBC_URL>.*?</JDBC_URL>",
                f"<JDBC_URL>{jdbc_url}</JDBC_URL>",
                updated,
                flags=re.DOTALL,
            )

        if schema_host is not None and str(schema_host).strip():
            updated = re.sub(r"<HOST>.*?</HOST>", f"<HOST>{schema_host}</HOST>", updated, flags=re.DOTALL)

        if schema_setup_env is not None:
            updated = re.sub(
                r'(<SETUPINFO\b[^>]*\bNAME=")[^"]*(")',
                rf"\g<1>{schema_setup_env}\g<2>",
                updated,
            )

        if schema_apply_same_for_all is not None:
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

        if schema_tablespace_autoextend is not None:
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

        if schema_external_directory_value is not None:
            updated = re.sub(
                r'(<DIRECTORY\b[^>]*\bID="OFS_BD_PACK_EXTERNAL_DIRECTORY_1"[^>]*\bVALUE=")[^"]*(")',
                rf"\g<1>{schema_external_directory_value}\g<2>",
                updated,
            )

        if schema_config_schema_name is not None:
            updated = re.sub(
                r'(<SCHEMA\b[^>]*\bTYPE="CONFIG"[^>]*\bNAME=")[^"]*(")',
                rf"\g<1>{schema_config_schema_name}\g<2>",
                updated,
            )

        if schema_atomic_schema_name is not None:
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

        src_path = await self._resolve_repo_bd_pack_file_path(
            host, username, password, repo_dir=repo_dir, filename="OFS_BD_SCHEMA_IN.xml"
        )
        if not src_path:
            return {"success": False, "logs": logs, "error": "OFS_BD_SCHEMA_IN.xml not found in repo"}
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
            return {"success": True, "logs": logs, "changed": False, "source_path": src_path}

        ts = time.strftime("%Y%m%d_%H%M%S")
        backup_cmd = f"cp -f {src_path} {src_path}.backup.{ts}"
        await self.ssh_service.execute_command(host, username, password, backup_cmd, get_pty=True)
        write = await self._write_remote_file(host, username, password, src_path, patched)
        if not write.get("success"):
            return {"success": False, "logs": logs, "error": write.get("error")}

        logs.append("[OK] Updated OFS_BD_SCHEMA_IN.xml in repo (local clone)")
        return {"success": True, "logs": logs, "changed": True, "source_path": src_path}

    def _patch_ofs_bd_pack_xml_content(self, content: str, *, pack_app_enable: dict[str, bool]) -> str:
        updated = content

        def _set_enable_for_app(app_id: str, enable: bool, text: str) -> str:
            value = "YES" if enable else ""

            # Preferred: update ENABLE="..." in place
            pat = re.compile(
                r'(<APP_ID\b[^>]*\bENABLE=")([^"]*)("[^>]*>\s*' + re.escape(app_id) + r'\s*</APP_ID>)',
                flags=re.IGNORECASE,
            )
            if pat.search(text):
                return pat.sub(rf"\1{value}\3", text)

            # Fallback: inject ENABLE attr if missing
            pat2 = re.compile(
                r'(<APP_ID\b)([^>]*>\s*' + re.escape(app_id) + r'\s*</APP_ID>)',
                flags=re.IGNORECASE,
            )
            return pat2.sub(rf'\1 ENABLE="{value}"\2', text)

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
        src_path = await self._resolve_repo_bd_pack_file_path(
            host, username, password, repo_dir=repo_dir, filename="OFS_BD_PACK.xml"
        )
        if not src_path:
            return {"success": False, "logs": logs, "error": "OFS_BD_PACK.xml not found in repo"}
        logs.append(f"[INFO] Patching repo XML: {src_path}")

        read = await self._read_remote_file(host, username, password, src_path)
        if not read.get("success"):
            return {"success": False, "logs": logs, "error": read.get("error")}

        original = read.get("content", "")
        patched = self._patch_ofs_bd_pack_xml_content(original, pack_app_enable=pack_app_enable)

        if patched == original:
            logs.append("[INFO] No changes needed for OFS_BD_PACK.xml")
            return {"success": True, "logs": logs, "changed": False, "source_path": src_path}

        ts = time.strftime("%Y%m%d_%H%M%S")
        await self.ssh_service.execute_command(host, username, password, f"cp -f {src_path} {src_path}.backup.{ts}", get_pty=True)
        write = await self._write_remote_file(host, username, password, src_path, patched)
        if not write.get("success"):
            return {"success": False, "logs": logs, "error": write.get("error")}

        logs.append("[OK] Updated OFS_BD_PACK.xml in repo (local clone)")
        return {"success": True, "logs": logs, "changed": True, "source_path": src_path}

    def _patch_default_properties_content(self, content: str, *, updates: dict[str, Optional[str]]) -> str:
        """
        Preserve exact template order/layout and rewrite only dynamically editable
        property lines (those containing both '=' and '--').
        Also supports reruns after comments were removed in a prior run by
        updating user-input-section keys if UI provided a non-None value.
        """
        lines = content.splitlines(keepends=True)
        out_lines: list[str] = []
        in_user_input_section = False

        for raw_line in lines:
            line_no_eol = raw_line.rstrip("\r\n")
            eol = raw_line[len(line_no_eol):]

            if "##Start: User input required for silent installer" in line_no_eol:
                in_user_input_section = True
                out_lines.append(raw_line)
                continue
            if "## End: User input required for silent installer" in line_no_eol:
                in_user_input_section = False
                out_lines.append(raw_line)
                continue

            # Keep headers and blank lines exactly as-is.
            if not line_no_eol or line_no_eol.startswith("##"):
                out_lines.append(raw_line)
                continue

            # Editable lines are dynamic: must contain '=' and '--'.
            if "=" in line_no_eol and "--" in line_no_eol:
                key_part, rhs = line_no_eol.split("=", 1)
                key = key_part.strip()
                value_before_comment = rhs.split("--", 1)[0].strip()
                user_value = updates.get(key)
                effective_value = value_before_comment if user_value is None else str(user_value)
                out_lines.append(f"{key}={effective_value}{eol}")
                continue

            # Rerun support: once inline comments are stripped, keep updating
            # user-input-section keys from UI without touching auto-populated section.
            if in_user_input_section and "=" in line_no_eol:
                key_part, rhs = line_no_eol.split("=", 1)
                key = key_part.strip()
                user_value = updates.get(key)
                if user_value is not None:
                    out_lines.append(f"{key}={str(user_value)}{eol}")
                    continue

            # All non-editable/system lines are copied byte-for-byte.
            out_lines.append(raw_line)

        return "".join(out_lines)

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
        src_path = await self._resolve_repo_bd_pack_file_path(
            host, username, password, repo_dir=repo_dir, filename="default.properties"
        )
        if not src_path:
            return {"success": False, "logs": logs, "error": "default.properties not found in repo"}
        logs.append(f"[INFO] Patching repo properties: {src_path}")

        read = await self._read_remote_file(host, username, password, src_path)
        if not read.get("success"):
            return {"success": False, "logs": logs, "error": read.get("error")}

        original = read.get("content", "")
        patched = self._patch_default_properties_content(original, updates=updates)

        if patched == original:
            logs.append("[INFO] No changes needed for default.properties")
            return {"success": True, "logs": logs, "changed": False, "source_path": src_path}

        ts = time.strftime("%Y%m%d_%H%M%S")
        await self.ssh_service.execute_command(host, username, password, f"cp -f {src_path} {src_path}.backup.{ts}", get_pty=True)
        write = await self._write_remote_file(host, username, password, src_path, patched)
        if not write.get("success"):
            return {"success": False, "logs": logs, "error": write.get("error")}

        logs.append("[OK] Updated default.properties in repo (local clone)")
        return {"success": True, "logs": logs, "changed": True, "source_path": src_path}

    def _patch_ofsaai_install_config_content(self, content: str, *, updates: dict[str, Optional[str]]) -> tuple[str, list[str]]:
        updated = content
        warnings: list[str] = []

        for name, value in updates.items():
            if value is None:
                continue
            pat = re.compile(
                rf'(<InteractionVariable\b[^>]*\bname\s*=\s*["\']{re.escape(name)}["\'][^>]*>)(.*?)(</InteractionVariable>)',
                flags=re.DOTALL | re.IGNORECASE,
            )
            if not pat.search(updated):
                warnings.append(f"[WARN] InteractionVariable not found: {name}")
                continue
            updated = pat.sub(rf"\g<1>{value}\g<3>", updated)

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
        src_path = await self._resolve_repo_bd_pack_file_path(
            host, username, password, repo_dir=repo_dir, filename="OFSAAI_InstallConfig.xml"
        )
        if not src_path:
            return {"success": False, "logs": logs, "error": "OFSAAI_InstallConfig.xml not found in repo"}
        logs.append(f"[INFO] Patching repo XML: {src_path}")

        read = await self._read_remote_file(host, username, password, src_path)
        if not read.get("success"):
            return {"success": False, "logs": logs, "error": read.get("error")}

        original = read.get("content", "")
        patched, warnings = self._patch_ofsaai_install_config_content(original, updates=updates)
        logs.extend(warnings)

        if patched == original:
            logs.append("[INFO] No changes needed for OFSAAI_InstallConfig.xml")
            return {"success": True, "logs": logs, "changed": False, "source_path": src_path}

        ts = time.strftime("%Y%m%d_%H%M%S")
        await self.ssh_service.execute_command(host, username, password, f"cp -f {src_path} {src_path}.backup.{ts}", get_pty=True)
        write = await self._write_remote_file(host, username, password, src_path, patched)
        if not write.get("success"):
            return {"success": False, "logs": logs, "error": write.get("error")}

        logs.append("[OK] Updated OFSAAI_InstallConfig.xml in repo (local clone)")
        return {"success": True, "logs": logs, "changed": True, "source_path": src_path}

    async def run_osc_schema_creator(
        self,
        host: str,
        username: str,
        password: str,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_prompt_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        osc_candidates = [
            "/u01/Installation_Kit/BD_PACK_INSTALLATION_KIT/OFS_BD_PACK/schema_creator/bin/osc.sh",
        ]
        osc_path = None
        for candidate in osc_candidates:
            check = await self.ssh_service.execute_command(host, username, password, f"test -x {candidate}")
            if check["success"]:
                osc_path = candidate
                break
        if osc_path is None:
            return {"success": False, "logs": [], "error": "osc.sh not found or not executable in expected locations"}

        schema_creator_dir = os.path.dirname(os.path.dirname(osc_path))
        pack_root_dir = os.path.dirname(schema_creator_dir)

        # Align Linux version compatibility for osc path too (not only envCheck path).
        # Some kits keep VerInfo.txt in different subfolders under OFS_BD_PACK.
        verinfo_preflight_cmd = (
            f"pack_root={shell_escape(pack_root_dir)}; "
            "patched=0; "
            "found=0; "
            "while IFS= read -r vf; do "
            "  found=1; "
            "  if grep -Eq '^[[:space:]]*Linux_VERSION' \"$vf\"; then "
            "    sed -i -E 's/^[[:space:]]*Linux_VERSION.*$/Linux_VERSION=7,8,9/' \"$vf\"; "
            "  else "
            "    echo 'Linux_VERSION=7,8,9' >> \"$vf\"; "
            "  fi; "
            "  patched=$((patched+1)); "
            "  echo \"[INFO] VerInfo patched: $vf\"; "
            "done < <(find \"$pack_root\" -type f -name 'VerInfo.txt' 2>/dev/null); "
            "if [ \"$found\" -eq 0 ]; then "
            "  echo '[WARN] VerInfo.txt not found under OFS_BD_PACK'; "
            "else "
            "  echo \"[INFO] VerInfo files patched count: $patched\"; "
            "fi"
        )

        # User requirement: run from schema_creator/bin and use lowercase -s
        # Some kits also accept -S; if -s fails, we retry with -S.
        inner_cmd = (
            "source /home/oracle/.profile >/dev/null 2>&1; "
            f"{verinfo_preflight_cmd}; "
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

        captured_lines: list[str] = []
        pending = ""

        async def output_collector(text: str) -> None:
            nonlocal pending
            if not text:
                return

            pending += text.replace("\r", "\n")
            parts = pending.split("\n")
            for line in parts[:-1]:
                cleaned = line.strip()
                if cleaned:
                    captured_lines.append(cleaned)
            pending = parts[-1]

            if on_output_callback is not None:
                forwarded = on_output_callback(text)
                if inspect.isawaitable(forwarded):
                    await forwarded

        result = await self.ssh_service.execute_interactive_command(
            host,
            username,
            password,
            command,
            on_output_callback=output_collector,
            on_prompt_callback=on_prompt_callback,
            timeout=3600,
        )
        tail = pending.strip()
        if tail:
            captured_lines.append(tail)

        fatal_runtime_patterns = [
            re.compile(r"Exception in thread \"main\"", re.IGNORECASE),
            re.compile(r"NoClassDefFoundError", re.IGNORECASE),
            re.compile(r"ClassNotFoundException", re.IGNORECASE),
            re.compile(r"\bSP2-0306\b", re.IGNORECASE),
            re.compile(r"\bSP2-0157\b", re.IGNORECASE),
            re.compile(r"\bORA-01017\b", re.IGNORECASE),
            re.compile(r"\bFAIL\b", re.IGNORECASE),
            re.compile(r"ERROR while applying", re.IGNORECASE),
        ]
        runtime_fatal_lines = [
            line for line in captured_lines if any(p.search(line) for p in fatal_runtime_patterns)
        ]
        if runtime_fatal_lines:
            logs = ["[ERROR] osc.sh runtime output contains fatal errors:"] + [
                f"[OSCOUT] {line}" for line in runtime_fatal_lines[:20]
            ]
            return {"success": False, "logs": logs, "error": "osc.sh runtime output contains fatal errors"}

        logs_dir = f"{schema_creator_dir}/logs"

        latest_log_cmd = (
            f"log_file=$(ls -1t {logs_dir}/* 2>/dev/null | head -n 1); "
            "if [ -z \"$log_file\" ]; then echo 'LOG_NOT_FOUND'; exit 0; fi; "
            "echo $log_file"
        )
        latest_log_result = await self.ssh_service.execute_command(host, username, password, latest_log_cmd)
        latest_log = (latest_log_result.get("stdout") or "").splitlines()[0].strip() if latest_log_result.get("stdout") else ""

        if not latest_log or latest_log == "LOG_NOT_FOUND":
            return {
                "success": False,
                "logs": ["[ERROR] osc.sh completed but schema_creator log file was not found"],
                "error": "schema_creator log file not found",
            }

        grep_cmd = f"grep -Ein 'ERROR|FAIL' {shell_escape(latest_log)} || true"
        grep_result = await self.ssh_service.execute_command(host, username, password, grep_cmd)
        matches = [line.strip() for line in (grep_result.get('stdout') or '').splitlines() if line.strip()]

        schema_exists_pattern = re.compile(r"(already\s+exist|already\s+exists|ora-00955|name is already used)", re.IGNORECASE)
        schema_exists_lines = [line for line in matches if schema_exists_pattern.search(line)]
        fatal_lines = [line for line in matches if line not in schema_exists_lines]

        if schema_exists_lines:
            logs = [f"[INFO] Checked log: {latest_log}"]
            logs.append("[WARN] Schema already exists. Skipping schema creation and moving to next step.")
            logs.extend([f"[OSCLOG] {line}" for line in schema_exists_lines])
            if fatal_lines:
                logs.extend([f"[OSCLOG] {line}" for line in fatal_lines])
                return {"success": False, "logs": logs, "error": "osc.sh log contains non-skippable ERROR/FAIL"}
            return {"success": True, "logs": logs}

        if fatal_lines:
            logs = [f"[ERROR] osc.sh log contains ERROR/FAIL in {latest_log}:"] + [f"[OSCLOG] {line}" for line in fatal_lines]
            return {"success": False, "logs": logs, "error": "osc.sh log contains ERROR/FAIL"}

        if not result.get("success"):
            return {"success": False, "logs": [f"[INFO] Checked log: {latest_log}"], "error": "osc.sh failed"}

        return {"success": True, "logs": [f"[INFO] Checked log: {latest_log}", "[OK] No Error , after osc.sh"]}

    async def run_setup_silent(
        self,
        host: str,
        username: str,
        password: str,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_prompt_callback: Optional[Callable[[str], Any]] = None,
        pack_app_enable: Optional[dict[str, bool]] = None,
        installation_mode: Optional[str] = None,

        install_sanc: Optional[bool] = None,
    ) -> dict:
        setup_candidates = [
            "/u01/Installation_Kit/BD_PACK_INSTALLATION_KIT/OFS_BD_PACK/bin/setup.sh",
        ]

        setup_path = None
        for candidate in setup_candidates:
            check = await self.ssh_service.execute_command(host, username, password, f"test -x {candidate}")
            if check["success"]:
                setup_path = candidate
                break
        if setup_path is None:
            return {"success": False, "logs": [], "error": "setup.sh not found or not executable in expected locations"}

        inner_cmd = (
            "source /home/oracle/.profile >/dev/null 2>&1; "
            f"cd $(dirname {setup_path}) && "
            "./setup.sh SILENT"
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

        # Capture output lines for failure-pattern detection
        captured_lines: list[str] = []
        pending_buf = ""

        async def _setup_output_collector(text: str) -> None:
            nonlocal pending_buf
            if not text:
                return
            pending_buf += text.replace("\r", "\n")
            parts = pending_buf.split("\n")
            for line in parts[:-1]:
                cleaned = line.strip()
                if cleaned:
                    captured_lines.append(cleaned)
            pending_buf = parts[-1]
            if on_output_callback is not None:
                forwarded = on_output_callback(text)
                if inspect.isawaitable(forwarded):
                    await forwarded

        result = await self.ssh_service.execute_interactive_command(
            host,
            username,
            password,
            command,
            on_output_callback=_setup_output_collector,
            on_prompt_callback=on_prompt_callback,
            timeout=36000,
        )
        tail = pending_buf.strip()
        if tail:
            captured_lines.append(tail)

        summary = await self._collect_installation_summary_after_setup(
            host,
            username,
            password,
            pack_app_enable=pack_app_enable,
            installation_mode=installation_mode,

            install_sanc=install_sanc,
        )
        summary_logs = summary.get("logs", [])

        # Detect application-level failures (setup.sh may exit 0 even on failure)
        setup_fatal_patterns = [
            re.compile(r"Installation terminated", re.IGNORECASE),
            re.compile(r"Pre-?Check failed", re.IGNORECASE),
            re.compile(r"APP Pre-?Check failed", re.IGNORECASE),
            re.compile(r"Installation\s+failed", re.IGNORECASE),
            re.compile(r"INSTALLATION.*FAIL", re.IGNORECASE),
            re.compile(r"Exception in thread", re.IGNORECASE),
            re.compile(r"NoClassDefFoundError", re.IGNORECASE),
            re.compile(r"ClassNotFoundException", re.IGNORECASE),
        ]
        fatal_output_lines = [
            line for line in captured_lines if any(p.search(line) for p in setup_fatal_patterns)
        ]

        if not result.get("success") or fatal_output_lines:
            error_detail = "setup.sh SILENT failed"
            if fatal_output_lines:
                error_detail = f"setup.sh SILENT application failure detected: {fatal_output_lines[0][:120]}"
            error_logs = []
            if fatal_output_lines:
                error_logs = ["[ERROR] setup.sh output contains fatal errors:"] + [
                    f"[SETUP] {line}" for line in fatal_output_lines[:10]
                ]
            return {"success": False, "logs": error_logs + summary_logs, "error": error_detail}

        logs = [f"[OK] setup.sh SILENT completed from {setup_path}"] + summary_logs
        return {"success": True, "logs": logs}

    async def _collect_installation_summary_after_setup(
        self,
        host: str,
        username: str,
        password: str,
        **_kwargs,
    ) -> dict:
        pack_log_path = "/u01/Installation_Kit/BD_PACK_INSTALLATION_KIT/OFS_BD_PACK/logs/Pack_Install.log"
        cmd = (
            f'log={shell_escape(pack_log_path)}; '
            'if [ -f "$log" ]; then '
            'tail -80 "$log"; '
            'else '
            'echo "FILE_NOT_FOUND"; '
            'fi'
        )
        result = await self.ssh_service.execute_command(host, username, password, cmd)
        out = (result.get("stdout") or "").strip()
        if not out or out == "FILE_NOT_FOUND":
            return {
                "success": True,
                "logs": [f"[WARN] Pack_Install.log not found at: {pack_log_path}"],
                "has_missing": True,
            }
        logs = ["", f"--- Pack_Install.log ({pack_log_path}) ---"] + out.splitlines()
        return {"success": True, "logs": logs, "has_missing": False}

    async def run_environment_check(
        self,
        host: str,
        username: str,
        password: str,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_prompt_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        bin_dir = "/u01/Installation_Kit/BD_PACK_INSTALLATION_KIT/OFS_BD_PACK/OFS_AAI/bin"
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

        captured_lines: list[str] = []
        pending = ""

        async def output_collector(text: str) -> None:
            nonlocal pending
            if not text:
                return

            # Keep a line-buffer copy so we can inspect envCheck output content.
            pending += text.replace("\r", "\n")
            parts = pending.split("\n")
            for line in parts[:-1]:
                cleaned = line.strip()
                if cleaned:
                    captured_lines.append(cleaned)
            pending = parts[-1]

            if on_output_callback is not None:
                forwarded = on_output_callback(text)
                if inspect.isawaitable(forwarded):
                    await forwarded

        result = await self.ssh_service.execute_interactive_command(
            host,
            username,
            password,
            command,
            on_output_callback=output_collector,
            on_prompt_callback=on_prompt_callback,
            timeout=3600,
        )
        if not result.get("success"):
            return {"success": False, "logs": [], "error": "envCheck.sh failed"}

        tail = pending.strip()
        if tail:
            captured_lines.append(tail)

        error_fail_pattern = re.compile(r"\b(?:ERROR|FAIL)\b", re.IGNORECASE)
        matched_lines = [line for line in captured_lines if error_fail_pattern.search(line)]

        if matched_lines:
            logs = ["[ERROR] envCheck detected ERROR/FAIL lines:"] + [f"[ENVCHK] {line}" for line in matched_lines]
            return {"success": False, "logs": logs, "error": "envCheck output contains ERROR/FAIL"}

        return {"success": True, "logs": ["[OK] No Error, envCheck SUCCESS"]}

    # ============== ECM MODULE METHODS ==============

    async def download_and_extract_ecm_installer(
        self,
        host: str,
        username: str,
        password: str,
    ) -> dict:
        """Download and extract ECM installer kit from ECM_PACK folder in repo."""
        logs: list[str] = []
        target_dir = "/u01/Installation_Kit/ECM_PACK_INSTALLATION_KIT"
        repo_dir = Config.REPO_DIR
        safe_dir_cfg = f"-c safe.directory={repo_dir}"

        # Check if already extracted
        await self.ssh_service.execute_command(host, username, password, f"mkdir -p {target_dir}", get_pty=True)
        check_existing = await self.validation.check_directory_exists(host, username, password, f"{target_dir}/OFS_ECM_PACK")
        if check_existing.get("exists"):
            logs.append("[OK] ECM installer kit already extracted")
            return {"success": True, "logs": logs}

        git_auth_setup = self._git_auth_setup_cmd()
        cmd_prepare = (
            f"{git_auth_setup}"
            f"if [ -d {repo_dir}/.git ]; then "
            f"cd {repo_dir} && "
            f"(git -c http.sslVerify=false -c protocol.version=2 {safe_dir_cfg} pull --ff-only --no-tags || "
            f"(git config --global --add safe.directory {repo_dir} && git -c http.sslVerify=false -c protocol.version=2 {safe_dir_cfg} pull --ff-only --no-tags)); "
            f"else git -c http.sslVerify=false -c protocol.version=2 clone --depth 1 --single-branch --no-tags {Config.REPO_URL} {repo_dir}; fi"
        )
        result = await self.ssh_service.execute_command(host, username, password, cmd_prepare, timeout=1800, get_pty=True)
        if not result["success"]:
            if result.get("stdout"):
                logs.append(result["stdout"])
            if result.get("stderr"):
                logs.append(result["stderr"])
            return {"success": False, "logs": logs, "error": result.get("stderr") or "Failed to prepare installer repo"}
        logs.append("[OK] Repository ready for ECM installer kit")

        # Find ECM zip file in ECM_PACK folder
        find_zip_cmd = (
            f"installer_zip=$(ls -1t {repo_dir}/ECM_PACK/*.zip 2>/dev/null | head -n 1); "
            "if [ -z \"$installer_zip\" ]; then echo 'INSTALLER_ZIP_NOT_FOUND'; exit 1; fi; "
            "echo $installer_zip"
        )
        zip_result = await self.ssh_service.execute_command(host, username, password, find_zip_cmd)
        if not zip_result["success"] or "INSTALLER_ZIP_NOT_FOUND" in zip_result.get("stdout", ""):
            return {"success": False, "logs": logs, "error": "ECM installer kit zip not found in repo ECM_PACK folder"}

        zip_path = zip_result.get("stdout", "").splitlines()[0].strip()
        logs.append(f"[INFO] ECM installer zip found: {zip_path}")

        # Extract as oracle user
        unzip_cmd = (
            "if command -v bsdtar >/dev/null 2>&1; then "
            f"bsdtar -xf {shell_escape(zip_path)} -C {target_dir}; "
            "else "
            f"unzip -oq {shell_escape(zip_path)} -d {target_dir}; "
            "fi"
        )
        unzip_cmd_shell = f"bash -lc {shell_escape(unzip_cmd)}"
        if username == "oracle":
            unzip_as_oracle_cmd = f"mkdir -p {target_dir} && {unzip_cmd_shell}"
        else:
            unzip_as_oracle_cmd = (
                "if command -v sudo >/dev/null 2>&1; then "
                f"sudo mkdir -p {target_dir} && "
                f"sudo chown -R oracle:oinstall {target_dir} && "
                f"sudo chmod -R 775 {target_dir} && "
                f"(sudo chmod a+r {shell_escape(zip_path)} 2>/dev/null || true) && "
                f"sudo -u oracle {unzip_cmd_shell}; "
                "else "
                f"mkdir -p {target_dir} && "
                f"chown -R oracle:oinstall {target_dir} && "
                f"chmod -R 775 {target_dir} && "
                f"(chmod a+r {shell_escape(zip_path)} 2>/dev/null || true) && "
                f"su - oracle -c {shell_escape(unzip_cmd_shell)}; "
                "fi"
            )

        unzip_result = await self.ssh_service.execute_command(
            host, username, password, unzip_as_oracle_cmd, timeout=1800, get_pty=True
        )
        if not unzip_result["success"]:
            if unzip_result.get("stdout"):
                logs.append(unzip_result["stdout"])
            if unzip_result.get("stderr"):
                logs.append(unzip_result["stderr"])
            rc = unzip_result.get("returncode")
            return {
                "success": False,
                "logs": logs,
                "error": unzip_result.get("stderr")
                or unzip_result.get("stdout")
                or (f"Failed to unzip ECM installer kit (rc={rc})" if rc is not None else "Failed to unzip ECM installer kit"),
            }
        logs.append("[OK] ECM installer kit extracted")

        # Set oracle ownership and 775 permissions on extracted folder
        ecm_pack_dir = f"{target_dir}/OFS_ECM_PACK"
        chown_chmod_cmd = f"chown -R oracle:oinstall {ecm_pack_dir} && chmod -R 775 {ecm_pack_dir}"
        perm_result = await self.ssh_service.execute_command(
            host, username, password, chown_chmod_cmd, timeout=300, get_pty=True
        )
        if perm_result["success"]:
            logs.append("[OK] ECM pack ownership set to oracle:oinstall with 775 permissions")
        else:
            logs.append(f"[WARN] Failed to set permissions: {perm_result.get('stderr', '')}")

        return {"success": True, "logs": logs}

    async def set_ecm_permissions(self, host: str, username: str, password: str) -> dict:
        """Set permissions and ownership on ECM kit directory."""
        cmd = "chown -R oracle:oinstall /u01/Installation_Kit/ECM_PACK_INSTALLATION_KIT/OFS_ECM_PACK && chmod -R 775 /u01/Installation_Kit/ECM_PACK_INSTALLATION_KIT/OFS_ECM_PACK"
        result = await self.ssh_service.execute_command(host, username, password, cmd, get_pty=True)
        if not result["success"]:
            return {"success": False, "logs": [], "error": result.get("stderr") or "Failed to set ECM permissions"}
        return {"success": True, "logs": ["[OK] Ownership and permissions set on OFS_ECM_PACK"]}

    async def _resolve_repo_ecm_pack_file_path(
        self,
        host: str,
        username: str,
        password: str,
        *,
        repo_dir: str,
        filename: str,
    ) -> Optional[str]:
        """Resolve file path in ECM_PACK folder of repo."""
        preferred_path = f"{repo_dir}/ECM_PACK/{filename}"
        preferred_check = await self.ssh_service.execute_command(
            host, username, password, f"test -f {shell_escape(preferred_path)} && echo FOUND"
        )
        if preferred_check.get("success") and "FOUND" in (preferred_check.get("stdout") or ""):
            return preferred_path

        fallback_cmd = (
            f"src=$(find {repo_dir}/ECM_PACK -type f -name '{filename}' ! -name '*_BEFORE*' -print | head -n 1); "
            "if [ -z \"$src\" ]; then echo 'NOT_FOUND'; exit 0; fi; "
            "echo $src"
        )
        fallback_result = await self.ssh_service.execute_command(host, username, password, fallback_cmd)
        src_lines = (fallback_result.get("stdout") or "").splitlines()
        if not src_lines:
            return None
        first = src_lines[0].strip()
        if not first or first == "NOT_FOUND":
            return None
        return first

    async def _resolve_repo_sanc_pack_file_path(
        self,
        host: str,
        username: str,
        password: str,
        *,
        repo_dir: str,
        filename: str,
    ) -> Optional[str]:
        """Resolve file path for SANC files in the repo.

        Prefer SANC-specific folders if they exist, but fall back to a generic
        search so layout changes in the Git repo don't break automation.
        """
        # First try a SANC-specific subfolder (SANC_PACK or SANC_INSTALLER_KIT_AUTOMATION)
        candidate_dirs = [
            f"{repo_dir}/SANC_PACK",
            f"{repo_dir}/SANC_INSTALLER_KIT_AUTOMATION",
        ]
        for base in candidate_dirs:
            preferred_path = f"{base}/{filename}"
            preferred_check = await self.ssh_service.execute_command(
                host,
                username,
                password,
                f"test -f {shell_escape(preferred_path)} && echo FOUND",
            )
            if preferred_check.get("success") and "FOUND" in (preferred_check.get("stdout") or ""):
                return preferred_path

        # Fallback: search anywhere under repo for the given filename, but avoid *_BEFORE copies.
        fallback_cmd = (
            f"src=$(find {repo_dir} -type f -name '{filename}' ! -name '*_BEFORE*' -print | head -n 1); "
            "if [ -z \"$src\" ]; then echo 'NOT_FOUND'; exit 0; fi; "
            "echo $src"
        )
        fallback_result = await self.ssh_service.execute_command(host, username, password, fallback_cmd)
        src_lines = (fallback_result.get("stdout") or "").splitlines()
        if not src_lines:
            return None
        first = src_lines[0].strip()
        if not first or first == "NOT_FOUND":
            return None
        return first

    def _patch_ofs_ecm_schema_in_content(
        self,
        content: str,
        *,
        ecm_schema_jdbc_host: Optional[str],
        ecm_schema_jdbc_port: Optional[int],
        ecm_schema_jdbc_service: Optional[str],
        ecm_schema_host: Optional[str],
        ecm_schema_setup_env: Optional[str],
        ecm_schema_prefix_schema_name: Optional[str],
        ecm_schema_apply_same_for_all: Optional[str],
        ecm_schema_default_password: Optional[str],
        ecm_schema_datafile_dir: Optional[str],
        ecm_schema_config_schema_name: Optional[str],
        ecm_schema_atomic_schema_name: Optional[str],
    ) -> str:
        """Patch OFS_ECM_SCHEMA_IN.xml content with provided values."""
        updated = content

        # Update JDBC_URL
        if ecm_schema_jdbc_host is not None and ecm_schema_jdbc_port is not None and ecm_schema_jdbc_service is not None:
            jdbc_url = f"jdbc:oracle:thin:@//{ecm_schema_jdbc_host}:{ecm_schema_jdbc_port}/{ecm_schema_jdbc_service}"
            updated = re.sub(
                r"<JDBC_URL>.*?</JDBC_URL>",
                f"<JDBC_URL>{jdbc_url}</JDBC_URL>",
                updated,
                flags=re.DOTALL,
            )

        # Update HOST
        if ecm_schema_host is not None and str(ecm_schema_host).strip():
            updated = re.sub(r"<HOST>.*?</HOST>", f"<HOST>{ecm_schema_host}</HOST>", updated, flags=re.DOTALL)

        # Update SETUPINFO NAME and PREFIX_SCHEMA_NAME
        if ecm_schema_setup_env is not None or ecm_schema_prefix_schema_name is not None:
            def replace_setupinfo(m: re.Match) -> str:
                tag = m.group(0)
                if ecm_schema_setup_env is not None:
                    tag = re.sub(r'NAME="[^"]*"', f'NAME="{ecm_schema_setup_env}"', tag)
                if ecm_schema_prefix_schema_name is not None:
                    tag = re.sub(r'PREFIX_SCHEMA_NAME="[^"]*"', f'PREFIX_SCHEMA_NAME="{ecm_schema_prefix_schema_name}"', tag)
                return tag
            updated = re.sub(r'<SETUPINFO\b[^>]*/>', replace_setupinfo, updated)

        # Update PASSWORD
        if ecm_schema_apply_same_for_all is not None:
            updated = re.sub(
                r'(<PASSWORD\b[^>]*\bAPPLYSAMEFORALL=")[^"]*(")',
                rf"\g<1>{ecm_schema_apply_same_for_all}\g<2>",
                updated,
            )

        if ecm_schema_default_password is not None:
            updated = re.sub(
                r'(<PASSWORD\b[^>]*\bDEFAULT=")[^"]*(")',
                rf"\g<1>{ecm_schema_default_password}\g<2>",
                updated,
            )

        # Update DATAFILE paths
        if ecm_schema_datafile_dir:
            base_dir = ecm_schema_datafile_dir.rstrip("/")

            def _repl_datafile(m: re.Match) -> str:
                prefix, path, suffix = m.group(1), m.group(2), m.group(3)
                filename = os.path.basename(path)
                return f'{prefix}{base_dir}/{filename}{suffix}'

            updated = re.sub(r'(\bDATAFILE=")([^"]+)(")', _repl_datafile, updated)

        # Update CONFIG schema name
        if ecm_schema_config_schema_name is not None:
            updated = re.sub(
                r'(<SCHEMA\b[^>]*\bTYPE="CONFIG"[^>]*\bNAME=")[^"]*(")',
                rf"\g<1>{ecm_schema_config_schema_name}\g<2>",
                updated,
            )

        # Update ATOMIC schema name
        if ecm_schema_atomic_schema_name is not None:
            updated = re.sub(
                r'(<SCHEMA\b[^>]*\bTYPE="ATOMIC"[^>]*\bNAME=")[^"]*(")',
                rf"\g<1>{ecm_schema_atomic_schema_name}\g<2>",
                updated,
            )

        return updated

    async def _patch_ofs_ecm_schema_in_repo(
        self,
        host: str,
        username: str,
        password: str,
        *,
        repo_dir: str,
        ecm_schema_jdbc_host: Optional[str],
        ecm_schema_jdbc_port: Optional[int],
        ecm_schema_jdbc_service: Optional[str],
        ecm_schema_host: Optional[str],
        ecm_schema_setup_env: Optional[str],
        ecm_schema_prefix_schema_name: Optional[str],
        ecm_schema_apply_same_for_all: Optional[str],
        ecm_schema_default_password: Optional[str],
        ecm_schema_datafile_dir: Optional[str],
        ecm_schema_config_schema_name: Optional[str],
        ecm_schema_atomic_schema_name: Optional[str],
    ) -> dict:
        """Patch OFS_ECM_SCHEMA_IN.xml in the repo."""
        logs: list[str] = []

        src_path = await self._resolve_repo_ecm_pack_file_path(
            host, username, password, repo_dir=repo_dir, filename="OFS_ECM_SCHEMA_IN.xml"
        )
        if not src_path:
            return {"success": False, "logs": logs, "error": "OFS_ECM_SCHEMA_IN.xml not found in repo ECM_PACK folder"}
        logs.append(f"[INFO] Patching ECM schema XML: {src_path}")

        read = await self._read_remote_file(host, username, password, src_path)
        if not read.get("success"):
            return {"success": False, "logs": logs, "error": read.get("error")}

        original = read.get("content", "")
        patched = self._patch_ofs_ecm_schema_in_content(
            original,
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
        )

        if patched == original:
            logs.append("[INFO] No changes needed for OFS_ECM_SCHEMA_IN.xml")
            return {"success": True, "logs": logs, "changed": False, "source_path": src_path}

        ts = time.strftime("%Y%m%d_%H%M%S")
        backup_cmd = f"cp -f {src_path} {src_path}.backup.{ts}"
        await self.ssh_service.execute_command(host, username, password, backup_cmd, get_pty=True)
        write = await self._write_remote_file(host, username, password, src_path, patched)
        if not write.get("success"):
            return {"success": False, "logs": logs, "error": write.get("error")}

        logs.append("[OK] Updated OFS_ECM_SCHEMA_IN.xml in repo")
        return {"success": True, "logs": logs, "changed": True, "source_path": src_path}

    # ============== SANC MODULE HELPERS ==============

    def _patch_ofs_sanc_schema_in_content(
        self,
        content: str,
        *,
        sanc_schema_jdbc_host: Optional[str],
        sanc_schema_jdbc_port: Optional[int],
        sanc_schema_jdbc_service: Optional[str],
        sanc_schema_host: Optional[str],
        sanc_schema_setup_env: Optional[str],
        sanc_schema_apply_same_for_all: Optional[str],
        sanc_schema_default_password: Optional[str],
        sanc_schema_datafile_dir: Optional[str],
        sanc_schema_tablespace_autoextend: Optional[str],
        sanc_schema_external_directory_value: Optional[str],
        sanc_schema_config_schema_name: Optional[str],
        sanc_schema_atomic_schema_name: Optional[str],
    ) -> str:
        """Patch OFS_SANC_SCHEMA_IN.xml content with UI-provided values.

        This mirrors the BD/ECM schema behaviour but targets the SANC schema file.
        """
        updated = content

        # JDBC URL
        if (
            sanc_schema_jdbc_host is not None
            and sanc_schema_jdbc_port is not None
            and sanc_schema_jdbc_service is not None
        ):
            jdbc_url = f"jdbc:oracle:thin:@//{sanc_schema_jdbc_host}:{sanc_schema_jdbc_port}/{sanc_schema_jdbc_service}"
            updated = re.sub(
                r"<JDBC_URL>.*?</JDBC_URL>",
                f"<JDBC_URL>{jdbc_url}</JDBC_URL>",
                updated,
                flags=re.DOTALL,
            )

        # HOST
        if sanc_schema_host is not None and str(sanc_schema_host).strip():
            updated = re.sub(r"<HOST>.*?</HOST>", f"<HOST>{sanc_schema_host}</HOST>", updated, flags=re.DOTALL)

        # SETUPINFO NAME
        if sanc_schema_setup_env is not None:
            updated = re.sub(
                r'(<SETUPINFO\b[^>]*\bNAME=")[^"]*(")',
                rf"\g<1>{sanc_schema_setup_env}\g<2>",
                updated,
            )

        # PASSWORD attributes
        if sanc_schema_apply_same_for_all is not None:
            updated = re.sub(
                r'(<PASSWORD\b[^>]*\bAPPLYSAMEFORALL=")[^"]*(")',
                rf"\g<1>{sanc_schema_apply_same_for_all}\g<2>",
                updated,
            )

        if sanc_schema_default_password is not None:
            updated = re.sub(
                r'(<PASSWORD\b[^>]*\bDEFAULT=")[^"]*(")',
                rf"\g<1>{sanc_schema_default_password}\g<2>",
                updated,
            )

        # TABLESPACE AUTOEXTEND
        if sanc_schema_tablespace_autoextend is not None:
            updated = re.sub(
                r'(\bAUTOEXTEND=")[^"]*(")',
                rf"\g<1>{sanc_schema_tablespace_autoextend}\g<2>",
                updated,
            )

        # DATAFILE directory
        if sanc_schema_datafile_dir:
            base_dir = sanc_schema_datafile_dir.rstrip("/")

            def _repl_datafile(m: re.Match) -> str:
                prefix, path, suffix = m.group(1), m.group(2), m.group(3)
                filename = os.path.basename(path)
                return f"{prefix}{base_dir}/{filename}{suffix}"

            updated = re.sub(r'(\bDATAFILE=")([^"]+)(")', _repl_datafile, updated)

        # DIRECTORY VALUE (no strict ID match – SANC XML may use its own IDs)
        if sanc_schema_external_directory_value is not None:
            updated = re.sub(
                r'(<DIRECTORY\b[^>]*\bVALUE=")[^"]*(")',
                rf"\g<1>{sanc_schema_external_directory_value}\g<2>",
                updated,
            )

        # CONFIG schema name
        if sanc_schema_config_schema_name is not None:
            updated = re.sub(
                r'(<SCHEMA\b[^>]*\bTYPE="CONFIG"[^>]*\bNAME=")[^"]*(")',
                rf"\g<1>{sanc_schema_config_schema_name}\g<2>",
                updated,
            )

        # ATOMIC schema name
        if sanc_schema_atomic_schema_name is not None:
            updated = re.sub(
                r'(<SCHEMA\b[^>]*\bTYPE="ATOMIC"[^>]*\bNAME=")[^"]*(")',
                rf"\g<1>{sanc_schema_atomic_schema_name}\g<2>",
                updated,
            )

        return updated

    async def _patch_ofs_sanc_schema_in_repo(
        self,
        host: str,
        username: str,
        password: str,
        *,
        repo_dir: str,
        sanc_schema_jdbc_host: Optional[str],
        sanc_schema_jdbc_port: Optional[int],
        sanc_schema_jdbc_service: Optional[str],
        sanc_schema_host: Optional[str],
        sanc_schema_setup_env: Optional[str],
        sanc_schema_apply_same_for_all: Optional[str],
        sanc_schema_default_password: Optional[str],
        sanc_schema_datafile_dir: Optional[str],
        sanc_schema_tablespace_autoextend: Optional[str],
        sanc_schema_external_directory_value: Optional[str],
        sanc_schema_config_schema_name: Optional[str],
        sanc_schema_atomic_schema_name: Optional[str],
    ) -> dict:
        """Patch OFS_SANC_SCHEMA_IN.xml in the repo."""
        logs: list[str] = []

        src_path = await self._resolve_repo_sanc_pack_file_path(
            host, username, password, repo_dir=repo_dir, filename="OFS_SANC_SCHEMA_IN.xml"
        )
        if not src_path:
            return {"success": False, "logs": logs, "error": "OFS_SANC_SCHEMA_IN.xml not found in repo"}
        logs.append(f"[INFO] Patching SANC schema XML: {src_path}")

        read = await self._read_remote_file(host, username, password, src_path)
        if not read.get("success"):
            return {"success": False, "logs": logs, "error": read.get("error")}

        original = read.get("content", "")
        patched = self._patch_ofs_sanc_schema_in_content(
            original,
            sanc_schema_jdbc_host=sanc_schema_jdbc_host,
            sanc_schema_jdbc_port=sanc_schema_jdbc_port,
            sanc_schema_jdbc_service=sanc_schema_jdbc_service,
            sanc_schema_host=sanc_schema_host,
            sanc_schema_setup_env=sanc_schema_setup_env,
            sanc_schema_apply_same_for_all=sanc_schema_apply_same_for_all,
            sanc_schema_default_password=sanc_schema_default_password,
            sanc_schema_datafile_dir=sanc_schema_datafile_dir,
            sanc_schema_tablespace_autoextend=sanc_schema_tablespace_autoextend,
            sanc_schema_external_directory_value=sanc_schema_external_directory_value,
            sanc_schema_config_schema_name=sanc_schema_config_schema_name,
            sanc_schema_atomic_schema_name=sanc_schema_atomic_schema_name,
        )

        if patched == original:
            logs.append("[INFO] No changes needed for OFS_SANC_SCHEMA_IN.xml")
            return {"success": True, "logs": logs, "changed": False, "source_path": src_path}

        ts = time.strftime("%Y%m%d_%H%M%S")
        backup_cmd = f"cp -f {src_path} {src_path}.backup.{ts}"
        await self.ssh_service.execute_command(host, username, password, backup_cmd, get_pty=True)
        write = await self._write_remote_file(host, username, password, src_path, patched)
        if not write.get("success"):
            return {"success": False, "logs": logs, "error": write.get("error")}

        logs.append("[OK] Updated OFS_SANC_SCHEMA_IN.xml in repo")
        return {"success": True, "logs": logs, "changed": True, "source_path": src_path}

    def _patch_sanc_properties_swiftinfo(self, content: str, swiftinfo: Optional[str]) -> str:
        """Patch or inject SWIFTINFO property in a default.properties-style file."""
        if swiftinfo is None:
            return content

        lines = content.splitlines()
        updated_lines: list[str] = []
        found = False
        for line in lines:
            if re.match(r"^\s*SWIFTINFO\s*=", line):
                updated_lines.append(f"SWIFTINFO={swiftinfo}")
                found = True
            else:
                updated_lines.append(line)
        if not found:
            updated_lines.append(f"SWIFTINFO={swiftinfo}")
        return "\n".join(updated_lines) + "\n"

    def _patch_ecm_default_properties_content(self, content: str, *, updates: dict[str, Optional[str]]) -> str:
        """Patch ECM default.properties content with provided values."""
        lines = content.splitlines(keepends=True)
        out_lines: list[str] = []

        for raw_line in lines:
            line_no_eol = raw_line.rstrip("\r\n")
            eol = raw_line[len(line_no_eol):]

            # Keep headers and blank lines
            if not line_no_eol or line_no_eol.startswith("##"):
                out_lines.append(raw_line)
                continue

            # Handle property lines
            if "=" in line_no_eol:
                key_part = line_no_eol.split("=", 1)[0].strip()
                user_value = updates.get(key_part)
                if user_value is not None:
                    # Strip inline comments if present
                    if "--" in line_no_eol:
                        out_lines.append(f"{key_part}={str(user_value)}{eol}")
                    else:
                        out_lines.append(f"{key_part}={str(user_value)}{eol}")
                    continue

            out_lines.append(raw_line)

        return "".join(out_lines)

    async def _patch_ecm_default_properties_repo(
        self,
        host: str,
        username: str,
        password: str,
        *,
        repo_dir: str,
        updates: dict[str, Optional[str]],
    ) -> dict:
        """Patch ECM default.properties in the repo."""
        logs: list[str] = []
        src_path = await self._resolve_repo_ecm_pack_file_path(
            host, username, password, repo_dir=repo_dir, filename="default.properties"
        )
        if not src_path:
            return {"success": False, "logs": logs, "error": "ECM default.properties not found in repo"}
        logs.append(f"[INFO] Patching ECM properties: {src_path}")

        read = await self._read_remote_file(host, username, password, src_path)
        if not read.get("success"):
            return {"success": False, "logs": logs, "error": read.get("error")}

        original = read.get("content", "")
        patched = self._patch_ecm_default_properties_content(original, updates=updates)

        if patched == original:
            logs.append("[INFO] No changes needed for ECM default.properties")
            return {"success": True, "logs": logs, "changed": False, "source_path": src_path}

        ts = time.strftime("%Y%m%d_%H%M%S")
        await self.ssh_service.execute_command(host, username, password, f"cp -f {src_path} {src_path}.backup.{ts}", get_pty=True)
        write = await self._write_remote_file(host, username, password, src_path, patched)
        if not write.get("success"):
            return {"success": False, "logs": logs, "error": write.get("error")}

        logs.append("[OK] Updated ECM default.properties in repo")
        return {"success": True, "logs": logs, "changed": True, "source_path": src_path}

    async def _patch_ecm_ofsaai_install_config_repo(
        self,
        host: str,
        username: str,
        password: str,
        *,
        repo_dir: str,
        updates: dict[str, Optional[str]],
    ) -> dict:
        """Patch ECM OFSAAI_InstallConfig.xml in the repo."""
        logs: list[str] = []
        src_path = await self._resolve_repo_ecm_pack_file_path(
            host, username, password, repo_dir=repo_dir, filename="OFSAAI_InstallConfig.xml"
        )
        if not src_path:
            return {"success": False, "logs": logs, "error": "ECM OFSAAI_InstallConfig.xml not found in repo"}
        logs.append(f"[INFO] Patching ECM OFSAAI XML: {src_path}")

        read = await self._read_remote_file(host, username, password, src_path)
        if not read.get("success"):
            return {"success": False, "logs": logs, "error": read.get("error")}

        original = read.get("content", "")
        patched, warnings = self._patch_ofsaai_install_config_content(original, updates=updates)
        logs.extend(warnings)

        if patched == original:
            logs.append("[INFO] No changes needed for ECM OFSAAI_InstallConfig.xml")
            return {"success": True, "logs": logs, "changed": False, "source_path": src_path}

        ts = time.strftime("%Y%m%d_%H%M%S")
        await self.ssh_service.execute_command(host, username, password, f"cp -f {src_path} {src_path}.backup.{ts}", get_pty=True)
        write = await self._write_remote_file(host, username, password, src_path, patched)
        if not write.get("success"):
            return {"success": False, "logs": logs, "error": write.get("error")}

        logs.append("[OK] Updated ECM OFSAAI_InstallConfig.xml in repo")
        return {"success": True, "logs": logs, "changed": True, "source_path": src_path}

    async def apply_ecm_config_files_from_repo(
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
        """
        Fetch ECM config files from git repo, patch with UI values, and copy to ECM kit locations.
        """
        logs: list[str] = []
        updated_repo_pathspecs: set[str] = set()
        repo_dir = Config.REPO_DIR
        kit_dir = "/u01/Installation_Kit/ECM_PACK_INSTALLATION_KIT/OFS_ECM_PACK"
        safe_dir_cfg = f"-c safe.directory={repo_dir}"
        fast_config_apply = str(Config.FAST_CONFIG_APPLY).strip().lower() in {"1", "true", "yes", "y"}
        enable_config_push = str(Config.ENABLE_CONFIG_PUSH).strip().lower() in {"1", "true", "yes", "y"}

        # Ensure repo is present
        git_auth_setup = self._git_auth_setup_cmd()
        if fast_config_apply:
            cmd_prepare_repo = (
                "mkdir -p /u01/Installation_Kit/ECM_PACK_INSTALLATION_KIT && "
                f"{git_auth_setup}"
                f"if [ -d {repo_dir}/.git ]; then "
                "echo 'REPO_READY_FAST'; "
                f"else git -c http.sslVerify=false -c protocol.version=2 clone --depth 1 --single-branch --no-tags {Config.REPO_URL} {repo_dir}; fi"
            )
        else:
            cmd_prepare_repo = (
                "mkdir -p /u01/Installation_Kit/ECM_PACK_INSTALLATION_KIT && "
                f"{git_auth_setup}"
                f"if [ -d {repo_dir}/.git ]; then "
                f"cd {repo_dir} && "
                f"(git -c http.sslVerify=false -c protocol.version=2 {safe_dir_cfg} pull --ff-only --no-tags || "
                f"(git config --global --add safe.directory {repo_dir} && git -c http.sslVerify=false -c protocol.version=2 {safe_dir_cfg} pull --ff-only --no-tags)); "
                f"else git -c http.sslVerify=false -c protocol.version=2 clone --depth 1 --single-branch --no-tags {Config.REPO_URL} {repo_dir}; fi"
            )
        repo_result = await self.ssh_service.execute_command(
            host, username, password, cmd_prepare_repo, timeout=1800, get_pty=True
        )
        if not repo_result["success"]:
            if repo_result.get("stdout"):
                logs.append(repo_result["stdout"])
            if repo_result.get("stderr"):
                logs.append(repo_result["stderr"])
            return {"success": False, "logs": logs, "error": repo_result.get("stderr") or "Failed to prepare repo for ECM"}
        logs.append("[OK] Repo prepared for ECM config file fetch")

        # ECM file mappings (source in repo -> destination in kit)
        mappings = [
            ("OFS_ECM_SCHEMA_IN.xml", f"{kit_dir}/schema_creator/conf/OFS_ECM_SCHEMA_IN.xml"),
            ("default.properties", f"{kit_dir}/OFS_NGECM/conf/default.properties"),
            ("OFSAAI_InstallConfig.xml", f"{kit_dir}/OFS_AAI/conf/OFSAAI_InstallConfig.xml"),
        ]

        # Sanity checks
        check_repo = await self.ssh_service.execute_command(host, username, password, f"test -d {repo_dir}")
        if not check_repo["success"]:
            return {"success": False, "logs": logs, "error": f"Repo dir not found: {repo_dir}"}
        check_kit = await self.ssh_service.execute_command(host, username, password, f"test -d {kit_dir}")
        if not check_kit["success"]:
            return {"success": False, "logs": logs, "error": f"ECM installer kit not found: {kit_dir}"}

        # Patch OFS_ECM_SCHEMA_IN.xml
        schema_patch = await self._patch_ofs_ecm_schema_in_repo(
            host, username, password,
            repo_dir=repo_dir,
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
        )
        logs.extend(schema_patch.get("logs", []))
        if not schema_patch.get("success"):
            return {"success": False, "logs": logs, "error": schema_patch.get("error")}
        schema_changed = bool(schema_patch.get("changed"))
        if schema_patch.get("source_path"):
            updated_repo_pathspecs.add(self._repo_rel_path(repo_dir, schema_patch["source_path"]))

        # Patch ECM default.properties
        # Apply defaults using target host IP dynamically
        base_url = f"http://{host}:7002"
        ecm_props = {
            "BASE_COUNTRY": ecm_prop_base_country or "US",
            "DEFAULT_JURISDICTION": ecm_prop_default_jurisdiction or "AMEA",
            "SMTP_HOST": ecm_prop_smtp_host or host,
            "WEB_SERVICE_USER": ecm_prop_web_service_user,
            "WEB_SERVICE_PASSWORD": ecm_prop_web_service_password,
            "NLS_LENGTH_SEMANTICS": ecm_prop_nls_length_semantics or "CHAR",
            "ANALYST_DATA_SOURCE": ecm_prop_analyst_data_source or "ANALYST",
            "MINER_DATA_SOURCE": ecm_prop_miner_data_source or "MINER",
            "CONFIGURE_OBIEE": ecm_prop_configure_obiee or "0",
            "FSDF_UPLOAD_MODEL": ecm_prop_fsdf_upload_model or "1",
            "AMLSOURCE": ecm_prop_amlsource or "FCCMATOMIC",
            "KYCSOURCE": ecm_prop_kycsource or "FCCMATOMIC",
            "CSSOURCE": ecm_prop_cssource or "FCCMATOMIC",
            "EXTERNALSYSTEMSOURCE": ecm_prop_externalsystemsource or "FCCMATOMIC",
            "TBAMLSOURCE": ecm_prop_tbamlsource or "FCCMATOMIC",
            "FATCASOURCE": ecm_prop_fatcasource or "",
            "OFSECM_DATASRCNAME": ecm_prop_ofsecm_datasrcname or "FCCMINFO",
            "COMN_GATWAY_DS": ecm_prop_comn_gateway_ds or "FCCMINFO",
            "T2JURL": ecm_prop_t2jurl or base_url,
            "J2TURL": ecm_prop_j2turl or base_url,
            "CMNGTWYURL": ecm_prop_cmngtwyurl or base_url,
            "BDURL": ecm_prop_bdurl or f"{base_url}/FICHOME",
            "OFSS_WLS_URL": ecm_prop_ofss_wls_url or base_url,
            "AAI_URL": ecm_prop_aai_url or f"{base_url}/FICHOME",
            "CS_URL": ecm_prop_cs_url or f"{base_url}/FICHOME",
            "ARACHNYS_NNS_SERVICE_URL": ecm_prop_arachnys_nns_service_url or f"{base_url}/FICHOME",
        }
        props_patch = await self._patch_ecm_default_properties_repo(
            host, username, password, repo_dir=repo_dir, updates=ecm_props
        )
        logs.extend(props_patch.get("logs", []))
        if not props_patch.get("success"):
            return {"success": False, "logs": logs, "error": props_patch.get("error")}
        props_changed = bool(props_patch.get("changed"))
        if props_patch.get("source_path"):
            updated_repo_pathspecs.add(self._repo_rel_path(repo_dir, props_patch["source_path"]))

        # Patch ECM OFSAAI_InstallConfig.xml
        ecm_aai_updates = {
            "WEBAPPSERVERTYPE": ecm_aai_webappservertype,
            "DBSERVER_IP": ecm_aai_dbserver_ip,
            "ORACLE_SID/SERVICE_NAME": ecm_aai_oracle_service_name,
            "ABS_DRIVER_PATH": ecm_aai_abs_driver_path,
            "OLAP_SERVER_IMPLEMENTATION": ecm_aai_olap_server_implementation,
            "SFTP_ENABLE": ecm_aai_sftp_enable,
            "FILE_TRANSFER_PORT": ecm_aai_file_transfer_port,
            "JAVAPORT": ecm_aai_javaport,
            "NATIVEPORT": ecm_aai_nativeport,
            "AGENTPORT": ecm_aai_agentport,
            "ICCPORT": ecm_aai_iccport,
            "ICCNATIVEPORT": ecm_aai_iccnativeport,
            "OLAPPORT": ecm_aai_olapport,
            "MSGPORT": ecm_aai_msgport,
            "ROUTERPORT": ecm_aai_routerport,
            "AMPORT": ecm_aai_amport,
            "HTTPS_ENABLE": ecm_aai_https_enable,
            "WEB_SERVER_IP": ecm_aai_web_server_ip,
            "WEB_SERVER_PORT": ecm_aai_web_server_port,
            "CONTEXT_NAME": ecm_aai_context_name,
            "WEBAPP_CONTEXT_PATH": ecm_aai_webapp_context_path,
            "WEB_LOCAL_PATH": ecm_aai_web_local_path,
            "WEBLOGIC_DOMAIN_HOME": ecm_aai_weblogic_domain_home,
            "OFSAAI_FTPSHARE_PATH": ecm_aai_ftspshare_path,
            "OFSAAI_SFTP_USER_ID": ecm_aai_sftp_user_id,
        }
        aai_patch = await self._patch_ecm_ofsaai_install_config_repo(
            host, username, password, repo_dir=repo_dir, updates=ecm_aai_updates
        )
        logs.extend(aai_patch.get("logs", []))
        if not aai_patch.get("success"):
            return {"success": False, "logs": logs, "error": aai_patch.get("error")}
        aai_changed = bool(aai_patch.get("changed"))
        if aai_patch.get("source_path"):
            updated_repo_pathspecs.add(self._repo_rel_path(repo_dir, aai_patch["source_path"]))

        logs.append(
            "[INFO] ECM UI sync summary: "
            f"OFS_ECM_SCHEMA_IN.xml={'UPDATED' if schema_changed else 'UNCHANGED'}, "
            f"default.properties={'UPDATED' if props_changed else 'UNCHANGED'}, "
            f"OFSAAI_InstallConfig.xml={'UPDATED' if aai_changed else 'UNCHANGED'}"
        )

        # Copy files from repo to kit locations
        for filename, dest_path in mappings:
            src_path = await self._resolve_repo_ecm_pack_file_path(
                host, username, password, repo_dir=repo_dir, filename=filename
            )
            if not src_path:
                return {"success": False, "logs": logs, "error": f"ECM file not found in repo: {filename}"}
            logs.append(f"[INFO] Using ECM {filename} from repo: {src_path}")

            # Backup existing file before replacing
            backup_cmd = (
                f"if [ -f {dest_path} ]; then "
                f"cp -f {dest_path} {dest_path}.backup.$(date +%Y%m%d_%H%M%S); "
                "fi"
            )
            await self.ssh_service.execute_command(host, username, password, backup_cmd, get_pty=True)

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
                    "error": copy_result.get("stderr") or f"Failed to copy ECM {filename} to kit",
                }
            logs.append(f"[OK] Updated ECM kit file: {dest_path}")

        # Fix ownership of entire ECM kit directory to oracle
        fix_ownership_cmd = "chown -R oracle:oinstall /u01/Installation_Kit/ECM_PACK_INSTALLATION_KIT/OFS_ECM_PACK && chmod -R 775 /u01/Installation_Kit/ECM_PACK_INSTALLATION_KIT/OFS_ECM_PACK"
        await self.ssh_service.execute_command(host, username, password, fix_ownership_cmd, get_pty=True)
        logs.append("[OK] Fixed ECM kit ownership to oracle:oinstall")

        # Push changes to git if enabled
        if enable_config_push:
            push_result = await self._commit_and_push_repo_changes(
                host, username, password,
                repo_dir=repo_dir,
                commit_message="Update ECM installer configs from UI inputs",
                pathspecs=sorted(updated_repo_pathspecs) if updated_repo_pathspecs else ["ECM_PACK"],
            )
            logs.extend(push_result.get("logs", []))
        else:
            logs.append("[INFO] ECM config push skipped (OFSAA_ENABLE_CONFIG_PUSH is disabled)")

        return {"success": True, "logs": logs}

    async def apply_sanc_config_files_from_repo(
        self,
        host: str,
        username: str,
        password: str,
        *,
        # OFS_SANC_SCHEMA_IN.xml params
        sanc_schema_jdbc_host: Optional[str] = None,
        sanc_schema_jdbc_port: Optional[int] = None,
        sanc_schema_jdbc_service: Optional[str] = None,
        sanc_schema_host: Optional[str] = None,
        sanc_schema_setup_env: Optional[str] = None,
        sanc_schema_apply_same_for_all: Optional[str] = None,
        sanc_schema_default_password: Optional[str] = None,
        sanc_schema_datafile_dir: Optional[str] = None,
        sanc_schema_tablespace_autoextend: Optional[str] = None,
        sanc_schema_external_directory_value: Optional[str] = None,
        sanc_schema_config_schema_name: Optional[str] = None,
        sanc_schema_atomic_schema_name: Optional[str] = None,
        # SANC default.properties SWIFTINFO values
        sanc_cs_swiftinfo: Optional[str] = None,
        sanc_tflt_swiftinfo: Optional[str] = None,
        # OFSAAI_InstallConfig.xml params (reuse BD Pack structure)
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
        """Fetch SANC config files from git repo, patch with UI values, and copy to SANC kit locations."""
        logs: list[str] = []
        updated_repo_pathspecs: set[str] = set()
        repo_dir = Config.REPO_DIR
        kit_dir = "/u01/Installation_Kit/SANC_PACK_INSTALLATION_KIT/OFS_SANC_PACK"
        safe_dir_cfg = f"-c safe.directory={repo_dir}"
        fast_config_apply = str(Config.FAST_CONFIG_APPLY).strip().lower() in {"1", "true", "yes", "y"}
        enable_config_push = str(Config.ENABLE_CONFIG_PUSH).strip().lower() in {"1", "true", "yes", "y"}

        # Ensure repo is present
        git_auth_setup = self._git_auth_setup_cmd()
        if fast_config_apply:
            cmd_prepare_repo = (
                "mkdir -p /u01/Installation_Kit/SANC_PACK_INSTALLATION_KIT && "
                f"{git_auth_setup}"
                f"if [ -d {repo_dir}/.git ]; then "
                "echo 'REPO_READY_FAST'; "
                f"else git -c http.sslVerify=false -c protocol.version=2 clone --depth 1 --single-branch --no-tags {Config.REPO_URL} {repo_dir}; fi"
            )
        else:
            cmd_prepare_repo = (
                "mkdir -p /u01/Installation_Kit/SANC_PACK_INSTALLATION_KIT && "
                f"{git_auth_setup}"
                f"if [ -d {repo_dir}/.git ]; then "
                f"cd {repo_dir} && "
                f"(git -c http.sslVerify=false -c protocol.version=2 {safe_dir_cfg} pull --ff-only --no-tags || "
                f"(git config --global --add safe.directory {repo_dir} && git -c http.sslVerify=false -c protocol.version=2 {safe_dir_cfg} pull --ff-only --no-tags)); "
                f"else git -c http.sslVerify=false -c protocol.version=2 clone --depth 1 --single-branch --no-tags {Config.REPO_URL} {repo_dir}; fi"
            )

        result = await self.ssh_service.execute_command(host, username, password, cmd_prepare_repo, timeout=1800, get_pty=True)
        if not result.get("success"):
            if result.get("stdout"):
                logs.append(result["stdout"])
            if result.get("stderr"):
                logs.append(result["stderr"])
            return {"success": False, "logs": logs, "error": result.get("stderr") or "Failed to prepare SANC installer repo"}
        logs.append("[OK] Repository ready for SANC configs")

        # 1) Patch SANC schema XML in repo and copy to kit
        sanc_schema_patch = await self._patch_ofs_sanc_schema_in_repo(
            host,
            username,
            password,
            repo_dir=repo_dir,
            sanc_schema_jdbc_host=sanc_schema_jdbc_host,
            sanc_schema_jdbc_port=sanc_schema_jdbc_port,
            sanc_schema_jdbc_service=sanc_schema_jdbc_service,
            sanc_schema_host=sanc_schema_host,
            sanc_schema_setup_env=sanc_schema_setup_env,
            sanc_schema_apply_same_for_all=sanc_schema_apply_same_for_all,
            sanc_schema_default_password=sanc_schema_default_password,
            sanc_schema_datafile_dir=sanc_schema_datafile_dir,
            sanc_schema_tablespace_autoextend=sanc_schema_tablespace_autoextend,
            sanc_schema_external_directory_value=sanc_schema_external_directory_value,
            sanc_schema_config_schema_name=sanc_schema_config_schema_name,
            sanc_schema_atomic_schema_name=sanc_schema_atomic_schema_name,
        )
        logs.extend(sanc_schema_patch.get("logs", []))
        if not sanc_schema_patch.get("success"):
            return {"success": False, "logs": logs, "error": sanc_schema_patch.get("error")}
        if sanc_schema_patch.get("changed") and sanc_schema_patch.get("source_path"):
            updated_repo_pathspecs.add("SANC")
            src_path = sanc_schema_patch["source_path"]
            dest_path = f"{kit_dir}/schema_creator/conf/OFS_SANC_SCHEMA_IN.xml"
            copy_cmd = f"mkdir -p {os.path.dirname(dest_path)} && cp -f {shell_escape(src_path)} {shell_escape(dest_path)}"
            copy_result = await self.ssh_service.execute_command(host, username, password, copy_cmd, get_pty=True)
            if not copy_result.get("success"):
                return {
                    "success": False,
                    "logs": logs,
                    "error": copy_result.get("stderr") or "Failed to copy OFS_SANC_SCHEMA_IN.xml to kit",
                }
            logs.append(f"[OK] Updated SANC kit schema: {dest_path}")

        # 2) Patch default.properties_CS (SWIFTINFO only)
        cs_src = await self._resolve_repo_sanc_pack_file_path(
            host, username, password, repo_dir=repo_dir, filename="default.properties_CS"
        )
        if cs_src:
            read_cs = await self._read_remote_file(host, username, password, cs_src)
            if not read_cs.get("success"):
                return {"success": False, "logs": logs, "error": read_cs.get("error")}
            original_cs = read_cs.get("content", "")
            patched_cs = self._patch_sanc_properties_swiftinfo(original_cs, sanc_cs_swiftinfo)
            if patched_cs != original_cs:
                ts = time.strftime("%Y%m%d_%H%M%S")
                await self.ssh_service.execute_command(host, username, password, f"cp -f {cs_src} {cs_src}.backup.{ts}", get_pty=True)
                write_cs = await self._write_remote_file(host, username, password, cs_src, patched_cs)
                if not write_cs.get("success"):
                    return {"success": False, "logs": logs, "error": write_cs.get("error")}
                logs.append("[OK] Updated default.properties_CS in repo")
                updated_repo_pathspecs.add("SANC")
            dest_cs = f"{kit_dir}/OFS_CS/conf/default.properties"
            copy_cs_cmd = f"mkdir -p {os.path.dirname(dest_cs)} && cp -f {shell_escape(cs_src)} {shell_escape(dest_cs)}"
            copy_cs = await self.ssh_service.execute_command(host, username, password, copy_cs_cmd, get_pty=True)
            if not copy_cs.get("success"):
                return {"success": False, "logs": logs, "error": copy_cs.get("stderr") or "Failed to copy CS default.properties to kit"}
            logs.append(f"[OK] Updated SANC kit CS default.properties: {dest_cs}")
        else:
            logs.append("[WARN] default.properties_CS not found in repo - CS SWIFTINFO will not be patched")

        # 3) Patch default.properties_TFLT (SWIFTINFO only)
        tflt_src = await self._resolve_repo_sanc_pack_file_path(
            host, username, password, repo_dir=repo_dir, filename="default.properties_TFLT"
        )
        if tflt_src:
            read_tflt = await self._read_remote_file(host, username, password, tflt_src)
            if not read_tflt.get("success"):
                return {"success": False, "logs": logs, "error": read_tflt.get("error")}
            original_tflt = read_tflt.get("content", "")
            patched_tflt = self._patch_sanc_properties_swiftinfo(original_tflt, sanc_tflt_swiftinfo)
            if patched_tflt != original_tflt:
                ts = time.strftime("%Y%m%d_%H%M%S")
                await self.ssh_service.execute_command(host, username, password, f"cp -f {tflt_src} {tflt_src}.backup.{ts}", get_pty=True)
                write_tflt = await self._write_remote_file(host, username, password, tflt_src, patched_tflt)
                if not write_tflt.get("success"):
                    return {"success": False, "logs": logs, "error": write_tflt.get("error")}
                logs.append("[OK] Updated default.properties_TFLT in repo")
                updated_repo_pathspecs.add("SANC")
            dest_tflt = f"{kit_dir}/OFS_TFLT/conf/default.properties"
            copy_tflt_cmd = f"mkdir -p {os.path.dirname(dest_tflt)} && cp -f {shell_escape(tflt_src)} {shell_escape(dest_tflt)}"
            copy_tflt = await self.ssh_service.execute_command(host, username, password, copy_tflt_cmd, get_pty=True)
            if not copy_tflt.get("success"):
                return {"success": False, "logs": logs, "error": copy_tflt.get("stderr") or "Failed to copy TFLT default.properties to kit"}
            logs.append(f"[OK] Updated SANC kit TFLT default.properties: {dest_tflt}")
        else:
            logs.append("[WARN] default.properties_TFLT not found in repo - TFLT SWIFTINFO will not be patched")

        # 4) OFSAAI_InstallConfig.xml – reuse BD Pack structure and copy into SANC kit
        aai_updates = {
            "WEBAPPSERVERTYPE": aai_webappservertype,
            "DBSERVER_IP": aai_dbserver_ip,
            "ORACLE_SID": aai_oracle_service_name,
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
        aai_patch = await self._patch_ofsaai_install_config_repo(
            host,
            username,
            password,
            repo_dir=repo_dir,
            updates=aai_updates,
        )
        logs.extend(aai_patch.get("logs", []))
        if not aai_patch.get("success"):
            return {"success": False, "logs": logs, "error": aai_patch.get("error")}
        if aai_patch.get("changed") and aai_patch.get("source_path"):
            updated_repo_pathspecs.add("OFS_AAI")
            aai_src = aai_patch["source_path"]
            dest_aai = f"{kit_dir}/OFS_AAI/conf/OFSAAI_InstallConfig.xml"
            copy_aai_cmd = f"mkdir -p {os.path.dirname(dest_aai)} && cp -f {shell_escape(aai_src)} {shell_escape(dest_aai)}"
            copy_aai = await self.ssh_service.execute_command(host, username, password, copy_aai_cmd, get_pty=True)
            if not copy_aai.get("success"):
                return {"success": False, "logs": logs, "error": copy_aai.get("stderr") or "Failed to copy OFSAAI_InstallConfig.xml to SANC kit"}
            logs.append(f"[OK] Updated SANC kit OFSAAI_InstallConfig.xml: {dest_aai}")

        # Fix ownership of SANC kit directory
        fix_ownership_cmd = "chown -R oracle:oinstall /u01/Installation_Kit/SANC_PACK_INSTALLATION_KIT/OFS_SANC_PACK && chmod -R 775 /u01/Installation_Kit/SANC_PACK_INSTALLATION_KIT/OFS_SANC_PACK"
        await self.ssh_service.execute_command(host, username, password, fix_ownership_cmd, get_pty=True)
        logs.append("[OK] Fixed SANC kit ownership to oracle:oinstall")

        # Push repo changes (same pattern as BD Pack and ECM)
        if enable_config_push:
            push_result = await self._commit_and_push_repo_changes(
                host,
                username,
                password,
                repo_dir=repo_dir,
                commit_message="Update SANC installer configs from UI inputs",
                pathspecs=sorted(updated_repo_pathspecs) if updated_repo_pathspecs else ["SANC_PACK"],
            )
            logs.extend(push_result.get("logs", []))
        else:
            logs.append("[INFO] SANC config push skipped (OFSAA_ENABLE_CONFIG_PUSH is disabled)")

        return {"success": True, "logs": logs}

    async def run_ecm_osc_schema_creator(
        self,
        host: str,
        username: str,
        password: str,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_prompt_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        """Run ECM schema creator osc.sh."""
        osc_path = "/u01/Installation_Kit/ECM_PACK_INSTALLATION_KIT/OFS_ECM_PACK/schema_creator/bin/osc.sh"
        
        check = await self.ssh_service.execute_command(host, username, password, f"test -x {osc_path}")
        if not check["success"]:
            return {"success": False, "logs": [], "error": "ECM osc.sh not found or not executable"}

        schema_creator_dir = os.path.dirname(os.path.dirname(osc_path))
        pack_root_dir = os.path.dirname(schema_creator_dir)

        # Patch VerInfo.txt for Linux version compatibility
        verinfo_preflight_cmd = (
            f"pack_root={shell_escape(pack_root_dir)}; "
            "patched=0; "
            "found=0; "
            "while IFS= read -r vf; do "
            "  found=1; "
            "  if grep -Eq '^[[:space:]]*Linux_VERSION' \"$vf\"; then "
            "    sed -i -E 's/^[[:space:]]*Linux_VERSION.*$/Linux_VERSION=7,8,9/' \"$vf\"; "
            "  else "
            "    echo 'Linux_VERSION=7,8,9' >> \"$vf\"; "
            "  fi; "
            "  patched=$((patched+1)); "
            "  echo \"[INFO] VerInfo patched: $vf\"; "
            "done < <(find \"$pack_root\" -type f -name 'VerInfo.txt' 2>/dev/null); "
            "if [ \"$found\" -eq 0 ]; then "
            "  echo '[WARN] VerInfo.txt not found under OFS_ECM_PACK'; "
            "else "
            "  echo \"[INFO] VerInfo files patched count: $patched\"; "
            "fi"
        )

        # Use script -c to provide a proper TTY for osc.sh which reads from /dev/tty
        osc_run_cmd = f"cd $(dirname {osc_path}) && (./osc.sh -s || ./osc.sh -S)"
        inner_cmd = (
            "source /home/oracle/.profile >/dev/null 2>&1; "
            f"{verinfo_preflight_cmd}; "
            f"script -q -c {shell_escape(osc_run_cmd)} /dev/null"
        )
        if username == "oracle":
            command = f"bash -lc {shell_escape(inner_cmd)}"
        else:
            command = f"su - oracle -c {shell_escape('bash -lc ' + shell_escape(inner_cmd))}"

        captured_lines: list[str] = []
        pending = ""

        async def output_collector(text: str) -> None:
            nonlocal pending
            if not text:
                return

            pending += text.replace("\r", "\n")
            parts = pending.split("\n")
            for line in parts[:-1]:
                cleaned = line.strip()
                if cleaned:
                    captured_lines.append(cleaned)
            pending = parts[-1]

            if on_output_callback is not None:
                forwarded = on_output_callback(text)
                if inspect.isawaitable(forwarded):
                    await forwarded

        result = await self.ssh_service.execute_interactive_command(
            host, username, password, command,
            on_output_callback=output_collector,
            on_prompt_callback=on_prompt_callback,
            timeout=3600,
        )
        tail = pending.strip()
        if tail:
            captured_lines.append(tail)

        # Check for fatal errors in output
        fatal_runtime_patterns = [
            re.compile(r"Exception in thread \"main\"", re.IGNORECASE),
            re.compile(r"NoClassDefFoundError", re.IGNORECASE),
            re.compile(r"ClassNotFoundException", re.IGNORECASE),
            re.compile(r"\bSP2-0306\b", re.IGNORECASE),
            re.compile(r"\bSP2-0157\b", re.IGNORECASE),
            re.compile(r"\bORA-01017\b", re.IGNORECASE),
            re.compile(r"\bFAIL\b", re.IGNORECASE),
            re.compile(r"ERROR while applying", re.IGNORECASE),
        ]
        runtime_fatal_lines = [
            line for line in captured_lines if any(p.search(line) for p in fatal_runtime_patterns)
        ]
        if runtime_fatal_lines:
            logs = ["[ERROR] ECM osc.sh runtime output contains fatal errors:"] + [
                f"[OSCOUT] {line}" for line in runtime_fatal_lines[:20]
            ]
            return {"success": False, "logs": logs, "error": "ECM osc.sh runtime output contains fatal errors"}

        # Check log file
        logs_dir = f"{schema_creator_dir}/logs"
        latest_log_cmd = (
            f"log_file=$(ls -1t {logs_dir}/* 2>/dev/null | head -n 1); "
            "if [ -z \"$log_file\" ]; then echo 'LOG_NOT_FOUND'; exit 0; fi; "
            "echo $log_file"
        )
        latest_log_result = await self.ssh_service.execute_command(host, username, password, latest_log_cmd)
        latest_log = (latest_log_result.get("stdout") or "").splitlines()[0].strip() if latest_log_result.get("stdout") else ""

        if not latest_log or latest_log == "LOG_NOT_FOUND":
            return {
                "success": False,
                "logs": ["[ERROR] ECM osc.sh completed but schema_creator log file was not found"],
                "error": "ECM schema_creator log file not found",
            }

        grep_cmd = f"grep -Ein 'ERROR|FAIL' {shell_escape(latest_log)} || true"
        grep_result = await self.ssh_service.execute_command(host, username, password, grep_cmd)
        matches = [line.strip() for line in (grep_result.get('stdout') or '').splitlines() if line.strip()]

        schema_exists_pattern = re.compile(r"(already\s+exist|already\s+exists|ora-00955|name is already used)", re.IGNORECASE)
        schema_exists_lines = [line for line in matches if schema_exists_pattern.search(line)]
        fatal_lines = [line for line in matches if line not in schema_exists_lines]

        if schema_exists_lines:
            logs = [f"[INFO] Checked ECM log: {latest_log}"]
            logs.append("[WARN] ECM Schema already exists. Skipping schema creation and moving to next step.")
            logs.extend([f"[OSCLOG] {line}" for line in schema_exists_lines])
            if fatal_lines:
                logs.extend([f"[OSCLOG] {line}" for line in fatal_lines])
                return {"success": False, "logs": logs, "error": "ECM osc.sh log contains non-skippable ERROR/FAIL"}
            return {"success": True, "logs": logs}

        if fatal_lines:
            logs = [f"[ERROR] ECM osc.sh log contains ERROR/FAIL in {latest_log}:"] + [f"[OSCLOG] {line}" for line in fatal_lines]
            return {"success": False, "logs": logs, "error": "ECM osc.sh log contains ERROR/FAIL"}

        if not result.get("success"):
            return {"success": False, "logs": [f"[INFO] Checked ECM log: {latest_log}"], "error": "ECM osc.sh failed"}

        return {"success": True, "logs": [f"[INFO] Checked ECM log: {latest_log}", "[OK] No Error, ECM osc.sh SUCCESS"]}

    async def run_ecm_setup_silent(
        self,
        host: str,
        username: str,
        password: str,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_prompt_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        """Run ECM setup.sh SILENT."""
        setup_path = "/u01/Installation_Kit/ECM_PACK_INSTALLATION_KIT/OFS_ECM_PACK/bin/setup.sh"

        check = await self.ssh_service.execute_command(host, username, password, f"test -x {setup_path}")
        if not check["success"]:
            return {"success": False, "logs": [], "error": "ECM setup.sh not found or not executable"}

        inner_cmd = (
            "source /home/oracle/.profile >/dev/null 2>&1; "
            f"cd $(dirname {setup_path}) && "
            "./setup.sh SILENT"
        )
        if username == "oracle":
            command = f"bash -lc {shell_escape(inner_cmd)}"
        else:
            command = f"su - oracle -c {shell_escape('bash -lc ' + shell_escape(inner_cmd))}"

        # Capture output lines for failure-pattern detection
        captured_lines: list[str] = []
        pending_buf = ""

        async def _ecm_setup_output_collector(text: str) -> None:
            nonlocal pending_buf
            if not text:
                return
            pending_buf += text.replace("\r", "\n")
            parts = pending_buf.split("\n")
            for line in parts[:-1]:
                cleaned = line.strip()
                if cleaned:
                    captured_lines.append(cleaned)
            pending_buf = parts[-1]
            if on_output_callback is not None:
                forwarded = on_output_callback(text)
                if inspect.isawaitable(forwarded):
                    await forwarded

        result = await self.ssh_service.execute_interactive_command(
            host, username, password, command,
            on_output_callback=_ecm_setup_output_collector,
            on_prompt_callback=on_prompt_callback,
            timeout=36000,
        )
        tail = pending_buf.strip()
        if tail:
            captured_lines.append(tail)

        # Collect installation summary
        pack_log_path = "/u01/Installation_Kit/ECM_PACK_INSTALLATION_KIT/OFS_ECM_PACK/logs/Pack_Install.log"
        summary_cmd = (
            f'log={shell_escape(pack_log_path)}; '
            'if [ -f "$log" ]; then '
            'tail -80 "$log"; '
            'else '
            'echo "FILE_NOT_FOUND"; '
            'fi'
        )
        summary_result = await self.ssh_service.execute_command(host, username, password, summary_cmd)
        summary_out = (summary_result.get("stdout") or "").strip()

        summary_logs: list[str] = []
        if not summary_out or summary_out == "FILE_NOT_FOUND":
            summary_logs.append(f"[WARN] ECM Pack_Install.log not found at: {pack_log_path}")
        else:
            summary_logs = ["", f"--- ECM Pack_Install.log ({pack_log_path}) ---"] + summary_out.splitlines()

        # Detect application-level failures (setup.sh may exit 0 even on failure)
        setup_fatal_patterns = [
            re.compile(r"Installation terminated", re.IGNORECASE),
            re.compile(r"Pre-?Check failed", re.IGNORECASE),
            re.compile(r"APP Pre-?Check failed", re.IGNORECASE),
            re.compile(r"Installation\s+failed", re.IGNORECASE),
            re.compile(r"INSTALLATION.*FAIL", re.IGNORECASE),
            re.compile(r"Exception in thread", re.IGNORECASE),
            re.compile(r"NoClassDefFoundError", re.IGNORECASE),
            re.compile(r"ClassNotFoundException", re.IGNORECASE),
        ]
        fatal_output_lines = [
            line for line in captured_lines if any(p.search(line) for p in setup_fatal_patterns)
        ]

        if not result.get("success") or fatal_output_lines:
            error_detail = "ECM setup.sh SILENT failed"
            if fatal_output_lines:
                error_detail = f"ECM setup.sh SILENT application failure detected: {fatal_output_lines[0][:120]}"
            error_logs = []
            if fatal_output_lines:
                error_logs = ["[ERROR] ECM setup.sh output contains fatal errors:"] + [
                    f"[SETUP] {line}" for line in fatal_output_lines[:10]
                ]
            return {"success": False, "logs": error_logs + summary_logs, "error": error_detail}

        logs = [f"[OK] ECM setup.sh SILENT completed from {setup_path}"] + summary_logs
        return {"success": True, "logs": logs}

    # ============== SANC MODULE METHODS ==============

    async def download_and_extract_sanc_installer(
        self,
        host: str,
        username: str,
        password: str,
    ) -> dict:
        """Download and extract SANC installer kit from SANC folder in repo."""
        logs: list[str] = []
        target_dir = "/u01/Installation_Kit/SANC_PACK_INSTALLATION_KIT"
        repo_dir = Config.REPO_DIR
        safe_dir_cfg = f"-c safe.directory={repo_dir}"

        # Check if already extracted
        await self.ssh_service.execute_command(host, username, password, f"mkdir -p {target_dir}", get_pty=True)
        check_existing = await self.validation.check_directory_exists(
            host, username, password, f"{target_dir}/OFS_SANC_PACK"
        )
        if check_existing.get("exists"):
            logs.append("[OK] SANC installer kit already extracted")
            return {"success": True, "logs": logs}

        git_auth_setup = self._git_auth_setup_cmd()
        cmd_prepare = (
            f"{git_auth_setup}"
            f"if [ -d {repo_dir}/.git ]; then "
            f"cd {repo_dir} && "
            f"(git -c http.sslVerify=false -c protocol.version=2 {safe_dir_cfg} pull --ff-only --no-tags || "
            f"(git config --global --add safe.directory {repo_dir} && git -c http.sslVerify=false -c protocol.version=2 {safe_dir_cfg} pull --ff-only --no-tags)); "
            f"else git -c http.sslVerify=false -c protocol.version=2 clone --depth 1 --single-branch --no-tags {Config.REPO_URL} {repo_dir}; fi"
        )
        result = await self.ssh_service.execute_command(host, username, password, cmd_prepare, timeout=1800, get_pty=True)
        if not result.get("success"):
            if result.get("stdout"):
                logs.append(result["stdout"])
            if result.get("stderr"):
                logs.append(result["stderr"])
            return {"success": False, "logs": logs, "error": result.get("stderr") or "Failed to prepare SANC installer repo"}
        logs.append("[OK] Repository ready for SANC installer kit")

        # Prefer zip inside SANC_PACK; fall back to first SANC*.zip anywhere
        find_zip_cmd = (
            f"installer_zip=$(ls -1t {repo_dir}/SANC_PACK/*.zip 2>/dev/null | head -n 1); "
            "if [ -z \"$installer_zip\" ]; then "
            f"installer_zip=$(find {repo_dir} -maxdepth 4 -type f -name '*SANC*.zip' 2>/dev/null | head -n 1); "
            "fi; "
            "if [ -z \"$installer_zip\" ]; then echo 'INSTALLER_ZIP_NOT_FOUND'; exit 1; fi; "
            "echo $installer_zip"
        )
        zip_result = await self.ssh_service.execute_command(host, username, password, find_zip_cmd)
        if not zip_result.get("success") or "INSTALLER_ZIP_NOT_FOUND" in (zip_result.get("stdout") or ""):
            return {"success": False, "logs": logs, "error": "SANC installer kit zip not found in repo"}

        zip_path = (zip_result.get("stdout") or "").splitlines()[0].strip()
        logs.append(f"[INFO] SANC installer zip found: {zip_path}")

        # Extract as oracle user
        unzip_cmd = (
            "if command -v bsdtar >/dev/null 2>&1; then "
            f"bsdtar -xf {shell_escape(zip_path)} -C {target_dir}; "
            "else "
            f"unzip -oq {shell_escape(zip_path)} -d {target_dir}; "
            "fi"
        )
        unzip_cmd_shell = f"bash -lc {shell_escape(unzip_cmd)}"
        if username == "oracle":
            unzip_as_oracle_cmd = f"mkdir -p {target_dir} && {unzip_cmd_shell}"
        else:
            unzip_as_oracle_cmd = (
                "if command -v sudo >/dev/null 2>&1; then "
                f"sudo mkdir -p {target_dir} && "
                f"sudo chown -R oracle:oinstall {target_dir} && "
                f"sudo chmod -R 775 {target_dir} && "
                f"(sudo chmod a+r {shell_escape(zip_path)} 2>/dev/null || true) && "
                f"sudo -u oracle {unzip_cmd_shell}; "
                "else "
                f"mkdir -p {target_dir} && "
                f"chown -R oracle:oinstall {target_dir} && "
                f"chmod -R 775 {target_dir} && "
                f"(chmod a+r {shell_escape(zip_path)} 2>/dev/null || true) && "
                f"su - oracle -c {shell_escape(unzip_cmd_shell)}; "
                "fi"
            )

        unzip_result = await self.ssh_service.execute_command(
            host, username, password, unzip_as_oracle_cmd, timeout=1800, get_pty=True
        )
        if not unzip_result.get("success"):
            if unzip_result.get("stdout"):
                logs.append(unzip_result["stdout"])
            if unzip_result.get("stderr"):
                logs.append(unzip_result["stderr"])
            rc = unzip_result.get("returncode")
            return {
                "success": False,
                "logs": logs,
                "error": unzip_result.get("stderr")
                or unzip_result.get("stdout")
                or (f"Failed to unzip SANC installer kit (rc={rc})" if rc is not None else "Failed to unzip SANC installer kit"),
            }
        logs.append("[OK] SANC installer kit extracted")

        # Ensure SANC pack folder has correct ownership/permissions
        sanc_pack_dir = f"{target_dir}/OFS_SANC_PACK"
        chown_chmod_cmd = f"chown -R oracle:oinstall {sanc_pack_dir} && chmod -R 775 {sanc_pack_dir}"
        perm_result = await self.ssh_service.execute_command(
            host, username, password, chown_chmod_cmd, timeout=300, get_pty=True
        )
        if perm_result.get("success"):
            logs.append("[OK] SANC pack ownership set to oracle:oinstall with 775 permissions")
        else:
            logs.append(f"[WARN] Failed to set SANC permissions: {perm_result.get('stderr', '')}")

        return {"success": True, "logs": logs}

    async def set_sanc_permissions(self, host: str, username: str, password: str) -> dict:
        """Set permissions and ownership on SANC kit directory."""
        cmd = "chown -R oracle:oinstall /u01/Installation_Kit/SANC_PACK_INSTALLATION_KIT/OFS_SANC_PACK && chmod -R 775 /u01/Installation_Kit/SANC_PACK_INSTALLATION_KIT/OFS_SANC_PACK"
        result = await self.ssh_service.execute_command(host, username, password, cmd, get_pty=True)
        if not result.get("success"):
            return {"success": False, "logs": [], "error": result.get("stderr") or "Failed to set SANC permissions"}
        return {"success": True, "logs": ["[OK] Ownership and permissions set on OFS_SANC_PACK"]}

    async def run_sanc_osc_schema_creator(
        self,
        host: str,
        username: str,
        password: str,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_prompt_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        """Run SANC schema creator osc.sh."""
        osc_path = "/u01/Installation_Kit/SANC_PACK_INSTALLATION_KIT/OFS_SANC_PACK/schema_creator/bin/osc.sh"

        check = await self.ssh_service.execute_command(host, username, password, f"test -x {osc_path}")
        if not check.get("success"):
            return {"success": False, "logs": [], "error": "SANC osc.sh not found or not executable"}

        schema_creator_dir = os.path.dirname(os.path.dirname(osc_path))
        pack_root_dir = os.path.dirname(schema_creator_dir)

        verinfo_preflight_cmd = (
            f"pack_root={shell_escape(pack_root_dir)}; "
            "patched=0; "
            "found=0; "
            "while IFS= read -r vf; do "
            "  found=1; "
            "  if grep -Eq '^[[:space:]]*Linux_VERSION' \"$vf\"; then "
            "    sed -i -E 's/^[[:space:]]*Linux_VERSION.*$/Linux_VERSION=7,8,9/' \"$vf\"; "
            "  else "
            "    echo 'Linux_VERSION=7,8,9' >> \"$vf\"; "
            "  fi; "
            "  patched=$((patched+1)); "
            "  echo \"[INFO] VerInfo patched: $vf\"; "
            "done < <(find \"$pack_root\" -type f -name 'VerInfo.txt' 2>/dev/null); "
            "if [ \"$found\" -eq 0 ]; then "
            "  echo '[WARN] VerInfo.txt not found under OFS_SANC_PACK'; "
            "else "
            "  echo \"[INFO] VerInfo files patched count: $patched\"; "
            "fi"
        )

        osc_run_cmd = f"cd $(dirname {osc_path}) && (./osc.sh -s || ./osc.sh -S)"
        inner_cmd = (
            "source /home/oracle/.profile >/dev/null 2>&1; "
            f"{verinfo_preflight_cmd}; "
            f"script -q -c {shell_escape(osc_run_cmd)} /dev/null"
        )
        if username == "oracle":
            command = f"bash -lc {shell_escape(inner_cmd)}"
        else:
            command = f"su - oracle -c {shell_escape('bash -lc ' + shell_escape(inner_cmd))}"

        captured_lines: list[str] = []
        pending = ""

        async def _sanc_osc_output_collector(text: str) -> None:
            nonlocal pending
            if not text:
                return

            pending += text.replace("\r", "\n")
            parts = pending.split("\n")
            for line in parts[:-1]:
                cleaned = line.strip()
                if cleaned:
                    captured_lines.append(cleaned)
            pending = parts[-1]

            if on_output_callback is not None:
                forwarded = on_output_callback(text)
                if inspect.isawaitable(forwarded):
                    await forwarded

        result = await self.ssh_service.execute_interactive_command(
            host,
            username,
            password,
            command,
            on_output_callback=_sanc_osc_output_collector,
            on_prompt_callback=on_prompt_callback,
            timeout=3600,
        )
        tail = pending.strip()
        if tail:
            captured_lines.append(tail)

        fatal_runtime_patterns = [
            re.compile(r"Exception in thread \"main\"", re.IGNORECASE),
            re.compile(r"NoClassDefFoundError", re.IGNORECASE),
            re.compile(r"ClassNotFoundException", re.IGNORECASE),
            re.compile(r"\bSP2-0306\b", re.IGNORECASE),
            re.compile(r"\bSP2-0157\b", re.IGNORECASE),
            re.compile(r"\bORA-01017\b", re.IGNORECASE),
            re.compile(r"\bFAIL\b", re.IGNORECASE),
            re.compile(r"ERROR while applying", re.IGNORECASE),
        ]
        runtime_fatal_lines = [
            line for line in captured_lines if any(p.search(line) for p in fatal_runtime_patterns)
        ]
        if runtime_fatal_lines:
            logs = ["[ERROR] SANC osc.sh runtime output contains fatal errors:"] + [
                f"[OSCOUT] {line}" for line in runtime_fatal_lines[:20]
            ]
            return {"success": False, "logs": logs, "error": "SANC osc.sh runtime output contains fatal errors"}

        logs_dir = f"{schema_creator_dir}/logs"
        latest_log_cmd = (
            f"log_file=$(ls -1t {logs_dir}/* 2>/dev/null | head -n 1); "
            "if [ -z \"$log_file\" ]; then echo 'LOG_NOT_FOUND'; exit 0; fi; "
            "echo $log_file"
        )
        latest_log_result = await self.ssh_service.execute_command(host, username, password, latest_log_cmd)
        latest_log = (latest_log_result.get("stdout") or "").splitlines()[0].strip() if latest_log_result.get("stdout") else ""

        if not latest_log or latest_log == "LOG_NOT_FOUND":
            return {
                "success": False,
                "logs": ["[ERROR] SANC osc.sh completed but schema_creator log file was not found"],
                "error": "SANC schema_creator log file not found",
            }

        grep_cmd = f"grep -Ein 'ERROR|FAIL' {shell_escape(latest_log)} || true"
        grep_result = await self.ssh_service.execute_command(host, username, password, grep_cmd)
        matches = [line.strip() for line in (grep_result.get("stdout") or "").splitlines() if line.strip()]

        schema_exists_pattern = re.compile(r"(already\s+exist|already\s+exists|ora-00955|name is already used)", re.IGNORECASE)
        schema_exists_lines = [line for line in matches if schema_exists_pattern.search(line)]
        fatal_lines = [line for line in matches if line not in schema_exists_lines]

        if schema_exists_lines:
            logs = [f"[INFO] Checked SANC log: {latest_log}"]
            logs.append("[WARN] SANC schema already exists. Skipping schema creation and moving to next step.")
            logs.extend([f"[OSCLOG] {line}" for line in schema_exists_lines])
            if fatal_lines:
                logs.extend([f"[OSCLOG] {line}" for line in fatal_lines])
                return {"success": False, "logs": logs, "error": "SANC osc.sh log contains non-skippable ERROR/FAIL"}
            return {"success": True, "logs": logs}

        if fatal_lines:
            logs = [
                f"[ERROR] SANC osc.sh log contains ERROR/FAIL in {latest_log}:"
            ] + [f"[OSCLOG] {line}" for line in fatal_lines]
            return {"success": False, "logs": logs, "error": "SANC osc.sh log contains ERROR/FAIL"}

        if not result.get("success"):
            return {
                "success": False,
                "logs": [f"[INFO] Checked SANC log: {latest_log}"],
                "error": "SANC osc.sh failed",
            }

        return {"success": True, "logs": [f"[INFO] Checked SANC log: {latest_log}", "[OK] No Error, SANC osc.sh SUCCESS"]}

    async def run_sanc_setup_silent(
        self,
        host: str,
        username: str,
        password: str,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_prompt_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        """Run SANC setup.sh SILENT."""
        setup_path = "/u01/Installation_Kit/SANC_PACK_INSTALLATION_KIT/OFS_SANC_PACK/bin/setup.sh"

        check = await self.ssh_service.execute_command(host, username, password, f"test -x {setup_path}")
        if not check.get("success"):
            return {"success": False, "logs": [], "error": "SANC setup.sh not found or not executable"}

        inner_cmd = (
            "source /home/oracle/.profile >/dev/null 2>&1; "
            f"cd $(dirname {setup_path}) && "
            "./setup.sh SILENT"
        )
        if username == "oracle":
            command = f"bash -lc {shell_escape(inner_cmd)}"
        else:
            command = f"su - oracle -c {shell_escape('bash -lc ' + shell_escape(inner_cmd))}"

        captured_lines: list[str] = []
        pending_buf = ""

        async def _sanc_setup_output_collector(text: str) -> None:
            nonlocal pending_buf
            if not text:
                return
            pending_buf += text.replace("\r", "\n")
            parts = pending_buf.split("\n")
            for line in parts[:-1]:
                cleaned = line.strip()
                if cleaned:
                    captured_lines.append(cleaned)
            pending_buf = parts[-1]
            if on_output_callback is not None:
                forwarded = on_output_callback(text)
                if inspect.isawaitable(forwarded):
                    await forwarded

        result = await self.ssh_service.execute_interactive_command(
            host,
            username,
            password,
            command,
            on_output_callback=_sanc_setup_output_collector,
            on_prompt_callback=on_prompt_callback,
            timeout=36000,
        )
        tail = pending_buf.strip()
        if tail:
            captured_lines.append(tail)

        pack_log_path = "/u01/Installation_Kit/SANC_PACK_INSTALLATION_KIT/OFS_SANC_PACK/logs/Pack_Install.log"
        summary_cmd = (
            f"log={shell_escape(pack_log_path)}; "
            "if [ -f \"$log\" ]; then "
            "tail -80 \"$log\"; "
            "else "
            "echo \"FILE_NOT_FOUND\"; "
            "fi"
        )
        summary_result = await self.ssh_service.execute_command(host, username, password, summary_cmd)
        summary_out = (summary_result.get("stdout") or "").strip()

        summary_logs: list[str] = []
        if not summary_out or summary_out == "FILE_NOT_FOUND":
            summary_logs.append(f"[WARN] SANC Pack_Install.log not found at: {pack_log_path}")
        else:
            summary_logs = ["", f"--- SANC Pack_Install.log ({pack_log_path}) ---"] + summary_out.splitlines()

        setup_fatal_patterns = [
            re.compile(r"Installation terminated", re.IGNORECASE),
            re.compile(r"Pre-?Check failed", re.IGNORECASE),
            re.compile(r"APP Pre-?Check failed", re.IGNORECASE),
            re.compile(r"Installation\s+failed", re.IGNORECASE),
            re.compile(r"INSTALLATION.*FAIL", re.IGNORECASE),
            re.compile(r"Exception in thread", re.IGNORECASE),
            re.compile(r"NoClassDefFoundError", re.IGNORECASE),
            re.compile(r"ClassNotFoundException", re.IGNORECASE),
        ]
        fatal_output_lines = [
            line for line in captured_lines if any(p.search(line) for p in setup_fatal_patterns)
        ]

        if not result.get("success") or fatal_output_lines:
            error_detail = "SANC setup.sh SILENT failed"
            if fatal_output_lines:
                error_detail = f"SANC setup.sh SILENT application failure detected: {fatal_output_lines[0][:120]}"
            error_logs: list[str] = []
            if fatal_output_lines:
                error_logs = ["[ERROR] SANC setup.sh output contains fatal errors:"] + [
                    f"[SETUP] {line}" for line in fatal_output_lines[:10]
                ]
            return {"success": False, "logs": error_logs + summary_logs, "error": error_detail}

        logs = [f"[OK] SANC setup.sh SILENT completed from {setup_path}"] + summary_logs
        return {"success": True, "logs": logs}

    # ============== DATABASE PRIVILEGES ==============

    async def grant_database_privileges(
        self,
        host: str,
        username: str,
        password: str,
        db_sys_password: str,
        db_jdbc_host: str,
        db_jdbc_port: int,
        db_jdbc_service: str,
        config_schema_name: str,
        atomic_schema_name: str,
        on_subtask_callback: Optional[Callable[[str], Any]] = None,
        on_output_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        """
        Grant database privileges to ATOMIC and CONFIG schema users via SQL scripts from Git.
        
        Fetches SQL files from Git repo:
        - ofsaa_auto_installation/configuration/privileges_atomic_user.sql
        - ofsaa_auto_installation/configuration/privileges_config_user.sql
        
        Executes via: sqlplus "sys/<password>@<host>:<port>/<service> as sysdba"
        """
        logs: list[str] = []
        repo_dir = Config.REPO_DIR
        config_dir = f"{repo_dir}/configuration"

        # STEP 1-pre: Unlock Oracle accounts (ORA-28000 prevention)
        await self._call_subtask_callback(
            on_subtask_callback,
            "[FICHOME] : Unlocking Oracle schema accounts"
        )
        unlock_sql = (
            f"ALTER USER {atomic_schema_name} ACCOUNT UNLOCK;\n"
            f"ALTER USER {config_schema_name} ACCOUNT UNLOCK;\n"
            "EXIT;\n"
        )
        sqlplus_login_unlock = (
            f"sys/{db_sys_password}@{db_jdbc_host}:{db_jdbc_port}/{db_jdbc_service} as sysdba"
        )
        unlock_cmd = (
            f"source /home/oracle/.profile >/dev/null 2>&1; "
            f"sqlplus {shell_escape(sqlplus_login_unlock)} <<'EOUNLOCK'\n{unlock_sql}EOUNLOCK"
        )
        unlock_result = await self.ssh_service.execute_command(
            host, username, password, unlock_cmd, timeout=120, get_pty=True
        )
        unlock_stdout = (unlock_result.get("stdout") or "").strip()
        for line in unlock_stdout.splitlines():
            cleaned = line.strip()
            if cleaned:
                log_line = f"[FICHOME] UNLOCK: {cleaned}"
                logs.append(log_line)
                await self._call_output_callback(on_output_callback, log_line)
        if unlock_result.get("success"):
            ok_msg = f"[OK] Oracle accounts unlocked: {atomic_schema_name}, {config_schema_name}"
            logs.append(ok_msg)
            await self._call_output_callback(on_output_callback, ok_msg)
        else:
            warn_msg = f"[WARN] Account unlock may have had issues (continuing): {(unlock_result.get('stderr') or '')[:120]}"
            logs.append(warn_msg)
            await self._call_output_callback(on_output_callback, warn_msg)

        # STEP 1a: Grant ATOMIC user privileges
        await self._call_subtask_callback(
            on_subtask_callback,
            "[FICHOME] : Granting ATOMIC schema user privileges"
        )
        
        atomic_sql_file = f"{config_dir}/privileges_atomic_user.sql"
        atomic_result = await self._grant_user_privileges(
            host, username, password,
            db_sys_password=db_sys_password,
            db_jdbc_host=db_jdbc_host,
            db_jdbc_port=db_jdbc_port,
            db_jdbc_service=db_jdbc_service,
            schema_name=atomic_schema_name,
            sql_file_path=atomic_sql_file,
            user_type="ATOMIC",
            on_output_callback=on_output_callback,
        )
        logs.extend(atomic_result.get("logs", []))
        
        # STEP 1b: Grant CONFIG user privileges
        await self._call_subtask_callback(
            on_subtask_callback,
            "[FICHOME] : Granting CONFIG schema user privileges"
        )
        
        config_sql_file = f"{config_dir}/privileges_config_user.sql"
        config_result = await self._grant_user_privileges(
            host, username, password,
            db_sys_password=db_sys_password,
            db_jdbc_host=db_jdbc_host,
            db_jdbc_port=db_jdbc_port,
            db_jdbc_service=db_jdbc_service,
            schema_name=config_schema_name,
            sql_file_path=config_sql_file,
            user_type="CONFIG",
            on_output_callback=on_output_callback,
        )
        logs.extend(config_result.get("logs", []))
        
        # Non-blocking: Log warnings but don't fail deployment
        return {"success": True, "logs": logs}

    async def _grant_user_privileges(
        self,
        host: str,
        username: str,
        password: str,
        db_sys_password: str,
        db_jdbc_host: str,
        db_jdbc_port: int,
        db_jdbc_service: str,
        schema_name: str,
        sql_file_path: str,
        user_type: str,
        on_output_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        """
        Execute privilege grant SQL script for a specific schema user.
        
        Reads SQL file from Git, replaces {SCHEMA_NAME} placeholder, executes via sqlplus.
        """
        logs: list[str] = []
        
        # Check if SQL file exists
        check_cmd = f"test -f {sql_file_path}"
        check_result = await self.ssh_service.execute_command(host, username, password, check_cmd)
        
        if not check_result.get("success"):
            logs.append(f"[WARN] {user_type} privileges SQL file not found: {sql_file_path}")
            return {"success": True, "logs": logs}
        
        # Read SQL file content
        read_cmd = f"cat {sql_file_path}"
        read_result = await self.ssh_service.execute_command(host, username, password, read_cmd)
        sql_content = (read_result.get("stdout") or "").strip()
        
        if not sql_content:
            logs.append(f"[WARN] {user_type} privileges SQL file is empty: {sql_file_path}")
            return {"success": True, "logs": logs}
        
        # Replace schema name placeholders (multiple formats)
        # 1. Our custom placeholders
        sql_content = sql_content.replace("{SCHEMA_NAME}", schema_name)
        sql_content = sql_content.replace("${SCHEMA_NAME}", schema_name)
        # 2. SQL*Plus substitution variables: ACCEPT <var> / &<var>
        #    Remove ACCEPT lines (they prompt for input which doesn't work in heredoc)
        import re
        sql_content = re.sub(r'(?i)^ACCEPT\s+\w+\s+.*$', '', sql_content, flags=re.MULTILINE)
        #    Replace all common SQL*Plus variable patterns with actual schema name
        #    Handles: &database_username, &username, &schema_name (with optional & doubling and trailing dot)
        sql_content = re.sub(r'&&?database_username\.?', schema_name, sql_content, flags=re.IGNORECASE)
        sql_content = re.sub(r'&&?username\.?', schema_name, sql_content, flags=re.IGNORECASE)
        sql_content = re.sub(r'&&?schema_name\.?', schema_name, sql_content, flags=re.IGNORECASE)
        
        # Build sqlplus connection string
        sqlplus_login = f"sys/{db_sys_password}@{db_jdbc_host}:{db_jdbc_port}/{db_jdbc_service} as sysdba"
        
        # Execute SQL via sqlplus heredoc (source oracle profile for sqlplus in PATH)
        sql_body = sql_content + "\nEXIT;\n"
        sqlplus_cmd = f"source /home/oracle/.profile >/dev/null 2>&1; sqlplus {shell_escape(sqlplus_login)} <<'EOGRANT'\n{sql_body}EOGRANT"
        
        msg = f"[FICHOME] Executing {user_type} privileges SQL for schema: {schema_name}"
        logs.append(msg)
        await self._call_output_callback(on_output_callback, msg)
        
        result = await self.ssh_service.execute_command(
            host, username, password, sqlplus_cmd, timeout=300, get_pty=True
        )
        
        stdout = (result.get("stdout") or "").strip()
        stderr = (result.get("stderr") or "").strip()
        
        # Stream full sqlplus output to UI
        if stdout:
            for line in stdout.splitlines():
                cleaned = line.strip()
                if cleaned:
                    log_line = f"[FICHOME] {user_type}: {cleaned}"
                    logs.append(log_line)
                    await self._call_output_callback(on_output_callback, log_line)
        
        if not result.get("success"):
            warn_msg = f"[WARN] {user_type} privileges grant had issues: {stderr}"
            logs.append(warn_msg)
            await self._call_output_callback(on_output_callback, warn_msg)
        else:
            ok_msg = f"[OK] {user_type} schema user privileges granted: {schema_name}"
            logs.append(ok_msg)
            await self._call_output_callback(on_output_callback, ok_msg)
        
        return {"success": True, "logs": logs}

    # ============== OFSAA SCRIPTS ==============

    async def run_startofsaa_script(
        self,
        host: str,
        username: str,
        password: str,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_subtask_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        """
        Copy and execute startofsaa.sh from Git repo as oracle user.
        
        Fetches: ofsaa_auto_installation/configuration/startofsaa.sh
        Copies to: /u01/startofsaa.sh
        Executes as: oracle user
        Streams: Full output to WebSocket
        """
        logs: list[str] = []
        repo_dir = Config.REPO_DIR
        source_script = f"{repo_dir}/configuration/startofsaa.sh"
        dest_script = "/u01/startofsaa.sh"
        
        await self._call_subtask_callback(on_subtask_callback, "[FICHOME] Running startofsaa.sh")
        
        try:
            # Check if source script exists
            check_cmd = f"test -f {source_script}"
            check_result = await self.ssh_service.execute_command(host, username, password, check_cmd)
            
            if not check_result.get("success"):
                error_msg = f"startofsaa.sh not found in Git repo: {source_script}"
                logs.append(f"[ERROR] {error_msg}")
                return {"success": False, "logs": logs, "error": error_msg}
            
            # Copy script to /u01
            copy_cmd = f"cp {source_script} {dest_script} && chmod 755 {dest_script}"
            copy_result = await self.ssh_service.execute_command(host, username, password, copy_cmd)
            
            if not copy_result.get("success"):
                error_msg = f"Failed to copy startofsaa.sh to /u01"
                logs.append(f"[ERROR] {error_msg}")
                return {"success": False, "logs": logs, "error": error_msg}
            
            logs.append("[OK] startofsaa.sh copied to /u01")
            
            # Execute as oracle user (source profile first so $FIC_HOME is set)
            exec_cmd = f"sudo -u oracle bash -c 'source /home/oracle/.profile && bash {dest_script}'"
            
            def handle_output(line: str) -> None:
                logs.append(f"[FICHOME] {line}")
                if on_output_callback:
                    try:
                        result = on_output_callback(line)
                        if inspect.isawaitable(result):
                            asyncio.create_task(result)
                    except Exception:
                        pass
            
            exec_result = await self.ssh_service.execute_interactive_command(
                host, username, password, exec_cmd,
                on_output_callback=handle_output,
                timeout=600
            )
            
            if not exec_result.get("success"):
                error_msg = f"startofsaa.sh execution failed: {exec_result.get('stderr')}"
                logs.append(f"[ERROR] {error_msg}")
                return {"success": False, "logs": logs, "error": error_msg}
            
            logs.append("[OK] startofsaa.sh executed successfully")
            return {"success": True, "logs": logs}
        
        except Exception as e:
            error_msg = f"startofsaa.sh execution failed: {str(e)}"
            logs.append(f"[ERROR] : {error_msg}")
            return {"success": False, "logs": logs, "error": error_msg}

    async def run_checkofsaa_script(
        self,
        host: str,
        username: str,
        password: str,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_subtask_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        """
        Copy and execute checkofsaa.sh from Git repo as oracle user.
        
        Fetches: ofsaa_auto_installation/configuration/checkofsaa.sh
        Copies to: /u01/checkofsaa.sh
        Executes as: oracle user
        Streams: Full output to WebSocket
        """
        logs: list[str] = []
        repo_dir = Config.REPO_DIR
        source_script = f"{repo_dir}/configuration/checkofsaa.sh"
        dest_script = "/u01/checkofsaa.sh"
        
        await self._call_subtask_callback(on_subtask_callback, "[FICHOME] Running checkofsaa.sh")
        
        try:
            # Check if source script exists
            check_cmd = f"test -f {source_script}"
            check_result = await self.ssh_service.execute_command(host, username, password, check_cmd)
            
            if not check_result.get("success"):
                error_msg = f"checkofsaa.sh not found in Git repo: {source_script}"
                logs.append(f"[ERROR] {error_msg}")
                return {"success": False, "logs": logs, "error": error_msg}
            
            # Copy script to /u01
            copy_cmd = f"cp {source_script} {dest_script} && chmod 755 {dest_script}"
            copy_result = await self.ssh_service.execute_command(host, username, password, copy_cmd)
            
            if not copy_result.get("success"):
                error_msg = f"Failed to copy checkofsaa.sh to /u01"
                logs.append(f"[ERROR] {error_msg}")
                return {"success": False, "logs": logs, "error": error_msg}
            
            logs.append("[OK] checkofsaa.sh copied to /u01")
            
            # Execute as oracle user (source profile first so $FIC_HOME is set)
            exec_cmd = f"sudo -u oracle bash -c 'source /home/oracle/.profile && bash {dest_script}'"
            
            def handle_output(line: str) -> None:
                logs.append(f"[FICHOME] {line}")
                if on_output_callback:
                    try:
                        result = on_output_callback(line)
                        if inspect.isawaitable(result):
                            asyncio.create_task(result)
                    except Exception:
                        pass
            
            exec_result = await self.ssh_service.execute_interactive_command(
                host, username, password, exec_cmd,
                on_output_callback=handle_output,
                timeout=600
            )
            
            if not exec_result.get("success"):
                error_msg = f"checkofsaa.sh execution failed: {exec_result.get('stderr')}"
                logs.append(f"[ERROR] {error_msg}")
                return {"success": False, "logs": logs, "error": error_msg}
            
            logs.append("[OK] checkofsaa.sh executed successfully")
            return {"success": True, "logs": logs}
        
        except Exception as e:
            error_msg = f"checkofsaa.sh execution failed: {str(e)}"
            logs.append(f"[ERROR]  {error_msg}")
            return {"success": False, "logs": logs, "error": error_msg}

    # ============== EAR CREATION & EXPLODING ==============

    async def deploy_fichome(
        self,
        host: str,
        username: str,
        password: str,
        on_subtask_callback: Optional[Callable[[str], Any]] = None,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        db_sys_password: Optional[str] = None,
        db_jdbc_host: Optional[str] = None,
        db_jdbc_port: int = 1521,
        db_jdbc_service: Optional[str] = None,
        config_schema_name: Optional[str] = None,
        atomic_schema_name: Optional[str] = None,
        weblogic_domain_home: Optional[str] = None,
        # STEP 5: WebLogic app deployment params
        deploy_app_enabled: bool = False,
        admin_url: Optional[str] = None,
        weblogic_username: Optional[str] = None,
        weblogic_password: Optional[str] = None,
        wl_home: Optional[str] = None,
        deploy_app_path: Optional[str] = None,
        deploy_app_target_server: Optional[str] = None,
    ) -> dict:
        """
        EAR Creation & Exploding: Build FICHOME.ear/war and create exploded deployment.
        
        Workflow:
        1. Grant database privileges to ATOMIC and CONFIG schema users
        2. Run single script (backup, ant.sh build, exploded EAR/WAR creation)
        3. Run startofsaa.sh from Git configuration
        4. Run checkofsaa.sh from Git configuration
        5. Deploy FICHOME.ear to WebLogic via WLST (optional)
        
        The script:
        - Takes timestamped backups of FICHOME.ear/war in ficweb
        - Builds with ant.sh
        - Deletes existing EAR_DIR in domain if present
        - Creates exploded EAR/WAR structure in domain applications
        """
        logs: list[str] = []
        
        if not weblogic_domain_home:
            return {"success": False, "logs": logs, "error": "weblogic_domain_home is required"}
        
        # Grant database privileges (non-blocking)
        if db_sys_password and config_schema_name and atomic_schema_name and db_jdbc_service:
            await self._call_subtask_callback(on_subtask_callback, "[FICHOME] Granting database privileges")
            
            privileges_result = await self.grant_database_privileges(
                host, username, password,
                db_sys_password=db_sys_password,
                db_jdbc_host=db_jdbc_host or host,
                db_jdbc_port=db_jdbc_port,
                db_jdbc_service=db_jdbc_service,
                config_schema_name=config_schema_name,
                atomic_schema_name=atomic_schema_name,
                on_subtask_callback=on_subtask_callback,
                on_output_callback=on_output_callback,
            )
            logs.extend(privileges_result.get("logs", []))
        else:
            logs.append("[INFO] Skipping database privileges (insufficient parameters)")
        
        # Run EAR creation & exploding script
        await self._call_subtask_callback(on_subtask_callback, "[FICHOME] Running EAR creation & exploding script")
        
        # Build the single deployment script that runs as oracle user
        deploy_script = f"""#!/bin/bash
set -e

FICWEB="/u01/OFSAA/FICHOME/ficweb"
DOMAIN="{weblogic_domain_home}"
APP_DIR="${{DOMAIN}}/applications"
EAR_DIR="${{APP_DIR}}/FICHOME.ear"
WAR_DIR="${{EAR_DIR}}/FICHOME.war"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

cd ${{FICWEB}}
[ -f FICHOME.ear ] && mv FICHOME.ear FICHOME.ear_bkp_${{TIMESTAMP}} && echo "Backed up FICHOME.ear -> FICHOME.ear_bkp_${{TIMESTAMP}}" || echo "No existing FICHOME.ear to backup"
[ -f FICHOME.war ] && mv FICHOME.war FICHOME.war_bkp_${{TIMESTAMP}} && echo "Backed up FICHOME.war -> FICHOME.war_bkp_${{TIMESTAMP}}" || echo "No existing FICHOME.war to backup"

echo "Building FICHOME with ant.sh"
source /home/oracle/.profile >/dev/null 2>&1 || true
./ant.sh
chmod -R 777 FICHOME.war FICHOME.ear

if [ -d "${{EAR_DIR}}" ]; then
    echo "Removing existing EAR directory: ${{EAR_DIR}}"
    rm -rf "${{EAR_DIR}}"
fi

mkdir -p ${{EAR_DIR}}
chmod -R 777 ${{APP_DIR}}

echo "Extracting EAR contents"
cp ${{FICWEB}}/FICHOME.ear ${{EAR_DIR}}/
cd ${{EAR_DIR}}
jar -xvf FICHOME.ear
rm -rf FICHOME.ear FICHOME.war

echo "Extracting WAR contents"
mkdir -p ${{WAR_DIR}}
cp ${{FICWEB}}/FICHOME.war ${{WAR_DIR}}/
cd ${{WAR_DIR}}
jar -xvf FICHOME.war
rm -f FICHOME.war

chmod -R 777 ${{EAR_DIR}}

echo "Exploded EAR/WAR deployment ready at: ${{EAR_DIR}}"
"""
        
        # Write script to remote, execute as oracle user
        script_path = "/tmp/fichome_deploy.sh"
        write_cmd = f"cat > {script_path} << 'EOFSCRIPT'\n{deploy_script}EOFSCRIPT\nchmod 755 {script_path}"
        write_result = await self.ssh_service.execute_command(host, username, password, write_cmd, get_pty=True)
        if not write_result.get("success"):
            error_msg = f"Failed to write deployment script: {write_result.get('stderr')}"
            logs.append(f"[ERROR] {error_msg}")
            return {"success": False, "logs": logs, "error": error_msg}
        
        # Execute as oracle user with streaming output
        if username == "oracle":
            exec_cmd = f"bash {script_path}"
        else:
            exec_cmd = f"su - oracle -c 'bash {script_path}'"
        
        captured_lines: list[str] = []
        pending = ""
        
        async def deploy_output_collector(text: str) -> None:
            nonlocal pending
            if not text:
                return
            pending += text.replace("\r", "\n")
            parts = pending.split("\n")
            for line in parts[:-1]:
                cleaned = line.strip()
                if cleaned:
                    captured_lines.append(cleaned)
                    # Forward with STEP 2 prefix (matching steps 3/4 format)
                    prefixed = f"[FICHOME] {cleaned}"
                    logs.append(prefixed)
                    await self._call_output_callback(on_output_callback, prefixed)
            pending = parts[-1]
        
        deploy_result = await self.ssh_service.execute_interactive_command(
            host, username, password, exec_cmd,
            on_output_callback=deploy_output_collector,
            timeout=1200,
        )
        tail = pending.strip()
        if tail:
            captured_lines.append(tail)
        
        # Cleanup script
        await self.ssh_service.execute_command(host, username, password, f"rm -f {script_path}")
        
        if not deploy_result.get("success"):
            error_detail = "EAR creation & exploding script failed"
            if captured_lines:
                error_detail = f"Deployment script failed: {captured_lines[-1][:120]}"
            logs.append(f"[ERROR] {error_detail}")
            return {"success": False, "logs": logs, "error": error_detail}
        
        logs.append("[OK] EAR creation & exploding completed successfully")
        
        # STEP 3: Run startofsaa.sh (BLOCKING)
        startofsaa_result = await self.run_startofsaa_script(
            host, username, password,
            on_output_callback=on_output_callback,
            on_subtask_callback=on_subtask_callback
        )
        logs.extend(startofsaa_result.get("logs", []))
        if not startofsaa_result.get("success"):
            return {
                "success": False,
                "logs": logs,
                "error": startofsaa_result.get("error") or "startofsaa.sh execution failed",
            }
        
        # STEP 4: Run checkofsaa.sh (BLOCKING)
        checkofsaa_result = await self.run_checkofsaa_script(
            host, username, password,
            on_output_callback=on_output_callback,
            on_subtask_callback=on_subtask_callback
        )
        logs.extend(checkofsaa_result.get("logs", []))
        if not checkofsaa_result.get("success"):
            return {
                "success": False,
                "logs": logs,
                "error": checkofsaa_result.get("error") or "checkofsaa.sh execution failed",
            }
        
        # Deploy FICHOME.ear to WebLogic via WLST (optional)
        if deploy_app_enabled and admin_url and weblogic_username and weblogic_password and deploy_app_path and deploy_app_target_server:
            app_deploy_result = await self.deploy_weblogic_application(
                host, username, password,
                admin_url=admin_url,
                weblogic_username=weblogic_username,
                weblogic_password=weblogic_password,
                wl_home=wl_home,
                app_path=deploy_app_path,
                target_server=deploy_app_target_server,
                on_output_callback=on_output_callback,
                on_subtask_callback=on_subtask_callback,
            )
            logs.extend(app_deploy_result.get("logs", []))
            if not app_deploy_result.get("success"):
                return {
                    "success": False,
                    "logs": logs,
                    "error": app_deploy_result.get("error") or "WebLogic application deployment failed",
                }
        logs.append("[OK] Deployment completed: All steps successful")
        return {"success": True, "logs": logs}

    # ============== WEBLOGIC APPLICATION DEPLOYMENT ==============

    async def deploy_weblogic_application(
        self,
        host: str,
        username: str,
        password: str,
        admin_url: str,
        weblogic_username: str,
        weblogic_password: str,
        app_path: str,
        target_server: str,
        wl_home: Optional[str] = None,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_subtask_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        """
        Deploy FICHOME.ear application to WebLogic server via WLST.
        
        Connects to WebLogic admin, undeploys existing app if present, then deploys new EAR.
        """
        logs: list[str] = []
        app_name = "FICHOME"

        await self._call_subtask_callback(on_subtask_callback, "[FICHOME] Deploying application to WebLogic")

        # Auto-discover WLST using find command: find /u01 -name wlst.sh | grep -i wlserver
        find_cmd = "find /u01 -name wlst.sh 2>/dev/null | grep -i wlserver | head -1"
        find_result = await self.ssh_service.execute_command(host, username, password, find_cmd, timeout=30)
        if not find_result.get("success"):
            error_msg = f"Failed to find WLST: {find_result.get('stderr')}"
            logs.append(f"[ERROR] {error_msg}")
            return {"success": False, "logs": logs, "error": error_msg}
        
        wlst_path = find_result.get("stdout", "").strip()
        if not wlst_path:
            error_msg = "WLST not found in /u01 (find /u01 -name wlst.sh returned no results)"
            logs.append(f"[ERROR] {error_msg}")
            return {"success": False, "logs": logs, "error": error_msg}
        
        logs.append(f"[INFO] WLST auto-discovered at: {wlst_path}")

        # Build WLST Python script
        wlst_script = f"""# WebLogic WLST Application Deployment Script
appName = '{app_name}'
appPath = '{app_path}'
targetServer = '{target_server}'

print('Connecting to WebLogic at {admin_url}...')
connect('{weblogic_username}', '{weblogic_password}', '{admin_url}')

edit()
startEdit()

# Check if the application is already deployed
apps = cmo.getAppDeployments()
appExists = False

for app in apps:
    if app.getName() == appName:
        appExists = True
        print('Existing deployment found: ' + appName)
        break

# Stop and undeploy if the application exists
if appExists:
    try:
        print('Stopping application: ' + appName)
        stopApplication(appName)
    except:
        print('Application may already be stopped.')

    print('Undeploying existing application: ' + appName)
    undeploy(appName, targets=targetServer)

# Deploy the new application
print('Deploying application: ' + appName)
deploy(
    appName=appName,
    path=appPath,
    targets=targetServer
)

save()
activate()

print('Application ' + appName + ' deployed successfully to ' + targetServer)

disconnect()
exit()
"""

        # Write WLST script to remote, then execute
        script_path = "/tmp/fichome_app_deploy.py"
        wrapper_script = f"""#!/bin/bash
set -e
cat > {script_path} << 'WLSTEOF'
{wlst_script}WLSTEOF

WLST="{wlst_path}"
echo "Executing WLST from: $WLST"
"$WLST" {script_path}
RET=$?
rm -f {script_path}
exit $RET
"""

        wrapper_path = "/tmp/fichome_app_deploy.sh"
        write_cmd = f"cat > {wrapper_path} << 'EOFSCRIPT'\n{wrapper_script}EOFSCRIPT\nchmod 755 {wrapper_path}"
        write_result = await self.ssh_service.execute_command(host, username, password, write_cmd, get_pty=True)
        if not write_result.get("success"):
            error_msg = f"Failed to write WLST deployment script: {write_result.get('stderr')}"
            logs.append(f"[ERROR] {error_msg}")
            return {"success": False, "logs": logs, "error": error_msg}

        # Execute (as current SSH user, not oracle — WLST needs WebLogic env)
        exec_cmd = f"bash {wrapper_path}"

        captured_lines: list[str] = []
        pending = ""

        async def wlst_output_collector(text: str) -> None:
            nonlocal pending
            if not text:
                return
            pending += text.replace("\r", "\n")
            parts = pending.split("\n")
            for line in parts[:-1]:
                cleaned = line.strip()
                if cleaned:
                    captured_lines.append(cleaned)
                    prefixed = f"[FICHOME] {cleaned}"
                    logs.append(prefixed)
                    await self._call_output_callback(on_output_callback, prefixed)
            pending = parts[-1]

        deploy_result = await self.ssh_service.execute_interactive_command(
            host, username, password, exec_cmd,
            on_output_callback=wlst_output_collector,
            timeout=1800,
        )
        tail = pending.strip()
        if tail:
            captured_lines.append(tail)

        # Cleanup
        await self.ssh_service.execute_command(host, username, password, f"rm -f {wrapper_path}")

        if not deploy_result.get("success"):
            error_detail = "WebLogic application deployment failed"
            if captured_lines:
                error_detail = f"WLST deployment failed: {captured_lines[-1][:120]}"
            logs.append(f"[ERROR] {error_detail}")
            return {"success": False, "logs": logs, "error": error_detail}

        logs.append("[OK] Application deployed to WebLogic successfully")
        return {"success": True, "logs": logs}

    # ============== COMBINED DATASOURCE + APP DEPLOYMENT (SINGLE WLST SESSION) ==============

    async def create_datasources_and_deploy_app(
        self,
        host: str,
        username: str,
        password: str,
        admin_url: str,
        weblogic_username: str,
        weblogic_password: str,
        datasources: list[dict] | None = None,
        deploy_app_enabled: bool = False,
        deploy_app_path: str | None = None,
        deploy_app_target_server: str | None = None,
        wl_home: str | None = None,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_subtask_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        """
        Create all datasources AND deploy FICHOME.ear in a SINGLE WLST session.
        
        - Connects to WebLogic once
        - Deletes + recreates each datasource (idempotent)
        - Tests all datasource connection pools
        - Undeploys + deploys FICHOME.ear (if enabled)
        - Disconnects once
        
        Much faster than running separate WLST sessions per datasource.
        """
        logs: list[str] = []
        ds_list = datasources or []

        await self._call_subtask_callback(
            on_subtask_callback,
            f"[WLST] Creating {len(ds_list)} datasource(s)"
            + (" + deploying FICHOME" if deploy_app_enabled else "")
            + " in single WLST session"
        )

        # ── Build datasource definitions block for WLST Python ──
        ds_defs = "datasources = [\n"
        for ds in ds_list:
            targets = ds.get("targets", [])
            if isinstance(targets, str):
                targets = [t.strip() for t in targets.split(",") if t.strip()]
            targets_str = ", ".join(f"'{t}'" for t in targets)
            ds_defs += f"""    {{
        'dsName': '{ds["ds_name"]}',
        'jndiName': '{ds["jndi_name"]}',
        'dbUrl': '{ds["db_url"]}',
        'dbUser': '{ds["db_user"]}',
        'dbPassword': '{ds["db_password"]}',
        'targets': [{targets_str}]
    }},
"""
        ds_defs += "]\n"

        # ── Build app deployment block ──
        deploy_block = ""
        if deploy_app_enabled and deploy_app_path and deploy_app_target_server:
            deploy_block = f"""
# ================================================================
# APPLICATION DEPLOYMENT: FICHOME
# ================================================================
print('')
print('===== APPLICATION DEPLOYMENT =====')

appName = 'FICHOME'
appPath = '{deploy_app_path}'
targetServer = '{deploy_app_target_server}'

# ---- STEP 1: Force remove any existing FICHOME deployment ----
print('Checking for existing ' + appName + ' deployment...')
try:
    domainConfig()
    cd('/AppDeployments')
    existingApps = ls(returnMap='true')
    if appName in existingApps:
        print('Found existing ' + appName + '. Removing it...')
except:
    print('Could not list deployments, will try force undeploy anyway.')

# Always try to stop + undeploy regardless of detection
try:
    stopApplication(appName, block='true')
    print('Stopped ' + appName + '.')
except:
    pass

try:
    undeploy(appName, block='true')
    print('Undeployed ' + appName + ' successfully.')
except:
    print('No existing ' + appName + ' to undeploy (clean state).')

# ---- STEP 2: Deploy (same as manual working script) ----
print('Deploying: ' + appName + ' -> ' + targetServer)
print('Path: ' + appPath)

deployFailed = False
try:
    edit()
    startEdit()
    deploy(appName=appName, path=appPath, targets=targetServer)
    save()
    activate()
    print('Application ' + appName + ' deployed successfully to ' + targetServer)
except Exception, e:
    errMsg = str(e)
    try:
        cancelEdit('y')
    except:
        pass
    print('WARNING: Deployment issue: ' + errMsg)
    print('Check WebLogic Console -> Deployments for actual status.')

# ---- STEP 3: Start application (move from Installed -> Active) ----
try:
    startApplication(appName, block='true')
    print('Application ' + appName + ' started successfully - now servicing all requests.')
except Exception, e:
    print('WARNING: Could not start application: ' + str(e))
    print('You may need to start it manually from WebLogic Console.')
"""

        # ── Build complete WLST Python script ──
        # Two-phase approach: Phase 1 deletes all existing DS + activates (cleans ghost refs),
        # Phase 2 creates fresh DS + activates (clean config.xml, no orphans)
        wlst_script = f"""from java.lang import String
import jarray
from java.lang import Thread
from javax.management import ObjectName
import traceback

adminUrl  = '{admin_url}'
username  = '{weblogic_username}'
password  = '{weblogic_password}'

{ds_defs}

dsNames = [ds['dsName'] for ds in datasources]

# ================================================================
# CONNECT
# ================================================================
print('Connecting to WebLogic at ' + adminUrl + '...')
connect(username, password, adminUrl)

# ================================================================
# CANCEL ANY STALE EDIT SESSION
# ================================================================
try:
    edit()
    cancelEdit('y')
    print('Cancelled stale edit session.')
except:
    print('No stale edit session to cancel.')

# ================================================================
# PHASE 1: DELETE ALL EXISTING DATASOURCES
# ================================================================
if len(datasources) > 0:
    print('')
    print('===== PHASE 1: DELETE EXISTING DATASOURCES =====')
    edit()
    startEdit()

    cd('/JDBCSystemResources')
    existing = ls(returnMap='true')
    deleteCount = 0

    for dsName in dsNames:
        if dsName in existing:
            print('Deleting datasource: ' + dsName)
            delete(dsName, 'JDBCSystemResource')
            cd('/JDBCSystemResources')
            deleteCount += 1
        else:
            print('Datasource ' + dsName + ' does not exist, skip delete.')

    if deleteCount > 0:
        save()
        activate()
        print('Phase 1 complete: Deleted ' + str(deleteCount) + ' datasource(s) and activated.')
    else:
        print('No existing datasources to delete.')
        cancelEdit('y')

    # ================================================================
    # PHASE 2: CREATE FRESH DATASOURCES
    # ================================================================
    print('')
    print('===== PHASE 2: CREATE FRESH DATASOURCES =====')
    edit()
    startEdit()

    for ds in datasources:
        dsName   = ds['dsName']
        jndiName = ds['jndiName']
        dbUrl    = ds['dbUrl']
        dbUser   = ds['dbUser']
        dbPassword = ds['dbPassword']
        targets  = ds['targets']

        print('')
        print('--- Creating datasource: ' + dsName + ' ---')
        cd('/')
        cmo.createJDBCSystemResource(dsName)

        cd('/JDBCSystemResources/' + dsName + '/JDBCResource/' + dsName)
        cmo.setName(dsName)

        # JNDI
        cd('/JDBCSystemResources/' + dsName + '/JDBCResource/' + dsName + '/JDBCDataSourceParams/' + dsName)
        set('JNDINames', jarray.array([String(jndiName)], String))

        # Driver params
        cd('/JDBCSystemResources/' + dsName +
           '/JDBCResource/' + dsName +
           '/JDBCDriverParams/' + dsName)
        set('Url', dbUrl)
        set('DriverName', 'oracle.jdbc.OracleDriver')
        cmo.setPassword(dbPassword)

        # Username property
        cd('/JDBCSystemResources/' + dsName +
           '/JDBCResource/' + dsName +
           '/JDBCDriverParams/' + dsName + '/Properties/' + dsName)
        try:
            cmo.createProperty('user')
        except:
            pass
        cd('Properties/user')
        set('Value', dbUser)

        # Connection pool
        cd('/JDBCSystemResources/' + dsName +
           '/JDBCResource/' + dsName +
           '/JDBCConnectionPoolParams/' + dsName)
        set('InitialCapacity', 0)
        set('MaxCapacity', 10)
        set('TestTableName', 'SQL ISVALID')

        # Target assignment
        cd('/JDBCSystemResources/' + dsName)
        targetList = []
        for t in targets:
            t = t.strip()
            if not t:
                continue
            print('  Targeting: ' + t)
            serverMBean = getMBean('/Servers/' + t)
            if serverMBean is not None:
                targetList.append(serverMBean.getObjectName())
            else:
                print('  WARNING: Server ' + t + ' not found, skipping')
        if len(targetList) > 0:
            set('Targets', jarray.array(targetList, ObjectName))
        else:
            print('  WARNING: No valid targets found for ' + dsName)

        print('Datasource ' + dsName + ' configured.')

    save()
    activate()
    print('')
    print('Phase 2 complete: All datasources created and activated.')

    # ================================================================
    # TEST DATASOURCE POOLS
    # ================================================================
    print('')
    print('Waiting 10 seconds for MBean registration...')
    Thread.sleep(10000)

    print('')
    print('===== TESTING DATASOURCE CONNECTIONS =====')
    serverConfig()
    domainRuntime()

    runningSrv = []
    try:
        cd('/ServerRuntimes')
        rawList = ls(returnMap='true')
        for item in rawList:
            runningSrv.append(str(item))
        print('Running servers: ' + str(runningSrv))
    except Exception, e:
        print('WARNING: Could not list ServerRuntimes: ' + str(e))

    passCount = 0
    failCount = 0
    skipCount = 0

    for ds in datasources:
        dsName  = ds['dsName']
        targets = ds['targets']

        for targetServer in targets:
            targetServer = targetServer.strip()
            label = dsName + ' on ' + targetServer

            if targetServer not in runningSrv:
                print('SKIP  - ' + label + ' (server not running)')
                skipCount += 1
                continue

            try:
                cd('/ServerRuntimes/' + targetServer +
                   '/JDBCServiceRuntime/' + targetServer +
                   '/JDBCDataSourceRuntimeMBeans/' + dsName)
                cmo.testPool()
                print('OK    - ' + label)
                passCount += 1
            except Exception, e:
                print('FAIL  - ' + label + ': ' + str(e))
                failCount += 1

    print('')
    print('--- Test Summary ---')
    print('Passed : ' + str(passCount))
    print('Failed : ' + str(failCount))
    print('Skipped: ' + str(skipCount))
{deploy_block}
# ================================================================
# DISCONNECT
# ================================================================
print('')
print('Disconnecting from WebLogic...')
disconnect()
exit()
"""

        # ── Write WLST script to remote and execute ──
        script_path = "/tmp/wlst_ds_deploy_$$.py"
        wrapper_script = f"""#!/bin/bash
set -e

source /home/oracle/.profile >/dev/null 2>&1 || true

WLST=$(find /u01 -name wlst.sh 2>/dev/null | grep -i wlserver | head -1)
if [ -z "$WLST" ]; then
    echo "ERROR: wlst.sh not found under /u01"
    exit 1
fi
echo "Using WLST: $WLST"

TMP_WLST="/tmp/wlst_combined_$$.py"

cat <<'WLSTEOF' > "$TMP_WLST"
{wlst_script}
WLSTEOF

echo "Executing combined WLST script..."
"$WLST" "$TMP_WLST"
RET=$?

rm -f "$TMP_WLST"
exit $RET
"""

        wrapper_path = "/tmp/wlst_combined_deploy.sh"
        write_cmd = f"cat > {wrapper_path} << 'EOFSCRIPT'\n{wrapper_script}EOFSCRIPT\nchmod 755 {wrapper_path}"

        write_result = await self.ssh_service.execute_command(
            host, username, password, write_cmd, get_pty=True
        )
        if not write_result.get("success"):
            error_msg = f"Failed to write WLST script: {write_result.get('stderr')}"
            logs.append(f"[ERROR] {error_msg}")
            return {"success": False, "logs": logs, "error": error_msg}

        # Execute as oracle user
        exec_cmd = (
            f"bash {wrapper_path}"
            if username == "oracle"
            else f"su - oracle -c 'bash {wrapper_path}'"
        )

        captured_lines: list[str] = []
        pending = ""

        async def wlst_output_collector(text: str) -> None:
            nonlocal pending
            if not text:
                return
            pending += text.replace("\r", "\n")
            parts = pending.split("\n")
            for line in parts[:-1]:
                cleaned = line.strip()
                if cleaned:
                    captured_lines.append(cleaned)
                    prefixed = f"[WLST] {cleaned}"
                    logs.append(prefixed)
                    await self._call_output_callback(on_output_callback, prefixed)
            pending = parts[-1]

        result = await self.ssh_service.execute_interactive_command(
            host, username, password, exec_cmd,
            on_output_callback=wlst_output_collector,
            timeout=1800,
        )
        tail = pending.strip()
        if tail:
            captured_lines.append(tail)

        # Cleanup
        await self.ssh_service.execute_command(
            host, username, password, f"rm -f {wrapper_path}"
        )

        if not result.get("success"):
            error_detail = "WLST combined datasource/deploy failed"
            if captured_lines:
                error_detail = f"WLST failed: {captured_lines[-1][:120]}"
            logs.append(f"[ERROR] {error_detail}")
            return {"success": False, "logs": logs, "error": error_detail}

        # Check captured output for deploy failure markers
        deploy_failed = any("DEPLOY_FAILED:" in line for line in captured_lines)
        if deploy_failed:
            error_detail = "FICHOME deployment failed"
            for line in captured_lines:
                if "DEPLOY_FAILED:" in line:
                    error_detail = line
                    break
            logs.append(f"[ERROR] {error_detail}")
            return {"success": False, "logs": logs, "error": error_detail}

        logs.append("[OK] All datasources created"
                     + (" and FICHOME deployed" if deploy_app_enabled else "")
                     + " successfully")
        return {"success": True, "logs": logs}

    # ============== WEBLOGIC DATASOURCE CREATION (SINGLE) ==============

    async def create_weblogic_datasource(
        self,
        host: str,
        username: str,
        password: str,
        admin_url: str,
        weblogic_username: str,
        weblogic_password: str,
        ds_name: str,
        jndi_name: str,
        db_url: str,
        db_user: str,
        db_password: str,
        targets: list[str],
        wl_home: Optional[str] = None,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_subtask_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:

        logs: list[str] = []

        await self._call_subtask_callback(
            on_subtask_callback, f"[DATASOURCE] Creating datasource: {ds_name}"
        )

        targets_csv = ",".join(t.strip() for t in targets)

        script_content = f"""#!/bin/bash
set -e

source /home/oracle/.profile >/dev/null 2>&1 || true

WLST=$(find /u01 -name wlst.sh 2>/dev/null | grep -i wlserver | head -1)
if [ -z "$WLST" ]; then
    echo "ERROR: WLST not found via find /u01 -name wlst.sh | grep -i wlserver"
    exit 1
fi
echo "Using WLST: $WLST"

TMP_WLST="/tmp/create_ds_{ds_name}_$$.py"

cat <<'WLSTEOF' > "$TMP_WLST"
from java.lang import String
import jarray
from javax.management import ObjectName

adminUrl  = '{admin_url}'
username  = '{weblogic_username}'
password  = '{weblogic_password}'

dsName   = '{ds_name}'
jndiName = '{jndi_name}'

dbUrl      = '{db_url}'
dbUser     = '{db_user}'
dbPassword = '{db_password}'
driver     = 'oracle.jdbc.OracleDriver'

targets = '{targets_csv}'.split(',')

print('Connecting to WebLogic...')
connect(username, password, adminUrl)

# Cancel any stale edit session
try:
    edit()
    cancelEdit('y')
    print('Cancelled stale edit session.')
except:
    print('No stale edit session to cancel.')

# Phase 1: Delete existing datasource
print('')
print('===== PHASE 1: DELETE EXISTING DATASOURCE =====')
edit()
startEdit()

cd('/JDBCSystemResources')
if dsName in ls(returnMap='true'):
    print('Deleting existing datasource: ' + dsName)
    delete(dsName, 'JDBCSystemResource')
    save()
    activate()
    print('Phase 1 complete: Deleted ' + dsName)
else:
    print('Datasource ' + dsName + ' does not exist, skip delete.')
    cancelEdit('y')

# Phase 2: Create fresh datasource
print('')
print('===== PHASE 2: CREATE FRESH DATASOURCE =====')
edit()
startEdit()

print('Creating datasource: ' + dsName)
cd('/')
cmo.createJDBCSystemResource(dsName)

cd('/JDBCSystemResources/' + dsName + '/JDBCResource/' + dsName)
cmo.setName(dsName)

# JNDI
cd('/JDBCSystemResources/' + dsName + '/JDBCResource/' + dsName + '/JDBCDataSourceParams/' + dsName)
set('JNDINames', jarray.array([String(jndiName)], String))

# Driver params
cd('/JDBCSystemResources/' + dsName +
   '/JDBCResource/' + dsName +
   '/JDBCDriverParams/' + dsName)

set('Url', dbUrl)
set('DriverName', driver)
cmo.setPassword(dbPassword)

# Username property
cd('/JDBCSystemResources/' + dsName +
   '/JDBCResource/' + dsName +
   '/JDBCDriverParams/' + dsName + '/Properties/' + dsName)

try:
    cmo.createProperty('user')
except:
    pass

cd('Properties/user')
set('Value', dbUser)

# Pool params
cd('/JDBCSystemResources/' + dsName +
   '/JDBCResource/' + dsName +
   '/JDBCConnectionPoolParams/' + dsName)

set('InitialCapacity', 0)
set('MaxCapacity', 10)
set('TestTableName', 'SQL ISVALID')

# Targeting
cd('/JDBCSystemResources/' + dsName)

targetList = []
for t in targets:
    t = t.strip()
    if not t:
        continue
    print('Targeting datasource to: ' + t)
    serverMBean = getMBean('/Servers/' + t)
    if serverMBean is not None:
        targetList.append(serverMBean.getObjectName())
    else:
        print('WARNING: Server ' + t + ' not found, skipping')

if len(targetList) > 0:
    set('Targets', jarray.array(targetList, ObjectName))
else:
    print('WARNING: No valid targets found')

save()
activate()

print('Datasource created successfully.')

# Test datasource
domainRuntime()
for t in targets:
    try:
        print('Testing datasource on ' + t)
        cd('/ServerRuntimes/' + t +
           '/JDBCServiceRuntime/' + t +
           '/JDBCDataSourceRuntimeMBeans/' + dsName)
        print('Test result: ' + str(cmo.testPool()))
    except:
        print('Test failed on ' + t)

disconnect()
exit()
WLSTEOF

echo "Executing WLST..."
"$WLST" "$TMP_WLST"

rm -f "$TMP_WLST"
echo "Datasource {ds_name} completed."
"""

        script_path = f"/tmp/create_ds_{ds_name}.sh"

        write_cmd = f"""cat > {script_path} << 'EOF'
{script_content}
EOF
chmod 755 {script_path}
"""

        write_result = await self.ssh_service.execute_command(
            host, username, password, write_cmd, get_pty=True
        )

        if not write_result.get("success"):
            return {"success": False, "logs": ["Script write failed"]}

        exec_cmd = (
            f"bash {script_path}"
            if username == "oracle"
            else f"su - oracle -c 'bash {script_path}'"
        )

        result = await self.ssh_service.execute_interactive_command(
            host,
            username,
            password,
            exec_cmd,
            on_output_callback=on_output_callback,
            timeout=600,
        )

        await self.ssh_service.execute_command(
            host, username, password, f"rm -f {script_path}"
        )

        if not result.get("success"):
            return {"success": False, "logs": ["Datasource creation failed"]}

        return {"success": True, "logs": [f"Datasource {ds_name} created successfully"]}

    # ============== CALLBACK HELPERS ==============

    async def _call_subtask_callback(
        self,
        callback: Optional[Callable[[str], Any]],
        message: str,
    ) -> None:
        """Helper to call subtask callback safely."""
        if callback is not None:
            try:
                result = callback(message)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                pass

    async def _call_output_callback(
        self,
        callback: Optional[Callable[[str], Any]],
        message: str,
    ) -> None:
        """Helper to call output callback safely."""
        if callback is not None:
            try:
                result = callback(message)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                pass