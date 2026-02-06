from .ssh_service import SSHService
from .validation import ValidationService


class MountPointService:
    """Create mount point and OFSAA directories."""

    def __init__(self, ssh_service: SSHService, validation: ValidationService) -> None:
        self.ssh_service = ssh_service
        self.validation = validation

    async def ensure_mount_point(self, host: str, username: str, password: str) -> dict:
        logs: list[str] = []

        u01_check = await self.validation.check_directory_exists(host, username, password, "/u01")
        if u01_check.get("exists"):
            logs.append("[OK] /u01 already exists")
        else:
            result = await self.ssh_service.execute_command(
                host, username, password, "mkdir -p /u01", get_pty=True
            )
            if not result["success"]:
                return {
                    "success": False,
                    "logs": logs,
                    "error": result.get("stderr") or "Failed to create /u01",
                }
            logs.append("[OK] Created /u01")

        result = await self.ssh_service.execute_command(
            host, username, password, "chown -R oracle:oinstall /u01", get_pty=True
        )
        if not result["success"]:
            return {
                "success": False,
                "logs": logs,
                "error": result.get("stderr") or "Failed to set ownership on /u01",
            }
        logs.append("[OK] Set ownership on /u01")

        return {"success": True, "logs": logs}

    async def ensure_ofsaa_directories(self, host: str, username: str, password: str) -> dict:
        logs: list[str] = []
        dirs = [
            "/u01/OFSAA/FICHOME",
            "/u01/OFSAA/FTPSHARE",
            "/u01/installer_kit",
        ]

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
                "error": result.get("stderr") or "Failed to set ownership on OFSAA directories",
            }
        logs.append("[OK] Set ownership on OFSAA directories")

        return {"success": True, "logs": logs}
