from typing import Any, Callable, Optional

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

    async def apply_config_files_from_repo(self, host: str, username: str, password: str) -> dict:
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

    async def run_osc_schema_creator(
        self,
        host: str,
        username: str,
        password: str,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_prompt_callback: Optional[Callable[[str], Any]] = None,
    ) -> dict:
        osc_path = "/u01/installer_kit/OFS_BD_PACK/schema_creator/bin/osc.sh"
        check = await self.ssh_service.execute_command(host, username, password, f"test -x {osc_path}")
        if not check["success"]:
            return {"success": False, "logs": [], "error": "osc.sh not found or not executable"}

        inner_cmd = f"source /home/oracle/.profile >/dev/null 2>&1; cd $(dirname {osc_path}) && ./osc.sh -S"
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
