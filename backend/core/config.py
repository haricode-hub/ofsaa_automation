from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Config:
    """Centralized default configuration values."""
    REPO_URL: str = "https://infrarepo.jmrinfotech.com:8443/ofsaa_agentic/ofsaa_auto_installation.git"
    REPO_DIR: str = "/u01/installer_kit/ofsaa_auto_installation"

    # Git credentials used on the target host for clone/pull/push.
    # NOTE: Prefer setting these via environment variables on the backend host.
    GIT_USERNAME: str = os.getenv("OFSAA_GIT_USERNAME", "2473")
    GIT_PASSWORD: str = os.getenv("OFSAA_GIT_PASSWORD", "Asdf@123")

    DEFAULT_FIC_HOME: str = "/u01/OFSAA/FICHOME"
    DEFAULT_JAVA_HOME: str = "/u01/jdk-11.0.16"
    DEFAULT_JAVA_BIN: str = "/u01/jdk-11.0.16/bin"
    DEFAULT_ORACLE_HOME: str = "/u01/app/oracle/product/19.0.0/client_1"
    DEFAULT_TNS_ADMIN: str = "/u01/app/oracle/product/19.0.0/client_1/network/admin"
    DEFAULT_ORACLE_SID: str = "OFSAAPDB"

    INSTALLER_ZIP_NAME: str = "p33940349_81100_Linux-x86-64.zip"
    JAVA_ARCHIVE_HINT: str = "jdk-11"


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
        "Applying config XMLs/properties, running osc.sh, and setup.sh SILENT",
    ]

    PROGRESS_VALUES = [12, 24, 36, 48, 60, 70, 80, 90, 100]

    @classmethod
    def progress_for_index(cls, index: int) -> int:
        if index < 0:
            return 0
        if index >= len(cls.PROGRESS_VALUES):
            return 100
        return cls.PROGRESS_VALUES[index]
