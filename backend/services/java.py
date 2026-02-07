from typing import Optional

from core.config import Config
from services.ssh_service import SSHService
from services.validation import ValidationService


class JavaService:
    """Handles Java installation and OFSAA directory creation."""

    def __init__(self, ssh_service: SSHService, validation: ValidationService) -> None:
        self.ssh_service = ssh_service
        self.validation = validation

    async def install_java_from_repo(self, host: str, username: str, password: str) -> dict:
        logs: list[str] = []

        existing = await self.validation.find_java_installation(host, username, password)
        if existing:
            logs.append(f"[OK] Java already installed at {existing}")
            return {"success": True, "logs": logs, "java_home": existing}

        logs.append("[INFO] Java not found, downloading from repository")

        repo_dir = Config.REPO_DIR
        safe_dir_cfg = f"-c safe.directory={repo_dir}"
        clone_cmd = (
            f"mkdir -p /u01/installer_kit && "
            f"if [ -d {repo_dir}/.git ]; then "
            f"cd {repo_dir} && "
            f"(git -c http.sslVerify=false {safe_dir_cfg} pull --ff-only || "
            f"(git config --global --add safe.directory {repo_dir} && git -c http.sslVerify=false {safe_dir_cfg} pull --ff-only)); "
            f"else git -c http.sslVerify=false clone {Config.REPO_URL} {repo_dir}; fi"
        )
        result = await self.ssh_service.execute_command(host, username, password, clone_cmd, timeout=1800, get_pty=True)
        if not result["success"]:
            if result.get("stdout"):
                logs.append(result["stdout"])
            if result.get("stderr"):
                logs.append(result["stderr"])
            return {
                "success": False,
                "logs": logs,
                "error": result.get("stderr") or "Failed to clone Java repository",
            }
        logs.append("[OK] Repository ready for Java download")

        find_cmd = (
            f"java_archive=$(find {repo_dir} -maxdepth 1 -type f "
            f"\\( -name \"{Config.JAVA_ARCHIVE_HINT}*.tar.gz\" -o -name \"{Config.JAVA_ARCHIVE_HINT}*.tgz\" -o -name \"{Config.JAVA_ARCHIVE_HINT}*.zip\" \\) "
            "-print | head -n 1); "
            "if [ -z \"$java_archive\" ]; then echo 'JAVA_ARCHIVE_NOT_FOUND'; exit 1; fi; "
            "echo $java_archive"
        )
        archive_result = await self.ssh_service.execute_command(host, username, password, find_cmd)
        if not archive_result["success"] or "JAVA_ARCHIVE_NOT_FOUND" in archive_result.get("stdout", ""):
            return {"success": False, "logs": logs, "error": "Java archive not found in repo"}

        archive_path = archive_result.get("stdout", "").splitlines()[0].strip()
        logs.append(f"[INFO] Java archive found: {archive_path}")

        extract_cmd = (
            f"if echo {archive_path} | grep -E '\\.zip$' >/dev/null 2>&1; then "
            f"unzip -o {archive_path} -d /u01; "
            f"else tar -xzf {archive_path} -C /u01; fi"
        )
        extract_result = await self.ssh_service.execute_command(
            host, username, password, extract_cmd, timeout=1800, get_pty=True
        )
        if not extract_result["success"]:
            return {
                "success": False,
                "logs": logs,
                "error": extract_result.get("stderr") or "Failed to extract Java archive",
            }
        logs.append("[OK] Java extracted to /u01")

        detect_cmd = "ls -d /u01/jdk* | head -n 1"
        detect_result = await self.ssh_service.execute_command(host, username, password, detect_cmd)
        if not detect_result["success"] or not detect_result.get("stdout"):
            return {"success": False, "logs": logs, "error": "Unable to detect JAVA_HOME after extraction"}

        java_home = detect_result.get("stdout", "").splitlines()[0].strip()
        logs.append(f"[OK] Detected JAVA_HOME: {java_home}")
        return {"success": True, "logs": logs, "java_home": java_home}

    async def create_ofsaa_directories(self, host: str, username: str, password: str) -> dict:
        logs: list[str] = []
        dirs = ["/u01/OFSAA/FICHOME", "/u01/OFSAA/FTPSHARE", "/u01/installer_kit"]
        for path in dirs:
            check = await self.validation.check_directory_exists(host, username, password, path)
            if check.get("exists"):
                logs.append(f"[OK] {path} already exists")
                continue
            result = await self.ssh_service.execute_command(
                host, username, password, f"mkdir -p {path}", get_pty=True
            )
            if not result["success"]:
                return {
                    "success": False,
                    "logs": logs,
                    "error": result.get("stderr") or f"Failed to create {path}",
                }
            logs.append(f"[OK] Created {path}")

        result = await self.ssh_service.execute_command(
            host, username, password, "chown -R oracle:oinstall /u01/OFSAA /u01/installer_kit", get_pty=True
        )
        if not result["success"]:
            return {
                "success": False,
                "logs": logs,
                "error": result.get("stderr") or "Failed to set ownership on /u01/OFSAA",
            }
        logs.append("[OK] Set ownership on /u01/OFSAA")

        perm_result = await self.ssh_service.execute_command(
            host,
            username,
            password,
            "chmod 775 /u01/OFSAA/FICHOME /u01/OFSAA/FTPSHARE",
            get_pty=True,
        )
        if not perm_result["success"]:
            return {
                "success": False,
                "logs": logs,
                "error": perm_result.get("stderr") or "Failed to set 775 permissions on OFSAA directories",
            }
        logs.append("[OK] Set 775 permissions on /u01/OFSAA/FICHOME and /u01/OFSAA/FTPSHARE")
        return {"success": True, "logs": logs}
