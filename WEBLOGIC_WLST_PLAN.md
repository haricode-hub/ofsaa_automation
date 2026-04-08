# WebLogic WLST Datasource & Deployment Integration Plan

## Overview

After FICHOME deployment (17 steps), add two optional post-deployment operations:
1. **Create WebLogic Datasources** — Run WLST scripts to create 5 JDBC datasources
2. **Deploy FICHOME to WebLogic** — Run WLST script to deploy FICHOME EAR

Both are controlled by **checkboxes** in the FICHOME deployment form.

---

## Dynamic Fields & Derivation

### Shared WebLogic Connection Fields (UI Input)

| Field | UI Label | Example | Notes |
|-------|----------|---------|-------|
| `wls_admin_url` | Admin URL | `t3://192.168.0.39:7001` | User enters WebLogic admin URL |
| `wls_username` | Username | `weblogic` | WebLogic admin username |
| `wls_password` | Password | `Welcome1` | WebLogic admin password |

### WLST Path — Derived (NO separate field)

```
WLST_PATH = {WEBLOGIC_DOMAIN_HOME}/../../../oracle_common/common/bin/wlst.sh
```

- `WEBLOGIC_DOMAIN_HOME` is already extracted in FICHOME Step 2 from `OFSAAI_InstallConfig.xml`
- Example: if `WEBLOGIC_DOMAIN_HOME = /u01/Oracle/Middleware/Oracle_Home/user_projects/domains/DEMO_OFSAA_DOMAIN`
- Then `WLST_PATH = /u01/Oracle/Middleware/Oracle_Home/oracle_common/common/bin/wlst.sh`
- Backend will resolve by walking up from domain home to find `wlst.sh`
- Fallback: try `$ORACLE_HOME/oracle_common/common/bin/wlst.sh` and common known paths

### Database Fields for Datasources — Derived from existing form fields

| DS Field | Derived From | Example |
|----------|-------------|---------|
| `dbUrl` | `schema_jdbc_host`, `schema_jdbc_port`, `schema_jdbc_service` | `jdbc:oracle:thin:@//192.168.0.48:1521/OFSAAPDB2` |
| `dbUser` (for ATOMIC DS) | `atomic_schema_name` from form | `OFSATOMIC1` |
| `dbUser` (for CONFIG DS) | `config_schema_name` from form | `OFSCONFIG1` |
| `dbPassword` | `schema_default_password` from form | `oracle123` |

### Deployment Fields (UI Input, shown when "Deploy to WebLogic" checked)

| Field | UI Label | Example |
|-------|----------|---------|
| `wls_app_name` | Application Name | `FICHOME-2` |
| `wls_app_path` | EAR Path | `/u01/app/.../applications/FICHOME1.ear` |
| `wls_deploy_targets` | Deploy Targets | `MS1` |

---

## 5 Datasources — User Selects Which to Create (Checkboxes)

Each datasource is a **checkbox**. User picks which ones to create.

| # | DS Name | JNDI Name | DB User Source | Default Targets |
|---|---------|-----------|---------------|-----------------|
| 1 | FCCMINFO | jdbc/FCCMINFO | `atomic_schema_name` | `MS1` |
| 2 | FCCMINFOCNF | jdbc/FCCMINFOCNF | `config_schema_name` | `AdminServer, MS1` |
| 3 | FICMASTER | jdbc/FICMASTER | `config_schema_name` | `MS1` |
| 4 | FICOME | jdbc/FICOME | `atomic_schema_name` | `AdminServer, MS1` |
| 5 | MINER | jdbc/MINER | `atomic_schema_name` | `AdminServer, MS1` |

**Targets field per datasource** — Editable text field, pre-populated with defaults above.

---

## Implementation — Layer by Layer

### Layer 1: Schema (`backend/schemas/installation.py`)

Add fields to `FichomeDeploymentRequest`:

