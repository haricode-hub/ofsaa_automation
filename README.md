# OFSAA Installation Automation System

Complete automation system for Oracle Financial Services products (OFSAA BD Pack, ECM, SANC) with intelligent SSH-based installation management.

## Quick Start

### Local Development

**Terminal 1 — Backend:**
```bash
cd backend
uv sync
uv run python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd frontend
bun install
bun run dev
```

Open: http://localhost:3000

---

## Production Server Deployment (PM2)

### Prerequisites (install once on server)
```bash
# Install Node.js 18+ and PM2
npm install -g pm2

# Install Bun
curl -fsSL https://bun.sh/install | bash

# Install UV (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### One-Time Setup

**1. Clone the project and configure environment:**
```bash
git clone <repo-url> /path/to/ofsaa-automation
cd /path/to/ofsaa-automation

# Create backend .env
cp backend/.env.example backend/.env
vi backend/.env
```

**Key values in `backend/.env`:**
```dotenv
ALLOWED_ORIGIN=http://<SERVER_IP>
OFSAA_REPO_URL=https://github.com/yourorg/ofsaa-repo.git
OFSAA_REPO_DIR=/u01/OFSAA_REPO
OFSAA_GIT_USERNAME=your_git_username
OFSAA_GIT_PASSWORD=your_git_password
OFSAA_INSTALLER_ZIP_NAME=OFS_BD_PACK.zip
OFSAA_JAVA_ARCHIVE_HINT=jdk-11
OFSAA_FAST_CONFIG_APPLY=1
OFSAA_ENABLE_CONFIG_PUSH=0
```

**2. Set frontend API URL for production:**
```bash
echo "NEXT_PUBLIC_API_URL=http://<SERVER_IP>:8000" > frontend/.env.production
```

**3. Install dependencies and build:**
```bash
cd backend && uv sync && cd ..
cd frontend && bun install && bun run build && cd ..
```

**4. Update ecosystem.config.js with your server IP:**
Edit `ecosystem.config.js` and replace `192.168.0.166` with your server IP in both `NEXT_PUBLIC_API_URL` and `ALLOWED_ORIGIN`.

**5. Open firewall ports:**
```bash
sudo firewall-cmd --add-port=3000/tcp --permanent
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
```

### Start the Application
```bash
pm2 start ecosystem.config.js
```

Open: `http://<SERVER_IP>:3000`

### Auto-Start on Reboot
```bash
pm2 save
pm2 startup   # run the command it outputs as root
```

### Redeploy After Code Changes
```bash
git pull

# If frontend files changed:
cd frontend && bun run build && cd ..

# If pyproject.toml changed:
cd backend && uv sync && cd ..

pm2 restart all
```

### PM2 Commands
```bash
pm2 status              # Show process status
pm2 logs                # Live logs (all)
pm2 logs backend        # Backend logs only
pm2 logs frontend       # Frontend logs only
pm2 restart all         # Restart both services
pm2 restart backend     # Restart backend only
pm2 stop all            # Stop both
pm2 delete all          # Remove from PM2
```

### Changing Server IP
```bash
# 1. Update frontend production env
echo "NEXT_PUBLIC_API_URL=http://<NEW_IP>:8000" > frontend/.env.production

# 2. Update backend/.env → ALLOWED_ORIGIN=http://<NEW_IP>

# 3. Update ecosystem.config.js → both NEXT_PUBLIC_API_URL and ALLOWED_ORIGIN

# 4. Rebuild and restart
cd frontend && bun run build && cd ..
pm2 restart all
```

---

## Supported Modules

| Module | Flag | Kit Location |
|--------|------|-------------|
| BD Pack | `install_bdpack` | `/u01/BD_Installer_Kit/OFS_BD_PACK` |
| ECM | `install_ecm` | `/u01/ECM_Installer_Kit/OFS_ECM_PACK` |
| SANC | `install_sanc` | `/u01/SANC_INSTALLER_KIT_AUTOMATION/OFS_SANC_PACK` |

### Installation Flows

