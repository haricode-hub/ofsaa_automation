# AGENTS.md

## Purpose
This repository implements **OFSAA Installation Automation** — a full-stack web application that automates Oracle Financial Services (OFSAA) installation, configuration, and WebLogic deployment on remote Linux servers via SSH.

**Modules**: BD Pack (baseline), ECM Pack, SANC Pack, FICHOME Deployment, WebLogic Datasource/App Deployment.

---

## Technology Stack

| Layer | Technology | Details |
|-------|-----------|---------|
| **Backend** | FastAPI (Python 3.8+) | Async, Paramiko SSH, WebSocket streaming |
| **Frontend** | Next.js 15 + React 19 + TypeScript | Tailwind CSS, Framer Motion, Heroicons |
| **Communication** | WebSocket `/ws/{task_id}` | Real-time logs, status, interactive prompts |
| **Package Mgmt** | `uv` (Python), `npm` (Node) | Backend: `uv sync && uv run uvicorn`, Frontend: `npm run dev` |
| **Deployment** | PM2 via `ecosystem.config.js` | Both backend and frontend managed by PM2 |
| **SSH** | Paramiko | Interactive commands, keep-alive, prompt detection |
| **Logging** | Disk-persistent `/tmp/ofsaa_logs/{task_id}.log` | Full recovery on reconnect/restart |

---

## High-Level Architecture

```
Frontend Form Submit -> POST /api/installation/start (or /deploy-fichome, /create-datasources)
                     -> Backend creates task_id, spawns async process
                     -> Returns { task_id } immediately
                     -> Frontend navigates to /logs/{taskId}
                     -> Opens WebSocket /ws/{task_id}
                     -> Backend sends historical logs on connect (disk recovery)
                     -> Live streaming: output, status, progress, prompts
                     -> Interactive prompts: user responds via WebSocket
                     -> Completion: status=completed or status=failed
```

---

## Project Structure

```
backend/
  main.py                         # FastAPI app, WebSocket /ws/{task_id}, CORS
  pyproject.toml                  # Python deps (fastapi, paramiko, etc.)
  .env.example                    # Environment variable template
  core/
    config.py                     # Env vars, step names, default paths
    logging.py                    # Logger setup, timing context manager
    websocket_manager.py          # WS connection manager, input queues
  routers/
    installation.py               # All API endpoints + async task orchestration
  schemas/
    installation.py               # Pydantic models (Request/Response/Status)
  services/
    installation_service.py       # Orchestrator - delegates to all sub-services
    installer.py                  # Core: Git ops, XML patching, script execution,
                                  #   BD/ECM/SANC modules, FICHOME deploy, WLST
    ssh_service.py                # Paramiko SSH wrapper (exec, interactive, keepalive)
    recovery_service.py           # Backup/restore, schema drop, failure cleanup
    log_persistence.py            # Disk-based log persistence per task
    validation.py                 # Pre-checks (user, group, dir, file, package)
    oracle_user_setup.py          # Create oracle user + oinstall group
    mount_point.py                # Create /u01 mount point
    packages.py                   # Install ksh, git, unzip
    profile.py                    # Create/update /home/oracle/.profile
    java.py                       # Java installation from repo
    oracle_client.py              # Oracle client detection + profile update
    utils.py                      # shell_escape(), sed_escape()

frontend/
  package.json                    # Node deps (next, react, tailwind, framer-motion)
  src/
    app/
      layout.tsx                  # Root layout ("OFSAA Installation Portal")
      page.tsx                    # Home - tabbed: Installation | Deployment
      globals.css                 # Tailwind globals + custom theme
      logs/[taskId]/page.tsx      # Real-time log viewer with step tracking
    components/
      InstallationForm.tsx        # BD + ECM + SANC installation form (~800 lines)
      DeploymentForm.tsx          # EAR + Datasources + App Deploy form (~500 lines)
      DatasourceForm.tsx          # Standalone datasource creation form
      EcmPackForm.tsx             # ECM config fields (~500 lines)
      EcmPackPage.tsx             # ECM wrapper with BD->ECM field sync
      EcmPackPreview.tsx          # ECM default.properties preview/download
      SancPackForm.tsx            # SANC config fields (~500 lines)
      SancPackPage.tsx            # SANC wrapper with BD->SANC field sync
      OracleClientTerraformForm.tsx  # Oracle Client via Terraform
      BackgroundMatrix.tsx        # Animated dot matrix background
    lib/
      api.ts                      # getApiUrl(), getWebSocketUrl()
```

