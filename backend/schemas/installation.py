from pydantic import BaseModel, Field
from typing import Any, Optional, List, Dict

class InstallationRequest(BaseModel):
    """Schema for installation request"""
    host: str = Field(..., description="Target host IP address or hostname")
    username: str = Field(..., description="Root username for SSH connection")
    password: str = Field(..., description="Root password for SSH connection")
    
    # Checkpoint/Resume support (repurposed: resume ECM from BD backup)
    resume_from_checkpoint: bool = Field(default=False, description="Resume from BD backup (skip BD Pack, start ECM from backup restore point)")
    
    # Database SYS/DBA password for backup/restore/cleanup operations
    db_sys_password: Optional[str] = Field(default=None, description="Oracle SYS password for sqlplus connections (backup/restore/schema cleanup)")
    
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
    prop_datadumpdt_minus_0: Optional[str] = Field(default=None, description="DATADUMPDT_MINUS_0")
    prop_endthisweek_minus_00: Optional[str] = Field(default=None, description="ENDTHISWEEK_MINUS_00")
    prop_startnextmnth_minus_00: Optional[str] = Field(default=None, description="STARTNEXTMNTH_MINUS_00")
    prop_analyst_data_source: Optional[str] = Field(default="ANALYST", description="ANALYST_DATA_SOURCE")
    prop_miner_data_source: Optional[str] = Field(default="MINER", description="MINER_DATA_SOURCE")
    prop_web_service_user: Optional[str] = Field(default=None, description="WEB_SERVICE_USER")
    prop_web_service_password: Optional[str] = Field(default=None, description="WEB_SERVICE_PASSWORD")
    prop_nls_length_semantics: Optional[str] = Field(default="CHAR", description="NLS_LENGTH_SEMANTICS")
    prop_configure_obiee: Optional[str] = Field(default="0", description="CONFIGURE_OBIEE (0-9)")
    prop_obiee_url: Optional[str] = Field(default="", description="OBIEE_URL (can be empty)")
    prop_sw_rmiport: Optional[str] = Field(default="8204", description="SW_RMIPORT")
    prop_big_data_enable: Optional[str] = Field(default="FALSE", description="BIG_DATA_ENABLE (TRUE/FALSE)")
    prop_sqoop_working_dir: Optional[str] = Field(default="", description="SQOOP_WORKING_DIR")
    prop_ssh_auth_alias: Optional[str] = Field(default="", description="SSH_AUTH_ALIAS")
    prop_ssh_host_name: Optional[str] = Field(default="", description="SSH_HOST_NAME")
    prop_ssh_port: Optional[str] = Field(default="", description="SSH_PORT")
    prop_cssource: Optional[str] = Field(default="", description="CSSOURCE")
    prop_csloadtype: Optional[str] = Field(default="", description="CSLOADTYPE")
    prop_crrsource: Optional[str] = Field(default="", description="CRRSOURCE")
    prop_crrloadtype: Optional[str] = Field(default="", description="CRRLOADTYPE")
    prop_fsdf_upload_model: Optional[str] = Field(default="1", description="FSDF_UPLOAD_MODEL (0/1)")

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
    installation_mode: Optional[str] = Field(default="fresh", description="Installation mode: fresh/addon/auto")
    install_sanc: Optional[bool] = Field(default=None, description="Install SANC module")

    # Module selection flags
    install_bdpack: bool = Field(default=False, description="Install BD Pack module")
    install_ecm: bool = Field(default=False, description="Install ECM module")

    # ============== ECM MODULE FIELDS ==============
    # OFS_ECM_SCHEMA_IN.xml fields
    ecm_schema_jdbc_host: Optional[str] = Field(default=None, description="ECM DB host for JDBC_URL")
    ecm_schema_jdbc_port: Optional[int] = Field(default=1521, description="ECM DB port for JDBC_URL")
    ecm_schema_jdbc_service: Optional[str] = Field(default=None, description="ECM DB service/SID for JDBC_URL")
    ecm_schema_host: Optional[str] = Field(default=None, description="ECM Application hostname")
    ecm_schema_setup_env: Optional[str] = Field(default="DEV", description="ECM SETUPINFO NAME")
    ecm_schema_prefix_schema_name: Optional[str] = Field(default="N", description="ECM PREFIX_SCHEMA_NAME (Y/N)")
    ecm_schema_apply_same_for_all: Optional[str] = Field(default="Y", description="ECM PASSWORD APPLYSAMEFORALL")
    ecm_schema_default_password: Optional[str] = Field(default=None, description="ECM Schema password")
    ecm_schema_datafile_dir: Optional[str] = Field(default=None, description="ECM Datafile directory path")
    ecm_schema_config_schema_name: Optional[str] = Field(default=None, description="ECM CONFIG schema name")
    ecm_schema_atomic_schema_name: Optional[str] = Field(default=None, description="ECM ATOMIC schema name")

    # ECM default.properties fields
    ecm_prop_base_country: Optional[str] = Field(default="US", description="ECM BASE_COUNTRY")
    ecm_prop_default_jurisdiction: Optional[str] = Field(default="AMEA", description="ECM DEFAULT_JURISDICTION")
    ecm_prop_smtp_host: Optional[str] = Field(default=None, description="ECM SMTP_HOST")
    ecm_prop_web_service_user: Optional[str] = Field(default="oracle", description="ECM WEB_SERVICE_USER")
    ecm_prop_web_service_password: Optional[str] = Field(default=None, description="ECM WEB_SERVICE_PASSWORD")
    ecm_prop_nls_length_semantics: Optional[str] = Field(default="BYTE", description="ECM NLS_LENGTH_SEMANTICS")
    ecm_prop_analyst_data_source: Optional[str] = Field(default="ANALYST", description="ECM ANALYST_DATA_SOURCE")
    ecm_prop_miner_data_source: Optional[str] = Field(default="MINER", description="ECM MINER_DATA_SOURCE")
    ecm_prop_configure_obiee: Optional[str] = Field(default="0", description="ECM CONFIGURE_OBIEE")
    ecm_prop_fsdf_upload_model: Optional[str] = Field(default="0", description="ECM FSDF_UPLOAD_MODEL")
    ecm_prop_amlsource: Optional[str] = Field(default="OFSATOMIC", description="ECM AMLSOURCE")
    ecm_prop_kycsource: Optional[str] = Field(default="OFSATOMIC", description="ECM KYCSOURCE")
    ecm_prop_cssource: Optional[str] = Field(default="OFSATOMIC", description="ECM CSSOURCE")
    ecm_prop_externalsystemsource: Optional[str] = Field(default="OFSATOMIC", description="ECM EXTERNALSYSTEMSOURCE")
    ecm_prop_tbamlsource: Optional[str] = Field(default="OFSATOMIC", description="ECM TBAMLSOURCE")
    ecm_prop_fatcasource: Optional[str] = Field(default="OFSATOMIC", description="ECM FATCASOURCE")
    ecm_prop_ofsecm_datasrcname: Optional[str] = Field(default="FCCMINFO", description="ECM OFSECM_DATASRCNAME")
    ecm_prop_comn_gateway_ds: Optional[str] = Field(default="FCCMINFO", description="ECM COMN_GATWAY_DS")
    ecm_prop_t2jurl: Optional[str] = Field(default=None, description="ECM T2JURL")
    ecm_prop_j2turl: Optional[str] = Field(default=None, description="ECM J2TURL")
    ecm_prop_cmngtwyurl: Optional[str] = Field(default=None, description="ECM CMNGTWYURL")
    ecm_prop_bdurl: Optional[str] = Field(default=None, description="ECM BDURL")
    ecm_prop_ofss_wls_url: Optional[str] = Field(default=None, description="ECM OFSS_WLS_URL")
    ecm_prop_aai_url: Optional[str] = Field(default=None, description="ECM AAI_URL")
    ecm_prop_cs_url: Optional[str] = Field(default=None, description="ECM CS_URL")
    ecm_prop_arachnys_nns_service_url: Optional[str] = Field(default=None, description="ECM ARACHNYS_NNS_SERVICE_URL")

    # ECM OFSAAI_InstallConfig.xml fields (inherited from BD Pack structure)
    ecm_aai_webappservertype: Optional[str] = Field(default="3", description="ECM WEBAPPSERVERTYPE")
    ecm_aai_dbserver_ip: Optional[str] = Field(default=None, description="ECM DBSERVER_IP")
    ecm_aai_oracle_service_name: Optional[str] = Field(default=None, description="ECM ORACLE_SERVICE_NAME")
    ecm_aai_abs_driver_path: Optional[str] = Field(default=None, description="ECM ABS_DRIVER_PATH")
    ecm_aai_olap_server_implementation: Optional[str] = Field(default="0", description="ECM OLAP_SERVER_IMPLEMENTATION")
    ecm_aai_sftp_enable: Optional[str] = Field(default="1", description="ECM SFTP_ENABLE")
    ecm_aai_file_transfer_port: Optional[str] = Field(default="22", description="ECM FILE_TRANSFER_PORT")
    ecm_aai_javaport: Optional[str] = Field(default="9999", description="ECM JAVAPORT")
    ecm_aai_nativeport: Optional[str] = Field(default="6666", description="ECM NATIVEPORT")
    ecm_aai_agentport: Optional[str] = Field(default="6510", description="ECM AGENTPORT")
    ecm_aai_iccport: Optional[str] = Field(default="6507", description="ECM ICCPORT")
    ecm_aai_iccnativeport: Optional[str] = Field(default="6509", description="ECM ICCNATIVEPORT")
    ecm_aai_olapport: Optional[str] = Field(default="10101", description="ECM OLAPPORT")
    ecm_aai_msgport: Optional[str] = Field(default="6501", description="ECM MSGPORT")
    ecm_aai_routerport: Optional[str] = Field(default="6502", description="ECM ROUTERPORT")
    ecm_aai_amport: Optional[str] = Field(default="6506", description="ECM AMPORT")
    ecm_aai_https_enable: Optional[str] = Field(default="1", description="ECM HTTPS_ENABLE")
    ecm_aai_web_server_ip: Optional[str] = Field(default=None, description="ECM WEB_SERVER_IP")
    ecm_aai_web_server_port: Optional[str] = Field(default="7002", description="ECM WEB_SERVER_PORT")
    ecm_aai_context_name: Optional[str] = Field(default="FICHOME", description="ECM CONTEXT_NAME")
    ecm_aai_webapp_context_path: Optional[str] = Field(default=None, description="ECM WEBAPP_CONTEXT_PATH")
    ecm_aai_web_local_path: Optional[str] = Field(default="/u01/OFSAA/FTPSHARE", description="ECM WEB_LOCAL_PATH")
    ecm_aai_weblogic_domain_home: Optional[str] = Field(default=None, description="ECM WEBLOGIC_DOMAIN_HOME")
    ecm_aai_ftspshare_path: Optional[str] = Field(default="/u01/OFSAA/FTPSHARE", description="ECM OFSAAI_FTPSHARE_PATH")
    ecm_aai_sftp_user_id: Optional[str] = Field(default="oracle", description="ECM OFSAAI_SFTP_USER_ID")

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