| Scenario | Steps |
|----------|-------|
| BD only | Steps 1-10 (user setup → setup.sh SILENT) |
| BD + ECM | BD steps 1-10 → backup → ECM steps 1-4 |
| BD + SANC | BD steps 1-10 → SANC steps 1-4 |
| BD + ECM + SANC | BD steps 1-10 → backup → ECM steps 1-4 → SANC steps 1-4 |

### Auto-Answered Prompts

During `envCheck.sh`, `osc.sh`, and `setup.sh`, the system automatically answers:

| Prompt | Auto-Answer | Source |
|--------|-------------|--------|
| Oracle DB user name / SYSDBA Privileges | `SYS AS SYSDBA` | Hardcoded |
| User Password | From UI | `db_sys_password` field |
| Oracle SID/SERVICE name | From UI | `oracle_sid` field |
| All Y/N confirmations (ONLINE mode, schema, INFODOM) | `Y` | Auto |

### Pre-Module Actions
- **RAM clearing**: `echo 2 | sudo tee /proc/sys/vm/drop_caches` runs before each module
- **open_cursors**: `ALTER SYSTEM SET open_cursors=2000 SCOPE=BOTH` runs on DB server before BD Pack

## Profile Configuration

The installation form includes fields for customizing environment variables:

- **FIC_HOME**: OFSAA installation directory (default: `/u01/OFSAA/FICHOME`)
- **JAVA_HOME**: Java installation path (auto-detected if left empty)
- **JAVA_BIN**: Java binaries path (auto-detected if left empty)
- **ORACLE_SID**: Oracle System Identifier (default: `ORCL`)

## Backup, Restore & Failure Handling

### Backup/Restore Scripts (Git-Controlled)
The `backup_Restore` folder is maintained in Git (same repository as Installer Kit):
- `backup_ofs_schemas.sh` — DB schema backup
- `restore_ofs_schemas.sh` — DB schema restore
- Scripts are **never created/edited locally** — always pulled from Git
- DB password and SERVICE come from the UI (`db_sys_password`, `schema_jdbc_service`)

### Installation Scenarios

| Scenario | What Happens |
|----------|--------------|
| **BD Only** | BD installs → auto app backup + DB backup |
| **BD + ECM** | BD installs → auto backup → ECM installs |
| **BD + ECM + SANC** | BD installs → auto backup → ECM installs → SANC installs |
| **ECM fails** | Auto-restore to BD state → retry ECM only |
| **BD osc.sh fails** | Kill Java → drop schemas/tablespaces → clear cache → retry BD |

### Automatic Backup (After BD Success)
After BD Pack completes, the system automatically:
1. Verifies backup/restore scripts exist in Git repo
2. Creates application backup: `tar -cvf OFSAA_BKP.tar.gz OFSAA`
3. Creates DB schema backup: `./backup_ofs_schemas.sh system <DB_PASS> <SERVICE>`

### ECM Failure → Restore to BD State
If ECM osc.sh or setup.sh fails, the system automatically:
1. Removes existing OFSAA: `rm -rf OFSAA`
2. Restores application: `tar -xvf OFSAA_BKP.tar.gz`
3. Restores DB schemas: `./restore_ofs_schemas.sh system <DB_PASS> <SERVICE>`
4. User retries ECM only with `resume_from_checkpoint: true`

### BD osc.sh Failure → Cleanup
When BD osc.sh fails, automatic cleanup:
- Kills Java processes
- Drops OFSAA users/tablespaces via `sqlplus "sys/<DB_PASS>@<host>:<port>/<service> as sysdba"`
- Clears system cache
- Full BD reinstall required

### Key Rules
- BD backup = restore point for ECM
- ECM failure → restore BD → retry ECM only (BD reinstall NOT required)
- DB SYS password from UI (`db_sys_password` field) — never hardcoded
- Git is the single source of truth for backup/restore scripts

---

## Project Structure

