# OFSAA Installation — Architecture & Flow

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                           │
│                                                                     │
│  InstallationForm.tsx ──POST /start──► gets task_id                 │
│  DeploymentForm.tsx   ──POST /deploy──► gets task_id                │
│                            │                                        │
│                            ▼                                        │
│  logs/[taskId]/page.tsx ◄──────── WebSocket /ws/{task_id}           │
│  (real-time log viewer)           (logs, status, prompts)           │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND                                  │
│                                                                     │
│  routers/installation.py                                            │
│    POST /api/installation/start ──► spawns async background task    │
│                                                                     │
│  main.py                                                            │
│    WebSocket /ws/{task_id} ──► streams logs + accepts prompt input  │
│                                                                     │
│  core/task_manager.py ◄──► core/log_persistence.py                  │
│    (status, progress)        (/tmp/ofsaa_logs/{task_id}.log)        │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SERVICE LAYER                                    │
│                                                                     │
│  installation_service.py (orchestrator)                             │
│    ├── oracle_user_setup.py   (Step 1)                              │
│    ├── mount_point.py         (Step 2)                              │
│    ├── packages.py            (Step 3)                              │
│    ├── profile.py             (Step 4)                              │
│    ├── java.py                (Steps 5, 6)                          │
│    ├── oracle_client.py       (Step 7)                              │
│    ├── installer.py           (Steps 8-10 + ECM + SANC)            │
│    └── recovery_service.py    (Cleanup, Backup, Restore)            │
│         ├── backup.py         (expdp)                               │
│         └── restore.py        (impdp)                               │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SSH LAYER (Paramiko)                             │
│                                                                     │
│  ssh_service.py                                                     │
│    execute_command()             ── simple commands                  │
│    execute_interactive_command() ── osc.sh / setup.sh prompts       │
│    test_connection()             ── SSH connectivity check           │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  REMOTE LINUX SERVER                                  │
│                                                                     │
│  /home/oracle/.profile          Oracle user profile                 │
│  /u01/OFSAA/FICHOME             OFSAA application root              │
│  /u01/BD_Installer_Kit          BD Pack kit                         │
│  /u01/ECM_Installer_Kit         ECM Pack kit                        │
│  /u01/SANC_Installer_Kit        SANC Pack kit                       │
│  /u01/jdk-11.0.16               JAVA_HOME                          │
│  Oracle DB                      OFSATOMIC + OFSCONFIG schemas       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Installation Flow — All Steps

### Phase 0: Pre-check

```
User fills form → POST /api/installation/start
  │
  ├── Generate task_id (UUID)
  ├── Register task in task_manager
  ├── Spawn async worker: run_installation_process()
  ├── Return { task_id } to frontend
  │
  └── Frontend opens WebSocket /ws/{task_id} for live logs
```

```
SSH Connect (3 retries, 1s delay between)
  ├── FAIL → status=failed, stop
  └── OK   → check resume_from_checkpoint
               ├── YES → validate checkpoint exists → skip to ECM
               └── NO  → continue to BD Pack
```

---

### Phase 1: BD Pack Installation (10 Steps)

**Guard**: `install_bdpack = true` AND `resume_from_checkpoint = false`

| Step | Progress | Action | Service File |
|------|----------|--------|--------------|
| Pre | — | Set `open_cursors=2000` on DB server | ssh_service.py |
| Pre | — | Clear filesystem caches (if BD-only run) | ssh_service.py |
| 1 | 10% | Create `oracle` user + `oinstall` group | oracle_user_setup.py |
| 2 | 20% | Create mount point `/u01` | mount_point.py |
| 3 | 30% | Install `ksh`, `git`, `unzip` packages | packages.py |
| 4 | 40% | Create `/home/oracle/.profile` | profile.py |
| 5 | 50% | Install Java (JDK) from Git repo + update `JAVA_HOME` in profile | java.py |
| 6 | 60% | Create OFSAA directory structure (`/u01/OFSAA/FICHOME`) | java.py |
| 7 | 70% | Detect Oracle client + update `ORACLE_HOME` in profile | oracle_client.py |
| 8 | 80% | Download BD kit from Git → set permissions → run `envCheck.sh` (interactive) | installer.py |
| 9 | 90% | Patch 4 config files in Git repo → run `osc.sh` schema creator (interactive) | installer.py |
| 10 | 100% | Run `setup.sh SILENT` (main BD install, interactive) | installer.py |

