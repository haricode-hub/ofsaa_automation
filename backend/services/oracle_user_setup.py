from .ssh_service import SSHService
from .validation import ValidationService


class OracleUserSetupService:
    """Create oracle user and oinstall group if missing."""

    def __init__(self, ssh_service: SSHService, validation: ValidationService) -> None:
        self.ssh_service = ssh_service
        self.validation = validation

    async def ensure_oracle_user(self, host: str, username: str, password: str) -> dict:
        logs: list[str] = []

        group_check = await self.validation.check_group_exists(host, username, password, "oinstall")
        if group_check.get("exists"):
            logs.append("[OK] oinstall group already exists")
        else:
            result = await self.ssh_service.execute_command(
                host, username, password, "groupadd -f oinstall", get_pty=True
            )
            if not result["success"]:
                return {
                    "success": False,
                    "logs": logs,
                    "error": result.get("stderr") or "Failed to create oinstall group",
                }
            logs.append("[OK] Created oinstall group")

        user_check = await self.validation.check_user_exists(host, username, password, "oracle")
        if user_check.get("exists"):
            logs.append("[OK] oracle user already exists")
        else:
            result = await self.ssh_service.execute_command(
                host,
                username,
                password,
                "useradd -g oinstall -m oracle",
                get_pty=True,
            )
            if not result["success"]:
                return {
                    "success": False,
                    "logs": logs,
                    "error": result.get("stderr") or "Failed to create oracle user",
                }
            logs.append("[OK] Created oracle user")

        return {"success": True, "logs": logs}