```python
# --- WebLogic Post-Deployment ---
create_datasources: bool = Field(default=False, description="Create WebLogic JDBC datasources via WLST")
deploy_to_weblogic: bool = Field(default=False, description="Deploy FICHOME EAR to WebLogic via WLST")

# WebLogic admin connection (required if either checkbox is True)
wls_admin_url: Optional[str] = Field(default=None, description="WebLogic admin URL e.g. t3://host:7001")
wls_username: Optional[str] = Field(default=None, description="WebLogic admin username")
wls_password: Optional[str] = Field(default=None, description="WebLogic admin password")

# Datasource DB password (derived from schema_default_password but editable)
wls_ds_db_password: Optional[str] = Field(default=None, description="DB password for JDBC datasources")

# Datasource selection — which of the 5 to create
wls_ds_fccminfo: bool = Field(default=False, description="Create FCCMINFO datasource")
wls_ds_fccminfocnf: bool = Field(default=False, description="Create FCCMINFOCNF datasource")
wls_ds_ficmaster: bool = Field(default=False, description="Create FICMASTER datasource")
wls_ds_ficome: bool = Field(default=False, description="Create FICOME datasource")
wls_ds_miner: bool = Field(default=False, description="Create MINER datasource")

# Targets per datasource (editable, comma-separated)
wls_ds_fccminfo_targets: Optional[str] = Field(default="MS1")
wls_ds_fccminfocnf_targets: Optional[str] = Field(default="AdminServer,MS1")
wls_ds_ficmaster_targets: Optional[str] = Field(default="MS1")
wls_ds_ficome_targets: Optional[str] = Field(default="AdminServer,MS1")
wls_ds_miner_targets: Optional[str] = Field(default="AdminServer,MS1")

# Deployment fields (required if deploy_to_weblogic is True)
wls_app_name: Optional[str] = Field(default=None, description="WebLogic application name e.g. FICHOME-2")
wls_app_path: Optional[str] = Field(default=None, description="EAR file path on server")
wls_deploy_targets: Optional[str] = Field(default="MS1", description="Deployment targets")
```

---

### Layer 2: Installer (`backend/services/installer.py`)

Add 3 new methods to `InstallerService`:

#### Method 1: `_resolve_wlst_path(host, username, password, weblogic_domain_home) -> str`

```
Strategy:
1. Parse WEBLOGIC_DOMAIN_HOME to find Oracle Middleware home
   e.g. /u01/Oracle/Middleware/Oracle_Home/user_projects/domains/DOMAIN
   -> Oracle home = /u01/Oracle/Middleware/Oracle_Home
2. Try: {oracle_home}/oracle_common/common/bin/wlst.sh
3. Fallback: find / -name wlst.sh -path "*/oracle_common/*" 2>/dev/null | head -1
4. Return resolved path or raise error
```

#### Method 2: `create_weblogic_datasource(host, ..., ds_name, jndi_name, db_user, targets, ...) -> dict`

```
Strategy:
1. Build WLST .py script content from TEMPLATE (the full FCCMINFO.py pattern)
2. Replace dynamic values:
   - adminUrl, username, password (WebLogic)
   - dsName, jndiName (datasource identity)
   - dbUrl, dbUser, dbPassword, driver (DB connection)
   - targets (server list)
3. Upload script to /tmp/wlst_ds_{dsName}.py via SSH
4. Run: wlst.sh /tmp/wlst_ds_{dsName}.py
5. Stream output to WebSocket
6. Cleanup temp script
7. Return success/failure with logs
```

**WLST Template** — Embedded as a Python string constant (the full FCCMINFO.py content with placeholders):
```python
WLST_DATASOURCE_TEMPLATE = '''
# ================================
# WebLogic WLST Datasource Script
# ================================
from java.lang import String
import jarray
from java.lang import Thread
from javax.management import ObjectName
import traceback

adminUrl  = '{admin_url}'
username  = '{wls_username}'
password  = '{wls_password}'
dsName   = '{ds_name}'
jndiName = '{jndi_name}'
dbUrl      = '{db_url}'
dbUser     = '{db_user}'
dbPassword = '{db_password}'
driver     = 'oracle.jdbc.OracleDriver'
targets = {targets}

connect(username, password, adminUrl)
edit()
startEdit()
... [full script from FCCMINFO.py] ...
'''
```

#### Method 3: `deploy_fichome_to_weblogic(host, ..., app_name, app_path, targets, ...) -> dict`

```
Strategy:
1. Build WLST deployment .py script from TEMPLATE (testdeployment.py pattern)
2. Replace dynamic values
3. Upload to /tmp/wlst_deploy.py
4. Run: wlst.sh /tmp/wlst_deploy.py
5. Stream output
6. Cleanup
7. Return success/failure
```

**WLST Deploy Template**:
```python
WLST_DEPLOY_TEMPLATE = '''
connect('{wls_username}', '{wls_password}', '{admin_url}')
edit()
startEdit()
deploy(appName='{app_name}', path='{app_path}', targets='{targets}')
save()
activate()
domainRuntime()
... [verification from FICOME.py] ...
disconnect()
exit()
'''
```

---

### Layer 3: Service Layer (`backend/services/installation_service.py`)

Add thin wrapper methods:

