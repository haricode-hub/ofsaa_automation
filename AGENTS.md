# AGENTS.md

## Purpose
This repository implements **OFSAA Installation Automation** with a stable **BD Pack module** as the baseline. When adding new modules (ECM, SANC, future packs), do not break existing BD Pack behavior, API contracts, or file layout.

---

## Architecture Overview

### Technology Stack
- **Backend**: FastAPI (Python 3.x) with async support
- **Frontend**: Next.js 14 + React + TypeScript + Tailwind CSS
- **Communication**: WebSocket for real-time logs and SSH via Paramiko
- **State Management**: In-memory task tracking with WebSocket broadcast

### High-Level Flow
```
Frontend Form Submit  ->  POST /api/installation/start
                      ->  Creates task_id, spawns async installation process
                      ->  WebSocket /ws/{task_id} streams logs/status
                      ->  10-step installation workflow executes
                      ->  Viewer at /logs/{task_id} displays progress
```

---

## Baseline Module: BD Pack (Do Not Break)

### Module Identity
- **Module name**: `BD Pack`
- **Backend entry API**: `/api/installation/*`
- **Module flag field**: `install_bdpack: bool`

### Key Files
| Layer | File | Responsibility |
|-------|------|----------------|
| Router | `backend/routers/installation.py` | API endpoints, task orchestration |
| Schema | `backend/schemas/installation.py` | Pydantic models for request/response |
| Orchestrator | `backend/services/installation_service.py` | Workflow step composition |
| Installer | `backend/services/installer.py` | Git clone, XML/properties patching, osc.sh, setup.sh |
| SSH | `backend/services/ssh_service.py` | Remote command execution |
| UI Form | `frontend/src/components/InstallationForm.tsx` | Main installation form |

### Installation Steps (10 Steps)
```python
STEP_NAMES = [
    "Creating oracle user and oinstall group",      # Step 1
    "Creating mount point /u01",                    # Step 2
    "Installing KSH and git",                       # Step 3
    "Creating .profile file",                       # Step 4
    "Installing Java and updating profile",         # Step 5
    "Creating OFSAA directory structure",           # Step 6
    "Checking Oracle client and updating profile",  # Step 7
    "Setting up OFSAA installer and running environment check", # Step 8
    "Applying config XMLs/properties and running osc.sh",       # Step 9
    "Installing BD PACK with /setup.sh SILENT",                 # Step 10
]
```

### Config Files Patched (BD Pack)
| File | Kit Location | Description |
|------|--------------|-------------|
| `OFS_BD_SCHEMA_IN.xml` | `schema_creator/conf/` | JDBC, schema names, tablespaces |
| `OFS_BD_PACK.xml` | `conf/` | Application enable flags |
| `default.properties` | `OFS_AML/conf/` | Silent installer properties |
| `OFSAAI_InstallConfig.xml` | `OFS_AAI/conf/` | Web server, ports, SFTP config |

---

## Current Code Structure

### Backend (`backend/`)
```
backend/
├── main.py                     # FastAPI app bootstrap, WebSocket endpoint
├── core/
│   ├── config.py               # Config class with env vars, step names
│   ├── logging.py              # Logging setup
│   └── websocket_manager.py    # WebSocket connection manager
├── routers/
│   └── installation.py         # API routes, task workflow orchestration
├── schemas/
│   └── installation.py         # Pydantic models (InstallationRequest, etc.)
└── services/
    ├── installation_service.py # Service composition (delegates to sub-services)
    ├── installer.py            # Git operations, XML patching, script execution
    ├── ssh_service.py          # SSH connection and command execution
    ├── recovery_service.py     # Cleanup after failures
    ├── validation.py           # Directory/file checks
    ├── java.py                 # Java installation
    ├── packages.py             # Package installation (ksh, git)
    ├── profile.py              # .profile creation/updates
    ├── mount_point.py          # /u01 mount point setup
    ├── oracle_client.py        # Oracle client detection
    ├── oracle_user_setup.py    # Oracle user/group creation
    └── utils.py                # Shell escape, helpers
```

### Frontend (`frontend/`)
```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Root layout
│   │   ├── page.tsx            # Home page (renders InstallationForm)
│   │   ├── globals.css         # Tailwind globals
│   │   └── logs/[taskId]/page.tsx  # Real-time log viewer
│   └── components/
│       ├── InstallationForm.tsx     # Main BD Pack installation form
│       ├── EcmPackForm.tsx          # ECM configuration form fields
│       ├── EcmPackPage.tsx          # ECM section wrapper
│       ├── EcmPackPreview.tsx       # ECM review component
│       └── BackgroundMatrix.tsx     # Background animation
```

