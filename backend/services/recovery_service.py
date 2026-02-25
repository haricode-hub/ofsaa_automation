"""Recovery service for OSC.SH and setup.sh failures, plus backup/restore."""

import logging
from typing import Optional

from core.config import Config
from services.ssh_service import SSHService
from services.utils import shell_escape


logger = logging.getLogger(__name__)


class RecoveryService:
    """Handles cleanup, backup, and recovery from installation failures."""

    def __init__(self, ssh_service: SSHService) -> None:
        self.ssh_service = ssh_service

    # ------------------------------------------------------------------
    # Sqlplus connection helper
    # ------------------------------------------------------------------
    def _sqlplus_conn_str(
        self,
        db_sys_password: str,
        db_jdbc_host: str,
        db_jdbc_port: int,
        db_jdbc_service: str,
    ) -> str:
        """Build sqlplus connection string: sys/<pass>@<host>:<port>/<service> as sysdba"""
        return f'"sys/{db_sys_password}@{db_jdbc_host}:{db_jdbc_port}/{db_jdbc_service} as sysdba"'

    # ------------------------------------------------------------------
    # BD osc.sh failure cleanup
    # ------------------------------------------------------------------
    async def cleanup_after_osc_failure(
        self,
        app_host: str,
        app_username: str,
        app_password: str,
        db_host: str,
        db_username: str,
        db_password: str,
        *,
        db_sys_password: Optional[str] = None,
        db_jdbc_host: Optional[str] = None,
        db_jdbc_port: int = 1521,
        db_jdbc_service: Optional[str] = None,
    ) -> dict:
        """Execute full cleanup after OSC.SH failure: kill Java, drop schema, clear cache."""
        logs = ["[RECOVERY] Starting cleanup after osc.sh failure..."]
        failed_steps = []

        # Step 1: Kill all Java processes for oracle user on app server
        logs.append("[RECOVERY] Step 1: Killing all Java processes for oracle user...")
        kill_result = await self._kill_java_processes(app_host, app_username, app_password)
        logs.extend(kill_result.get("logs", []))
        if not kill_result.get("success"):
            failed_steps.append("Kill Java processes")

        # Step 2: Drop database schema on DB server
        logs.append("[RECOVERY] Step 2: Dropping database schemas and tablespaces...")
        drop_result = await self._drop_database_schema(
            db_host, db_username, db_password,
            db_sys_password=db_sys_password,
            db_jdbc_host=db_jdbc_host,
            db_jdbc_port=db_jdbc_port,
            db_jdbc_service=db_jdbc_service,
        )
        logs.extend(drop_result.get("logs", []))
        if not drop_result.get("success"):
            failed_steps.append("Drop database schema")

        # Step 3: Clear cache on app server
        logs.append("[RECOVERY] Step 3: Clearing system cache on app server...")
        cache_result_app = await self._clear_system_cache(app_host, app_username, app_password)
        logs.extend(cache_result_app.get("logs", []))
        if not cache_result_app.get("success"):
            failed_steps.append("Clear app server cache")

        # Step 4: Clear cache on DB server (only if DB host differs from app host)
        if db_host and db_host != app_host:
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

    # ------------------------------------------------------------------
    # Backup methods
    # ------------------------------------------------------------------
    async def ensure_backup_restore_scripts(
        self,
        host: str,
        username: str,
        password: str,
    ) -> dict:
        """Ensure backup_Restore scripts exist in the git repo on the target server."""
        logs = []
        repo_dir = Config.REPO_DIR
        backup_dir = f"{repo_dir}/backup_Restore"

        # Check if backup_Restore folder and scripts exist
        check_cmd = (
            f"test -f {backup_dir}/backup_ofs_schemas.sh && "
            f"test -f {backup_dir}/restore_ofs_schemas.sh && "
            f"echo 'SCRIPTS_FOUND' || echo 'SCRIPTS_MISSING'"
        )
        result = await self.ssh_service.execute_command(host, username, password, check_cmd)
        stdout = (result.get("stdout") or "").strip()

        if "SCRIPTS_FOUND" in stdout:
            logs.append(f"[BACKUP] Backup/restore scripts found in {backup_dir}")
            # Ensure scripts are executable
            chmod_cmd = f"chmod +x {backup_dir}/backup_ofs_schemas.sh {backup_dir}/restore_ofs_schemas.sh"
            await self.ssh_service.execute_command(host, username, password, chmod_cmd)
            logs.append("[BACKUP] Scripts set to executable")
            return {"success": True, "logs": logs, "backup_dir": backup_dir}
        else:
            logs.append(f"[BACKUP] ERROR: Backup/restore scripts not found in {backup_dir}")
            logs.append("[BACKUP] Ensure the Git repo contains backup_Restore/backup_ofs_schemas.sh and restore_ofs_schemas.sh")
            return {"success": False, "logs": logs, "error": "Backup/restore scripts not found in Git repo"}

    async def backup_application(
        self,
        host: str,
        username: str,
        password: str,
        *,
        ofsaa_dir: str = "/u01",
        backup_filename: str = "OFSAA_BKP.tar.gz",
    ) -> dict:
        """Create application backup: tar -cvf OFSAA_BKP.tar.gz OFSAA"""
        logs = ["[BACKUP] Starting application backup..."]

        # Verify OFSAA directory exists
        check_cmd = f"test -d {ofsaa_dir}/OFSAA && echo 'EXISTS' || echo 'MISSING'"
        check_result = await self.ssh_service.execute_command(host, username, password, check_cmd)
        if "MISSING" in (check_result.get("stdout") or ""):
            logs.append(f"[BACKUP] ERROR: {ofsaa_dir}/OFSAA directory not found")
            return {"success": False, "logs": logs, "error": "OFSAA directory not found"}

        # Remove old backup if exists
        rm_cmd = f"rm -f {ofsaa_dir}/{backup_filename}"
        await self.ssh_service.execute_command(host, username, password, rm_cmd)

        # Create tar backup
        tar_cmd = f"cd {ofsaa_dir} && tar -cvf {backup_filename} OFSAA"
        logs.append(f"[BACKUP] Running: cd {ofsaa_dir} && tar -cvf {backup_filename} OFSAA")
        tar_result = await self.ssh_service.execute_command(
            host, username, password, tar_cmd, timeout=3600
        )

        if not tar_result.get("success"):
            stderr = tar_result.get("stderr", "")
            logs.append(f"[BACKUP] ERROR: Application backup failed: {stderr}")
            return {"success": False, "logs": logs, "error": f"Application backup failed: {stderr}"}

        # Verify backup file was created
        verify_cmd = f"test -f {ofsaa_dir}/{backup_filename} && stat --format='%s' {ofsaa_dir}/{backup_filename}"
        verify_result = await self.ssh_service.execute_command(host, username, password, verify_cmd)
        file_size = (verify_result.get("stdout") or "").strip()

        if file_size and file_size.isdigit():
            size_mb = int(file_size) / (1024 * 1024)
            logs.append(f"[BACKUP] Application backup created: {ofsaa_dir}/{backup_filename} ({size_mb:.1f} MB)")
        else:
            logs.append(f"[BACKUP] Application backup created: {ofsaa_dir}/{backup_filename}")

        return {"success": True, "logs": logs, "backup_path": f"{ofsaa_dir}/{backup_filename}"}

    async def backup_db_schemas(
        self,
        host: str,
        username: str,
        password: str,
        *,
        db_sys_password: str,
        db_jdbc_service: str,
    ) -> dict:
        """Run DB schema backup: backup_ofs_schemas.sh system <DB_PASS> <SERVICE>"""
        logs = ["[BACKUP] Starting DB schema backup..."]
        repo_dir = Config.REPO_DIR
        backup_dir = f"{repo_dir}/backup_Restore"

        # Ensure scripts exist first
        scripts_result = await self.ensure_backup_restore_scripts(host, username, password)
        logs.extend(scripts_result.get("logs", []))
        if not scripts_result.get("success"):
            return {"success": False, "logs": logs, "error": "Backup scripts not available"}

        # Run backup script: ./backup_ofs_schemas.sh system <DB_PASS> <SERVICE>
        backup_cmd = (
            f"cd {backup_dir} && "
            f"./backup_ofs_schemas.sh system {shell_escape(db_sys_password)} {shell_escape(db_jdbc_service)}"
        )
        logs.append(f"[BACKUP] Running: cd {backup_dir} && ./backup_ofs_schemas.sh system ****** {db_jdbc_service}")
        backup_result = await self.ssh_service.execute_command(
            host, username, password, backup_cmd, timeout=3600
        )

        stdout = (backup_result.get("stdout") or "").strip()
        stderr = (backup_result.get("stderr") or "").strip()

        if stdout:
            # Log output but mask password
            for line in stdout.splitlines():
                logs.append(f"[BACKUP] {line}")

        if not backup_result.get("success"):
            logs.append(f"[BACKUP] ERROR: DB schema backup failed: {stderr}")
            return {"success": False, "logs": logs, "error": f"DB schema backup failed: {stderr}"}

        logs.append("[BACKUP] DB schema backup completed successfully")
        return {"success": True, "logs": logs}

    # ------------------------------------------------------------------
    # Restore methods
    # ------------------------------------------------------------------
    async def restore_application(
        self,
        host: str,
        username: str,
        password: str,
        *,
        ofsaa_dir: str = "/u01",
        backup_filename: str = "OFSAA_BKP.tar.gz",
    ) -> dict:
        """Restore application: rm -rf OFSAA then tar -xvf OFSAA_BKP.tar.gz"""
        logs = ["[RESTORE] Starting application restore..."]

        # Verify backup file exists
        check_cmd = f"test -f {ofsaa_dir}/{backup_filename} && echo 'EXISTS' || echo 'MISSING'"
        check_result = await self.ssh_service.execute_command(host, username, password, check_cmd)
        if "MISSING" in (check_result.get("stdout") or ""):
            logs.append(f"[RESTORE] ERROR: Backup file {ofsaa_dir}/{backup_filename} not found")
            return {"success": False, "logs": logs, "error": "Application backup file not found"}

        # Step 1: Remove existing OFSAA directory (mandatory per guide)
        logs.append("[RESTORE] Step 1: Removing existing OFSAA directory...")
        rm_cmd = f"rm -rf {ofsaa_dir}/OFSAA"
        rm_result = await self.ssh_service.execute_command(host, username, password, rm_cmd, timeout=600)
        if not rm_result.get("success"):
            logs.append(f"[RESTORE] ERROR: Failed to remove OFSAA directory: {rm_result.get('stderr', '')}")
            return {"success": False, "logs": logs, "error": "Failed to remove OFSAA directory"}
        logs.append("[RESTORE] Existing OFSAA directory removed")

        # Step 2: Extract backup
        logs.append("[RESTORE] Step 2: Restoring application from backup...")
        tar_cmd = f"cd {ofsaa_dir} && tar -xvf {backup_filename}"
        tar_result = await self.ssh_service.execute_command(
            host, username, password, tar_cmd, timeout=3600
        )
        if not tar_result.get("success"):
            stderr = tar_result.get("stderr", "")
            logs.append(f"[RESTORE] ERROR: Application restore failed: {stderr}")
            return {"success": False, "logs": logs, "error": f"Application restore failed: {stderr}"}

        # Verify OFSAA directory exists after restore
        verify_cmd = f"test -d {ofsaa_dir}/OFSAA && echo 'RESTORED' || echo 'FAILED'"
        verify_result = await self.ssh_service.execute_command(host, username, password, verify_cmd)
        if "RESTORED" in (verify_result.get("stdout") or ""):
            logs.append("[RESTORE] Application restored successfully from backup")
            return {"success": True, "logs": logs}
        else:
            logs.append("[RESTORE] ERROR: OFSAA directory not found after restore")
            return {"success": False, "logs": logs, "error": "OFSAA directory not found after restore"}

    async def restore_db_schemas(
        self,
        host: str,
        username: str,
        password: str,
        *,
        db_sys_password: str,
        db_jdbc_service: str,
    ) -> dict:
        """Run DB schema restore: restore_ofs_schemas.sh system <DB_PASS> <SERVICE>"""
        logs = ["[RESTORE] Starting DB schema restore..."]
        repo_dir = Config.REPO_DIR
        backup_dir = f"{repo_dir}/backup_Restore"

        # Ensure scripts exist
        scripts_result = await self.ensure_backup_restore_scripts(host, username, password)
        logs.extend(scripts_result.get("logs", []))
        if not scripts_result.get("success"):
            return {"success": False, "logs": logs, "error": "Restore scripts not available"}

        # Run restore script: ./restore_ofs_schemas.sh system <DB_PASS> <SERVICE>
        restore_cmd = (
            f"cd {backup_dir} && "
            f"./restore_ofs_schemas.sh system {shell_escape(db_sys_password)} {shell_escape(db_jdbc_service)}"
        )
        logs.append(f"[RESTORE] Running: cd {backup_dir} && ./restore_ofs_schemas.sh system ****** {db_jdbc_service}")
        restore_result = await self.ssh_service.execute_command(
            host, username, password, restore_cmd, timeout=3600
        )

        stdout = (restore_result.get("stdout") or "").strip()
        stderr = (restore_result.get("stderr") or "").strip()

        if stdout:
            for line in stdout.splitlines():
                logs.append(f"[RESTORE] {line}")

        if not restore_result.get("success"):
            logs.append(f"[RESTORE] ERROR: DB schema restore failed: {stderr}")
            return {"success": False, "logs": logs, "error": f"DB schema restore failed: {stderr}"}

        logs.append("[RESTORE] DB schema restore completed successfully")
        return {"success": True, "logs": logs}

    async def full_restore_to_bd_state(
        self,
        host: str,
        username: str,
        password: str,
        *,
        db_sys_password: str,
        db_jdbc_service: str,
        ofsaa_dir: str = "/u01",
        backup_filename: str = "OFSAA_BKP.tar.gz",
    ) -> dict:
        """Full restore to BD state: rm OFSAA -> restore app tar -> restore DB schemas."""
        logs = ["[RESTORE] ===== FULL RESTORE TO BD STATE ====="]
        failed_steps = []

        # Step 1: Restore application (rm -rf + tar extract)
        logs.append("[RESTORE] --- Step 1: Restoring application backup ---")
        app_result = await self.restore_application(
            host, username, password,
            ofsaa_dir=ofsaa_dir,
            backup_filename=backup_filename,
        )
        logs.extend(app_result.get("logs", []))
        if not app_result.get("success"):
            failed_steps.append("Restore application")

        # Step 2: Restore DB schemas
        logs.append("[RESTORE] --- Step 2: Restoring DB schemas ---")
        db_result = await self.restore_db_schemas(
            host, username, password,
            db_sys_password=db_sys_password,
            db_jdbc_service=db_jdbc_service,
        )
        logs.extend(db_result.get("logs", []))
        if not db_result.get("success"):
            failed_steps.append("Restore DB schemas")

        if failed_steps:
            logs.append(f"[RESTORE] PARTIAL RESTORE - Failed steps: {', '.join(failed_steps)}")
            return {"success": False, "logs": logs, "failed_steps": failed_steps}

        logs.append("[RESTORE] ===== FULL RESTORE TO BD STATE COMPLETED SUCCESSFULLY =====")
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

    async def _drop_database_schema(
        self,
        host: str,
        username: str,
        password: str,
        *,
        db_sys_password: Optional[str] = None,
        db_jdbc_host: Optional[str] = None,
        db_jdbc_port: int = 1521,
        db_jdbc_service: Optional[str] = None,
    ) -> dict:
        """Drop all OFSAA users and tablespaces from Oracle database."""
        logs = []

        # Build sqlplus connection string
        if db_sys_password and db_jdbc_host and db_jdbc_service:
            sqlplus_conn = self._sqlplus_conn_str(db_sys_password, db_jdbc_host, db_jdbc_port, db_jdbc_service)
            logs.append(f"[RECOVERY] Using sqlplus connection: sys/******@{db_jdbc_host}:{db_jdbc_port}/{db_jdbc_service}")
        else:
            # Fallback to OS authentication
            sqlplus_conn = '"/ as sysdba"'
            logs.append("[RECOVERY] WARNING: No DB credentials provided, using OS authentication (/ as sysdba)")

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

        # Build a single SQL script for all drops (more efficient than individual commands)
        sql_lines = []
        for user in users:
            sql_lines.append(f"drop user {user} CASCADE;")
        for tbsp in tablespaces:
            sql_lines.append(f"DROP TABLESPACE {tbsp} INCLUDING CONTENTS AND DATAFILES CASCADE CONSTRAINTS;")
        sql_lines.append("EXIT;")
        full_sql = "\\n".join(sql_lines)

        logs.append("[RECOVERY] Dropping OFSAA users and tablespaces...")
        cmd = f'echo -e "{full_sql}" | sqlplus -s {sqlplus_conn}'
        result = await self.ssh_service.execute_command(host, username, password, cmd, timeout=600)

        stdout = (result.get("stdout") or "").strip()
        stderr = (result.get("stderr") or "").strip()

        if stdout:
            for line in stdout.splitlines():
                line = line.strip()
                if line:
                    logs.append(f"[RECOVERY] {line}")

        # Check for critical errors (connection failures, etc.)
        # ORA-01918 (user does not exist) and ORA-00959 (tablespace does not exist) are non-fatal
        critical_errors = []
        for line in (stdout + "\n" + stderr).splitlines():
            if "ORA-" in line and "ORA-01918" not in line and "ORA-00959" not in line:
                critical_errors.append(line.strip())

        if critical_errors:
            logs.append(f"[RECOVERY] WARNING: Some errors during schema drop: {'; '.join(critical_errors)}")

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
