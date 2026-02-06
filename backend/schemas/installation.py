from pydantic import BaseModel, Field
from typing import Optional, List, Dict

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

    # OFS_BD_PACK.xml user-driven inputs (optional): APP_ID -> ENABLE flag (True => YES, False => blank)
    pack_app_enable: Optional[Dict[str, bool]] = Field(default=None, description="Application enablement map for OFS_BD_PACK.xml")

    # default.properties user-driven inputs (optional)
    prop_base_country: Optional[str] = Field(default=None, description="BASE_COUNTRY")
    prop_default_jurisdiction: Optional[str] = Field(default=None, description="DEFAULT_JURISDICTION")
    prop_smtp_host: Optional[str] = Field(default=None, description="SMTP_HOST")
    prop_partition_date_format: Optional[str] = Field(default="DD-MM-YYYY", description="PARTITION_DATE_FORMAT")
    prop_web_service_user: Optional[str] = Field(default=None, description="WEB_SERVICE_USER")
    prop_web_service_password: Optional[str] = Field(default=None, description="WEB_SERVICE_PASSWORD")
    prop_configure_obiee: Optional[str] = Field(default="0", description="CONFIGURE_OBIEE (0-9)")
    prop_obiee_url: Optional[str] = Field(default="", description="OBIEE_URL (can be empty)")
    prop_sw_rmiport: Optional[str] = Field(default="8204", description="SW_RMIPORT")
    prop_big_data_enable: Optional[str] = Field(default="FALSE", description="BIG_DATA_ENABLE (TRUE/FALSE)")

    # OFSAAI_InstallConfig.xml user-driven inputs (optional)
    aai_webappservertype: Optional[str] = Field(default="3", description="WEBAPPSERVERTYPE (1/2/3)")
    aai_dbserver_ip: Optional[str] = Field(default=None, description="DBSERVER_IP")
    aai_oracle_service_name: Optional[str] = Field(default=None, description="ORACLE_SID/SERVICE_NAME")
    aai_abs_driver_path: Optional[str] = Field(default=None, description="ABS_DRIVER_PATH")
    aai_olap_server_implementation: Optional[str] = Field(default="0", description="OLAP_SERVER_IMPLEMENTATION")
    aai_sftp_enable: Optional[str] = Field(default="1", description="SFTP_ENABLE")
    aai_file_transfer_port: Optional[str] = Field(default="22", description="FILE_TRANSFER_PORT")
    aai_javaport: Optional[str] = Field(default="9999", description="JAVAPORT")
    aai_nativeport: Optional[str] = Field(default="6666", description="NATIVEPORT")
    aai_agentport: Optional[str] = Field(default="6510", description="AGENTPORT")
    aai_iccport: Optional[str] = Field(default="6507", description="ICCPORT")
    aai_iccnativeport: Optional[str] = Field(default="6509", description="ICCNATIVEPORT")
    aai_olapport: Optional[str] = Field(default="10101", description="OLAPPORT")
    aai_msgport: Optional[str] = Field(default="6501", description="MSGPORT")
    aai_routerport: Optional[str] = Field(default="6502", description="ROUTERPORT")
    aai_amport: Optional[str] = Field(default="6506", description="AMPORT")
    aai_https_enable: Optional[str] = Field(default="1", description="HTTPS_ENABLE")
    aai_web_server_ip: Optional[str] = Field(default=None, description="WEB_SERVER_IP")
    aai_web_server_port: Optional[str] = Field(default="7002", description="WEB_SERVER_PORT")
    aai_context_name: Optional[str] = Field(default="FICHOME", description="CONTEXT_NAME")
    aai_webapp_context_path: Optional[str] = Field(default=None, description="WEBAPP_CONTEXT_PATH")
    aai_web_local_path: Optional[str] = Field(default="/u01/OFSAA/FTPSHARE", description="WEB_LOCAL_PATH")
    aai_weblogic_domain_home: Optional[str] = Field(default=None, description="WEBLOGIC_DOMAIN_HOME")
    aai_ftspshare_path: Optional[str] = Field(default="/u01/OFSAA/FTPSHARE", description="OFSAAI_FTPSHARE_PATH")
    aai_sftp_user_id: Optional[str] = Field(default="oracle", description="OFSAAI_SFTP_USER_ID")

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
