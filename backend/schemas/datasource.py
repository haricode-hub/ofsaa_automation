from pydantic import BaseModel, Field
from typing import Optional, List


class DatasourceConfig(BaseModel):
    """Single WebLogic datasource definition"""
    ds_name: str = Field(..., description="Datasource name (e.g., FCCMINFOCNF)")
    jndi_name: str = Field(..., description="JNDI name (e.g., jdbc/FCCMINFOCNF)")
    db_url: str = Field(..., description="JDBC URL (e.g., jdbc:oracle:thin:@//host:1521/SID)")
    db_user: str = Field(..., description="Database username")
    db_password: str = Field(..., description="Database password")
    targets: List[str] = Field(..., description="Target servers (e.g., ['AdminServer', 'MS1'])")


class FichomeDeploymentRequest(BaseModel):
    """Schema for EAR Creation & Exploding request"""
    host: str = Field(..., description="Target host IP address or hostname")
    username: str = Field(..., description="SSH username (typically root)")
    password: str = Field(..., description="SSH password")

    # Database privilege grant parameters (STEP 1)
    db_sys_password: str = Field(..., description="Oracle SYS password for sqlplus connections")
    db_jdbc_host: Optional[str] = Field(default=None, description="Database host (defaults to target host if not provided)")
    db_jdbc_port: int = Field(default=1521, description="Database port")
    db_jdbc_service: str = Field(..., description="Database service name (e.g., FLEXPDB1)")

    # Schema names (determined by last installed module: SANC > ECM > BD)
    config_schema_name: str = Field(..., description="CONFIG schema name (from last installed module)")
    atomic_schema_name: str = Field(..., description="ATOMIC schema name (from last installed module)")

    # WebLogic domain (provided from UI)
    weblogic_domain_home: str = Field(..., description="WebLogic domain home path (e.g., /u01/Oracle/user_projects/domains/ofsaa_domain)")

    # Optional: Datasource creation (runs sequentially AFTER EAR completes)
    ds_enabled: bool = Field(default=False, description="Enable datasource creation after EAR deployment")
    admin_url: Optional[str] = Field(default=None, description="WebLogic admin URL (e.g., t3://192.168.0.39:7001)")
    weblogic_username: Optional[str] = Field(default=None, description="WebLogic admin username")
    weblogic_password: Optional[str] = Field(default=None, description="WebLogic admin password")
    wl_home: Optional[str] = Field(default=None, description="WL_HOME path for WLST")
    datasources: Optional[List[DatasourceConfig]] = Field(default=None, description="Datasources to create after EAR")

    # Optional: Application deployment to WebLogic (STEP 5)
    deploy_app_enabled: bool = Field(default=False, description="Enable WebLogic application deployment via WLST")
    deploy_app_path: Optional[str] = Field(default=None, description="Full path to FICHOME.ear file on target server")
    deploy_app_target_server: Optional[str] = Field(default=None, description="WebLogic target server name (e.g., MS1)")


class FichomeDeploymentResponse(BaseModel):
    """Schema for EAR Creation & Exploding response"""
    success: bool = Field(..., description="Whether deployment started successfully")
    task_id: str = Field(..., description="Unique task ID for tracking deployment progress")
    message: str = Field(..., description="Status message")
    estimated_duration: str = Field(default="15 minutes", description="Estimated duration")
    output: Optional[str] = None
    stderr: Optional[str] = None
    returncode: Optional[int] = None


class DatasourceCreationRequest(BaseModel):
    """Schema for WebLogic datasource creation request"""
    host: str = Field(..., description="Target app server IP (SSH)")
    username: str = Field(..., description="SSH username (typically root)")
    password: str = Field(..., description="SSH password")
    admin_url: str = Field(..., description="WebLogic admin URL (e.g., t3://192.168.0.39:7001)")
    weblogic_username: str = Field(..., description="WebLogic admin username")
    weblogic_password: str = Field(..., description="WebLogic admin password")
    wl_home: Optional[str] = Field(default=None, description="WL_HOME / WEBAPP_CONTEXT_PATH (e.g. /u01/Oracle/Middleware/Oracle_Home/wlserver)")
    datasources: List[DatasourceConfig] = Field(..., min_length=1, description="List of datasources to create")


class DatasourceCreationResponse(BaseModel):
    """Schema for WebLogic datasource creation response"""
    success: bool = Field(..., description="Whether creation started successfully")
    task_id: str = Field(..., description="Unique task ID for tracking progress")
    message: str = Field(..., description="Status message")
    total_datasources: int = Field(..., description="Number of datasources to create")