---

## API Contract

### Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/installation/start` | Start installation, returns task_id |
| GET | `/api/installation/status/{task_id}` | Get task status/progress |
| GET | `/api/installation/tasks` | List all tasks |
| POST | `/api/installation/test-connection` | Test SSH connectivity |
| GET | `/api/installation/rollback` | Get cached request for retry |
| GET | `/api/installation/checkpoint` | Get BD Pack checkpoint status |
| DELETE | `/api/installation/checkpoint` | Clear BD Pack checkpoint |
| WS | `/ws/{task_id}` | Real-time logs/status/prompts |

### Checkpoint/Resume System
The system supports checkpointing after BD Pack completion for ECM resume capability:

**Workflow:**
1. If both BD Pack and ECM selected → BD Pack runs first, checkpoint saved after completion
2. ECM runs after BD Pack completes
3. If ECM fails → User can resume from checkpoint (BD Pack skipped, ECM restarts)
4. After successful ECM completion → Checkpoint auto-cleared

**Request Fields:**
```python
resume_from_checkpoint: bool = False  # Set to True to skip BD Pack and resume ECM
```

**Example - Resume ECM after failure:**
```json
{
  "host": "1.2.3.4",
  "username": "root",
  "password": "secret",
  "install_bdpack": true,
  "install_ecm": true,
  "resume_from_checkpoint": true,
  "ecm_schema_jdbc_host": "db.example.com"
}
```

### Request Schema (InstallationRequest) - Key Fields
```python
# Core connection
host: str                       # Target server IP
username: str                   # SSH username (typically root)
password: str                   # SSH password

# Profile variables
fic_home: Optional[str]         # FIC_HOME path
java_home: Optional[str]        # Custom JAVA_HOME
oracle_sid: Optional[str]       # Oracle SID

# Schema config (OFS_BD_SCHEMA_IN.xml)
schema_jdbc_host: Optional[str]
schema_jdbc_port: Optional[int]
schema_jdbc_service: Optional[str]
schema_default_password: Optional[str]
schema_config_schema_name: Optional[str]
schema_atomic_schema_name: Optional[str]
# ... more schema fields

# Pack apps (OFS_BD_PACK.xml)
pack_app_enable: Optional[Dict[str, bool]]  # APP_ID -> enabled

# Properties (default.properties)
prop_base_country: Optional[str]
prop_default_jurisdiction: Optional[str]
# ... more property fields

# OFSAAI config (OFSAAI_InstallConfig.xml)
aai_webappservertype: Optional[str]
aai_dbserver_ip: Optional[str]
# ... more AAI fields

# Module flags
installation_mode: Optional[str]  # "fresh" | "addon"
install_bdpack: bool              # BD Pack installation
install_ecm: bool                 # ECM module flag (prepared)
install_sanc: Optional[bool]      # SANC module flag (placeholder)
```

---

## ECM Module (IMPLEMENTED)

### Module Identity
- **Module name**: `ECM Pack`
- **Module flag field**: `install_ecm: bool`
- **Kit Location**: `/u01/INSTALLER_KIT/OFS_ECM_PACK`
- **Repo Folder**: `ECM_PACK`

### ECM Installation Flow (4 Steps - Runs After BD Pack)
```python
# ECM skips steps 1-8 (oracle user, mount, packages, profile, Java, directories, Oracle client, envCheck)
# ECM runs after BD Pack completes:

ECM_STEP_1: "Downloading and extracting ECM installer kit"  # Progress: 82%
ECM_STEP_2: "Setting ECM kit permissions"                    # Progress: 85%
ECM_STEP_3: "Applying ECM configuration files"               # Progress: 88%
ECM_STEP_4a: "Running ECM schema creator (osc.sh)"           # Progress: 92%
ECM_STEP_4b: "Running ECM setup (setup.sh SILENT)"           # Progress: 96%
```

### Config Files Patched (ECM)
| File | Kit Location | Description |
|------|--------------|-------------|
| `OFS_ECM_SCHEMA_IN.xml` | `schema_creator/conf/` | JDBC, schema names, tablespaces |
| `default.properties` | `OFS_NGECM/conf/` | Silent installer properties |
| `OFSAAI_InstallConfig.xml` | `OFS_AAI/conf/` | Web server, ports, SFTP config |