---

## API Endpoints

| Method | Path | Purpose | Request Schema |
|--------|------|---------|---------------|
| POST | `/api/installation/start` | Start BD/ECM/SANC installation | `InstallationRequest` |
| GET | `/api/installation/status/{task_id}` | Get task status/progress | - |
| GET | `/api/installation/tasks` | List all tasks | - |
| GET | `/api/installation/logs/{task_id}/full` | Full log download | - |
| GET | `/api/installation/logs/{task_id}/tail` | Last N log lines | - |
| POST | `/api/installation/test-connection` | Test SSH connectivity | `{host, username, password}` |
| GET | `/api/installation/rollback` | Get cached request for retry | - |
| GET | `/api/installation/checkpoint` | Get BD Pack checkpoint status | - |
| DELETE | `/api/installation/checkpoint` | Clear BD Pack checkpoint | - |
| POST | `/api/installation/deploy-fichome` | EAR build + datasources + app deploy | `FichomeDeploymentRequest` |
| GET | `/api/installation/deploy-fichome/status/{task_id}` | Deployment task status | - |
| POST | `/api/installation/create-datasources` | Create WebLogic datasources | `DatasourceCreationRequest` |
| GET | `/api/installation/create-datasources/status/{task_id}` | DS creation status | - |
| WS | `/ws/{task_id}` | Real-time logs, status, prompts | - |

---

## Module Details

### BD Pack (Baseline - Do Not Break)

**Flag**: `install_bdpack: bool`
**Kit Location**: `/u01/BD_Installer_Kit/OFS_BD_PACK`

**10-Step Installation**:
| Step | Name | Progress |
|------|------|----------|
| 1 | Creating oracle user and oinstall group | 10% |
| 2 | Creating mount point /u01 | 20% |
| 3 | Installing KSH and git | 30% |
| 4 | Creating .profile file | 40% |
| 5 | Installing Java and updating profile | 50% |
| 6 | Creating OFSAA directory structure | 60% |
| 7 | Checking Oracle client and updating profile | 70% |
| 8 | Setting up OFSAA installer and running environment check | 80% |
| 9 | Applying config XMLs/properties and running osc.sh | 90% |
| 10 | Installing BD PACK with setup.sh SILENT | 100% |

**Config Files Patched**:
- `OFS_BD_SCHEMA_IN.xml` (schema_creator/conf/) via `_patch_ofs_bd_schema_in_repo()`
- `OFS_BD_PACK.xml` (conf/) via `_patch_ofs_bd_pack_xml_repo()`
- `default.properties` (OFS_AML/conf/) via `_patch_default_properties_repo()`
- `OFSAAI_InstallConfig.xml` (OFS_AAI/conf/) via `_patch_ofsaai_install_config_repo()`

---

### ECM Pack (Implemented)

**Flag**: `install_ecm: bool`
**Kit Location**: `/u01/ECM_Installer_Kit/OFS_ECM_PACK`

**4-Step Installation** (runs after BD Pack):
1. Downloading and extracting ECM installer kit (82%)
2. Setting ECM kit permissions (85%)
3. Applying ECM configuration files (88%)
4. Running osc.sh (92%) + setup.sh SILENT (96%)

**Config Files**: `OFS_ECM_SCHEMA_IN.xml`, `default.properties` (OFS_NGECM), `OFSAAI_InstallConfig.xml`
**Schema Fields**: Prefixed with `ecm_schema_*`, `ecm_prop_*`, `ecm_aai_*`

---

### SANC Pack (Implemented)

**Flag**: `install_sanc: bool`
**Kit Location**: `/u01/SANC_Installer_Kit/OFS_SANC_PACK`

**Same 4-step pattern as ECM** (runs after ECM if both selected)
**Extra Fields**: `cs_swiftinfo`, `tflt_swiftinfo`
**Schema Fields**: Prefixed with `sanc_schema_*`, `sanc_aai_*`

---

### FICHOME Deployment (EAR Creation & Exploding)

**Endpoint**: `POST /api/installation/deploy-fichome`
**Frontend**: `DeploymentForm.tsx`

**5-Step Workflow**:
1. Grant database privileges (ATOMIC + CONFIG schemas)
2. Run EAR creation script (backup -> ant.sh -> explode EAR/WAR)
3. Run startofsaa.sh
4. Run checkofsaa.sh
5. Combined WLST: create datasources + deploy FICHOME.ear (optional, single session)

