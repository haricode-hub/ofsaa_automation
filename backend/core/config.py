from dataclasses import dataclass, field
from typing import Any, Optional
import os


# ---------------------------------------------------------------------------
# Backup / Restore defaults — used by build_backup_params() as last-resort
# fallbacks when the request does not supply a value.
# ---------------------------------------------------------------------------
DEFAULT_SCHEMA_ATOMIC: str = "OFSATOMIC"
DEFAULT_SCHEMA_CONFIG: str = "OFSCONFIG"
DEFAULT_ORACLE_SID_BACKUP: str = "OFSAADB"


@dataclass
class BackupParams:
    """Single source of truth for all backup/restore parameters.

    Always built via build_backup_params(request, tag).
    Never construct manually at call sites.

    Fields
    ------
    tag            : "BD" | "ECM" | "SANC"
    db_service     : Oracle PDB / service name (from UI)
    schema_atomic  : ATOMIC schema name (e.g. OFSATOMIC1)
    schema_config  : CONFIG schema name (e.g. OFSCONFIG1)
    db_sys_password: Oracle SYS password
    oracle_sid     : Oracle SID on DB host
    app_host/username/password : SSH creds for application server
    db_ssh_*       : SSH creds for DB server (if separate from app server)
    """
    tag: str
    db_service: str
    schema_atomic: str
    schema_config: str
    db_sys_password: str
    oracle_sid: str
    app_host: str
    app_username: str
    app_password: str
    db_ssh_host: Optional[str] = None
    db_ssh_username: Optional[str] = None
    db_ssh_password: Optional[str] = None

    @property
    def effective_db_host(self) -> str:
        return self.db_ssh_host or self.app_host

    @property
    def effective_db_username(self) -> str:
        return self.db_ssh_username or self.app_username

    @property
    def effective_db_password(self) -> str:
        return self.db_ssh_password or self.app_password

    @property
    def schemas(self) -> list:
        return [s for s in [self.schema_atomic, self.schema_config] if s]


def build_backup_params(request: Any, tag: str) -> BackupParams:
    """Resolve all backup/restore parameters from a request for the given tag.

    All three tags (BD, ECM, SANC) share the same schema names and DB service
    from the main configuration fields (schema_atomic_schema_name,
    schema_config_schema_name, schema_jdbc_service).  The ECM/SANC-specific
    schema fields in the request are used only for XML patching, NOT for
    backup/restore.

    This is the ONLY place where schema names, db_service, and SSH credentials
    are resolved.  All callers (router, governor, recovery) must use this
    function instead of reading request fields directly.
    """
    if tag not in ("BD", "ECM", "SANC"):
        raise ValueError(f"Unsupported backup tag: {tag!r}")

    # All modules use the dedicated backup fields from the Main Configuration section.
    # Fall back to the XML-patching schema fields, then to defaults.
    schema_atomic = (
        getattr(request, "backup_schema_atomic", None)
        or request.schema_atomic_schema_name
        or DEFAULT_SCHEMA_ATOMIC
    )
    schema_config = (
        getattr(request, "backup_schema_config", None)
        or request.schema_config_schema_name
        or DEFAULT_SCHEMA_CONFIG
    )
    db_service = (
        getattr(request, "backup_jdbc_service", None)
        or request.schema_jdbc_service
        or ""
    )

    return BackupParams(
        tag=tag,
        db_service=db_service,
        schema_atomic=schema_atomic,
        schema_config=schema_config,
        db_sys_password=getattr(request, "db_sys_password", None) or "",
        oracle_sid=getattr(request, "oracle_sid", None) or DEFAULT_ORACLE_SID_BACKUP,
        app_host=request.host,
        app_username=request.username,
        app_password=request.password,
        db_ssh_host=getattr(request, "db_ssh_host", None),
        db_ssh_username=getattr(request, "db_ssh_username", None),
        db_ssh_password=getattr(request, "db_ssh_password", None),
    )


@dataclass(frozen=True)
class Config:
    """Centralized default configuration values."""
    REPO_URL: str = os.getenv("OFSAA_REPO_URL", "")
    REPO_DIR: str = os.getenv("OFSAA_REPO_DIR", "")

    # Git credentials used on the target host for clone/pull/push.
    # NOTE: Prefer setting these via environment variables on the backend host.
    GIT_USERNAME: str = os.getenv("OFSAA_GIT_USERNAME", "")
    GIT_PASSWORD: str = os.getenv("OFSAA_GIT_PASSWORD", "")

    DEFAULT_FIC_HOME: str = "/u01/OFSAA/FICHOME"
    DEFAULT_JAVA_HOME: str = "/u01/jdk-11.0.16"
    DEFAULT_JAVA_BIN: str = "/u01/jdk-11.0.16/bin"
    DEFAULT_ORACLE_HOME: str = "/u01/app/oracle/product/19.0.0/client_1"
    DEFAULT_TNS_ADMIN: str = "/u01/app/oracle/product/19.0.0/client_1/network/admin"
    DEFAULT_ORACLE_SID: str = "OFSAAPDB"

    INSTALLER_ZIP_NAME: str = os.getenv("OFSAA_INSTALLER_ZIP_NAME", "")
    JAVA_ARCHIVE_HINT: str = os.getenv("OFSAA_JAVA_ARCHIVE_HINT", "")
    JAVA_INSTALLER_HINT: str = os.getenv("OFSAA_JAVA_INSTALLER_HINT", "JAVA_INSTALLER")
    FAST_CONFIG_APPLY: str = os.getenv("OFSAA_FAST_CONFIG_APPLY", "1")
    ENABLE_CONFIG_PUSH: str = os.getenv("OFSAA_ENABLE_CONFIG_PUSH", "0")


class InstallationSteps:
    """Step labels and progress mapping for UI display."""
    STEP_NAMES = [
        "Creating oracle user and oinstall group",
        "Creating mount point /u01",
        "Installing KSH and git",
        "Creating .profile file",
        "Installing Java and updating profile",
        "Creating OFSAA directory structure",
        "Checking Oracle client and updating profile",
        "Setting up OFSAA installer and running environment check",
        "Applying config XMLs/properties and running osc.sh",
        "Installing BD PACK with /setup.sh SILENT",
    ]

    PROGRESS_VALUES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

    @classmethod
    def progress_for_index(cls, index: int) -> int:
        if index < 0:
            return 0
        if index >= len(cls.PROGRESS_VALUES):
            return 100
        return cls.PROGRESS_VALUES[index]
