import os
from typing import Optional, List

class Config:
    """Application configuration"""
    
    # SSH Configuration
    SSH_TIMEOUT: int = int(os.getenv("SSH_TIMEOUT", "30"))
    SSH_COMMAND_TIMEOUT: int = int(os.getenv("SSH_COMMAND_TIMEOUT", "600"))
    
    # Installation Configuration
    DEFAULT_FIC_HOME: str = os.getenv("DEFAULT_FIC_HOME", "/u01/OFSAA/FICHOME")
    DEFAULT_ORACLE_SID: str = os.getenv("DEFAULT_ORACLE_SID", "ORCL")
    JAVA_INSTALL_PATH: str = os.getenv("JAVA_INSTALL_PATH", "/opt/java")
    ORACLE_CLIENT_PATH: str = os.getenv("ORACLE_CLIENT_PATH", "/opt/oracle/instantclient_19_8")
    
    # Git Repository Configuration
    JAVA_REPO_URL: str = os.getenv("JAVA_REPO_URL", "https://infrarepo.jmrinfotech.com:8443/ofsaa_agentic/ofsaa_auto_installation")
    JAVA_FILE_NAME: str = os.getenv("JAVA_FILE_NAME", "jdk-11.0.16_linux-x64_bin__1_.tar.gz")
    OFSAA_INSTALLER_FILE: str = os.getenv("OFSAA_INSTALLER_FILE", "p33940349_81100_Linux-x86-64.zip")
    
    # Paths
    INSTALLER_KIT_PATH: str = "/u01/installer_kit"
    ORACLE_HOME_PATH: str = "/home/oracle"
    ORACLE_PROFILE_PATH: str = "/home/oracle/.profile"
    TEMP_DIR: str = "/tmp"  # Centralized temp directory
    
    # File Management
    SKIP_BACKUP_FILES: bool = bool(os.getenv("SKIP_BACKUP_FILES", "true").lower() == "true")
    CLEANUP_TEMP_FILES: bool = bool(os.getenv("CLEANUP_TEMP_FILES", "true").lower() == "true")
    MAX_LOG_LINES: int = int(os.getenv("MAX_LOG_LINES", "1000"))
    
    # Oracle Client Settings
    ORACLE_CLIENT_CHECK_ONLY: bool = bool(os.getenv("ORACLE_CLIENT_CHECK_ONLY", "true").lower() == "true")
    ORACLE_SEARCH_PATHS: List[str] = [
        "/u01/app/oracle/product/*/client*",
        "/opt/oracle/*/client*", 
        "/home/oracle/*/client*",
        "/usr/lib/oracle/*/client*",
        "/oracle/*/client*"
    ]
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Task Management
    TASK_CLEANUP_INTERVAL: int = int(os.getenv("TASK_CLEANUP_INTERVAL", "3600"))  # 1 hour
    MAX_TASKS_IN_MEMORY: int = int(os.getenv("MAX_TASKS_IN_MEMORY", "100"))

class InstallationSteps:
    """Constants for installation steps"""
    
    STEP_NAMES = {
        1: "Creating oracle user and oinstall group",
        2: "Creating mount point /u01", 
        3: "Installing KSH and git",
        4: "Creating .profile file",
        5: "Installing Java and updating profile",
        6: "Creating OFSAA directory structure",
        7: "Checking Oracle client and updating profile",
        8: "Setting up OFSAA installer and running environment check",
        9: "Updating profile with custom variables",
        10: "Verifying profile setup"
    }
    
    PROGRESS_MAP = {
        "connection_test": 8,
        "oracle_user_setup": 15,
        "mount_point_creation": 22,
        "packages_installation": 30,
        "profile_creation": 38,
        "java_installation": 46,
        "ofsaa_directories": 54,
        "oracle_client_check": 62,
        "installer_setup": 70,
        "environment_check": 78,
        "profile_update": 86,
        "verification": 94,
        "completed": 100
    }