---

### WebLogic Datasource + App Deployment

**Combined Method**: `installer.create_datasources_and_deploy_app()`

**How it works**:
1. Generates a single WLST Python script with all datasources from UI input
2. Wraps in bash script that auto-discovers wlst.sh:
   `find /u01 -name wlst.sh 2>/dev/null | grep -i wlserver | head -1`
3. SSHs to target, writes script, executes as oracle user
4. Single WebLogic session: connect -> delete+create each DS -> test pools -> undeploy+deploy app -> disconnect
5. Cleans up temp files

**Datasource Logic**: Delete existing -> Create new -> Set JNDI, driver, pool, targets -> Save & Activate -> Test pool
**App Deploy Logic**: Stop app (if running) -> Undeploy -> Deploy new -> Save & Activate

**Default Datasources** (from UI):
| DS Name | JNDI | DB User | Targets |
|---------|------|---------|---------|
| ANALYST | jdbc/ANALYST | OFSATOMIC | AdminServer, MS1 |
| FCCMINFO | jdbc/FCCMINFO | OFSATOMIC | MS1 |
| FCCMINFOCNF | jdbc/FCCMINFOCNF | OFSCONFIG | AdminServer, MS1 |
| FICMASTER | jdbc/FICMASTER | OFSCONFIG | MS1 |
| MINER | jdbc/MINER | OFSATOMIC | AdminServer, MS1 |

---

## Backup / Restore System

**Workflow (BD + ECM)**:
1. BD Pack installs (steps 1-10)
2. After BD success -> automatic backup: app tar + DB schema backup
3. ECM installs (steps 1-4)
4. If ECM fails -> automatic restore to BD state
5. User retries ECM with `resume_from_checkpoint: true`
6. After successful ECM -> checkpoint auto-cleared

**BD osc.sh Failure**: Kill Java -> Drop schemas/tablespaces via sqlplus -> Clear cache -> Full reinstall

**Backup Scripts** (Git-controlled): `<REPO_DIR>/backup_Restore/backup_ofs_schemas.sh`, `restore_ofs_schemas.sh`

**Key Fields**: `resume_from_checkpoint`, `db_sys_password`, `db_ssh_host/username/password`

---

## Persistent Logging

- **Write**: `LogPersistence.append_log()` -> `/tmp/ofsaa_logs/{task_id}.log`
- **Recovery**: Full history sent on WebSocket connect via `historical_logs` message
- **API**: `GET /logs/{task_id}/full` and `GET /logs/{task_id}/tail`
- **Guarantee**: No data loss on page refresh, backend restart, or network disconnect
- **Concurrency**: Per-task `asyncio.Lock`

---

## Frontend Architecture

### Home Page (`page.tsx`)
Tabbed: **Installation** (InstallationForm) | **Deployment** (DeploymentForm)
Dark glass-panel aesthetic with BackgroundMatrix animation.

### Log Viewer (`logs/[taskId]/page.tsx`)
- Left: step list with progress indicators
- Center: scrollable terminal output with auto-scroll
- Interactive prompts for osc.sh/setup.sh
- Status bar with color coding
- Download logs, auto-redirect on failure (120s countdown)

### Smart Auto-Population
- DB host/port/service -> rebuild all datasource JDBC URLs
- Schema names -> update datasource db_user fields
- Domain home -> auto-populate app path
- Password propagation across datasources
- BD Pack fields auto-sync to ECM/SANC sections

---

## Environment Variables

```bash
# Backend (.env)
ALLOWED_ORIGIN=http://192.168.0.166
OFSAA_REPO_URL=https://...
OFSAA_REPO_DIR=/u01/OFSAA_REPO
OFSAA_GIT_USERNAME=...
OFSAA_GIT_PASSWORD=...
OFSAA_INSTALLER_ZIP_NAME=...
OFSAA_JAVA_ARCHIVE_HINT=jdk-11
OFSAA_FAST_CONFIG_APPLY=1
OFSAA_ENABLE_CONFIG_PUSH=0

# Frontend (.env.local)
NEXT_PUBLIC_API_URL=http://192.168.0.165:8000
```

---

## Default Paths (Target Server)

