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
        db_ssh_host: Optional[str] = None,
        db_ssh_username: Optional[str] = None,
        db_ssh_password: Optional[str] = None,
    ) -> dict:
        """Execute full cleanup after OSC.SH failure: kill Java, drop schema, clear cache."""
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
            )
        else:
            drop_result = await self._drop_database_schema(
                app_host, app_username, app_password,
                db_sys_password=db_sys_password,
                db_jdbc_host=db_jdbc_host,
                db_jdbc_port=db_jdbc_port,
                db_jdbc_service=db_jdbc_service,
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
            # Convert Windows line endings (CRLF) to Unix (LF) to avoid ^M issues
            dos2unix_cmd = (
                f"sed -i 's/\\r$//' {backup_dir}/backup_ofs_schemas.sh {backup_dir}/restore_ofs_schemas.sh"
            )
            await self.ssh_service.execute_command(host, username, password, dos2unix_cmd)
            logs.append("[BACKUP] Scripts converted to Unix line endings")
            # Ensure scripts are executable
            chmod_cmd = f"chmod +x {backup_dir}/backup_ofs_schemas.sh {backup_dir}/restore_ofs_schemas.sh"
            await self.ssh_service.execute_command(host, username, password, chmod_cmd)
            logs.append("[BACKUP] Scripts set to executable")
            # Try to update the local git working copy to the latest remote
            try:
                # Use reset --hard to handle diverging branches
                git_pull_cmd = f"cd {repo_dir} && git fetch origin && git reset --hard origin/main"
                git_result = await self.ssh_service.execute_command(host, username, password, git_pull_cmd)
                git_stdout = (git_result.get("stdout") or "").strip()
                if git_stdout:
                    logs.append(f"[BACKUP] Git reset output: {git_stdout}")
                else:
                    logs.append("[BACKUP] Git reset completed (no output)")
            except Exception:
                logs.append("[BACKUP] WARNING: Git reset failed or not configured on repo host")
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
        logs = [f"[BACKUP] Starting application backup (tag={backup_tag})..."]

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
        db_ssh_host: Optional[str] = None,
        db_ssh_username: Optional[str] = None,
        db_ssh_password: Optional[str] = None,
    ) -> dict:
        """Run DB schema backup: backup_ofs_schemas.sh system <DB_PASS> <SERVICE>"""
        logs = ["[BACKUP] Starting DB schema backup..."]
        repo_dir = Config.REPO_DIR
        backup_dir = f"{repo_dir}/backup_Restore"

        # Ensure scripts exist on the application/repo host first
        scripts_result = await self.ensure_backup_restore_scripts(host, username, password)
        logs.extend(scripts_result.get("logs", []))
        if not scripts_result.get("success"):
            return {"success": False, "logs": logs, "error": "Backup scripts not available on repo host"}

        # Patch the backup script in the git repo with the provided SYS password and service
        try:
            # Read original script
            read_repo_cmd = f"cat {backup_dir}/backup_ofs_schemas.sh"
            read_repo_result = await self.ssh_service.execute_command(host, username, password, read_repo_cmd)
            orig_script = read_repo_result.get("stdout") or ""

            # Check if exports are already present to avoid duplicates
            if "export DB_USER=" not in orig_script or "export DB_PASS=" not in orig_script:
                # Prepend exports matching the expected names in backup_ofs_schemas.sh
                # Script expects: export DB_USER=system, export DB_PASS=, export SERVICE=
                patched_script = (
                    f"export DB_USER=system\n"
                    + f"export DB_PASS={db_sys_password}\n"
                    + f"export SERVICE={db_jdbc_service}\n"
                    + orig_script
                )
                
                # Write patched script back into the git repo (overwrite)
                write_repo_cmd = f"cat > {backup_dir}/backup_ofs_schemas.sh <<'EOFSCRIPT'\n{patched_script}\nEOFSCRIPT"
                await self.ssh_service.execute_command(host, username, password, write_repo_cmd)
                await self.ssh_service.execute_command(host, username, password, f"chmod +x {backup_dir}/backup_ofs_schemas.sh")
                logs.append("[BACKUP] Patched backup_ofs_schemas.sh in git repo with provided DB values (password masked)")
            else:
                # Update existing exports in place
                updated_script = orig_script
                updated_script = updated_script.replace("export DB_PASS=\n", f"export DB_PASS={db_sys_password}\n")
                updated_script = updated_script.replace("export DB_PASS=\r\n", f"export DB_PASS={db_sys_password}\n")
                updated_script = updated_script.replace("export SERVICE=\n", f"export SERVICE={db_jdbc_service}\n")
                updated_script = updated_script.replace("export SERVICE=\r\n", f"export SERVICE={db_jdbc_service}\n")
                
                # Handle existing values
                import re
                updated_script = re.sub(r'export DB_PASS=.*', f'export DB_PASS={db_sys_password}', updated_script)
                updated_script = re.sub(r'export SERVICE=.*', f'export SERVICE={db_jdbc_service}', updated_script)
                
                write_repo_cmd = f"cat > {backup_dir}/backup_ofs_schemas.sh <<'EOFSCRIPT'\n{updated_script}\nEOFSCRIPT"
                await self.ssh_service.execute_command(host, username, password, write_repo_cmd)
                await self.ssh_service.execute_command(host, username, password, f"chmod +x {backup_dir}/backup_ofs_schemas.sh")
                logs.append("[BACKUP] Updated existing exports in backup_ofs_schemas.sh (password masked)")
            # Commit and push the updated script into Git so the repo reflects the change
            try:
                git_username = Config.GIT_USERNAME
                git_password = Config.GIT_PASSWORD
                git_url = Config.REPO_URL
                
                # Build authenticated git URL if credentials are available
                if git_username and git_password and git_url:
                    # Extract base URL and add credentials
                    if "://" in git_url:
                        protocol, rest = git_url.split("://", 1)
                        # Properly escape special characters in password
                        escaped_password = git_password.replace('@', '%40').replace(':', '%3A')
                        auth_url = f"{protocol}://{git_username}:{escaped_password}@{rest}"
                    else:
                        auth_url = git_url
                    
                    git_commit_cmds = (
                        f"cd {repo_dir} && "
                        f"git add {backup_dir}/backup_ofs_schemas.sh && "
                        f"git commit -m 'Update backup_ofs_schemas.sh with DB export values for automated backup' || true && "
                        f"git remote set-url origin '{auth_url}' && "
                        f"git push origin main || true"
                    )
                else:
                    # Fallback without credentials
                    git_commit_cmds = (
                        f"cd {repo_dir} && git add {backup_dir}/backup_ofs_schemas.sh && "
                        f"git commit -m 'Update backup_ofs_schemas.sh with DB export values for automated backup' || true && "
                        f"git push || true"
                    )
                
                git_push_result = await self.ssh_service.execute_command(host, username, password, git_commit_cmds, timeout=120)
                git_out = (git_push_result.get("stdout") or "").strip()
                git_err = (git_push_result.get("stderr") or "").strip()
                if git_out:
                    logs.append(f"[BACKUP] Git push output: {git_out}")
                if git_err and "fatal: could not read Username" not in git_err:
                    logs.append(f"[BACKUP] Git push stderr: {git_err}")
            except Exception as e:
                logs.append(f"[BACKUP] WARNING: Failed to commit/push patched script to Git: {e}")
        except Exception as exc:  # pragma: no cover - defensive
            logs.append(f"[BACKUP] WARNING: Failed to patch script in repo: {exc}")

        # Determine where to execute the backup: prefer explicit db_ssh_host, otherwise use host (app host)
        target_ssh_host = db_ssh_host or host
        target_ssh_username = db_ssh_username or username
        target_ssh_password = db_ssh_password or password

        # Always execute the backup on the target DB host via SSH (repo-local execution removed)
        target_ssh_host = db_ssh_host or host
        target_ssh_username = db_ssh_username or username
        target_ssh_password = db_ssh_password or password

        logs.append(f"[BACKUP] Preparing to run backup on DB host {target_ssh_host}")

        # Read script content from repo host
        cat_cmd = f"cat {backup_dir}/backup_ofs_schemas.sh"
        read_result = await self.ssh_service.execute_command(host, username, password, cat_cmd)
        script_content = read_result.get("stdout") or ""
        if not script_content:
            logs.append("[BACKUP] ERROR: Failed to read backup script from repo host")
            return {"success": False, "logs": logs, "error": "Failed to read backup script from repo host"}

        # Write script to /u01/backup on DB host with proper line endings
        remote_dir = "/u01/backup"
        mkdir_cmd = f"mkdir -p {remote_dir} && chmod 700 {remote_dir}"
        await self.ssh_service.execute_command(target_ssh_host, target_ssh_username, target_ssh_password, mkdir_cmd)
        
        # Ensure script has proper Unix line endings and fix any shell option issues
        clean_script = script_content.replace('\r\n', '\n').replace('\r', '\n')
        # Fix potential pipefail issues by ensuring proper shell options
        if 'set -euo pipefail' in clean_script:
            clean_script = clean_script.replace('set -euo pipefail', 'set -eo pipefail')
        
        write_cmd = f"cat > {remote_dir}/backup_ofs_schemas.sh <<'EOFSCRIPT'\n{clean_script}\nEOFSCRIPT"
        await self.ssh_service.execute_command(target_ssh_host, target_ssh_username, target_ssh_password, write_cmd)
        await self.ssh_service.execute_command(target_ssh_host, target_ssh_username, target_ssh_password, f"chmod +x {remote_dir}/backup_ofs_schemas.sh")

        # Execute the script on DB host with proper environment variable handling
        # Create a wrapper script that explicitly sets and exports the variables
        wrapper_script = f"""#!/bin/bash
set -e
echo "Setting environment variables for backup..."
export DB_USER="system"
export DB_PASS="{db_sys_password}"
export SERVICE="{db_jdbc_service}"
export ORACLE_SID="{db_jdbc_service}"
echo "DB_USER=$DB_USER"
echo "SERVICE=$SERVICE"
echo "ORACLE_SID=$ORACLE_SID"
echo "DB_PASS is set: $([ -n "$DB_PASS" ] && echo "yes" || echo "no")"
cd {remote_dir}
echo "Executing backup script..."
# Set Oracle environment for local connections
export ORACLE_HOME=/u01/app/oracle/product/19.0.0/dbhome_1
export PATH=$ORACLE_HOME/bin:$PATH
echo "Oracle environment set: ORACLE_HOME=$ORACLE_HOME"
bash ./backup_ofs_schemas.sh
"""
        
        # Write wrapper script to DB host
        wrapper_cmd = f"cat > {remote_dir}/run_backup.sh <<'EOFWRAPPER'\n{wrapper_script}\nEOFWRAPPER"
        await self.ssh_service.execute_command(target_ssh_host, target_ssh_username, target_ssh_password, wrapper_cmd)
        await self.ssh_service.execute_command(target_ssh_host, target_ssh_username, target_ssh_password, f"chmod +x {remote_dir}/run_backup.sh")
        
        backup_cmd = f"cd {remote_dir} && bash ./run_backup.sh"
        logs.append(f"[BACKUP] Running on DB host: {backup_cmd} (with environment wrapper)")
        backup_result = await self.ssh_service.execute_command(
            target_ssh_host, target_ssh_username, target_ssh_password, backup_cmd, timeout=3600
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
    # Verify backup availability
    # ------------------------------------------------------------------
    async def verify_backups_exist(
        self,
        host: str,
        username: str,
        password: str,
        *,
        ofsaa_dir: str = "/u01",
        backup_tag: str = "BD",
        backup_dump_dir: str = "/u01/backup",
        db_ssh_host: Optional[str] = None,
        db_ssh_username: Optional[str] = None,
        db_ssh_password: Optional[str] = None,
    ) -> dict:
        """Check whether application tar and DB dump file exist on the target servers.

        Searches for the most recent OFSAA_BKP_<tag>_*.tar.gz file.
        Falls back to legacy OFSAA_BKP.tar.gz if no tagged backup found.

        Returns:
            {
                "app_backup_exists": bool,
                "db_backup_exists": bool,
                "both_exist": bool,
                "app_backup_path": str | None,
                "db_dump_path": str | None,
                "logs": list[str],
            }
        """
        logs: list[str] = []
        app_exists = False
        db_exists = False
        app_path: Optional[str] = None
        db_path: Optional[str] = None

        # Check application tar on app host — search for tagged backup, fallback to legacy
        find_app_cmd = (
            f"ls -1t {ofsaa_dir}/OFSAA_BKP_{backup_tag}_*.tar.gz 2>/dev/null | head -1"
        )
        app_result = await self.ssh_service.execute_command(host, username, password, find_app_cmd)
        found_path = (app_result.get("stdout") or "").strip()
        if not found_path:
            # Fallback: check legacy filename
            legacy_cmd = f"test -f {ofsaa_dir}/OFSAA_BKP.tar.gz && echo '{ofsaa_dir}/OFSAA_BKP.tar.gz' || echo ''"
            legacy_result = await self.ssh_service.execute_command(host, username, password, legacy_cmd)
            found_path = (legacy_result.get("stdout") or "").strip()
        if found_path:
            app_exists = True
            app_path = found_path
            logs.append(f"[VERIFY] Application backup found: {app_path}")
        else:
            logs.append(f"[VERIFY] Application backup NOT found (pattern: OFSAA_BKP_{backup_tag}_*.tar.gz)")

        # Check DB dump on DB host
        target_ssh_host = db_ssh_host or host
        target_ssh_username = db_ssh_username or username
        target_ssh_password = db_ssh_password or password

        find_dmp_cmd = f"ls -1t {backup_dump_dir}/*.dmp 2>/dev/null | head -1"
        dmp_result = await self.ssh_service.execute_command(
            target_ssh_host, target_ssh_username, target_ssh_password, find_dmp_cmd
        )
        dmp_path = (dmp_result.get("stdout") or "").strip()
        if dmp_path:
            db_exists = True
            db_path = dmp_path
            logs.append(f"[VERIFY] DB dump file found: {db_path}")
        else:
            logs.append(f"[VERIFY] DB dump file NOT found in {backup_dump_dir} on {target_ssh_host}")

        return {
            "app_backup_exists": app_exists,
            "db_backup_exists": db_exists,
            "both_exist": app_exists and db_exists,
            "app_backup_path": app_path,
            "db_dump_path": db_path,
            "logs": logs,
        }

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
    ) -> dict:
        """Restore application from the most recent OFSAA_BKP_<tag>_*.tar.gz backup.

        Falls back to legacy OFSAA_BKP.tar.gz if no tagged backup found.
        """
        logs = ["[RESTORE] Starting application restore..."]

        # Find the most recent tagged backup file
        find_cmd = f"ls -1t {ofsaa_dir}/OFSAA_BKP_{backup_tag}_*.tar.gz 2>/dev/null | head -1"
        find_result = await self.ssh_service.execute_command(host, username, password, find_cmd)
        backup_filename = (find_result.get("stdout") or "").strip()
        if backup_filename:
            # Extract just the filename from full path
            import os as _os
            backup_filename = _os.path.basename(backup_filename)
            logs.append(f"[RESTORE] Found tagged backup: {backup_filename}")
        else:
            # Fallback to legacy filename
            legacy_cmd = f"test -f {ofsaa_dir}/OFSAA_BKP.tar.gz && echo 'EXISTS' || echo 'MISSING'"
            legacy_result = await self.ssh_service.execute_command(host, username, password, legacy_cmd)
            if "EXISTS" in (legacy_result.get("stdout") or ""):
                backup_filename = "OFSAA_BKP.tar.gz"
                logs.append(f"[RESTORE] Using legacy backup: {backup_filename}")
            else:
                logs.append(f"[RESTORE] ERROR: No backup found (pattern: OFSAA_BKP_{backup_tag}_*.tar.gz or OFSAA_BKP.tar.gz)")
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
        db_ssh_host: Optional[str] = None,
        db_ssh_username: Optional[str] = None,
        db_ssh_password: Optional[str] = None,
        backup_dump_dir: str = "/u01/backup",
    ) -> dict:
        """Run DB schema restore using restore_ofs_schemas.sh from Git.

        Follows the same flow as backup_db_schemas:
        1. Read restore script from git repo
        2. Patch env vars (DB_USER, DB_PASS, SERVICE, DUMPFILE) into the script
        3. Commit/push patched script to git
        4. Discover .dmp file on DB host from backup_dump_dir
        5. Copy patched script to DB host
        6. Run via wrapper script with all env vars
        """
        import re as _re
        import os as _os

        logs = ["[RESTORE] Starting DB schema restore..."]
        repo_dir = Config.REPO_DIR
        backup_dir = f"{repo_dir}/backup_Restore"

        # Ensure scripts exist on the repo/app host first
        scripts_result = await self.ensure_backup_restore_scripts(host, username, password)
        logs.extend(scripts_result.get("logs", []))
        if not scripts_result.get("success"):
            return {"success": False, "logs": logs, "error": "Restore scripts not available on repo host"}

        # Determine where to execute the restore: prefer explicit db_ssh_host
        target_ssh_host = db_ssh_host or host
        target_ssh_username = db_ssh_username or username
        target_ssh_password = db_ssh_password or password

        # ------------------------------------------------------------------
        # Step 1: Discover the .dmp file on the DB server
        # ------------------------------------------------------------------
        logs.append(f"[RESTORE] Looking for .dmp dump file in {backup_dump_dir} on DB host {target_ssh_host} ...")
        find_dmp_cmd = f"ls -1t {backup_dump_dir}/*.dmp 2>/dev/null | head -1"
        find_result = await self.ssh_service.execute_command(
            target_ssh_host, target_ssh_username, target_ssh_password, find_dmp_cmd
        )
        dmp_path = (find_result.get("stdout") or "").strip()

        if not dmp_path:
            logs.append(f"[RESTORE] ERROR: No .dmp file found in {backup_dump_dir} on DB host {target_ssh_host}")
            return {"success": False, "logs": logs, "error": f"No .dmp dump file found in {backup_dump_dir}"}

        dmp_filename = _os.path.basename(dmp_path)
        logs.append(f"[RESTORE] Found dump file: {dmp_filename} (full path: {dmp_path})")

        # ------------------------------------------------------------------
        # Step 2: Patch restore script in git repo (same as backup flow)
        # ------------------------------------------------------------------
        try:
            read_repo_cmd = f"cat {backup_dir}/restore_ofs_schemas.sh"
            read_repo_result = await self.ssh_service.execute_command(host, username, password, read_repo_cmd)
            orig_script = read_repo_result.get("stdout") or ""
            if not orig_script:
                logs.append("[RESTORE] ERROR: Failed to read restore script from repo host")
                return {"success": False, "logs": logs, "error": "Failed to read restore script from repo host"}

            if "export DB_USER=" not in orig_script or "export DB_PASS=" not in orig_script:
                # Exports not present yet — prepend them
                patched_script = (
                    f"export DB_USER=system\n"
                    f"export DB_PASS={db_sys_password}\n"
                    f"export SERVICE={db_jdbc_service}\n"
                    f"export DUMPFILE={dmp_filename}\n"
                    + orig_script
                )
                write_repo_cmd = f"cat > {backup_dir}/restore_ofs_schemas.sh <<'EOFSCRIPT'\n{patched_script}\nEOFSCRIPT"
                await self.ssh_service.execute_command(host, username, password, write_repo_cmd)
                await self.ssh_service.execute_command(host, username, password, f"chmod +x {backup_dir}/restore_ofs_schemas.sh")
                logs.append("[RESTORE] Patched restore_ofs_schemas.sh in git repo with provided DB values (password masked)")
            else:
                # Update existing exports in place
                updated_script = orig_script
                updated_script = _re.sub(r'export DB_PASS=.*', f'export DB_PASS={db_sys_password}', updated_script)
                updated_script = _re.sub(r'export SERVICE=.*', f'export SERVICE={db_jdbc_service}', updated_script)
                updated_script = _re.sub(r'export DUMPFILE=.*', f'export DUMPFILE={dmp_filename}', updated_script)

                write_repo_cmd = f"cat > {backup_dir}/restore_ofs_schemas.sh <<'EOFSCRIPT'\n{updated_script}\nEOFSCRIPT"
                await self.ssh_service.execute_command(host, username, password, write_repo_cmd)
                await self.ssh_service.execute_command(host, username, password, f"chmod +x {backup_dir}/restore_ofs_schemas.sh")
                logs.append("[RESTORE] Updated existing exports in restore_ofs_schemas.sh (password masked)")

            # Commit and push the updated script into Git
            try:
                git_username = Config.GIT_USERNAME
                git_password = Config.GIT_PASSWORD
                git_url = Config.REPO_URL

                if git_username and git_password and git_url:
                    if "://" in git_url:
                        protocol, rest = git_url.split("://", 1)
                        escaped_password = git_password.replace('@', '%40').replace(':', '%3A')
                        auth_url = f"{protocol}://{git_username}:{escaped_password}@{rest}"
                    else:
                        auth_url = git_url

                    git_commit_cmds = (
                        f"cd {repo_dir} && "
                        f"git add {backup_dir}/restore_ofs_schemas.sh && "
                        f"git commit -m 'Update restore_ofs_schemas.sh with DB export values for automated restore' || true && "
                        f"git remote set-url origin '{auth_url}' && "
                        f"git push origin main || true"
                    )
                else:
                    git_commit_cmds = (
                        f"cd {repo_dir} && git add {backup_dir}/restore_ofs_schemas.sh && "
                        f"git commit -m 'Update restore_ofs_schemas.sh with DB export values for automated restore' || true && "
                        f"git push || true"
                    )

                git_push_result = await self.ssh_service.execute_command(host, username, password, git_commit_cmds, timeout=120)
                git_out = (git_push_result.get("stdout") or "").strip()
                git_err = (git_push_result.get("stderr") or "").strip()
                if git_out:
                    logs.append(f"[RESTORE] Git push output: {git_out}")
                if git_err and "fatal: could not read Username" not in git_err:
                    logs.append(f"[RESTORE] Git push stderr: {git_err}")
            except Exception as e:
                logs.append(f"[RESTORE] WARNING: Failed to commit/push patched script to Git: {e}")
        except Exception as exc:
            logs.append(f"[RESTORE] WARNING: Failed to patch script in repo: {exc}")

        # ------------------------------------------------------------------
        # Step 3: Copy patched script to DB host
        # ------------------------------------------------------------------
        logs.append(f"[RESTORE] Preparing to run restore on DB host {target_ssh_host}")

        # Re-read the (now patched) script from repo host
        cat_cmd = f"cat {backup_dir}/restore_ofs_schemas.sh"
        read_result = await self.ssh_service.execute_command(host, username, password, cat_cmd)
        script_content = read_result.get("stdout") or ""
        if not script_content:
            logs.append("[RESTORE] ERROR: Failed to read patched restore script from repo host")
            return {"success": False, "logs": logs, "error": "Failed to read patched restore script from repo host"}

        remote_dir = "/u01/backup"
        mkdir_cmd = f"mkdir -p {remote_dir} && chmod 700 {remote_dir}"
        await self.ssh_service.execute_command(target_ssh_host, target_ssh_username, target_ssh_password, mkdir_cmd)

        # Clean line endings
        clean_script = script_content.replace('\r\n', '\n').replace('\r', '\n')
        if 'set -euo pipefail' in clean_script:
            clean_script = clean_script.replace('set -euo pipefail', 'set -eo pipefail')

        write_cmd = f"cat > {remote_dir}/restore_ofs_schemas.sh <<'EOFSCRIPT'\n{clean_script}\nEOFSCRIPT"
        await self.ssh_service.execute_command(target_ssh_host, target_ssh_username, target_ssh_password, write_cmd)
        await self.ssh_service.execute_command(
            target_ssh_host, target_ssh_username, target_ssh_password,
            f"chmod +x {remote_dir}/restore_ofs_schemas.sh",
        )

        # ------------------------------------------------------------------
        # Step 4: Create wrapper script (same pattern as backup)
        # ------------------------------------------------------------------
        wrapper_script = f"""#!/bin/bash
set -e
echo "=== DB Schema Restore ==="
echo "Setting environment variables for restore..."
export DB_USER="system"
export DB_PASS="{db_sys_password}"
export SERVICE="{db_jdbc_service}"
export DUMPFILE="{dmp_filename}"
export ORACLE_SID="{db_jdbc_service}"
echo "DB_USER=$DB_USER"
echo "SERVICE=$SERVICE"
echo "DUMPFILE=$DUMPFILE"
echo "ORACLE_SID=$ORACLE_SID"
echo "DB_PASS is set: $([ -n \"$DB_PASS\" ] && echo \"yes\" || echo \"no\")"
cd {remote_dir}
echo "Executing restore script..."
# Set Oracle environment for local connections
export ORACLE_HOME=/u01/app/oracle/product/19.0.0/dbhome_1
export PATH=$ORACLE_HOME/bin:$PATH
echo "Oracle environment set: ORACLE_HOME=$ORACLE_HOME"
bash ./restore_ofs_schemas.sh
"""

        wrapper_cmd = f"cat > {remote_dir}/run_restore.sh <<'EOFWRAPPER'\n{wrapper_script}\nEOFWRAPPER"
        await self.ssh_service.execute_command(target_ssh_host, target_ssh_username, target_ssh_password, wrapper_cmd)
        await self.ssh_service.execute_command(
            target_ssh_host, target_ssh_username, target_ssh_password,
            f"chmod +x {remote_dir}/run_restore.sh",
        )

        # ------------------------------------------------------------------
        # Step 5: Execute via wrapper
        # ------------------------------------------------------------------
        restore_cmd = f"cd {remote_dir} && bash ./run_restore.sh"
        logs.append(
            f"[RESTORE] Running on DB host {target_ssh_host}: {restore_cmd} "
            f"(DB_USER=system, SERVICE={db_jdbc_service}, DUMPFILE={dmp_filename})"
        )
        restore_result = await self.ssh_service.execute_command(
            target_ssh_host, target_ssh_username, target_ssh_password,
            restore_cmd, timeout=3600,
        )

        stdout = (restore_result.get("stdout") or "").strip()
        stderr = (restore_result.get("stderr") or "").strip()

        if stdout:
            for line in stdout.splitlines():
                logs.append(f"[RESTORE] {line}")

        if not restore_result.get("success"):
            if stderr:
                logs.append(f"[RESTORE] STDERR: {stderr}")
            logs.append("[RESTORE] ERROR: DB schema restore failed")
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
        db_ssh_host: Optional[str] = None,
        db_ssh_username: Optional[str] = None,
        db_ssh_password: Optional[str] = None,
        ofsaa_dir: str = "/u01",
    ) -> dict:
        """Full restore to BD state: kill Java -> rm OFSAA -> restore app tar -> restore DB schemas."""
        logs = ["[RESTORE] ===== FULL RESTORE TO BD STATE ====="]
        failed_steps = []

        # Step 0: Kill all Java processes to release file locks and ports
        logs.append("[RESTORE] --- Step 0: Killing all Java processes ---")
        kill_result = await self.kill_java_processes(host, username, password)
        logs.extend(kill_result.get("logs", []))
        if not kill_result.get("success"):
            failed_steps.append("Kill Java processes")

        # Step 1: Restore application (rm -rf + tar extract from most recent BD backup)
        logs.append("[RESTORE] --- Step 1: Restoring application backup ---")
        app_result = await self.restore_application(
            host, username, password,
            ofsaa_dir=ofsaa_dir,
            backup_tag="BD",
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
            db_ssh_host=db_ssh_host,
            db_ssh_username=db_ssh_username,
            db_ssh_password=db_ssh_password,
        )
        logs.extend(db_result.get("logs", []))
        if not db_result.get("success"):
            failed_steps.append("Restore DB schemas")

        if failed_steps:
            logs.append(f"[RESTORE] PARTIAL RESTORE - Failed steps: {', '.join(failed_steps)}")
            return {"success": False, "logs": logs, "failed_steps": failed_steps}

        logs.append("[RESTORE] ===== FULL RESTORE TO BD STATE COMPLETED SUCCESSFULLY =====")
        return {"success": True, "logs": logs, "failed_steps": []}

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

        # Remove OFSAA directory
        rm_cmd = f"rm -rf {ofsaa_dir}/OFSAA"
        logs.append(f"[RECOVERY] Removing {ofsaa_dir}/OFSAA ...")
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
    ) -> dict:
        """Drop all OFSAA users and tablespaces from Oracle database.

        Connects via: sqlplus "sys/<db_sys_password>@<host>:<port>/<service> as sysdba"
        Then runs DROP USER ... CASCADE and DROP TABLESPACE ... for all OFSAA objects.
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

        # Users to drop
        users = ["OFSATOMIC", "OFSCONFIG"]

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