#### Step 9 Detail — Config Files Patched

| File | Location in Kit | Patch Method |
|------|----------------|--------------|
| `OFS_BD_SCHEMA_IN.xml` | `schema_creator/conf/` | `_patch_ofs_bd_schema_in_repo()` |
| `OFS_BD_PACK.xml` | `conf/` | `_patch_ofs_bd_pack_xml_repo()` |
| `default.properties` | `OFS_AML/conf/` | `_patch_default_properties_repo()` |
| `OFSAAI_InstallConfig.xml` | `OFS_AAI/conf/` | `_patch_ofsaai_install_config_repo()` |

#### After BD Success

```
BD Pack completes
  │
  ├── Save BD checkpoint in memory
  ├── Take application backup
  │     → tar -cvf /u01/OFSAA_BKP_BD_<timestamp>.tar.gz OFSAA
  ├── Take DB schema backup (if db_sys_password provided)
  │     → expdp OFSATOMIC,OFSCONFIG via backup.py
  └── Mark checkpoint as backup_taken = true
```

#### BD Failure Recovery

**osc.sh fails (Step 9):**
```
1. Kill all Java processes           → pkill -9 -f java
2. Remove /u01/OFSAA directory       → rm -rf /u01/OFSAA
3. Drop DB schemas + tablespaces     → sqlplus sys as sysdba
   - DROP USER OFSATOMIC CASCADE
   - DROP USER OFSCONFIG CASCADE
   - DROP TABLESPACE (46 tablespaces)
4. Clear system cache (app server)   → echo 2 > /proc/sys/vm/drop_caches
5. Clear system cache (DB server)    → same (if separate host)
→ status = failed
```

**setup.sh fails (Step 10):**
```
1. Kill all Java processes
→ status = failed
```

**Fresh install fails at Step 8+:**
```
Auto-cleanup triggered:
  → Kill Java + remove /u01/OFSAA
```

---

### Phase 2: ECM Pack Installation (4 Steps)

**Guard**: `install_ecm = true`

| Step | Action | Service File |
|------|--------|--------------|
| Pre | Verify BD backup exists (app tar + DB dump) | recovery_service.py |
| Pre | If missing → take fresh BD backup automatically | recovery_service.py |
| Pre | Clear filesystem caches | ssh_service.py |
| 1 | Download + extract ECM installer kit from Git | installer.py |
| 2 | Set ECM kit permissions (`chmod`) | installer.py |
| 3 | Patch ECM config files in Git repo | installer.py |
| 4a | Run ECM `osc.sh` schema creator (interactive) | installer.py |
| 4b | Run ECM `setup.sh SILENT` (interactive) | installer.py |

#### Step 3 Detail — ECM Config Files Patched

| File | Patch Method |
|------|--------------|
| `OFS_ECM_SCHEMA_IN.xml` | `_patch_ofs_ecm_schema_in_repo()` |
| `default.properties` (OFS_NGECM) | `_patch_ecm_default_properties_repo()` |
| `OFSAAI_InstallConfig.xml` | `_patch_ecm_ofsaai_install_config_repo()` |

#### After ECM Success

```
ECM Pack completes
  │
  ├── Take ECM application backup
  │     → tar -cvf /u01/OFSAA_BKP_ECM_<timestamp>.tar.gz OFSAA
  ├── Take ECM DB schema backup (expdp)
  └── Clear BD checkpoint (no longer needed)
```

#### ECM Failure Recovery (Auto-Restore to BD State)

```
ECM osc.sh or setup.sh fails
  │
  ├── 1. Kill all Java processes
  ├── 2. Restore application from BD backup
  │        → rm -rf /u01/OFSAA
  │        → tar -xvf /u01/OFSAA_BKP_BD_<timestamp>.tar.gz
  └── 3. Restore DB schemas from BD dump
           → impdp via restore.py
  │
  → status = failed
  → User can retry with resume_from_checkpoint = true
```

---

### Phase 3: SANC Pack Installation (4 Steps)

**Guard**: `install_sanc = true`

| Step | Action | Service File |
|------|--------|--------------|
| Pre | Clear filesystem caches | ssh_service.py |
| 1 | Download + extract SANC installer kit from Git | installer.py |
| 2 | Set SANC kit permissions (`chmod`) | installer.py |
| 3 | Patch SANC config files in Git repo | installer.py |
| 4a | Run SANC `osc.sh` schema creator (interactive) | installer.py |
| 4b | Run SANC `setup.sh SILENT` (interactive) | installer.py |

