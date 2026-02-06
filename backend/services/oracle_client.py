from typing import Optional

from core.config import Config
from services.ssh_service import SSHService
from services.validation import ValidationService
from services.profile import ProfileService


class OracleClientService:
    """Detect Oracle client installation and update profile."""

    def __init__(self, ssh_service: SSHService, validation: ValidationService, profile: ProfileService) -> None:
        self.ssh_service = ssh_service
        self.validation = validation
        self.profile = profile

    async def detect_oracle_sid(self, host: str, username: str, password: str) -> Optional[str]:
        cmd = (
            "if [ -f /etc/oratab ]; then "
            "awk -F: '($1 !~ /^#/ && $1 != \"\") {print $1; exit}' /etc/oratab; "
            "fi"
        )
        result = await self.ssh_service.execute_command(host, username, password, cmd)
        sid = result.get("stdout", "").strip()
        return sid or None

    async def check_existing_oracle_client_and_update_profile(
        self,
        host: str,
        username: str,
        password: str,
        oracle_sid: Optional[str],
    ) -> dict:
        logs: list[str] = []

        oracle_home = await self.validation.find_oracle_client(host, username, password)
        if not oracle_home:
            logs.append("[WARN] Oracle client not found. Skipping ORACLE_HOME update.")
            return {"success": True, "logs": logs}

        tns_admin = f"{oracle_home}/network/admin"
        sid_detected = await self.detect_oracle_sid(host, username, password)
        sid_value = sid_detected or oracle_sid or Config.DEFAULT_ORACLE_SID

        result = await self.profile.update_profile_variable(host, username, password, "ORACLE_HOME", oracle_home)
        if not result["success"]:
            return {"success": False, "logs": logs, "error": result.get("error")}
        logs.append(f"[OK] ORACLE_HOME set to {oracle_home}")

        result = await self.profile.update_profile_variable(host, username, password, "TNS_ADMIN", tns_admin)
        if not result["success"]:
            return {"success": False, "logs": logs, "error": result.get("error")}
        logs.append(f"[OK] TNS_ADMIN set to {tns_admin}")

        result = await self.profile.update_profile_variable(host, username, password, "ORACLE_SID", sid_value)
        if not result["success"]:
            return {"success": False, "logs": logs, "error": result.get("error")}
        logs.append(f"[OK] ORACLE_SID set to {sid_value}")

        return {
            "success": True,
            "logs": logs,
            "oracle_home": oracle_home,
            "tns_admin": tns_admin,
            "oracle_sid": sid_value,
        }
