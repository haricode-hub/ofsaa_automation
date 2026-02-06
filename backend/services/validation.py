from typing import Optional

from .ssh_service import SSHService


class ValidationService:
    """Common validation helpers for installation steps."""

    def __init__(self, ssh_service: SSHService) -> None:
        self.ssh_service = ssh_service

    async def check_user_exists(self, host: str, username: str, password: str, user: str) -> dict:
        result = await self.ssh_service.execute_command(
            host, username, password, f"id -u {user}", timeout=15
        )
        return {"exists": result["success"], "message": result.get("stdout", "")}

    async def check_group_exists(self, host: str, username: str, password: str, group: str) -> dict:
        result = await self.ssh_service.execute_command(
            host, username, password, f"getent group {group}", timeout=15
        )
        return {"exists": result["success"], "message": result.get("stdout", "")}

    async def check_directory_exists(self, host: str, username: str, password: str, path: str) -> dict:
        result = await self.ssh_service.execute_command(
            host, username, password, f"test -d {path}"
        )
        return {"exists": result["success"]}

    async def check_file_exists(self, host: str, username: str, password: str, path: str) -> dict:
        result = await self.ssh_service.execute_command(
            host, username, password, f"test -f {path}"
        )
        return {"exists": result["success"]}

    async def check_package_installed(self, host: str, username: str, password: str, package: str) -> dict:
        cmd = (
            "if command -v rpm >/dev/null 2>&1; then "
            f"rpm -q {package}; "
            "elif command -v dnf >/dev/null 2>&1 || command -v yum >/dev/null 2>&1; then "
            f"command -v {package}; "
            "else "
            f"command -v {package}; "
            "fi"
        )
        result = await self.ssh_service.execute_command(host, username, password, cmd)
        return {"installed": result["success"], "message": result.get("stdout", "")}

    async def get_package_version(self, host: str, username: str, password: str, package: str) -> dict:
        cmd = (
            "if command -v rpm >/dev/null 2>&1; then "
            f"rpm -q {package}; "
            f"elif command -v {package} >/dev/null 2>&1; then {package} --version; "
            "else echo 'unknown'; fi"
        )
        result = await self.ssh_service.execute_command(host, username, password, cmd)
        return {"success": result["success"], "message": result.get("stdout", "")}

    async def find_oracle_client(self, host: str, username: str, password: str) -> Optional[str]:
        cmd = (
            "for d in "
            "/u01/app/oracle/product/19.0.0/client_1 "
            "/u01/app/oracle/product/19c/client_1 "
            "/opt/oracle/product/19c/client_1 "
            "/opt/oracle/product/19.0.0/client_1; "
            "do if [ -x \"$d/bin/sqlplus\" ]; then echo $d; exit 0; fi; done; "
            "exit 1"
        )
        result = await self.ssh_service.execute_command(host, username, password, cmd)
        if result["success"] and result.get("stdout"):
            return result["stdout"].splitlines()[0].strip()
        return None

    async def find_java_installation(self, host: str, username: str, password: str) -> Optional[str]:
        cmd = (
            "if [ -d /u01/jdk-11.0.16 ]; then echo /u01/jdk-11.0.16; exit 0; fi; "
            "if command -v java >/dev/null 2>&1; then "
            "java_path=$(readlink -f $(command -v java)); "
            "if [ -n \"$java_path\" ]; then "
            "echo ${java_path%/bin/java}; exit 0; fi; fi; "
            "exit 1"
        )
        result = await self.ssh_service.execute_command(host, username, password, cmd)
        if result["success"] and result.get("stdout"):
            return result["stdout"].splitlines()[0].strip()
        return None

    async def backup_file(self, host: str, username: str, password: str, path: str) -> dict:
        cmd = (
            f"if [ -f {path} ]; then "
            "ts=$(date +%Y%m%d_%H%M%S); "
            f"cp {path} {path}.backup.$ts; "
            "echo backup_created; else echo no_file; fi"
        )
        result = await self.ssh_service.execute_command(host, username, password, cmd)
        return {"success": result["success"], "message": result.get("stdout", "")}