#### Step 3 Detail — SANC Config Files Patched

| File | Patch Method |
|------|--------------|
| `OFS_SANC_SCHEMA_IN.xml` | `_patch_ofs_sanc_schema_in_repo()` |
| `OFSAAI_InstallConfig.xml` | `_patch_sanc_ofsaai_install_config_repo()` |

Extra fields: `sanc_cs_swiftinfo`, `sanc_tflt_swiftinfo`

#### After SANC Success

```
SANC Pack completes
  │
  ├── Take SANC application backup
  │     → tar -cvf /u01/OFSAA_BKP_SANC_<timestamp>.tar.gz OFSAA
  └── Take SANC DB schema backup (expdp)
```

---

### Phase 4: Completion

```
All selected modules completed
  → status = completed
  → progress = 100%
```

---

## Checkpoint / Resume Flow

```
BD succeeds + backup taken ──► checkpoint saved in memory
                                     │
ECM fails ──► auto-restore to BD ────┘
                                     │
User retries with                    │
  resume_from_checkpoint = true ─────┘
    │
    ├── Validates checkpoint exists
    ├── Skips BD Pack entirely (Steps 1-10)
    ├── Starts directly at ECM Step 1
    └── On ECM success → checkpoint cleared
```

---

## Interactive Prompts

During `osc.sh`, `envCheck.sh`, and `setup.sh`, the scripts ask for user input.
These are handled via WebSocket:

```
Remote script outputs prompt (e.g., "Enter SYS password:")
  → ssh_service detects prompt pattern
  → Backend sends prompt to frontend via WebSocket
  → Frontend shows input dialog to user
  → User types response
  → Frontend sends response via WebSocket
  → Backend feeds response to SSH channel
  → Script continues
```

Prompt callbacks are defined in `core/prompt_helpers.py`:
- `make_osc_prompt_callback()` — for osc.sh (auto-fills DB password)
- `make_envcheck_prompt_callback()` — for envCheck.sh
- `make_setup_prompt_callback()` — for setup.sh

---

## File → Service Map

| File | Responsibility |
|------|---------------|
| `routers/installation.py` | API endpoints + main async worker |
| `services/installation_service.py` | Orchestrator, delegates to services |
| `services/oracle_user_setup.py` | Step 1: oracle user + oinstall group |
| `services/mount_point.py` | Step 2: /u01 mount point |
| `services/packages.py` | Step 3: ksh, git, unzip |
| `services/profile.py` | Step 4: /home/oracle/.profile |
| `services/java.py` | Steps 5-6: JDK install + OFSAA dirs |
| `services/oracle_client.py` | Step 7: Oracle client detection |
| `services/installer.py` | Steps 8-10 + all ECM/SANC operations |
| `services/recovery_service.py` | Cleanup, backup/restore orchestration |
| `services/backup.py` | DB schema backup (expdp) |
| `services/restore.py` | DB schema restore (impdp) |
| `services/ssh_service.py` | All remote commands (Paramiko SSH) |
| `services/validation.py` | Pre-checks (user, group, dir, file) |
| `services/utils.py` | shell_escape(), sed_escape() |
| `core/task_manager.py` | Task state, progress, log routing |
| `core/log_persistence.py` | Disk-based log persistence per task |
| `core/websocket_manager.py` | WebSocket connection + input queues |
| `core/prompt_helpers.py` | Auto-answer callbacks for scripts |
| `core/config.py` | Env vars, step names, default paths |
| `schemas/installation.py` | Pydantic request/response models |

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/installation/start` | Start BD/ECM/SANC installation |
| GET | `/api/installation/status/{task_id}` | Get task status/progress |
| GET | `/api/installation/tasks` | List all tasks |
| GET | `/api/installation/logs/{task_id}/full` | Full log download |
| GET | `/api/installation/logs/{task_id}/tail` | Last N log lines |
| POST | `/api/installation/test-connection` | Test SSH connectivity |
| GET | `/api/installation/rollback` | Get cached request for retry |
| GET | `/api/installation/checkpoint` | Get BD Pack checkpoint status |
| DELETE | `/api/installation/checkpoint` | Clear BD Pack checkpoint |
| WS | `/ws/{task_id}` | Real-time logs, status, prompts |