### ECM Backend Methods (installer.py)
```python
# Download/Extract
download_and_extract_ecm_installer()     # Extract to /u01/INSTALLER_KIT/OFS_ECM_PACK
set_ecm_permissions()                     # Set kit permissions

# Config Patching
apply_ecm_config_files_from_repo()        # Orchestrates all patches
_patch_ofs_ecm_schema_in_repo()           # Patch OFS_ECM_SCHEMA_IN.xml
_patch_ecm_default_properties_repo()      # Patch default.properties
_patch_ecm_ofsaai_install_config_repo()   # Patch OFSAAI_InstallConfig.xml

# Script Execution
run_ecm_osc_schema_creator()              # Run osc.sh -s
run_ecm_setup_silent()                    # Run setup.sh SILENT
```

### ECM Schema Fields (InstallationRequest)
```python
# OFS_ECM_SCHEMA_IN.xml params (prefix: ecm_schema_)
ecm_schema_jdbc_host, ecm_schema_jdbc_port, ecm_schema_jdbc_service
ecm_schema_host, ecm_schema_setup_env, ecm_schema_prefix_schema_name
ecm_schema_apply_same_for_all, ecm_schema_default_password
ecm_schema_datafile_dir, ecm_schema_config_schema_name, ecm_schema_atomic_schema_name

# default.properties params (prefix: ecm_prop_)
ecm_prop_base_country, ecm_prop_default_jurisdiction, ecm_prop_smtp_host
ecm_prop_web_service_user, ecm_prop_web_service_password, ecm_prop_nls_length_semantics
ecm_prop_analyst_data_source, ecm_prop_miner_data_source, ecm_prop_configure_obiee
ecm_prop_fsdf_upload_model, ecm_prop_amlsource, ecm_prop_kycsource, ecm_prop_cssource
ecm_prop_externalsystemsource, ecm_prop_tbamlsource, ecm_prop_fatcasource
ecm_prop_ofsecm_datasrcname, ecm_prop_comn_gateway_ds
ecm_prop_t2jurl, ecm_prop_j2turl, ecm_prop_cmngtwyurl, ecm_prop_bdurl
ecm_prop_ofss_wls_url, ecm_prop_aai_url, ecm_prop_cs_url, ecm_prop_arachnys_nns_service_url

# OFSAAI_InstallConfig.xml params (prefix: ecm_aai_)
ecm_aai_webappservertype, ecm_aai_dbserver_ip, ecm_aai_oracle_service_name
ecm_aai_abs_driver_path, ecm_aai_olap_server_implementation, ecm_aai_sftp_enable
# ... all port and path configs
```

### ECM Frontend Components
- `EcmPackForm.tsx` - Form fields for ECM configuration
- `EcmPackPage.tsx` - Wrapper that shows when `install_ecm` is enabled
- `EcmPackPreview.tsx` - Preview/review component
- `EcmFormData` interface - TypeScript types for all ECM fields

---

## Extension Pattern for New Modules (e.g., SANC)

Follow the ECM implementation pattern when adding new modules:

### Step 1: Schema Changes (`backend/schemas/installation.py`)
```python
# Add module-specific fields (prefix with module name)
sanc_schema_jdbc_host: Optional[str] = Field(default=None)
sanc_schema_jdbc_port: Optional[int] = Field(default=1521)
sanc_prop_some_field: Optional[str] = Field(default=None)
# ... etc
```

### Step 2: Installer Methods (`backend/services/installer.py`)
```python
# Add methods following ECM pattern:
async def download_and_extract_sanc_installer(...)
async def set_sanc_permissions(...)
async def apply_sanc_config_files_from_repo(...)
async def _patch_ofs_sanc_schema_in_repo(...)
async def run_sanc_osc_schema_creator(...)
async def run_sanc_setup_silent(...)
```

### Step 3: Service Layer (`backend/services/installation_service.py`)
```python
# Add wrapper methods delegating to installer
async def download_and_extract_sanc_installer(self, ...) -> dict:
    return await self.installer.download_and_extract_sanc_installer(...)
```

