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

        cmd_prepare = (
            f"mkdir -p {target_dir} && "
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

        check_existing = await self.validation.check_directory_exists(host, username, password, f"{target_dir}/OFS_BD_PACK")
        if check_existing.get("exists"):
            logs.append("[OK] Installer kit already extracted")
            return {"success": True, "logs": logs}

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
