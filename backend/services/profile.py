from typing import Optional

from core.config import Config
from services.ssh_service import SSHService
from services.validation import ValidationService
from services.utils import sed_escape


class ProfileService:
    """Manage /home/oracle/.profile creation and updates."""

    def __init__(self, ssh_service: SSHService, validation: ValidationService) -> None:
        self.ssh_service = ssh_service
        self.validation = validation

    def _profile_template(self) -> str:
        return (
            "alias c=clear\n"
            "alias p=\"ps -ef | grep $LOGNAME\"\n"
            "alias pp=\"ps -fu $LOGNAME\"\n"
            "PS1='$PWD>'\n"
            "export PS1\n"
            "\n"
            "stty erase ^?\n"
            "\n"
            "echo $PATH\n"
            f"export FIC_HOME={Config.DEFAULT_FIC_HOME}\n"
            "\n"
            f"export JAVA_HOME={Config.DEFAULT_JAVA_HOME}\n"
            f"export JAVA_BIN={Config.DEFAULT_JAVA_BIN}\n"
            "export ANT_HOME=$FIC_HOME/ficweb/apache-ant\n"
            "\n"
            f"export ORACLE_HOME={Config.DEFAULT_ORACLE_HOME}\n"
            f"export TNS_ADMIN={Config.DEFAULT_TNS_ADMIN}\n"
            "\n"
            "export LANG=en_US.utf8\n"
            "export NLS_LANG=AMERICAN_AMERICA.AL32UTF8\n"
            "\n"
            f"export ORACLE_SID={Config.DEFAULT_ORACLE_SID}\n"
            "\n"
            "export PATH=.:$JAVA_HOME/bin:$ORACLE_HOME/bin:/sbin:/bin:/usr/bin:/usr/kerberos/bin:/usr/local/bin:/usr/sbin:$PATH\n"
            "\n"
            "export LD_LIBRARY_PATH=$ORACLE_HOME/lib:/lib:/usr/lib\n"
            "export CLASSPATH=$ORACLE_HOME/jlib:$ORACLE_HOME/rdbms/jlib\n"
            "export SHELL=/bin/ksh\n"
            "\n"
            "echo \"********************************************************\"\n"
            "echo \"   THIS IS FCCM SKND SETUP,PLEASE DO NOT MAKE ANY CHANGE   \"\n"
            "echo \"********************************************************\"\n"
            "\n"
            "echo PROFILE EXECUTED\n"
            "echo $PATH\n"
            "echo \"SHELL Check :: \" $SHELL\n"
            "\n"
            "set -o emacs\n"
            "umask 0027\n"
            "\n"
            "export OS_VERSION=\"8\"\n"
            "export DB_CLIENT_VERSION=\"19.0\"\n"
            "\n"
            "ulimit -n 16000\n"
            "ulimit -u 16000\n"
            "ulimit -s 16000\n"
        )

    async def create_profile_file(self, host: str, username: str, password: str) -> dict:
        logs: list[str] = []
        profile_path = "/home/oracle/.profile"

        exists = await self.validation.check_file_exists(host, username, password, profile_path)
        if exists.get("exists"):
            backup = await self.validation.backup_file(host, username, password, profile_path)
            logs.append(f"[INFO] Existing profile backed up: {backup.get('message')}")

        template = self._profile_template()
        cmd = (
            f"cat <<'EOF' > {profile_path}\n"
            f"{template}\n"
            "EOF\n"
            f"chown oracle:oinstall {profile_path}\n"
            f"chmod 644 {profile_path}"
        )
        result = await self.ssh_service.execute_command(host, username, password, cmd, get_pty=True)
        if not result["success"]:
            return {
                "success": False,
                "logs": logs,
                "error": result.get("stderr") or "Failed to create .profile",
            }

        logs.append("[OK] .profile created with default configuration")
        return {"success": True, "logs": logs}

    async def update_profile_variable(
        self,
        host: str,
        username: str,
        password: str,
        variable: str,
        value: str,
    ) -> dict:
        profile_path = "/home/oracle/.profile"
        escaped_value = sed_escape(value)
        cmd = (
            f"if grep -q '^export {variable}=' {profile_path}; then "
            f"sed -i 's|^export {variable}=.*|export {variable}={escaped_value}|' {profile_path}; "
            f"else echo 'export {variable}={value}' >> {profile_path}; fi"
        )
        result = await self.ssh_service.execute_command(host, username, password, cmd, get_pty=True)
        if not result["success"]:
            return {
                "success": False,
                "error": result.get("stderr") or f"Failed to update {variable}",
            }
        return {"success": True}

    async def update_profile_with_custom_variables(
        self,
        host: str,
        username: str,
        password: str,
        fic_home: Optional[str],
        java_home: Optional[str],
        java_bin: Optional[str],
        oracle_sid: Optional[str],
    ) -> dict:
        logs: list[str] = []

        if fic_home:
            result = await self.update_profile_variable(host, username, password, "FIC_HOME", fic_home)
            if not result["success"]:
                return {"success": False, "logs": logs, "error": result.get("error")}
            logs.append(f"[OK] Updated FIC_HOME to {fic_home}")

        if java_home:
            result = await self.update_profile_variable(host, username, password, "JAVA_HOME", java_home)
            if not result["success"]:
                return {"success": False, "logs": logs, "error": result.get("error")}
            logs.append(f"[OK] Updated JAVA_HOME to {java_home}")

        if java_bin:
            result = await self.update_profile_variable(host, username, password, "JAVA_BIN", java_bin)
            if not result["success"]:
                return {"success": False, "logs": logs, "error": result.get("error")}
            logs.append(f"[OK] Updated JAVA_BIN to {java_bin}")

        if oracle_sid:
            result = await self.update_profile_variable(host, username, password, "ORACLE_SID", oracle_sid)
            if not result["success"]:
                return {"success": False, "logs": logs, "error": result.get("error")}
            logs.append(f"[OK] Updated ORACLE_SID to {oracle_sid}")

        if not logs:
            logs.append("[INFO] No custom profile overrides provided")

        return {"success": True, "logs": logs}

    async def verify_profile_setup(self, host: str, username: str, password: str) -> dict:
        cmd = (
            "bash -lc 'source /home/oracle/.profile >/dev/null 2>&1; "
            "echo FIC_HOME=$FIC_HOME; "
            "echo JAVA_HOME=$JAVA_HOME; "
            "echo JAVA_BIN=$JAVA_BIN; "
            "echo ORACLE_HOME=$ORACLE_HOME; "
            "echo TNS_ADMIN=$TNS_ADMIN; "
            "echo ORACLE_SID=$ORACLE_SID'"
        )
        result = await self.ssh_service.execute_command(host, username, password, cmd, get_pty=True)
        if not result["success"]:
            return {
                "success": False,
                "logs": [],
                "error": result.get("stderr") or "Profile verification failed",
            }
        logs = ["[OK] Profile verification output:"] + result.get("stdout", "").splitlines()
        return {"success": True, "logs": logs}