### Step 4: Router Changes (`backend/routers/installation.py`)
```python
# Add after BD Pack/ECM steps:
if request.install_sanc:
    await append_output(task_id, "[INFO] ===== SANC MODULE =====")
    # ... SANC installation steps
```

### Step 5: Frontend Components
```typescript
// Create SancPackForm.tsx, SancPackPage.tsx, SancPackPreview.tsx
// Update InstallationForm.tsx to include SANC section
```

---

## Contract Rules (Critical)

1. **Backward Compatibility**: Existing BD Pack payload must work without ECM fields
2. **Additive Only**: New fields should be Optional with defaults
3. **Module Isolation**: ECM logic should NOT modify BD Pack code paths
4. **Flag Guards**: Always check `if install_ecm:` before ECM operations
5. **Separate XML Handlers**: Create dedicated `_patch_ofs_ecm_*` methods
6. **Error Isolation**: ECM failure should not corrupt BD Pack installation

---

## Safety Checklist (ECM Implementation Complete)

- [x] BD Pack-only installation works with existing payload
- [x] `install_ecm: false` does not trigger any ECM code (guarded by `if request.install_ecm:`)
- [x] ECM fields have sensible defaults (all Optional with None defaults)
- [x] BD Pack XML patching unchanged (OFS_BD_*)
- [x] ECM XML patching uses separate methods (`_patch_ofs_ecm_*`)
- [x] WebSocket logs properly show ECM steps when enabled
- [x] Rollback endpoint still works for both modules
- [x] No changes to core infrastructure (SSH, WebSocket)

---

## Environment Variables

```bash
OFSAA_REPO_URL=<git_repo_url>     # Git repo with installer kits
OFSAA_REPO_DIR=/path/to/clone     # Clone location on target
OFSAA_GIT_USERNAME=<username>      # Git auth
OFSAA_GIT_PASSWORD=<password>      # Git auth
OFSAA_INSTALLER_ZIP_NAME=<name>    # Specific installer zip
OFSAA_JAVA_ARCHIVE_HINT=<hint>     # Java archive pattern
OFSAA_FAST_CONFIG_APPLY=1          # Skip git pull on config apply
OFSAA_ENABLE_CONFIG_PUSH=0         # Push config changes back to git
```

---

## Key Code Patterns

### XML Patching Pattern (installer.py)
```python
async def _patch_MODULENAME_xml_repo(self, host, username, password, *, repo_dir, **params) -> dict:
    logs: list[str] = []
    
    # 1. Find source file
    src_path = await self._resolve_repo_file_path(...)
    
    # 2. Read content
    read = await self._read_remote_file(host, username, password, src_path)
    original = read.get("content", "")
    
    # 3. Patch content
    patched = self._patch_MODULENAME_xml_content(original, **params)
    
    # 4. Write if changed
    if patched != original:
        await self._write_remote_file(host, username, password, src_path, patched)
        logs.append("[OK] Updated MODULENAME XML")
    
    return {"success": True, "logs": logs, "changed": patched != original}
```

### Script Execution Pattern (installer.py)
```python
async def run_module_script(self, host, username, password, on_output_callback, on_prompt_callback) -> dict:
    inner_cmd = "source /home/oracle/.profile; cd /path && ./script.sh"
    
    if username == "oracle":
        command = f"bash -lc {shell_escape(inner_cmd)}"
    else:
        command = f"sudo -u oracle bash -lc {shell_escape(inner_cmd)}"
    
    result = await self.ssh_service.execute_interactive_command(
        host, username, password, command,
        on_output_callback=on_output_callback,
        on_prompt_callback=on_prompt_callback,
        timeout=3600
    )
    return result
```

---

## Notes for Developers

- Prefer adding new helper functions over modifying shared code
- Use `shell_escape()` from utils.py for all shell arguments
- All XML patches should create timestamped backups
- Test ECM changes with `install_bdpack=True, install_ecm=True` (ECM runs after BD Pack)
- ECM module is fully implemented in backend
- Installation mode (fresh/addon) may affect ECM flow differently

---

## Module Status Summary

| Module | Status | Flag Field | Kit Location |
|--------|--------|------------|-------------|
| BD Pack | ✅ Implemented | `install_bdpack` | `/u01/installer_kit/OFS_BD_PACK` |
| ECM | ✅ Implemented | `install_ecm` | `/u01/INSTALLER_KIT/OFS_ECM_PACK` |
| SANC | ❌ Placeholder | `install_sanc` | TBD |