```python
async def create_weblogic_datasource(self, ...) -> dict:
    return await self.installer.create_weblogic_datasource(...)

async def deploy_fichome_to_weblogic(self, ...) -> dict:
    return await self.installer.deploy_fichome_to_weblogic(...)
```

---

### Layer 4: Router (`backend/routers/installation.py`)

In `execute_fichome_deployment()`, after 17-step `deploy_fichome()` succeeds:

```python
# Calculate total steps dynamically
total_steps = 17
if request.create_datasources:
    selected_ds = [name for name, enabled in [
        ("FCCMINFO", request.wls_ds_fccminfo),
        ("FCCMINFOCNF", request.wls_ds_fccminfocnf),
        ("FICMASTER", request.wls_ds_ficmaster),
        ("FICOME", request.wls_ds_ficome),
        ("MINER", request.wls_ds_miner),
    ] if enabled]
    total_steps += len(selected_ds)  # 1 step per datasource
if request.deploy_to_weblogic:
    total_steps += 1  # 1 step for deployment

# ... after step 17 success ...

step_counter = 17

if request.create_datasources:
    # Resolve WLST path from weblogic_domain_home
    wlst_path = await installation_service.installer._resolve_wlst_path(...)
    
    # Build dbUrl from existing request fields
    db_url = f"jdbc:oracle:thin:@//{request.db_jdbc_host}:{request.db_jdbc_port}/{request.db_jdbc_service}"
    
    # Define datasource configs
    DS_CONFIGS = [
        ("FCCMINFO",    "jdbc/FCCMINFO",    request.atomic_schema_name, request.wls_ds_fccminfo_targets, request.wls_ds_fccminfo),
        ("FCCMINFOCNF", "jdbc/FCCMINFOCNF", request.config_schema_name, request.wls_ds_fccminfocnf_targets, request.wls_ds_fccminfocnf),
        ("FICMASTER",   "jdbc/FICMASTER",   request.config_schema_name, request.wls_ds_ficmaster_targets, request.wls_ds_ficmaster),
        ("FICOME",      "jdbc/FICOME",      request.atomic_schema_name, request.wls_ds_ficome_targets, request.wls_ds_ficome),
        ("MINER",       "jdbc/MINER",       request.atomic_schema_name, request.wls_ds_miner_targets, request.wls_ds_miner),
    ]
    
    for ds_name, jndi_name, db_user, targets, enabled in DS_CONFIGS:
        if not enabled:
            continue
        step_counter += 1
        await websocket_send(task_id, f"[FICHOME] STEP {step_counter}: Creating datasource {ds_name}")
        
        result = await installation_service.installer.create_weblogic_datasource(
            host=request.host, username=request.username, password=request.password,
            wlst_path=wlst_path,
            admin_url=request.wls_admin_url,
            wls_username=request.wls_username,
            wls_password=request.wls_password,
            ds_name=ds_name, jndi_name=jndi_name,
            db_url=db_url, db_user=db_user,
            db_password=request.wls_ds_db_password,
            targets=targets,
            on_output_callback=on_output_callback,
        )
        # ... handle result ...

if request.deploy_to_weblogic:
    step_counter += 1
    await websocket_send(task_id, f"[FICHOME] STEP {step_counter}: Deploying FICHOME to WebLogic")
    
    result = await installation_service.installer.deploy_fichome_to_weblogic(
        host=request.host, username=request.username, password=request.password,
        wlst_path=wlst_path,
        admin_url=request.wls_admin_url,
        wls_username=request.wls_username,
        wls_password=request.wls_password,
        app_name=request.wls_app_name,
        app_path=request.wls_app_path,
        targets=request.wls_deploy_targets,
        on_output_callback=on_output_callback,
    )
    # ... handle result ...
```

---

### Layer 5: Frontend (`frontend/src/components/InstallationForm.tsx`)

#### Form Data Interface — Add fields

```typescript
// In FormData interface:
create_datasources: boolean
deploy_to_weblogic: boolean
wls_admin_url: string
wls_username: string
wls_password: string
wls_ds_db_password: string
wls_ds_fccminfo: boolean
wls_ds_fccminfocnf: boolean
wls_ds_ficmaster: boolean
wls_ds_ficome: boolean
wls_ds_miner: boolean
wls_ds_fccminfo_targets: string
wls_ds_fccminfocnf_targets: string
wls_ds_ficmaster_targets: string
wls_ds_ficome_targets: string
wls_ds_miner_targets: string
wls_app_name: string
wls_app_path: string
wls_deploy_targets: string
```

#### UI Section — Rendered after FICHOME deployment section

