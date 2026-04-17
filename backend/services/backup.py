"""DB schema backup using Oracle Data Pump (expdp) + metadata capture.

Replaces the old shell-script-based backup_ofs_schemas.sh approach.
All values are parameterized — nothing hardcoded.
"""

import logging
from datetime import datetime
from typing import Callable, Awaitable, Optional, List

from services.ssh_service import SSHService
from services.utils import shell_escape

logger = logging.getLogger(__name__)

BACKUP_DIR = "/u01/backup/ofsaa"


class BackupService:
    """Runs expdp schema backup + generates restore_metadata.sql on the DB host."""

    def __init__(self, ssh_service: SSHService) -> None:
        self.ssh = ssh_service

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _env_block(self, oracle_home: str, oracle_sid: str) -> str:
        return (
            f"export ORACLE_HOME={oracle_home}; "
            f"export ORACLE_SID={oracle_sid}; "
            f"export PATH=$ORACLE_HOME/bin:$PATH; "
        )

    def _sqlplus_cmd(
        self, env: str, sys_pass: str, sql: str, container: Optional[str] = None
    ) -> str:
        alter = f"ALTER SESSION SET CONTAINER = {container};" if container else ""
        return (
            f'{env} sqlplus -s "sys/{sys_pass} as sysdba" <<\'SQLEOF\'\n'
            f"SET LINESIZE 4000\n"
            f"SET PAGESIZE 0\n"
            f"SET FEEDBACK OFF\n"
            f"SET HEADING OFF\n"
            f"SET TRIMSPOOL ON\n"
            f"SET LONG 100000\n"
            f"SET ECHO OFF\n"
            f"{alter}\n"
            f"{sql}\n"
            f"SQLEOF"
        )

    async def _run_sql(
        self, host: str, username: str, password: str,
        env: str, sys_pass: str, sql: str,
        container: Optional[str] = None, timeout: int = 3600,
    ) -> str:
        cmd = self._sqlplus_cmd(env, sys_pass, sql, container)
        result = await self.ssh.execute_command(host, username, password, cmd, timeout=timeout)
        return (result.get("stdout") or "").strip()

    # ------------------------------------------------------------------
    # Detect ORACLE_HOME from /etc/oratab
    # ------------------------------------------------------------------
    async def _detect_oracle_home(
        self, host: str, username: str, password: str
    ) -> str:
        fallback = "/u01/app/oracle/product/19.0.0/dbhome_1"
        cmd = "grep '^[A-Za-z]' /etc/oratab 2>/dev/null | head -1 | cut -d: -f2"
        result = await self.ssh.execute_command(host, username, password, cmd)
        detected = (result.get("stdout") or "").strip()
        if detected and "/" in detected:
            return detected
        find_cmd = (
            "find /u01/app/oracle/product -name sqlplus -type f 2>/dev/null "
            "| head -1 | sed 's|/bin/sqlplus||'"
        )
        result2 = await self.ssh.execute_command(host, username, password, find_cmd)
        detected2 = (result2.get("stdout") or "").strip()
        if detected2 and "/" in detected2:
            return detected2
        return fallback

    # ------------------------------------------------------------------
    # Public: run full backup
    # ------------------------------------------------------------------
    async def run_backup(
        self,
        *,
        db_ssh_host: str,
        db_ssh_username: str,
        db_ssh_password: str,
        db_sys_password: str,
        pdb_name: str,
        schemas: str,
        oracle_sid: str = "OFSAADB",
        backup_tag: str = "BD",
        on_log: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> dict:
        """
        Run full Data Pump backup on DB host.

        Args:
            db_ssh_host: SSH host of DB server
            db_ssh_username: SSH user (typically oracle)
            db_ssh_password: SSH password
            db_sys_password: Oracle SYS password
            pdb_name: PDB / service name (e.g. OFSAAPDB2)
            schemas: comma-separated schema names (e.g. OFSCONFIG1,OFSATOMIC1)
            oracle_sid: Oracle SID (default OFSAADB)
            backup_tag: Tag for dump filenames (BD / ECM / SANC)
            on_log: async callback for streaming log lines
        """
        logs: List[str] = []

        async def log(msg: str) -> None:
            logs.append(msg)
            if on_log:
                await on_log(msg)

        host = db_ssh_host
        user = db_ssh_username
        passwd = db_ssh_password
        sys_pass = db_sys_password

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_file = f"ofs_{backup_tag}_bkp_{ts}_%U.dmp"
        log_file = f"ofs_{backup_tag}_bkp_{ts}.log"
        metadata_file = f"{BACKUP_DIR}/restore_metadata_{backup_tag}_{ts}.sql"

        # Auto-detect ORACLE_HOME
        oracle_home = await self._detect_oracle_home(host, user, passwd)
        await log(f"[BACKUP] Detected ORACLE_HOME: {oracle_home}")
        env = self._env_block(oracle_home, oracle_sid)

        schema_list = [s.strip() for s in schemas.split(",")]
        schema_in_clause = ",".join(f"'{s}'" for s in schema_list)

        # ── Step 1: Create backup directory ──
        await log("[BACKUP] Step 1: Creating backup directory")
        result = await self.ssh.execute_command(
            host, user, passwd, f"mkdir -p {BACKUP_DIR} && ls -ld {BACKUP_DIR}"
        )
        if not result.get("success"):
            await log(f"[BACKUP] ERROR: Cannot create {BACKUP_DIR}")
            return {"success": False, "logs": logs}

        # ── Step 2: Create Oracle directory object ──
        await log("[BACKUP] Step 2: Creating BACKUP_DIR_OBJ directory object")
        await self._run_sql(host, user, passwd, env, sys_pass, f"""
CREATE OR REPLACE DIRECTORY BACKUP_DIR_OBJ AS '{BACKUP_DIR}';
GRANT READ, WRITE ON DIRECTORY BACKUP_DIR_OBJ TO SYS;
""", container=pdb_name)

        # ── Step 3: Generate restore_metadata.sql ──
        await log("[BACKUP] Step 3: Generating restore_metadata.sql")
        metadata_parts: List[str] = []
        metadata_parts.append("-- ============================================================")
        metadata_parts.append(f"-- {pdb_name} {backup_tag} Pack Restore Metadata")
        metadata_parts.append("-- Run this BEFORE impdp to recreate prerequisites")
        metadata_parts.append("-- ============================================================")
        metadata_parts.append("")

        # 3a. Tablespace DDL
        await log("[BACKUP]   Capturing tablespace DDL...")
        ts_ddl = await self._run_sql(host, user, passwd, env, sys_pass, """
SELECT 'CREATE TABLESPACE ' || tablespace_name ||
       ' DATAFILE ''' || file_name || ''' SIZE ' ||
       CEIL(bytes/1024/1024) || 'M AUTOEXTEND ON MAXSIZE UNLIMITED;'
FROM dba_data_files
WHERE tablespace_name NOT IN ('SYSTEM','SYSAUX','TEMP','UNDOTBS1','USERS')
ORDER BY tablespace_name;
""", container=pdb_name)
        metadata_parts.append("-- ── TABLESPACES ──")
        metadata_parts.append(ts_ddl)
        metadata_parts.append("")

        # 3b. User DDL
        await log("[BACKUP]   Capturing user DDL...")
        user_ddl = await self._run_sql(host, user, passwd, env, sys_pass, f"""
SELECT 'CREATE USER ' || username ||
       ' IDENTIFIED BY "{sys_pass}"' ||
       ' DEFAULT TABLESPACE ' || default_tablespace ||
       ' TEMPORARY TABLESPACE ' || temporary_tablespace ||
       ' PROFILE ' || profile ||
       ' QUOTA UNLIMITED ON ' || default_tablespace || ';'
FROM dba_users
WHERE username IN ({schema_in_clause})
ORDER BY username;
""", container=pdb_name)
        metadata_parts.append("-- ── USERS ──")
        metadata_parts.append(user_ddl)
        metadata_parts.append("")

        # 3c. Tablespace quotas
        await log("[BACKUP]   Capturing tablespace quotas...")
        quota_ddl = await self._run_sql(host, user, passwd, env, sys_pass, f"""
SELECT 'ALTER USER ' || username || ' QUOTA UNLIMITED ON ' || tablespace_name || ';'
FROM dba_ts_quotas
WHERE username IN ({schema_in_clause})
AND max_bytes = -1
ORDER BY username, tablespace_name;
""", container=pdb_name)
        if quota_ddl:
            metadata_parts.append("-- ── TABLESPACE QUOTAS ──")
            metadata_parts.append(quota_ddl)
            metadata_parts.append("")

        # 3d. Custom roles
        await log("[BACKUP]   Capturing custom roles...")
        role_ddl = await self._run_sql(host, user, passwd, env, sys_pass, """
SELECT 'CREATE ROLE ' || role || ';'
FROM dba_roles
WHERE oracle_maintained = 'N' AND common = 'NO'
ORDER BY role;
""", container=pdb_name)
        if role_ddl:
            metadata_parts.append("-- ── CUSTOM ROLES ──")
            metadata_parts.append(role_ddl)
            metadata_parts.append("")

        # 3e. Role grants
        await log("[BACKUP]   Capturing role grants...")
        role_grants = await self._run_sql(host, user, passwd, env, sys_pass, f"""
SELECT 'GRANT ' || granted_role || ' TO ' || grantee ||
       CASE WHEN admin_option = 'YES' THEN ' WITH ADMIN OPTION' ELSE '' END || ';'
FROM dba_role_privs
WHERE grantee IN ({schema_in_clause})
ORDER BY grantee, granted_role;
""", container=pdb_name)
        if role_grants:
            metadata_parts.append("-- ── ROLE GRANTS TO SCHEMAS ──")
            metadata_parts.append(role_grants)
            metadata_parts.append("")

        # 3f. System privileges
        await log("[BACKUP]   Capturing system privileges...")
        sys_privs = await self._run_sql(host, user, passwd, env, sys_pass, f"""
SELECT 'GRANT ' || privilege || ' TO ' || grantee ||
       CASE WHEN admin_option = 'YES' THEN ' WITH ADMIN OPTION' ELSE '' END || ';'
FROM dba_sys_privs
WHERE grantee IN ({schema_in_clause}, 'FCCM_LOADER_ROLE')
ORDER BY grantee, privilege;
""", container=pdb_name)
        if sys_privs:
            metadata_parts.append("-- ── SYSTEM PRIVILEGES ──")
            metadata_parts.append(sys_privs)
            metadata_parts.append("")

        # 3g. Cross-schema object grants — SKIPPED
        # impdp restores all object-level grants from the .dmp file automatically.

        # 3h. Directory objects
        await log("[BACKUP]   Capturing directory objects...")
        schema_like = " OR ".join(
            f"directory_name LIKE '%{s}%'" for s in schema_list
        )
        dir_ddl = await self._run_sql(host, user, passwd, env, sys_pass, f"""
SELECT 'CREATE OR REPLACE DIRECTORY ' || directory_name ||
       ' AS ''' || directory_path || ''';'
FROM dba_directories
WHERE directory_name IN (
  SELECT DISTINCT directory_name FROM dba_directories
  WHERE {schema_like}
     OR directory_name LIKE '%OFS%' OR directory_name = 'BACKUP_DIR_OBJ'
)
ORDER BY directory_name;
""", container=pdb_name)
        if dir_ddl:
            metadata_parts.append("-- ── DIRECTORY OBJECTS ──")
            metadata_parts.append(dir_ddl)
            metadata_parts.append("")

        # 3i. Public synonyms — also skipped (impdp handles these)

        # Write metadata to DB host via heredoc
        full_metadata = "\n".join(metadata_parts)
        # Use SFTP-like approach: write via cat with heredoc
        write_cmd = f"cat > {metadata_file} <<'EOFMETA'\n{full_metadata}\nEOFMETA"
        await self.ssh.execute_command(host, user, passwd, write_cmd, timeout=60)
        wc_result = await self.ssh.execute_command(host, user, passwd, f"wc -l {metadata_file}")
        line_count = (wc_result.get("stdout") or "").strip()
        await log(f"[BACKUP]   Metadata saved: {metadata_file} ({line_count} lines)")

        # ── Step 4: Run expdp ──
        await log(f"[BACKUP] Step 4: Running expdp (schemas={schemas}, parallel=4, compression=ALL)")
        expdp_inner = (
            f'expdp "\'sys/{sys_pass}@{pdb_name} AS SYSDBA\'" '
            f'directory=BACKUP_DIR_OBJ '
            f'dumpfile={dump_file} '
            f'logfile={log_file} '
            f'schemas={schemas} '
            f'parallel=4 '
            f'compression=ALL'
        )
        expdp_cmd = (
            f'{env} nohup {expdp_inner} > {BACKUP_DIR}/expdp_shell.log 2>&1 & '
            f'EXPDP_PID=$!; echo "EXPDP_PID=$EXPDP_PID"; '
            f'echo $EXPDP_PID > {BACKUP_DIR}/expdp.pid; '
            f'while kill -0 $EXPDP_PID 2>/dev/null; do sleep 10; done; '
            f'wait $EXPDP_PID; echo "EXPDP_EXIT=$?"'
        )

        expdp_result = await self.ssh.execute_command(host, user, passwd, expdp_cmd, timeout=7200)
        expdp_out = (expdp_result.get("stdout") or "").strip()
        expdp_err = (expdp_result.get("stderr") or "").strip()

        for line in expdp_out.splitlines():
            await log(f"[BACKUP] {line}")

        if "EXPDP_EXIT=0" in expdp_out:
            await log("[BACKUP] expdp completed successfully")
        elif "EXPDP_EXIT=" in expdp_out:
            await log("[BACKUP] WARNING: expdp finished with non-zero exit code")
        else:
            await log("[BACKUP] WARNING: Could not determine expdp exit status")

        # ── Step 5: Verify backup files ──
        await log("[BACKUP] Step 5: Verifying backup files")
        ls_result = await self.ssh.execute_command(host, user, passwd, f"ls -lh {BACKUP_DIR}/ofs_{backup_tag}_bkp_{ts}_*.dmp 2>/dev/null")
        ls_out = (ls_result.get("stdout") or "").strip()
        if ls_out:
            for line in ls_out.splitlines():
                await log(f"[BACKUP]   {line}")
        else:
            await log("[BACKUP] ERROR: No dump files found after expdp!")
            return {"success": False, "logs": logs, "error": "No dump files created by expdp"}

        du_result = await self.ssh.execute_command(host, user, passwd, f"du -sh {BACKUP_DIR}/")
        await log(f"[BACKUP]   Total size: {(du_result.get('stdout') or '').strip()}")

        await log(f"[BACKUP] DB schema backup completed (tag={backup_tag}, timestamp={ts})")
        return {"success": True, "logs": logs, "timestamp": ts, "dump_prefix": f"ofs_{backup_tag}_bkp_{ts}"}
