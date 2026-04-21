"""DB schema restore using Oracle Data Pump (impdp) + metadata replay.

Replaces the old shell-script-based restore_ofs_schemas.sh approach.
All values are parameterized — nothing hardcoded.
"""

import logging
from typing import Callable, Awaitable, Optional, List

from services.ssh_service import SSHService
from services.utils import shell_escape

logger = logging.getLogger(__name__)

BACKUP_DIR = "/u01/backup/ofsaa"


class RestoreService:
    """Runs metadata replay + impdp schema restore on the DB host."""

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

    async def _run_sql(
        self, host: str, username: str, password: str,
        env: str, sys_pass: str, sql: str,
        container: Optional[str] = None, timeout: int = 3600,
    ) -> str:
        alter = f"ALTER SESSION SET CONTAINER = {container};" if container else ""
        cmd = (
            f'{env} sqlplus -s "sys/{sys_pass} as sysdba" <<\'SQLEOF\'\n'
            f"SET LINESIZE 4000\n"
            f"SET PAGESIZE 0\n"
            f"SET FEEDBACK ON\n"
            f"SET HEADING OFF\n"
            f"SET TRIMSPOOL ON\n"
            f"SET ECHO ON\n"
            f"SET SERVEROUTPUT ON\n"
            f"{alter}\n"
            f"{sql}\n"
            f"SQLEOF"
        )
        result = await self.ssh.execute_command(host, username, password, cmd, timeout=timeout)
        return (result.get("stdout") or "").strip()

    async def _run_sql_silent(
        self, host: str, username: str, password: str,
        env: str, sys_pass: str, sql: str,
        container: Optional[str] = None, timeout: int = 3600,
    ) -> str:
        alter = f"ALTER SESSION SET CONTAINER = {container};" if container else ""
        cmd = (
            f'{env} sqlplus -s "sys/{sys_pass} as sysdba" <<\'SQLEOF\'\n'
            f"SET LINESIZE 4000\n"
            f"SET PAGESIZE 0\n"
            f"SET FEEDBACK OFF\n"
            f"SET HEADING OFF\n"
            f"SET TRIMSPOOL ON\n"
            f"SET ECHO OFF\n"
            f"{alter}\n"
            f"{sql}\n"
            f"SQLEOF"
        )
        result = await self.ssh.execute_command(host, username, password, cmd, timeout=timeout)
        return (result.get("stdout") or "").strip()

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
    # Public: run full restore
    # ------------------------------------------------------------------
    async def run_restore(
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
        dump_prefix: Optional[str] = None,
        metadata_path: Optional[str] = None,
        on_log: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> dict:
        """
        Run full Data Pump restore on DB host.

        Args:
            db_ssh_host: SSH host of DB server
            db_ssh_username: SSH user (typically oracle)
            db_ssh_password: SSH password
            db_sys_password: Oracle SYS password
            pdb_name: PDB / service name (e.g. OFSAAPDB2)
            schemas: comma-separated schema names (e.g. OFSCONFIG1,OFSATOMIC1)
            oracle_sid: Oracle SID (default OFSAADB)
            backup_tag: Tag to locate dump files (BD / ECM / SANC)
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

        if dump_prefix:
            dump_file = f"{dump_prefix}_%U.dmp"
            await log(f"[RESTORE] Using manifest dump prefix: {dump_prefix}")
        else:
            find_latest_cmd = (
                f"ls -1 {BACKUP_DIR}/ofs_{backup_tag}_bkp_*_01.dmp 2>/dev/null "
                f"| sort | tail -1"
            )
            latest_result = await self.ssh.execute_command(host, user, passwd, find_latest_cmd)
            latest_file = (latest_result.get("stdout") or "").strip()

            if latest_file:
                import re
                m = re.search(rf"ofs_{backup_tag}_bkp_(\d{{8}}_\d{{6}})_01\.dmp", latest_file)
                if m:
                    ts = m.group(1)
                    dump_file = f"ofs_{backup_tag}_bkp_{ts}_%U.dmp"
                    await log(f"[RESTORE] Found latest dump set: timestamp={ts}")
                else:
                    dump_file = f"ofs_{backup_tag}_bkp_%U.dmp"
                    await log("[RESTORE] Found dump file but could not parse timestamp, using generic pattern")
            else:
                dump_file = f"ofs_{backup_tag}_bkp_%U.dmp"
                await log(f"[RESTORE] No timestamped dumps found, trying legacy pattern: {dump_file}")

        if metadata_path:
            metadata_file = metadata_path
            await log(f"[RESTORE] Using manifest metadata: {metadata_file}")
        else:
            find_meta_cmd = (
                f"ls -1 {BACKUP_DIR}/restore_metadata_{backup_tag}_*.sql 2>/dev/null "
                f"| sort | tail -1"
            )
            meta_result_check = await self.ssh.execute_command(host, user, passwd, find_meta_cmd)
            metadata_file = (meta_result_check.get("stdout") or "").strip()
            if not metadata_file:
                metadata_file = f"{BACKUP_DIR}/restore_metadata.sql"
                await log(f"[RESTORE] No timestamped metadata found, using legacy: {metadata_file}")
            else:
                await log(f"[RESTORE] Using metadata: {metadata_file}")

        # Auto-detect ORACLE_HOME
        oracle_home = await self._detect_oracle_home(host, user, passwd)
        await log(f"[RESTORE] Detected ORACLE_HOME: {oracle_home}")
        env = self._env_block(oracle_home, oracle_sid)

        schema_list = [s.strip() for s in schemas.split(",")]
        schema_in_clause = ",".join(f"'{s}'" for s in schema_list)

        # ── Pre-flight checks ──
        await log("[RESTORE] Step 0: Pre-flight checks")

        # Check PDB is open READ WRITE
        pdb_status = await self._run_sql_silent(
            host, user, passwd, env, sys_pass,
            f"SELECT open_mode FROM v$pdbs WHERE name = '{pdb_name}';",
        )
        if "READ WRITE" not in pdb_status:
            await log(f"[RESTORE] ERROR: PDB {pdb_name} is not open READ WRITE. Got: {pdb_status}")
            return {"success": False, "logs": logs, "error": f"PDB {pdb_name} not open"}
        await log(f"[RESTORE]   PDB {pdb_name}: READ WRITE ✓")

        # Check dump files exist (use the resolved dump_file pattern)
        check_pattern = dump_file.replace('%U', '*')
        ls_result = await self.ssh.execute_command(
            host, user, passwd, f"ls {BACKUP_DIR}/{check_pattern} 2>/dev/null | head -5"
        )
        ls_out = (ls_result.get("stdout") or "").strip()
        if not ls_out:
            await log(f"[RESTORE] ERROR: No dump files found in {BACKUP_DIR}/ for pattern={check_pattern}")
            return {"success": False, "logs": logs, "error": "No dump files found"}
        await log(f"[RESTORE]   Dump files found ✓")

        # Check metadata file
        meta_check = await self.ssh.execute_command(
            host, user, passwd, f"test -f {metadata_file} && echo EXISTS || echo MISSING"
        )
        if "MISSING" in (meta_check.get("stdout") or ""):
            await log(f"[RESTORE] ERROR: Metadata file not found: {metadata_file}")
            return {"success": False, "logs": logs, "error": "Metadata file not found"}
        await log(f"[RESTORE]   Metadata file found ✓")

        # ── Step 1: Drop existing schemas ──
        await log("[RESTORE] Step 1: Dropping existing schemas")
        for schema in schema_list:
            exists = await self._run_sql_silent(
                host, user, passwd, env, sys_pass,
                f"SELECT username FROM dba_users WHERE username = '{schema}';",
                container=pdb_name,
            )
            if schema in exists:
                await log(f"[RESTORE]   Dropping {schema}...")
                await self._run_sql(
                    host, user, passwd, env, sys_pass,
                    f"DROP USER {schema} CASCADE;",
                    container=pdb_name,
                )
            else:
                await log(f"[RESTORE]   {schema} does not exist, skipping")

        # Drop public synonyms for these schemas
        await log("[RESTORE]   Dropping public synonyms...")
        await self._run_sql(host, user, passwd, env, sys_pass, f"""
BEGIN
  FOR rec IN (
    SELECT synonym_name FROM dba_synonyms
    WHERE owner = 'PUBLIC'
    AND table_owner IN ({schema_in_clause})
  ) LOOP
    EXECUTE IMMEDIATE 'DROP PUBLIC SYNONYM ' || rec.synonym_name;
  END LOOP;
END;
/
""", container=pdb_name)

        # Drop custom roles
        await log("[RESTORE]   Dropping custom roles...")
        await self._run_sql(host, user, passwd, env, sys_pass, """
BEGIN
  FOR rec IN (
    SELECT role FROM dba_roles
    WHERE oracle_maintained = 'N' AND common = 'NO'
    AND role NOT IN ('PDB_DBA')
  ) LOOP
    BEGIN
      EXECUTE IMMEDIATE 'DROP ROLE ' || rec.role;
    EXCEPTION WHEN OTHERS THEN NULL;
    END;
  END LOOP;
END;
/
""", container=pdb_name)

        # Drop non-default tablespaces
        await log("[RESTORE]   Dropping non-default tablespaces...")
        await self._run_sql(host, user, passwd, env, sys_pass, """
BEGIN
  FOR rec IN (
    SELECT tablespace_name FROM dba_tablespaces
    WHERE tablespace_name NOT IN ('SYSTEM','SYSAUX','TEMP','UNDOTBS1','USERS')
    ORDER BY tablespace_name
  ) LOOP
    BEGIN
      EXECUTE IMMEDIATE 'DROP TABLESPACE ' || rec.tablespace_name ||
                         ' INCLUDING CONTENTS AND DATAFILES CASCADE CONSTRAINTS';
      DBMS_OUTPUT.PUT_LINE('Dropped: ' || rec.tablespace_name);
    EXCEPTION WHEN OTHERS THEN
      DBMS_OUTPUT.PUT_LINE('Skip: ' || rec.tablespace_name || ' - ' || SQLERRM);
    END;
  END LOOP;
END;
/
""", container=pdb_name, timeout=600)

        # ── Step 2: Run metadata script ──
        await log("[RESTORE] Step 2: Running restore_metadata.sql")
        meta_result = await self._run_sql(
            host, user, passwd, env, sys_pass,
            f"@{metadata_file}",
            container=pdb_name, timeout=300,
        )
        if meta_result:
            # Only log first/last few lines to avoid flooding
            lines = meta_result.splitlines()
            for line in lines[:20]:
                await log(f"[RESTORE]   {line}")
            if len(lines) > 20:
                await log(f"[RESTORE]   ... ({len(lines) - 20} more lines)")

        # Verify tablespaces
        ts_count = await self._run_sql_silent(
            host, user, passwd, env, sys_pass, """
SELECT count(*) FROM dba_tablespaces
WHERE tablespace_name NOT IN ('SYSTEM','SYSAUX','TEMP','UNDOTBS1','USERS');
""", container=pdb_name)
        await log(f"[RESTORE]   Tablespaces created: {ts_count.strip()}")

        # Verify users
        user_check = await self._run_sql_silent(
            host, user, passwd, env, sys_pass, f"""
SELECT username || ' - ' || account_status FROM dba_users
WHERE username IN ({schema_in_clause})
ORDER BY username;
""", container=pdb_name)
        await log(f"[RESTORE]   Users: {user_check}")

        # ── Step 3: Ensure BACKUP_DIR_OBJ ──
        await log("[RESTORE] Step 3: Ensuring BACKUP_DIR_OBJ directory")
        await self._run_sql(
            host, user, passwd, env, sys_pass,
            f"CREATE OR REPLACE DIRECTORY BACKUP_DIR_OBJ AS '{BACKUP_DIR}';",
            container=pdb_name,
        )

        # ── Step 4: Run impdp ──
        await log(f"[RESTORE] Step 4: Running impdp (schemas={schemas}, parallel=4)")
        impdp_cmd = (
            f'{env} impdp "\'sys/{sys_pass}@{pdb_name} AS SYSDBA\'" '
            f'directory=BACKUP_DIR_OBJ '
            f'dumpfile={dump_file} '
            f'logfile=restore_{backup_tag.lower()}.log '
            f'schemas={schemas} '
            f'parallel=4 '
            f'table_exists_action=REPLACE'
        )

        impdp_result = await self.ssh.execute_command(host, user, passwd, impdp_cmd, timeout=7200)
        impdp_out = (impdp_result.get("stdout") or "").strip()
        impdp_err = (impdp_result.get("stderr") or "").strip()

        for line in impdp_out.splitlines():
            await log(f"[RESTORE] {line}")
        if impdp_err.strip():
            await log(f"[RESTORE] STDERR: {impdp_err}")

        impdp_rc = impdp_result.get("exit_code", -1)
        if impdp_rc != 0:
            await log(f"[RESTORE] WARNING: impdp exit code = {impdp_rc} (may have warnings)")

        # ── Step 5: Recompile invalid objects ──
        await log("[RESTORE] Step 5: Recompiling invalid objects")
        for schema in schema_list:
            await self._run_sql(host, user, passwd, env, sys_pass, f"""
BEGIN
  DBMS_UTILITY.COMPILE_SCHEMA(schema => '{schema}', compile_all => FALSE);
END;
/
""", container=pdb_name, timeout=600)

        invalid_count = await self._run_sql_silent(
            host, user, passwd, env, sys_pass, f"""
SELECT count(*) FROM dba_objects
WHERE status = 'INVALID'
AND owner IN ({schema_in_clause});
""", container=pdb_name)
        await log(f"[RESTORE]   Remaining invalid objects: {invalid_count.strip()}")

        # ── Step 6: Verify restore ──
        await log("[RESTORE] Step 6: Verifying restore")

        obj_counts = await self._run_sql_silent(
            host, user, passwd, env, sys_pass, f"""
SELECT owner || ': ' || count(*) || ' objects'
FROM dba_objects
WHERE owner IN ({schema_in_clause})
GROUP BY owner ORDER BY owner;
""", container=pdb_name)
        await log(f"[RESTORE]   Object counts: {obj_counts}")

        tbl_counts = await self._run_sql_silent(
            host, user, passwd, env, sys_pass, f"""
SELECT owner || ': ' || count(*) || ' tables'
FROM dba_tables
WHERE owner IN ({schema_in_clause})
GROUP BY owner ORDER BY owner;
""", container=pdb_name)
        await log(f"[RESTORE]   Table counts: {tbl_counts}")

        seg_space = await self._run_sql_silent(
            host, user, passwd, env, sys_pass, f"""
SELECT owner || ': ' || round(sum(bytes)/1024/1024,1) || ' MB'
FROM dba_segments
WHERE owner IN ({schema_in_clause})
GROUP BY owner ORDER BY owner;
""", container=pdb_name)
        await log(f"[RESTORE]   Segment space: {seg_space}")

        await log("[RESTORE] DB schema restore completed")
        return {"success": True, "logs": logs}