| Path | Purpose |
|------|---------|
| `/u01/OFSAA/FICHOME` | FIC_HOME (OFSAA application root) |
| `/u01/jdk-11.0.16` | JAVA_HOME |
| `/u01/app/oracle/product/19.0.0/client_1` | ORACLE_HOME |
| `/u01/BD_Installer_Kit/OFS_BD_PACK` | BD Pack kit |
| `/u01/ECM_Installer_Kit/OFS_ECM_PACK` | ECM Pack kit |
| `/u01/SANC_Installer_Kit/OFS_SANC_PACK` | SANC Pack kit |
| `/u01/OFSAA/FICHOME/ficweb` | FICHOME.ear/war build |
| `/tmp/ofsaa_logs/{task_id}.log` | Persistent log files |
| `/home/oracle/.profile` | Oracle user profile |

---

## Startup Commands

```bash
# Backend
cd backend && uv sync && uv run python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend && npm install && npm run dev

# PM2 (Production)
pm2 start ecosystem.config.js
```

---

## Contract Rules (Critical)

1. **Backward Compatibility**: BD Pack payload must work without ECM/SANC fields
2. **Additive Only**: New fields must be `Optional` with defaults
3. **Module Isolation**: ECM/SANC must NOT modify BD Pack code paths
4. **Flag Guards**: Always check `if request.install_ecm:` before ECM operations
5. **Separate XML Handlers**: Dedicated `_patch_ofs_MODULE_*` methods per module
6. **Error Isolation**: Module failure must not corrupt previous module
7. **shell_escape()**: Use for ALL shell arguments
8. **Backup Scripts from Git**: Never create locally
9. **WLST idempotent**: Always delete-if-exists before create

---

## Key Code Patterns

### XML Patching (installer.py)
Resolve file in Git repo -> Read via SSH -> Patch content -> Write back if changed

### Script Execution (installer.py)
Source oracle profile -> Build inner command -> Wrap with su/sudo if not oracle -> execute_interactive_command with callbacks

### WLST Discovery
`find /u01 -name wlst.sh 2>/dev/null | grep -i wlserver | head -1`

### Combined WLST (create_datasources_and_deploy_app)
Build datasource defs from UI -> Generate WLST Python inline -> Wrap in bash -> SSH write+execute -> Stream output -> Cleanup

---

## Key Service Methods

### installer.py (52 async methods)
**BD**: download_and_extract_installer, set_permissions, apply_config_files_from_repo, run_osc_schema_creator, run_setup_silent, run_environment_check
**ECM**: download_and_extract_ecm_installer, set_ecm_permissions, apply_ecm_config_files_from_repo, run_ecm_osc_schema_creator, run_ecm_setup_silent
**SANC**: download_and_extract_sanc_installer, set_sanc_permissions, apply_sanc_config_files_from_repo, run_sanc_osc_schema_creator, run_sanc_setup_silent
**FICHOME**: deploy_fichome, grant_database_privileges, run_startofsaa_script, run_checkofsaa_script
**WebLogic**: deploy_weblogic_application, create_datasources_and_deploy_app, create_weblogic_datasource
**Internal**: _read_remote_file, _write_remote_file, _resolve_repo_*_file_path, _commit_and_push_repo_changes, _patch_ofs_*_repo

### recovery_service.py
cleanup_after_osc_failure, kill_java_processes, ensure_backup_restore_scripts, backup_application, backup_db_schemas, restore_application, restore_db_schemas, full_restore_to_bd_state, _drop_database_schema, _detect_oracle_home

---

## Extension Pattern for New Modules

1. **Schema** (schemas/installation.py): Add Optional fields with module prefix
2. **Installer** (services/installer.py): Add _patch_ofs_MODULE_*, run_MODULE_osc_*, run_MODULE_setup_*
3. **Service** (services/installation_service.py): Add wrapper methods
4. **Router** (routers/installation.py): Add after previous module, guarded by flag
5. **Frontend**: Create ModulePackForm.tsx, ModulePackPage.tsx, update InstallationForm.tsx

---

## Module Status

| Module | Backend | Frontend | Logging | Backup/Restore |
|--------|---------|----------|---------|---------------|
| BD Pack | Done | Done | Done | Done |
| ECM Pack | Done | Done | Done | Done |
| SANC Pack | Done | Done | Done | Done |
| FICHOME Deploy | Done | Done | Done | N/A |
| WebLogic DS + App | Done (combined single-session WLST) | Done | Done | N/A |
| Oracle Client Terraform | Done | Done | Done | N/A |
