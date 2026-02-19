"""Recovery service for OSC.SH and setup.sh failures."""

import logging
from typing import Optional

from services.ssh_service import SSHService
from services.utils import shell_escape


logger = logging.getLogger(__name__)


class RecoveryService:
    """Handles cleanup and recovery from installation failures."""

    def __init__(self, ssh_service: SSHService) -> None:
        self.ssh_service = ssh_service

    async def cleanup_after_osc_failure(
        self,
        host: str,
        db_host: str,
        username: str,
        password: str,
        db_username: str,
        db_password: str,
    ) -> dict:
        """Execute full cleanup after OSC.SH failure: kill Java, drop schema, clear cache."""
        logs = ["[RECOVERY] Starting cleanup after osc.sh failure..."]
        failed_steps = []

        # Step 1: Kill all Java processes for oracle user on app server
        logs.append("[RECOVERY] Step 1: Killing all Java processes for oracle user...")
        kill_result = await self._kill_java_processes(host, username, password)
        logs.extend(kill_result.get("logs", []))
        if not kill_result.get("success"):
            failed_steps.append("Kill Java processes")

        # Step 2: Drop database schema on DB server
        logs.append("[RECOVERY] Step 2: Dropping database schema...")
        drop_result = await self._drop_database_schema(db_host, db_username, db_password)
        logs.extend(drop_result.get("logs", []))
        if not drop_result.get("success"):
            failed_steps.append("Drop database schema")

        # Step 3: Clear cache on app server
        logs.append("[RECOVERY] Step 3: Clearing system cache on app server...")
        cache_result_app = await self._clear_system_cache(host, username, password)
        logs.extend(cache_result_app.get("logs", []))
        if not cache_result_app.get("success"):
            failed_steps.append("Clear app server cache")

        # Step 4: Clear cache on DB server
        logs.append("[RECOVERY] Step 4: Clearing system cache on DB server...")
        cache_result_db = await self._clear_system_cache(db_host, db_username, db_password)
        logs.extend(cache_result_db.get("logs", []))
        if not cache_result_db.get("success"):
            failed_steps.append("Clear DB server cache")

        logs.append("")
        if failed_steps:
            logs.append(f"[RECOVERY] PARTIAL SUCCESS - Failed: {', '.join(failed_steps)}")
            return {"success": False, "logs": logs, "failed_steps": failed_steps}

        logs.append("[RECOVERY] Cleanup completed successfully!")
        return {"success": True, "logs": logs, "failed_steps": []}

    async def _kill_java_processes(self, host: str, username: str, password: str) -> dict:
        """Kill all Java processes running under oracle user."""
        logs = []

        # First, check if any Java processes exist
        check_cmd = "pgrep -u oracle java | wc -l"
        check_result = await self.ssh_service.execute_command(host, username, password, check_cmd)
        out = (check_result.get("stdout") or "").strip()
        count = int(out) if out.isdigit() else 0

        if count == 0:
            logs.append("[RECOVERY] No Java processes found for oracle user")
            return {"success": True, "logs": logs}

        logs.append(f"[RECOVERY] Found {count} Java process(es) for oracle user. Killing...")

        # Get process list before killing
        list_cmd = "pgrep -u oracle java | tr '\\n' ' '"
        list_result = await self.ssh_service.execute_command(host, username, password, list_cmd)
        pids = (list_result.get("stdout") or "").strip()
        if pids:
            logs.append(f"[RECOVERY] Processes to kill: {pids}")

        # Kill all Java processes for oracle user
        kill_cmd = "pkill -9 -u oracle java"
        kill_result = await self.ssh_service.execute_command(host, username, password, kill_cmd)

        # Verify they're killed
        verify_cmd = "pgrep -u oracle java | wc -l"
        verify_result = await self.ssh_service.execute_command(host, username, password, verify_cmd)
        verify_out = (verify_result.get("stdout") or "").strip()
        remaining = int(verify_out) if verify_out.isdigit() else 0

        if remaining == 0:
            logs.append(f"[RECOVERY] Successfully killed {count} Java process(es)")
            return {"success": True, "logs": logs}
        else:
            logs.append(f"[RECOVERY] ERROR: {remaining} Java process(es) still running after kill attempt")
            return {"success": False, "logs": logs}

    async def _drop_database_schema(self, host: str, username: str, password: str) -> dict:
        """Drop all OFSAA users and tablespaces from Oracle database."""
        logs = []

        # List of users to drop
        users = ["OFSATOMIC", "OFSCONFIG"]

        # List of tablespaces to drop
        tablespaces = [
            "DATA_FATCA_TBSP", "COMM_DATA_TBSP", "IDX_KDD_TBSP", "DATA_MANTAS_TBSP",
            "DATA_MINER_TBSP", "IDX_MKT1_TBSP", "IDX_MKT2_TBSP", "DATA_CONF_TBSP",
            "DATA_CTR_TBSP", "DATA_FSDF1_TBSP", "IDX_CTR_TBSP", "IDX_MINER_TBSP",
            "IDX_BUS3_TBSP", "DATA_CM_TBSP", "IDX_BUS1_TBSP", "IDX_FATCA_TBSP",
            "IDX_BUS4_TBSP", "IDX_BUS5_TBSP", "IDX_BUS2_TBSP", "IDX_MKT4_TBSP",
            "IDX_CM_TBSP", "IDX_MKT3_TBSP", "DATA_AM_TBSP", "DATA_BUS6_TBSP",
            "DATA_MKT3_TBSP", "DATA_KYC_TBSP", "IDX_KYC_TBSP", "DATA_OB_TBSP",
            "DATA_MKT1_TBSP", "IDX_OB_TBSP", "IDX_BUS8_TBSP", "DATA_MKT2_TBSP",
            "DATA_MKT4_TBSP", "IDX_AM_TBSP", "IDX_MANTAS_TBSP", "IDX_BUS6_TBSP",
            "IDX_BUS7_TBSP", "DATA_BUS4_TBSP", "DATA_BUS8_TBSP", "DATA_KDD_TBSP",
            "DATA_BUS5_TBSP", "DATA_BUS7_TBSP", "DATA_BUS1_TBSP", "DATA_BUS2_TBSP",
            "DATA_BUS3_TBSP", "IDX_FSDF1_TBSP",
        ]

        logs.append("[RECOVERY] Dropping OFSAA users...")
        for user in users:
            drop_user_sql = f"drop user {user} CASCADE;"
            # Use echo with sqlplus for safer command execution
            cmd = f"echo \"{drop_user_sql}\" | sqlplus -s / as sysdba"
            result = await self.ssh_service.execute_command(host, username, password, cmd)
            if result.get("success") or "ORA-01918" not in (result.get("stderr", "") or ""):
                logs.append(f"[RECOVERY] Dropped user: {user}")
            else:
                stderr = result.get("stderr", "")
                if "does not exist" not in stderr and "ORA-01918" not in stderr:
                    logs.append(f"[RECOVERY] User {user} not found (already dropped or does not exist)")
                else:
                    logs.append(f"[RECOVERY] ERROR dropping user {user}: {stderr}")

        logs.append("[RECOVERY] Dropping tablespaces...")
        for tbsp in tablespaces:
            drop_tbsp_sql = f"DROP TABLESPACE {tbsp} INCLUDING CONTENTS AND DATAFILES CASCADE CONSTRAINTS;"
            cmd = f"echo \"{drop_tbsp_sql}\" | sqlplus -s / as sysdba"
            result = await self.ssh_service.execute_command(host, username, password, cmd)
            if result.get("success") or "ORA-00959" not in (result.get("stderr", "") or ""):
                logs.append(f"[RECOVERY] Dropped tablespace: {tbsp}")
            else:
                stderr = result.get("stderr", "")
                if "does not exist" not in stderr and "ORA-00959" not in stderr:
                    logs.append(f"[RECOVERY] Tablespace {tbsp} not found (already dropped or does not exist)")
                else:
                    logs.append(f"[RECOVERY] ERROR dropping tablespace {tbsp}: {stderr}")

        logs.append("[RECOVERY] Database schema cleanup completed")
        return {"success": True, "logs": logs}

    async def _clear_system_cache(self, host: str, username: str, password: str) -> dict:
        """Clear system cache using drop_caches."""
        logs = []

        # Clear cache: echo 2 | tee /proc/sys/vm/drop_caches
        cmd = "echo 2 | sudo tee /proc/sys/vm/drop_caches"
        result = await self.ssh_service.execute_command(host, username, password, cmd)

        if result.get("success"):
            logs.append(f"[RECOVERY] System cache cleared on {host}")
            return {"success": True, "logs": logs}
        else:
            stderr = result.get("stderr", "")
            logs.append(f"[RECOVERY] ERROR clearing cache: {stderr}")
            return {"success": False, "logs": logs}