```
├── backend/                    # FastAPI Python backend
│   ├── main.py                 # Application entry point + WebSocket
│   ├── pyproject.toml          # UV project config (deps)
│   ├── start.bat               # Windows start script
│   ├── .env                    # Environment variables
│   ├── routers/
│   │   └── installation.py     # API routes, task orchestration
│   ├── schemas/
│   │   └── installation.py     # Pydantic models
│   └── services/
│       ├── installation_service.py  # Service composition
│       ├── installer.py             # Git ops, XML patching, scripts
│       ├── recovery_service.py      # Backup, restore, cleanup
│       ├── ssh_service.py           # SSH + interactive command handling
│       └── ...                      # java, packages, profile, etc.
│
├── frontend/                   # Next.js React frontend
│   ├── src/app/
│   │   ├── page.tsx            # Main page (InstallationForm)
│   │   └── logs/[taskId]/      # Real-time log viewer + step tracker
│   └── src/components/
│       ├── InstallationForm.tsx # BD Pack form
│       ├── EcmPackForm.tsx     # ECM config fields
│       └── ...
│
├── ecosystem.config.js         # PM2 process config
├── DEPLOY.md                   # Detailed deployment guide
└── AGENTS.md                   # Architecture reference
```

## Recent Fixes & Updates (April 7, 2026)

### 1. FICHOME Deployment — Fixed Missing Wrapper Method
**Issue**: FICHOME deployment failed with `'InstallationService' object has no attribute 'deploy_fichome'`

**Root Cause**: The `deploy_fichome()` method existed in `installer.py` but was NOT exposed as a wrapper method in the `InstallationService` class. The router was calling `installation_service.deploy_fichome()` which didn't exist.

**Fix**:
- ✅ Added wrapper method `deploy_fichome()` to [Installation Service](backend/services/installation_service.py)
- ✅ Updated all 3 FICHOME deployment calls in [router](backend/routers/installation.py) to pass database credentials:
  - `db_sys_password` — Oracle SYS password
  - `db_jdbc_host`, `db_jdbc_port`, `db_jdbc_service` — Database connection info  
  - `config_schema_name`, `atomic_schema_name` — Schema names from last installed module

**Files Modified**:
- `backend/services/installation_service.py` — Added wrapper method
- `backend/routers/installation.py` — Updated 3 deployment calls with DB parameters

### 2. DB Backup Missing for ECM Module
**Issue**: DB backup was not being triggered after ECM installation. Only BD Pack and SANC had DB backups.

**Root Cause**: After ECM's `setup.sh` completes, the code only backed up the application (tar) but skipped DB schema backup. BD Pack and SANC had both.

**Fix**:
- ✅ Added DB schema backup after ECM module success (lines 1289–1319 in router)
- ✅ Uses ECM schema values if provided (`ecm_schema_config_schema_name`, `ecm_schema_atomic_schema_name`), falls back to BD schema names
- ✅ Shows same warning if fields missing as other modules

**Files Modified**:
- `backend/routers/installation.py` — Added ECM DB backup block

**Result**: Now ALL modules (BD, ECM, SANC) take both application + DB backups on success:
- **BD Pack success** → App backup (BD tag) + DB backup
- **ECM success** → App backup (ECM tag) + **DB backup (NEW)**
- **SANC success** → App backup (SANC tag) + DB backup

### 3. TypeScript Deprecation — Removed `baseUrl` 
**Issue**: TypeScript warning: `Option 'baseUrl' is deprecated and will stop functioning in TypeScript 7.0`

**Fix**:
- ✅ Removed deprecated `baseUrl: "."` from [tsconfig.json](frontend/tsconfig.json)
- ✅ Kept `paths` config which provides full functionality
- ✅ `@/` path aliases continue to work without deprecation warnings

**Files Modified**:
- `frontend/tsconfig.json` — Removed baseUrl line

---

## Troubleshooting

- **Port conflict**: Ensure ports 3000 and 8000 are free, or update configs accordingly
- **Bun not available**: Use `npm install` / `npm run dev` as fallback
- **SSH failures**: Verify credentials, network connectivity, and firewall rules (port 22)
- **API docs**: Visit `http://<host>:8000/docs` for the interactive Swagger UI