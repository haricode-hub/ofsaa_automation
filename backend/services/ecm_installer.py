from typing import Any, Callable, Optional
import inspect
import os
import re
import time

from core.config import Config
from services.ssh_service import SSHService
from services.validation import ValidationService
from services.utils import shell_escape


class ECMInstallerService:
    """Download ECM installer kit and run osc.sh and setup.sh."""

    def __init__(self, ssh_service: SSHService, validation: ValidationService) -> None:
        self.ssh_service = ssh_service
        self.validation = validation

    async def setup_ecm_git_repo(self, host: str, username: str, password: str) -> dict:
        """Clone or pull the latest ECM_PACK from Git."""
        logs: list[str] = []
        repo_dir = Config.REPO_DIR
        safe_dir_cfg = f"-c safe.directory={repo_dir}"

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
            return {"success": False, "logs": logs, "error": result.get("stderr") or "Failed to prepare ECM repo"}
        logs.append("[OK] ECM repository ready")
        return {"success": True, "logs": logs}

    async def download_and_extract_ecm_kit(self, host: str, username: str, password: str) -> dict:
        """Download and extract ECM_PACK zip to /u01/installer_kit."""
        logs: list[str] = []
        target_dir = "/u01/installer_kit"
        repo_dir = Config.REPO_DIR

        # Check if already extracted
        await self.ssh_service.execute_command(host, username, password, f"mkdir -p {target_dir}", get_pty=True)
        check_existing = await self.validation.check_directory_exists(
            host, username, password, f"{target_dir}/OFS_ECM_PACK"
        )
        if check_existing.get("exists"):
            logs.append("[OK] ECM installer kit already extracted")
            return {"success": True, "logs": logs}

        # Find ECM_PACK zip
        find_zip_cmd = (
            f"installer_zip=$(find {repo_dir}/ECM_PACK -maxdepth 1 -type f -name '*.zip' -print | head -n 1); "
            "if [ -z \"$installer_zip\" ]; then echo 'ECM_INSTALLER_ZIP_NOT_FOUND'; exit 1; fi; "
            "echo $installer_zip"
        )
        zip_result = await self.ssh_service.execute_command(host, username, password, find_zip_cmd)
        if not zip_result["success"] or "ECM_INSTALLER_ZIP_NOT_FOUND" in zip_result.get("stdout", ""):
            return {"success": False, "logs": logs, "error": "ECM installer kit zip not found in repo/ECM_PACK"}

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
                or (f"Failed to unzip ECM kit (rc={rc})" if rc is not None else "Failed to unzip ECM kit"),
            }
        logs.append("[OK] ECM installer kit extracted")
        return {"success": True, "logs": logs}

    async def backup_ecm_config_files(self, host: str, username: str, password: str) -> dict:
        """Backup existing ECM config files before replacement."""
        logs: list[str] = []
        ts = time.strftime("%Y%m%d_%H%M%S")
        
        config_paths = [
            "/u01/INSTALLER_KIT/OFS_ECM_PACK/schema_creator/conf/OFS_ECM_SCHEMA_IN.xml",
            "/u01/INSTALLER_KIT/OFS_ECM_PACK/OFS_NGECM/conf/default.properties",
            "/u01/INSTALLER_KIT/OFS_ECM_PACK/OFS_AAI/conf/OFSAAI_InstallConfig.xml",
        ]

        for config_path in config_paths:
            check = await self.ssh_service.execute_command(host, username, password, f"test -f {config_path}")
            if check["success"]:
                backup_cmd = f"cp -f {config_path} {config_path}.backup.{ts}"
                backup_result = await self.ssh_service.execute_command(host, username, password, backup_cmd, get_pty=True)
                if backup_result["success"]:
                    logs.append(f"[OK] Backed up: {config_path} -> {config_path}.backup.{ts}")
                else:
                    logs.append(f"[WARN] Failed to backup: {config_path}")
            else:
                logs.append(f"[INFO] Config file not found (skipped): {config_path}")

        return {"success": True, "logs": logs}

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
        """Apply ECM config files from Git repo to the extracted kit."""
        logs: list[str] = []
        repo_dir = Config.REPO_DIR
        git_auth_setup = self._git_auth_setup_cmd()
        safe_dir_cfg = f"-c safe.directory={repo_dir}"

        # Ensure repo is prepared
        cmd_prepare_repo = (
            "mkdir -p /u01/installer_kit && "
            f"{git_auth_setup}"
            f"if [ -d {repo_dir}/.git ]; then "
            "echo 'REPO_READY'; "
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
            return {"success": False, "logs": logs, "error": repo_result.get("stderr") or "Failed to prepare repo"}
        logs.append("[OK] Repo prepared for ECM config file fetch")

        # ECM config file mappings
        ecm_mappings = [
            ("OFS_ECM_SCHEMA_IN.xml", "/u01/INSTALLER_KIT/OFS_ECM_PACK/schema_creator/conf/OFS_ECM_SCHEMA_IN.xml"),
            ("default.properties", "/u01/INSTALLER_KIT/OFS_ECM_PACK/OFS_NGECM/conf/default.properties"),
            ("OFSAAI_InstallConfig.xml", "/u01/INSTALLER_KIT/OFS_ECM_PACK/OFS_AAI/conf/OFSAAI_InstallConfig.xml"),
        ]

        # Copy config files from repo to kit
        for filename, dest_path in ecm_mappings:
            src_path = await self._resolve_ecm_repo_file_path(
                host, username, password, repo_dir=repo_dir, filename=filename
            )
            if not src_path:
                return {"success": False, "logs": logs, "error": f"ECM file not found in repo: {filename}"}
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
                    "error": copy_result.get("stderr") or f"Failed to copy {filename} to ECM kit",
                }
            logs.append(f"[OK] Updated ECM config file: {dest_path}")

        return {"success": True, "logs": logs}

    async def run_ecm_schema_creator(
        self,
        host: str,
        username: str,
        password: str,
        *,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_prompt_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        """Run ECM schema creator (osc.sh -s) with interactive prompts."""
        osc_candidates = [
            "/u01/installer_kit/OFS_ECM_PACK/schema_creator/bin/osc.sh",
        ]
        osc_path = None
        for candidate in osc_candidates:
            check = await self.ssh_service.execute_command(host, username, password, f"test -x {candidate}")
            if check["success"]:
                osc_path = candidate
                break
        if osc_path is None:
            return {"success": False, "logs": [], "error": "ECM osc.sh not found or not executable"}

        schema_creator_dir = os.path.dirname(os.path.dirname(osc_path))
        pack_root_dir = os.path.dirname(schema_creator_dir)

        # Patch VerInfo.txt for Linux compatibility
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

        # Check for fatal errors
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
            logs = [f"[INFO] Checked log: {latest_log}"]
            logs.append("[WARN] ECM schema already exists. Skipping schema creation and moving to next step.")
            logs.extend([f"[OSCLOG] {line}" for line in schema_exists_lines])
            if fatal_lines:
                logs.extend([f"[OSCLOG] {line}" for line in fatal_lines])
                return {"success": False, "logs": logs, "error": "ECM osc.sh log contains non-skippable ERROR/FAIL"}
            return {"success": True, "logs": logs}

        if fatal_lines:
            logs = [f"[ERROR] ECM osc.sh log contains ERROR/FAIL in {latest_log}:"] + [f"[OSCLOG] {line}" for line in fatal_lines]
            return {"success": False, "logs": logs, "error": "ECM osc.sh log contains ERROR/FAIL"}

        if not result.get("success"):
            return {"success": False, "logs": [f"[INFO] Checked log: {latest_log}"], "error": "ECM osc.sh failed"}

        return {"success": True, "logs": [f"[INFO] Checked log: {latest_log}", "[OK] ECM schema creator (osc.sh) completed successfully"]}

    async def run_ecm_silent_installer(
        self,
        host: str,
        username: str,
        password: str,
        *,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_prompt_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        """Run ECM silent installer (setup.sh SILENT) with interactive prompts."""
        setup_candidates = [
            "/u01/installer_kit/OFS_ECM_PACK/bin/setup.sh",
            "/u01/INSTALLER_KIT/OFS_ECM_PACK/bin/setup.sh",
        ]

        setup_path = None
        for candidate in setup_candidates:
            check = await self.ssh_service.execute_command(host, username, password, f"test -x {candidate}")
            if check["success"]:
                setup_path = candidate
                break
        if setup_path is None:
            return {"success": False, "logs": [], "error": "ECM setup.sh not found or not executable"}

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

        result = await self.ssh_service.execute_interactive_command(
            host,
            username,
            password,
            command,
            on_output_callback=on_output_callback,
            on_prompt_callback=on_prompt_callback,
            timeout=36000,
        )

        if not result.get("success"):
            return {"success": False, "logs": [], "error": "ECM setup.sh SILENT failed"}

        logs = [f"[OK] ECM setup.sh SILENT completed from {setup_path}"]
        return {"success": True, "logs": logs}

    async def _resolve_ecm_repo_file_path(
        self,
        host: str,
        username: str,
        password: str,
        *,
        repo_dir: str,
        filename: str,
    ) -> Optional[str]:
        """Resolve ECM config file path from Git repo."""
        preferred_path = f"{repo_dir}/ECM_PACK/{filename}"
        preferred_check = await self.ssh_service.execute_command(
            host, username, password, f"test -f {shell_escape(preferred_path)} && echo FOUND"
        )
        if preferred_check.get("success") and "FOUND" in (preferred_check.get("stdout") or ""):
            return preferred_path

        # Fallback: search anywhere in ECM_PACK
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

    def _git_auth_setup_cmd(self) -> str:
        """Get Git authentication setup command based on config."""
        git_username = (Config.GIT_USERNAME or "").strip()
        git_password = (Config.GIT_PASSWORD or "").strip()
        if git_username and git_password:
            return f"export GIT_USERNAME='{shell_escape(git_username)}' GIT_PASSWORD='{shell_escape(git_password)}'; "
        return ""