```
┌─────────────────────────────────────────────────────────┐
│ ☐ WebLogic Post-Deployment                              │
│                                                         │
│ ┌─ WebLogic Connection ──────────────────────────────┐  │
│ │ Admin URL:  [t3://192.168.0.39:7001        ]       │  │
│ │ Username:   [weblogic                       ]       │  │
│ │ Password:   [••••••••                       ]       │  │
│ └────────────────────────────────────────────────────┘  │
│                                                         │
│ ☐ Create Datasources                                    │
│   DB Password: [oracle123                      ]        │
│   ┌──────────────────────────────────────────────┐      │
│   │ ☑ FCCMINFO     Targets: [MS1             ]  │      │
│   │ ☑ FCCMINFOCNF  Targets: [AdminServer,MS1 ]  │      │
│   │ ☑ FICMASTER    Targets: [MS1             ]  │      │
│   │ ☐ FICOME       Targets: [AdminServer,MS1 ]  │      │
│   │ ☐ MINER        Targets: [AdminServer,MS1 ]  │      │
│   └──────────────────────────────────────────────┘      │
│                                                         │
│ ☐ Deploy to WebLogic                                    │
│   App Name:    [FICHOME-2                      ]        │
│   EAR Path:    [/u01/.../FICHOME1.ear          ]        │
│   Targets:     [MS1                            ]        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### Auto-derivation Logic

- When `create_datasources` is checked:
  - `dbUrl` built from existing `schema_jdbc_host:schema_jdbc_port/schema_jdbc_service`
  - FCCMINFO/FICOME/MINER `dbUser` = `atomic_schema_name`
  - FCCMINFOCNF/FICMASTER `dbUser` = `config_schema_name`
  - `dbPassword` = `schema_default_password` (pre-populated, editable)

#### Submission Logic

The FICHOME deployment form already calls `/api/installation/deploy-fichome`. The new fields are sent as additional fields in the same request. Backend handles them after step 17.

---

## Execution Flow on Remote Server

```
Step 17 completes (checkofsaa.sh) ✓
         │
         ▼
[If create_datasources = true]
    │
    ├─ Resolve WLST path from WEBLOGIC_DOMAIN_HOME
    │    e.g. /u01/.../oracle_common/common/bin/wlst.sh
    │
    ├─ For each selected DS (FCCMINFO, FCCMINFOCNF, ...):
    │    1. Generate WLST .py from template (inject dynamic values)
    │    2. Upload to /tmp/wlst_ds_{name}.py on target via SSH
    │    3. Run: {wlst_path} /tmp/wlst_ds_{name}.py
    │    4. Stream stdout/stderr to WebSocket
    │    5. Delete /tmp/wlst_ds_{name}.py
    │    6. Report success/failure per DS
    │
[If deploy_to_weblogic = true]
    │
    ├─ Generate WLST deploy .py from template
    ├─ Upload to /tmp/wlst_deploy.py
    ├─ Run: {wlst_path} /tmp/wlst_deploy.py
    ├─ Stream output
    ├─ Verify deployment state
    └─ Cleanup
```

---

## Security Notes

- WebLogic credentials (`wls_password`) stored only in-memory during request, never logged
- WLST scripts written to `/tmp/` with restricted permissions, deleted after execution  
- DB passwords in WLST scripts use `set('Password', ...)` — WebLogic encrypts at rest
- `shell_escape()` used for all dynamic values to prevent command injection
- Template uses placeholder substitution (not f-strings on user input)

---

## Files to Modify

| File | Changes |
|------|---------|
| `backend/schemas/installation.py` | Add 18 fields to `FichomeDeploymentRequest` |
| `backend/services/installer.py` | Add `_resolve_wlst_path()`, `create_weblogic_datasource()`, `deploy_fichome_to_weblogic()`, 2 template constants |
| `backend/services/installation_service.py` | Add 2 thin wrapper methods |
| `backend/routers/installation.py` | Extend `execute_fichome_deployment()` with post-step-17 logic, dynamic total_steps |
| `frontend/src/components/InstallationForm.tsx` | Add form fields, checkboxes, WebLogic section UI |
| `frontend/src/app/logs/[taskId]/page.tsx` | Add dynamic FICHOME step names for DS/deploy steps |

---

## Step Summary (Dynamic Total)

| Steps | What | When |
|-------|------|------|
| 1–17 | Existing FICHOME deployment | Always |
| 18–22 | Create datasources (up to 5) | If `create_datasources` checked + each DS selected |
| 23 | Deploy FICHOME EAR to WebLogic | If `deploy_to_weblogic` checked |

Total steps = 17 + (number of selected datasources) + (1 if deploy checked)
