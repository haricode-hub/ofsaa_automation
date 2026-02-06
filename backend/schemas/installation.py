from pydantic import BaseModel, Field
from typing import Optional, List

class InstallationRequest(BaseModel):
    """Schema for installation request"""
    host: str = Field(..., description="Target host IP address or hostname")
    username: str = Field(..., description="Root username for SSH connection")
    password: str = Field(..., description="Root password for SSH connection")
    # Profile variables that user can customize
    fic_home: Optional[str] = Field(default="/u01/OFSAA/FICHOME", description="FIC_HOME path")
    java_home: Optional[str] = Field(default=None, description="Custom JAVA_HOME path (optional)")
    java_bin: Optional[str] = Field(default=None, description="Custom JAVA_BIN path (optional)")
    oracle_sid: Optional[str] = Field(default="ORCL", description="Oracle SID")

    # OFS_BD_SCHEMA_IN.xml user-driven inputs (optional)
    schema_jdbc_host: Optional[str] = Field(default=None, description="DB host for JDBC_URL")
    schema_jdbc_port: Optional[int] = Field(default=1521, description="DB port for JDBC_URL")
    schema_jdbc_service: Optional[str] = Field(default=None, description="DB service/SID for JDBC_URL")
    schema_host: Optional[str] = Field(default=None, description="Value for <HOST> in OFS_BD_SCHEMA_IN.xml")
    schema_setup_env: Optional[str] = Field(default=None, description="SETUPINFO NAME (DEV/UAT/PROD etc.)")
    schema_apply_same_for_all: Optional[str] = Field(default="Y", description="PASSWORD APPLYSAMEFORALL (Y/N)")
    schema_default_password: Optional[str] = Field(default=None, description="PASSWORD DEFAULT value")
    schema_datafile_dir: Optional[str] = Field(
        default=None,
        description="Base directory for TABLESPACE DATAFILE paths; filename will be preserved",
    )
    schema_tablespace_autoextend: Optional[str] = Field(default=None, description="TABLESPACE AUTOEXTEND (ON/OFF)")
    schema_external_directory_value: Optional[str] = Field(default=None, description="DIRECTORY VALUE path")
    schema_config_schema_name: Optional[str] = Field(default=None, description="SCHEMA TYPE=CONFIG NAME value")
    schema_atomic_schema_name: Optional[str] = Field(default=None, description="SCHEMA TYPE=ATOMIC NAME value (applies to all)")

class InstallationResponse(BaseModel):
    """Schema for installation response"""
    task_id: str
    status: str
    message: str

class InstallationStatus(BaseModel):
    """Schema for installation status"""
    task_id: str
    status: str
    current_step: Optional[str] = None
    progress: int = 0
    logs: List[str] = []
    error: Optional[str] = None

class SSHConnectionRequest(BaseModel):
    """Schema for SSH connection test"""
    host: str
    username: str
    password: str

class ServiceResult(BaseModel):
    """Schema for service operation results"""
    success: bool
    message: str
    logs: List[str] = []
    error: Optional[str] = None
    output: Optional[str] = None
    stderr: Optional[str] = None
    returncode: Optional[int] = None

class OracleClientConfig(BaseModel):
    """Schema for Oracle client configuration"""
    oracle_home: str
    tns_admin: str
    oracle_sid: str

class InteractivePrompt(BaseModel):
    """Schema for interactive command prompts"""
    task_id: str
    prompt_text: str
    timestamp: str

class InteractiveResponse(BaseModel):
    """Schema for interactive command responses"""
    task_id: str
    response_text: str
    check_only: bool = True  # Default to check existing instead of install
    skip_backups: bool = True  # Skip creating backup files
    
class OracleClientResult(BaseModel):
    """Schema for Oracle client operation results"""
    success: bool
    message: str
    logs: List[str] = []
    oracle_home: Optional[str] = None
    tns_admin: Optional[str] = None
    oracle_sid: Optional[str] = None
    validation_passed: bool = False
    error: Optional[str] = None
