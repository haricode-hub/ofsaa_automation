"""Recovery service for OSC.SH and setup.sh failures, plus backup/restore."""

import logging
from typing import Optional, Callable, Awaitable

from core.config import Config
from services.ssh_service import SSHService
from services.utils import shell_escape
from services.backup import BackupService
from services.restore import RestoreService


logger = logging.getLogger(__name__)


class RecoveryService:
    """Handles cleanup, backup, and recovery from installation failures."""

    def __init__(self, ssh_service: SSHService) -> None:
        self.ssh_service = ssh_service
        self.backup = BackupService(ssh_service)
        self.restore = RestoreService(ssh_service)

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
        schema_config_schema_name: Optional[str] = None,
        schema_atomic_schema_name: Optional[str] = None,
        db_ssh_host: Optional[str] = None,
        db_ssh_username: Optional[str] = None,
        db_ssh_password: Optional[str] = None,
    ) -> dict:
        """Execute full cleanup after OSC.SH failure: kill Java, drop schema, clear cache.
        
        Args:
            schema_config_schema_name: CONFIG schema name from UI (e.g., "OFSCONFIG")
            schema_atomic_schema_name: ATOMIC schema name from UI (e.g., "OFSATOMIC")
        """
        logs = ["[RECOVERY] Starting cleanup after osc.sh failure..."]
        failed_steps = []

        # Step 1: Kill all Java processes for oracle user on app server
        logs.append("[RECOVERY] Step 1: Killing all Java processes for oracle user...")
        kill_result = await self.kill_java_processes(app_host, app_username, app_password)
        logs.extend(kill_result.get("logs", []))
        if not kill_result.get("success"):
            failed_steps.append("Kill Java processes")

        # Step 2: Remove OFSAA folder on app server
        logs.append("[RECOVERY] Step 2: Removing /u01/OFSAA directory...")
        rm_result = await self._remove_ofsaa_directory(app_host, app_username, app_password)
        logs.extend(rm_result.get("logs", []))
        if not rm_result.get("success"):
            failed_steps.append("Remove OFSAA directory")

        # Step 3: Drop database schema (run sqlplus from app server, connects to DB remotely)
        logs.append("[RECOVERY] Step 3: Dropping database schemas and tablespaces...")
        # If DB-side SSH credentials provided, execute the schema drop on the DB host directly.
        if db_ssh_host and db_ssh_host != app_host:
            drop_exec_host = db_ssh_host
            drop_exec_user = db_ssh_username or db_username
            drop_exec_pass = db_ssh_password or db_password
            # When running on DB host, connect to local Oracle instance unless a separate jdbc host was provided
            drop_jdbc_host = db_jdbc_host or 'localhost'
            drop_result = await self._drop_database_schema(
                drop_exec_host, drop_exec_user, drop_exec_pass,
                db_sys_password=db_sys_password,
                db_jdbc_host=drop_jdbc_host,
                db_jdbc_port=db_jdbc_port,
                db_jdbc_service=db_jdbc_service,
                schema_config_schema_name=schema_config_schema_name,
                schema_atomic_schema_name=schema_atomic_schema_name,
            )
        else:
            drop_result = await self._drop_database_schema(
                app_host, app_username, app_password,
                db_sys_password=db_sys_password,
                db_jdbc_host=db_jdbc_host,
                db_jdbc_port=db_jdbc_port,
                db_jdbc_service=db_jdbc_service,
                schema_config_schema_name=schema_config_schema_name,
                schema_atomic_schema_name=schema_atomic_schema_name,
            )
        logs.extend(drop_result.get("logs", []))
        if not drop_result.get("success"):
            failed_steps.append("Drop database schema")

        # Step 4: Clear cache on app server
        logs.append("[RECOVERY] Step 4: Clearing system cache on app server...")
        cache_result_app = await self._clear_system_cache(app_host, app_username, app_password)
        logs.extend(cache_result_app.get("logs", []))
        if not cache_result_app.get("success"):
            failed_steps.append("Clear app server cache")

        # Step 5: Clear cache on DB server (only if DB host differs from app host)
        target_cache_host = db_ssh_host or db_host
        target_cache_user = db_ssh_username or db_username
        target_cache_pass = db_ssh_password or db_password
        if target_cache_host and target_cache_host != app_host:
            logs.append("[RECOVERY] Step 5: Clearing system cache on DB server...")
            cache_result_db = await self._clear_system_cache(target_cache_host, target_cache_user, target_cache_pass)
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
    # Auto-detect ORACLE_HOME on remote host
    # ------------------------------------------------------------------
    async def _detect_oracle_home(
        self,
        host: str,
        username: str,
        password: str,
    ) -> str:
        """Auto-detect ORACLE_HOME from /etc/oratab on the DB host.

        Parses lines like ``OFSAADB:/u01/app/oracle/product/19.0.0/dbhome_1:N``
        and returns the second colon-delimited field.

        Falls back to searching the filesystem if /etc/oratab is missing or empty.
        """
        fallback = "/u01/app/oracle/product/19.0.0/dbhome_1"

        # Primary: parse /etc/oratab (skip comments & blank lines)
        oratab_cmd = (
            "grep '^[A-Za-z]' /etc/oratab 2>/dev/null | head -1 | cut -d: -f2"
        )
        result = await self.ssh_service.execute_command(host, username, password, oratab_cmd)
        detected = (result.get("stdout") or "").strip()
        if detected and "/" in detected:
            logger.info("Detected ORACLE_HOME from /etc/oratab: %s", detected)
            return detected

        # Fallback: locate sqlplus binary
        find_cmd = (
            "find /u01/app/oracle/product -name sqlplus -type f 2>/dev/null "
            "| head -1 | sed 's|/bin/sqlplus||'"
        )
        result2 = await self.ssh_service.execute_command(host, username, password, find_cmd)
        detected2 = (result2.get("stdout") or "").strip()
        if detected2 and "/" in detected2:
            logger.info("Detected ORACLE_HOME via find: %s", detected2)
            return detected2

        logger.warning("Could not auto-detect ORACLE_HOME, using fallback: %s", fallback)
        return fallback

    # ------------------------------------------------------------------
    # Backup methods
    # ------------------------------------------------------------------
    async def backup_application(
        self,
        host: str,
        username: str,
        password: str,
        *,
        ofsaa_dir: str = "/u01",
        backup_tag: str = "BD",
    ) -> dict:
        """Create application backup with dated filename.

        Filename format: OFSAA_BKP_<tag>_<YYYYMMDD_HHMMSS>.tar.gz
        e.g. OFSAA_BKP_BD_20260226_143000.tar.gz
             OFSAA_BKP_ECM_20260226_160500.tar.gz
        """
        from datetime import datetime as _dt
        timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"OFSAA_BKP_{backup_tag}_{timestamp}.tar.gz"
        logs = [f"[BACKUP] Starting application backup as oracle user (tag={backup_tag})..."]

        # Verify OFSAA directory exists
        check_cmd = f"test -d {ofsaa_dir}/OFSAA && echo 'EXISTS' || echo 'MISSING'"
        check_result = await self.ssh_service.execute_command(host, username, password, check_cmd)
        if "MISSING" in (check_result.get("stdout") or ""):
            logs.append(f"[BACKUP] ERROR: {ofsaa_dir}/OFSAA directory not found")
            return {"success": False, "logs": logs, "error": "OFSAA directory not found"}

        # Remove old backup if exists (as oracle)
        rm_inner = f"rm -f {ofsaa_dir}/{backup_filename}"
        if username == "oracle":
            rm_cmd = rm_inner
        else:
            rm_cmd = (
                "if command -v sudo >/dev/null 2>&1; then "
                f"sudo -u oracle bash -c {shell_escape(rm_inner)}; "
                "else "
                f"su - oracle -c {shell_escape(rm_inner)}; "
                "fi"
            )
        await self.ssh_service.execute_command(host, username, password, rm_cmd)

        # Create tar backup as oracle user
        tar_inner = f"cd {ofsaa_dir} && tar -cvf {backup_filename} OFSAA"
        if username == "oracle":
            tar_cmd = tar_inner
        else:
            tar_cmd = (
                "if command -v sudo >/dev/null 2>&1; then "
                f"sudo -u oracle bash -c {shell_escape(tar_inner)}; "
                "else "
                f"su - oracle -c {shell_escape(tar_inner)}; "
                "fi"
            )
        logs.append(f"[BACKUP] Running as oracle: cd {ofsaa_dir} && tar -cvf {backup_filename} OFSAA")
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
        db_oracle_sid: str = "OFSAADB",
        schema_config_schema_name: Optional[str] = None,
        schema_atomic_schema_name: Optional[str] = None,
        db_ssh_host: Optional[str] = None,
        db_ssh_username: Optional[str] = None,
        db_ssh_password: Optional[str] = None,
        backup_tag: str = "BD",
        on_log: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> dict:
        """Run DB schema backup using Data Pump (expdp) + metadata capture.

        Schema names must be supplied explicitly by the caller.
        Use build_backup_params() at the call site to guarantee correct values.
        Hardcoded fallbacks have been intentionally removed.
        """
        schemas = [s for s in [schema_atomic_schema_name, schema_config_schema_name] if s]
        if not schemas:
            return {
                "success": False,
                "logs": ["[BACKUP] ERROR: No schema names provided. Use build_backup_params() to resolve them."],
                "error": "No schema names provided for backup",
            }
        schemas_str = ",".join(schemas)

        # Resolve DB host SSH credentials
        target_host = db_ssh_host or host
        target_user = db_ssh_username or username
        target_pass = db_ssh_password or password

        return await self.backup.run_backup(
            db_ssh_host=target_host,
            db_ssh_username=target_user,
            db_ssh_password=target_pass,
            db_sys_password=db_sys_password,
            pdb_name=db_jdbc_service,
            schemas=schemas_str,
            oracle_sid=db_oracle_sid,
            backup_tag=backup_tag,
            on_log=on_log,
        )

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
        backup_tag: str = "BD",
        backup_path: Optional[str] = None,
    ) -> dict:
        """Restore application from the most recent OFSAA_BKP_<tag>_*.tar.gz backup.

        Falls back to legacy OFSAA_BKP.tar.gz if no tagged backup found.
        """
        logs = ["[RESTORE] Starting application restore as oracle user..."]

        backup_file_path = backup_path
        if backup_file_path:
            import os as _os
            backup_filename = _os.path.basename(backup_file_path)
            logs.append(f"[RESTORE] Using manifest-selected application backup: {backup_file_path}")
        else:
            find_cmd = f"ls -1t {ofsaa_dir}/OFSAA_BKP_{backup_tag}_*.tar.gz 2>/dev/null | head -1"
            find_result = await self.ssh_service.execute_command(host, username, password, find_cmd)
            backup_filename = (find_result.get("stdout") or "").strip()
            if backup_filename:
                import os as _os
                backup_filename = _os.path.basename(backup_filename)
                backup_file_path = f"{ofsaa_dir}/{backup_filename}"
                logs.append(f"[RESTORE] Found tagged backup: {backup_filename}")
            else:
                legacy_cmd = f"test -f {ofsaa_dir}/OFSAA_BKP.tar.gz && echo 'EXISTS' || echo 'MISSING'"
                legacy_result = await self.ssh_service.execute_command(host, username, password, legacy_cmd)
                if "EXISTS" in (legacy_result.get("stdout") or ""):
                    backup_filename = "OFSAA_BKP.tar.gz"
                    backup_file_path = f"{ofsaa_dir}/{backup_filename}"
                    logs.append(f"[RESTORE] Using legacy backup: {backup_filename}")
                else:
                    logs.append(f"[RESTORE] ERROR: No backup found (pattern: OFSAA_BKP_{backup_tag}_*.tar.gz or OFSAA_BKP.tar.gz)")
                    return {"success": False, "logs": logs, "error": "Application backup file not found"}

        # Step 1: Remove existing OFSAA directory as oracle (mandatory per guide)
        logs.append("[RESTORE] Step 1: Removing existing OFSAA directory as oracle...")
        # Kill any processes holding files open under the OFSAA dir before removing.
        # Use only fuser -km here: lsof +D can take many minutes on large directory
        # trees and is not worth the wait — fuser is fast and sufficient.
        fuser_cmd = f"fuser -km {ofsaa_dir}/OFSAA 2>/dev/null || true"
        await self.ssh_service.execute_command(host, username, password, fuser_cmd, timeout=120)
        rm_inner = f"rm -rf {ofsaa_dir}/OFSAA"
        if username == "oracle":
            rm_cmd = rm_inner
        else:
            rm_cmd = (
                "if command -v sudo >/dev/null 2>&1; then "
                f"sudo -u oracle bash -c {shell_escape(rm_inner)}; "
                "else "
                f"su - oracle -c {shell_escape(rm_inner)}; "
                "fi"
            )
        rm_result = await self.ssh_service.execute_command(host, username, password, rm_cmd, timeout=600)
        if not rm_result.get("success"):
            # Last resort: remove with root and ignore sub-errors
            logs.append(f"[RESTORE] WARNING: rm as oracle failed, retrying as root: {rm_result.get('stderr', '')}")
            rm_root_result = await self.ssh_service.execute_command(host, username, password, f"rm -rf {ofsaa_dir}/OFSAA 2>&1 || true", timeout=600)
            if rm_root_result.get("success") or not rm_root_result.get("stderr", "").strip():
                logs.append("[RESTORE] Existing OFSAA directory removed (via root fallback)")
            else:
                logs.append(f"[RESTORE] ERROR: Failed to remove OFSAA directory: {rm_root_result.get('stderr', '')}")
                return {"success": False, "logs": logs, "error": "Failed to remove OFSAA directory"}
        else:
            logs.append("[RESTORE] Existing OFSAA directory removed")

        # Step 2: Extract backup as oracle user
        logs.append("[RESTORE] Step 2: Restoring application from backup as oracle...")
        tar_inner = f"cd {ofsaa_dir} && tar -xvf {shell_escape(backup_file_path)}"
        if username == "oracle":
            tar_cmd = tar_inner
        else:
            tar_cmd = (
                "if command -v sudo >/dev/null 2>&1; then "
                f"sudo -u oracle bash -c {shell_escape(tar_inner)}; "
                "else "
                f"su - oracle -c {shell_escape(tar_inner)}; "
                "fi"
            )
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
        db_oracle_sid: str = "OFSAADB",
        schema_config_schema_name: Optional[str] = None,
        schema_atomic_schema_name: Optional[str] = None,
        db_ssh_host: Optional[str] = None,
        db_ssh_username: Optional[str] = None,
        db_ssh_password: Optional[str] = None,
        backup_tag: str = "BD",
        schemas: Optional[list[str]] = None,
        dump_prefix: Optional[str] = None,
        metadata_path: Optional[str] = None,
        on_log: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> dict:
        """Run DB schema restore using Data Pump (impdp) + metadata replay."""
        resolved_schemas = list(schemas or [])
        if not resolved_schemas:
            if schema_atomic_schema_name:
                resolved_schemas.append(schema_atomic_schema_name)
            else:
                resolved_schemas.append("OFSATOMIC")
            if schema_config_schema_name:
                resolved_schemas.append(schema_config_schema_name)
            else:
                resolved_schemas.append("OFSCONFIG")
        schemas_str = ",".join(resolved_schemas)

        # Resolve DB host SSH credentials
        target_host = db_ssh_host or host
        target_user = db_ssh_username or username
        target_pass = db_ssh_password or password

        return await self.restore.run_restore(
            db_ssh_host=target_host,
            db_ssh_username=target_user,
            db_ssh_password=target_pass,
            db_sys_password=db_sys_password,
            pdb_name=db_jdbc_service,
            schemas=schemas_str,
            oracle_sid=db_oracle_sid,
            backup_tag=backup_tag,
            dump_prefix=dump_prefix,
            metadata_path=metadata_path,
            on_log=on_log,
        )

    async def full_restore_from_manifest(
        self,
        host: str,
        username: str,
        password: str,
        *,
        manifest: dict,
        db_sys_password: str,
        db_oracle_sid: str = "OFSAADB",
        db_ssh_host: Optional[str] = None,
        db_ssh_username: Optional[str] = None,
        db_ssh_password: Optional[str] = None,
        ofsaa_dir: str = "/u01",
    ) -> dict:
        logs = [f"[RESTORE] ===== FULL RESTORE FROM MANIFEST ({manifest.get('tag', 'UNKNOWN')}) ====="]
        failed_steps = []

        kill_result = await self.kill_java_processes(host, username, password)
        logs.extend(kill_result.get("logs", []))
        if not kill_result.get("success"):
            failed_steps.append("Kill Java processes")

        app_backup_path = manifest.get("app_backup", {}).get("path")
        db_service = manifest.get("db_service")
        dump_prefix = manifest.get("db_backup", {}).get("dump_prefix")
        metadata_path = manifest.get("db_backup", {}).get("metadata_path")
        manifest_schemas = manifest.get("schemas", [])
        backup_tag = manifest.get("tag", "BD")

        logs.append("[RESTORE] --- Step 1: Restoring application backup from manifest ---")
        app_result = await self.restore_application(
            host,
            username,
            password,
            ofsaa_dir=ofsaa_dir,
            backup_tag=backup_tag,
            backup_path=app_backup_path,
        )
        logs.extend(app_result.get("logs", []))
        if not app_result.get("success"):
            failed_steps.append("Restore application")

        logs.append("[RESTORE] --- Step 2: Restoring DB schemas from manifest ---")
        db_result = await self.restore_db_schemas(
            host,
            username,
            password,
            db_sys_password=db_sys_password,
            db_jdbc_service=db_service,
            db_oracle_sid=db_oracle_sid,
            db_ssh_host=db_ssh_host,
            db_ssh_username=db_ssh_username,
            db_ssh_password=db_ssh_password,
            backup_tag=backup_tag,
            schemas=manifest_schemas,
            dump_prefix=dump_prefix,
            metadata_path=metadata_path,
        )
        logs.extend(db_result.get("logs", []))
        if not db_result.get("success"):
            failed_steps.append("Restore DB schemas")

        if failed_steps:
            logs.append(f"[RESTORE] PARTIAL RESTORE - Failed steps: {', '.join(failed_steps)}")
            return {"success": False, "logs": logs, "failed_steps": failed_steps, "restored_tag": backup_tag}

        logs.append(f"[RESTORE] ===== FULL RESTORE FROM MANIFEST COMPLETED ({backup_tag}) =====")
        return {"success": True, "logs": logs, "failed_steps": [], "restored_tag": backup_tag}

    async def verify_cleanup_after_osc_failure(
        self,
        app_host: str,
        app_username: str,
        app_password: str,
        *,
        db_sys_password: Optional[str] = None,
        db_jdbc_host: Optional[str] = None,
        db_jdbc_port: int = 1521,
        db_jdbc_service: Optional[str] = None,
        schema_config_schema_name: Optional[str] = None,
        schema_atomic_schema_name: Optional[str] = None,
        db_ssh_host: Optional[str] = None,
        db_ssh_username: Optional[str] = None,
        db_ssh_password: Optional[str] = None,
    ) -> dict:
        logs = ["[RECOVERY] Verifying cleanup after osc.sh failure..."]
        failures: list[str] = []

        dir_check = await self.ssh_service.execute_command(
            app_host,
            app_username,
            app_password,
            "test -d /u01/OFSAA && echo EXISTS || echo MISSING",
        )
        if "EXISTS" in (dir_check.get("stdout") or ""):
            failures.append("/u01/OFSAA still exists")

        if db_sys_password and db_jdbc_service:
            check_host = db_ssh_host or app_host
            check_user = db_ssh_username or app_username
            check_pass = db_ssh_password or app_password
            jdbc_host = db_jdbc_host or check_host
            users = [schema for schema in [schema_atomic_schema_name, schema_config_schema_name] if schema]
            if users:
                conn = f"sys/{db_sys_password}@{jdbc_host}:{db_jdbc_port}/{db_jdbc_service} as sysdba"
                user_list = " UNION ALL ".join(f"SELECT '{user}' AS expected_user FROM dual" for user in users)
                sql = (
                    "SET HEADING OFF FEEDBACK OFF PAGESIZE 0\n"
                    f"WITH expected AS ({user_list}) "
                    "SELECT expected_user FROM expected WHERE EXISTS (SELECT 1 FROM dba_users WHERE username = expected_user);\n"
                    "EXIT;"
                )
                cmd = f"sqlplus -s {shell_escape(conn)} <<'EOSQL'\n{sql}\nEOSQL"
                sql_result = await self.ssh_service.execute_command(check_host, check_user, check_pass, cmd, timeout=300)
                remaining_users = [line.strip() for line in (sql_result.get("stdout") or "").splitlines() if line.strip()]
                if remaining_users:
                    failures.append(f"Schemas still exist: {', '.join(remaining_users)}")

        if failures:
            logs.append(f"[RECOVERY] Cleanup verification failed: {'; '.join(failures)}")
            return {"success": False, "logs": logs, "failures": failures}

        logs.append("[RECOVERY] Cleanup verification succeeded")
        return {"success": True, "logs": logs, "failures": []}

    async def _remove_ofsaa_directory(
        self,
        host: str,
        username: str,
        password: str,
        ofsaa_dir: str = "/u01",
    ) -> dict:
        """Remove the OFSAA directory during BD osc.sh failure cleanup."""
        logs = []

        # Check if OFSAA directory exists
        check_cmd = f"test -d {ofsaa_dir}/OFSAA && echo 'EXISTS' || echo 'MISSING'"
        check_result = await self.ssh_service.execute_command(host, username, password, check_cmd)
        stdout = (check_result.get("stdout") or "").strip()

        if "MISSING" in stdout:
            logs.append(f"[RECOVERY] {ofsaa_dir}/OFSAA directory does not exist, skipping removal")
            return {"success": True, "logs": logs}

        # Remove OFSAA directory as oracle user
        rm_inner = f"rm -rf {ofsaa_dir}/OFSAA"
        if username == "oracle":
            rm_cmd = rm_inner
        else:
            rm_cmd = (
                "if command -v sudo >/dev/null 2>&1; then "
                f"sudo -u oracle bash -c {shell_escape(rm_inner)}; "
                "else "
                f"su - oracle -c {shell_escape(rm_inner)}; "
                "fi"
            )
        logs.append(f"[RECOVERY] Removing {ofsaa_dir}/OFSAA as oracle user...")
        rm_result = await self.ssh_service.execute_command(host, username, password, rm_cmd, timeout=600)

        if not rm_result.get("success"):
            stderr = rm_result.get("stderr", "")
            logs.append(f"[RECOVERY] ERROR: Failed to remove OFSAA directory: {stderr}")
            return {"success": False, "logs": logs}

        # Verify removal
        verify_result = await self.ssh_service.execute_command(host, username, password, check_cmd)
        if "MISSING" in (verify_result.get("stdout") or ""):
            logs.append(f"[RECOVERY] {ofsaa_dir}/OFSAA directory removed successfully")
            return {"success": True, "logs": logs}
        else:
            logs.append(f"[RECOVERY] WARNING: {ofsaa_dir}/OFSAA may still exist after removal attempt")
            return {"success": False, "logs": logs}

    async def kill_java_processes(self, host: str, username: str, password: str) -> dict:
        """Kill ALL Java processes on the server unconditionally."""
        logs = []
        import asyncio

        logs.append("[RECOVERY] Killing ALL Java processes on the server...")

        # Force kill all Java processes (any user) - no checks, just kill
        kill_cmd = "pkill -9 -f java; killall -9 java 2>/dev/null; true"
        await self.ssh_service.execute_command(host, username, password, kill_cmd)
        await asyncio.sleep(2)

        # Second round to catch stragglers
        await self.ssh_service.execute_command(host, username, password, kill_cmd)

        logs.append("[RECOVERY] All Java processes killed")
        return {"success": True, "logs": logs}

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
        schema_config_schema_name: Optional[str] = None,
        schema_atomic_schema_name: Optional[str] = None,
    ) -> dict:
        """Drop all OFSAA users and tablespaces from Oracle database.

        Connects via: sqlplus "sys/<db_sys_password>@<host>:<port>/<service> as sysdba"
        Then runs DROP USER ... CASCADE and DROP TABLESPACE ... for all OFSAA objects.
        
        Args:
            schema_config_schema_name: CONFIG schema name (e.g., "OFSCONFIG") from UI
            schema_atomic_schema_name: ATOMIC schema name (e.g., "OFSATOMIC") from UI
        """
        logs = []

        # Validate required DB credentials
        if not db_sys_password or not db_jdbc_service:
            logs.append("[RECOVERY] ERROR: db_sys_password and db_jdbc_service are required for schema drop")
            logs.append("[RECOVERY] Please provide these values in the UI form")
            return {"success": False, "logs": logs}

        jdbc_host = db_jdbc_host or host
        conn_display = f"sys/******@{jdbc_host}:{db_jdbc_port}/{db_jdbc_service}"
        logs.append(f"[RECOVERY] Connecting to sqlplus: {conn_display} as sysdba")

        # Build the sqlplus connection command
        # Format: sqlplus "sys/Welcome#123@192.168.0.165:1521/FLEXPDB1 as sysdba"
        sqlplus_login = f"sys/{db_sys_password}@{jdbc_host}:{db_jdbc_port}/{db_jdbc_service} as sysdba"

        # Users to drop - derive from UI schema names, with defaults as fallback
        users = []
        if schema_atomic_schema_name:
            users.append(schema_atomic_schema_name)
        else:
            users.append("OFSATOMIC")  # default fallback
        
        if schema_config_schema_name:
            users.append(schema_config_schema_name)
        else:
            users.append("OFSCONFIG")  # default fallback

        # Tablespaces to drop
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

        # Build SQL statements
        sql_lines = []
        for user in users:
            sql_lines.append(f"drop user {user} CASCADE;")
        for tbsp in tablespaces:
            sql_lines.append(f"DROP TABLESPACE {tbsp} INCLUDING CONTENTS AND DATAFILES CASCADE CONSTRAINTS;")
        sql_lines.append("EXIT;")

        # Use heredoc to avoid shell special character issues with password
        # This runs: sqlplus "sys/pass@host:port/service as sysdba" <<'EOF'
        # drop user OFSATOMIC CASCADE;
        # ...
        # EOF
        sql_body = "\n".join(sql_lines)
        cmd = f"sqlplus {shell_escape(sqlplus_login)} <<'EOSQL'\n{sql_body}\nEOSQL"

        logs.append("[RECOVERY] Dropping OFSAA users and tablespaces...")
        logs.append(f"[RECOVERY] Users to drop: {', '.join(users)}")
        logs.append(f"[RECOVERY] Tablespaces to drop: {len(tablespaces)} tablespaces")

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
