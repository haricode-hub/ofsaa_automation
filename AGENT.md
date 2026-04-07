# OFSAA Installation Automation - Complete Setup Guide

## Table of Contents
1. [System Overview](#system-overview)
2. [Prerequisites](#prerequisites)
3. [Project Structure](#project-structure)
4. [Backend Setup](#backend-setup)
5. [Frontend Setup](#frontend-setup)
6. [Environment Configuration](#environment-configuration)
7. [Running the System](#running-the-system)
8. [Installation Workflows](#installation-workflows)
9. [Module Management](#module-management)
10. [Backup & Recovery](#backup--recovery)
11. [Troubleshooting](#troubleshooting)

---

## System Overview

### Technology Stack
- **Backend**: FastAPI (Python 3.x) with async support, managed by `uv`
- **Frontend**: Next.js 14 + React + TypeScript + Tailwind CSS
- **Communication**: WebSocket for real-time logs, SSH via Paramiko
- **State Management**: In-memory task tracking with WebSocket broadcast

### Architecture Flow
```
User Form Submission
    ↓
POST /api/installation/start
    ↓
Task Created + Async Execution
    ↓
WebSocket /ws/{task_id} Streams Logs
    ↓
10-Step Installation (BD Pack)
    ↓
Optional: 4-Step ECM Installation
    ↓
Logs Viewer at /logs/{task_id}
```

---

## Prerequisites

### System Requirements
- **Python**: 3.8+
- **Node.js**: 18+ (for Next.js)
- **Git**: For cloning OFSAA installer kits
- **Target Server**: Linux/Unix system with:
  - SSH access (root or sudoer)
  - Oracle Database (for BD Pack installation)
  - 50+ GB free disk space

### Local Development Tools
```bash
# Install uv (Python package manager)
pip install uv

# Or download from https://github.com/astral-sh/uv/releases
```

### Access Credentials
- **Git Repository**: Username & password for OFSAA installer kits
- **Target Server**: IP, SSH username, SSH password
- **Oracle Database**: SYS password for backup/restore operations
- **Optional**: Custom JAVA_HOME, FIC_HOME paths

---

## Project Structure

```
ofssa_installation/
├── backend/                        # FastAPI application
│   ├── main.py                    # FastAPI app & WebSocket setup
│   ├── pyproject.toml             # uv dependencies
│   ├── requirements.txt           # pip reference (use pyproject.toml)
│   ├── start.bat                  # Windows startup script
│   ├── core/
│   │   ├── config.py              # Environment config & step names
│   │   ├── logging.py             # Logging setup
│   │   └── websocket_manager.py   # WebSocket connection manager
│   ├── routers/
│   │   └── installation.py        # API endpoints
│   ├── schemas/
│   │   └── installation.py        # Pydantic request/response models
│   └── services/                  # Business logic
│       ├── installation_service.py
│       ├── installer.py
│       ├── ssh_service.py
│       ├── recovery_service.py
│       ├── validation.py
│       ├── java.py
│       ├── packages.py
│       ├── profile.py
│       ├── mount_point.py
│       ├── oracle_client.py
│       ├── oracle_user_setup.py
│       └── utils.py
│
├── frontend/                       # Next.js React application
│   ├── package.json               # npm dependencies
│   ├── tsconfig.json              # TypeScript config
│   ├── next.config.js             # Next.js config
│   ├── tailwind.config.js         # Tailwind CSS config
│   ├── start.bat                  # Windows startup script
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx         # Root layout
│   │   │   ├── page.tsx           # Home page
│   │   │   ├── globals.css        # Tailwind CSS
│   │   │   └── logs/[taskId]/
│   │   │       └── page.tsx       # Real-time log viewer
│   │   └── components/
│   │       ├── InstallationForm.tsx
│   │       ├── EcmPackForm.tsx
│   │       ├── EcmPackPage.tsx
│   │       ├── EcmPackPreview.tsx
│   │       └── BackgroundMatrix.tsx
│   └── lib/
│       ├── api.ts                 # API client
│       └── constants/
│
├── AGENTS.md                      # Architecture & API documentation
├── DEPLOY.md                      # Deployment guide
├── SANC_INSTALLATION_GUIDE.md    # SANC module documentation
├── README.md                      # Project overview
└── Configuration XML Files
    ├── OFS_BD_SCHEMA_IN.xml
    ├── OFS_BD_PACK.xml
    ├── OFS_ECM_SCHEMA_IN.xml
    ├── OFSAAI_InstallConfig.xml
    └── default.properties
```

---

## Backend Setup

### Step 1: Navigate to Backend Directory
```bash
cd backend
```

### Step 2: Initialize Python Environment with uv
```bash
# Sync dependencies
uv sync

# This creates a .venv directory with all required packages
```

### Step 3: Verify Installation
```bash
# Activate virtual environment
# On Windows:
.venv\Scripts\activate.ps1
# On Linux/Mac:
source .venv/bin/activate

# Verify python and uv
python --version
uv --version
```

### Step 4: Review Dependencies (pyproject.toml)
```toml
[project]
name = "ofsaa-installation"
version = "1.0.0"
dependencies = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "paramiko",
    "python-dotenv",
]

[tool.uv]
python-version = "3.9"
```

### Step 5: Check Core Configuration
- Edit `core/config.py` to verify environment variables
- Standard variables:
  - `OFSAA_REPO_URL` - Git repository URL
  - `OFSAA_REPO_DIR` - Clone location (default: `/u01/ofsaa`)
  - `OFSAA_GIT_USERNAME` - Git username
  - `OFSAA_GIT_PASSWORD` - Git password

---

## Frontend Setup

### Step 1: Navigate to Frontend Directory
```bash
cd frontend
```

### Step 2: Install Dependencies
```bash
npm install
```

### Step 3: Verify Installation
```bash
npm --version
node --version
```

### Step 4: Check Package Configuration
```json
{
  "name": "ofsaa-installation-ui",
  "version": "1.0.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint src/"
  }
}
```

### Step 5: Build for Production (Optional)
```bash
npm run build

# Verify build output
ls -la .next/
```

---

## Environment Configuration

### Step 1: Backend Environment Variables
Create `.env` file in `backend/` directory:

```bash
# Git Repository
OFSAA_REPO_URL=https://github.com/your-org/ofsaa-kits.git
OFSAA_REPO_DIR=/u01/ofsaa
OFSAA_GIT_USERNAME=your-git-user
OFSAA_GIT_PASSWORD=your-git-password

# Installer Configuration
OFSAA_INSTALLER_ZIP_NAME=OFSAA_BD_Installer.zip
OFSAA_JAVA_ARCHIVE_HINT=jdk-11
OFSAA_FAST_CONFIG_APPLY=0
OFSAA_ENABLE_CONFIG_PUSH=0

# Server
API_HOST=0.0.0.0
API_PORT=8000
```

### Step 2: Frontend Environment Variables
Create `.env.local` file in `frontend/` directory:

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Feature Flags
NEXT_PUBLIC_ENABLE_ECM=true
NEXT_PUBLIC_ENABLE_SANC=false
```

### Step 3: Database Connection (Optional)
If using persistent database:
```bash
# Add to backend/.env
DATABASE_URL=postgresql://user:password@localhost:5432/ofsaa_db
```

---

## Running the System

### Option 1: Development Mode (Separate Terminals)

#### Terminal 1: Start Backend
```bash
cd backend

# Activate environment
uv sync

# Run server
uv run python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

#### Terminal 2: Start Frontend
```bash
cd frontend

npm install

npm run dev
```

**Output:**
```
 ▲ Next.js 14.0.0
 - Local:        http://localhost:3000
 - Environments: .env.local
```

### Option 2: Windows Batch Scripts

#### Start Backend (Windows)
```bash
cd backend
.\start.bat
```

#### Start Frontend (Windows)
```bash
cd frontend
.\start.bat
```

### Option 3: Production Mode with PM2

```bash
# Install PM2 globally
npm install -g pm2

# Start with ecosystem.config.js
pm2 start ecosystem.config.js

# Monitor
pm2 logs

# Stop
pm2 stop all
pm2 delete all
```

---

## Installation Workflows

### Workflow A: BD Pack Only (Basic Installation)

**API Request:**
```bash
curl -X POST http://localhost:8000/api/installation/start \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.100",
    "username": "root",
    "password": "root_password",
    "install_bdpack": true,
    "install_ecm": false,
    "schema_jdbc_host": "192.168.1.50",
    "schema_jdbc_service": "ORCL"
  }'
```

**Response:**
```json
{
  "task_id": "uuid-string",
  "status": "started",
  "progress": 0
}
```

**Steps Executed:**
1. Create oracle user and oinstall group
2. Create mount point /u01
3. Install KSH and git
4. Create .profile file
5. Install Java and update profile
6. Create OFSAA directory structure
7. Check Oracle client and update profile
8. Setup OFSAA installer and run envCheck
9. Apply config XMLs/properties and run osc.sh
10. Install BD PACK with setup.sh SILENT

**Monitor Progress:**
```
WebSocket: ws://localhost:8000/ws/{task_id}

Browser: http://localhost:3000/logs/{task_id}
```

### Workflow B: BD Pack + ECM (Full Installation)

**API Request:**
```bash
curl -X POST http://localhost:8000/api/installation/start \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.100",
    "username": "root",
    "password": "root_password",
    "install_bdpack": true,
    "install_ecm": true,
    "install_sanc": false,
    "db_sys_password": "oracle_sys_password",
    "schema_jdbc_host": "192.168.1.50",
    "schema_jdbc_service": "ORCL",
    "ecm_schema_jdbc_host": "192.168.1.50",
    "ecm_schema_jdbc_service": "ORCL"
  }'
```

**Steps Executed:**

**BD Pack (Steps 1-10):** Same as Workflow A

**After BD Success:**
- Automatic backup of application (tar) + Database schema backup

**ECM Module (Steps 11-15):**
1. Download and extract ECM installer kit (82% progress)
2. Set ECM kit permissions (85% progress)
3. Apply ECM configuration files (88% progress)
4. Run ECM schema creator (92% progress)
5. Run ECM setup SILENT (96% progress)

**On ECM Failure:**
- Automatic rollback to BD state
- Restore application from backup
- Restore database schemas from backup
- User retries ECM with `resume_from_checkpoint: true`

### Workflow C: Retry After ECM Failure

**API Request:**
```bash
curl -X POST http://localhost:8000/api/installation/start \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.100",
    "username": "root",
    "password": "root_password",
    "install_bdpack": true,
    "install_ecm": true,
    "resume_from_checkpoint": true,
    "db_sys_password": "oracle_sys_password",
    "ecm_schema_jdbc_host": "192.168.1.50",
    "ecm_schema_jdbc_service": "ORCL"
  }'
```

**Behavior:**
- Skips BD Pack (steps 1-10)
- Restores BD state from backup
- Runs ECM installation (steps 11-15)

---

## Module Management

### Current Modules

#### 1. BD Pack (Baseline)
- **Status**: ✅ Fully Implemented
- **Flag Field**: `install_bdpack: bool`
- **Kit Location**: `/u01/BD_Installer_Kit/OFS_BD_PACK`
- **Config Files**:
  - `OFS_BD_SCHEMA_IN.xml` (schema configuration)
  - `OFS_BD_PACK.xml` (application flags)
  - `default.properties` (silent installer properties)
  - `OFSAAI_InstallConfig.xml` (web server config)

#### 2. ECM Pack
- **Status**: ✅ Fully Implemented
- **Flag Field**: `install_ecm: bool`
- **Kit Location**: `/u01/ECM_Installer_Kit/OFS_ECM_PACK`
- **Config Files**:
  - `OFS_ECM_SCHEMA_IN.xml`
  - `default.properties`
  - `OFSAAI_InstallConfig.xml`

#### 3. SANC Pack (Placeholder)
- **Status**: ❌ Not Implemented
- **Flag Field**: `install_sanc: bool` (reserved)
- **Kit Location**: TBD
- **Planned Steps**: 4 steps (similar to ECM)

### Adding New Modules

#### Step 1: Update Schema (`backend/schemas/installation.py`)
```python
# Add optional module fields
sanc_schema_jdbc_host: Optional[str] = Field(default=None)
sanc_schema_jdbc_port: Optional[int] = Field(default=1521)
sanc_prop_field_name: Optional[str] = Field(default=None)
install_sanc: Optional[bool] = False
```

#### Step 2: Add Installer Methods (`backend/services/installer.py`)
```python
async def download_and_extract_sanc_installer(self, ...):
    # Download and extract kit to /u01/SANC_Installer_Kit

async def apply_sanc_config_files_from_repo(self, ...):
    # Patch SANC-specific XML files

async def run_sanc_osc_schema_creator(self, ...):
    # Run osc.sh for SANC schema

async def run_sanc_setup_silent(self, ...):
    # Run setup.sh SILENT for SANC
```

#### Step 3: Add Service Methods (`backend/services/installation_service.py`)
```python
async def download_and_extract_sanc_installer(self, ...):
    return await self.installer.download_and_extract_sanc_installer(...)
    # ... other wrapper methods
```

#### Step 4: Update Router (`backend/routers/installation.py`)
```python
if request.install_sanc:
    await append_output(task_id, "[INFO] ===== SANC MODULE =====")
    # Add SANC installation steps
    # Steps 16-19 (after ECM)
```

#### Step 5: Frontend Components
```
Create:
- frontend/src/components/SancPackForm.tsx
- frontend/src/components/SancPackPage.tsx
- frontend/src/components/SancPackPreview.tsx

Update:
- frontend/src/components/InstallationForm.tsx (add SANC section)
```

---

## Backup & Recovery

### Backup Strategy

**Automatic Backup Triggers:**
1. After BD Pack completes successfully (step 10)
2. Before ECM installation begins

**What Gets Backed Up:**
```bash
# Application backup
tar -czf /u01/ofsaa_backup_$(date +%s).tar.gz /u01/OFSAA_Apps/

# Database backup (via backup_Restore/backup_ofs_schemas.sh)
bash backup_Restore/backup_ofs_schemas.sh system <DB_PASS> <SERVICE>
```

### Recovery Process

**On ECM Failure:**
```bash
# 1. Restore application
tar -xzf /u01/ofsaa_backup_*.tar.gz -C /u01/

# 2. Restore database schemas
bash backup_Restore/restore_ofs_schemas.sh system <DB_PASS> <SERVICE>

# 3. Clear system cache
rm -rf /u01/OFSAA_Apps/work/*

# 4. Restart WebLogic/application servers
```

**Manual Cleanup (If Needed):**
```bash
# Drop schemas via sqlplus
sqlplus "sys/<PASSWORD>@<HOST>:<PORT>/<SERVICE> as sysdba" << EOF
DROP TABLESPACE ofs_ts INCLUDING CONTENTS AND DATAFILES;
DROP USER ofs_config CASCADE;
DROP USER ofs_atomic CASCADE;
exit;
EOF
```

### Database Password Management

**Field in Request:**
```python
db_sys_password: Optional[str]  # Oracle SYS password
```

**Usage:**
- Backup/restore operations
- Schema creation/deletion
- Configuration validation

**Security:**
- Never logged to stdout
- Passed via environment variables to scripts
- Encrypted in transit (SSL/TLS)

---

## API Endpoints

### Installation Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/installation/start` | Start new installation |
| GET | `/api/installation/status/{task_id}` | Get task status |
| GET | `/api/installation/tasks` | List all tasks |
| POST | `/api/installation/test-connection` | Test SSH connectivity |
| GET | `/api/installation/rollback` | Get cached request |
| GET | `/api/installation/checkpoint` | Get checkpoint status |
| DELETE | `/api/installation/checkpoint` | Clear checkpoint |
| WS | `/ws/{task_id}` | WebSocket for logs/status |

### Request Schema

```python
class InstallationRequest(BaseModel):
    # Connection
    host: str
    username: str
    password: str
    
    # Module Flags
    install_bdpack: bool = True
    install_ecm: bool = False
    install_sanc: Optional[bool] = False
    
    # Checkpoint/Retry
    resume_from_checkpoint: bool = False
    db_sys_password: Optional[str] = None
    
    # Database Configuration
    schema_jdbc_host: Optional[str]
    schema_jdbc_port: Optional[int] = 1521
    schema_jdbc_service: Optional[str]
    schema_default_password: Optional[str]
    
    # ... 50+ additional fields for configuration
```

### Response Schema

```python
class InstallationResponse(BaseModel):
    task_id: str
    status: str  # "started", "running", "completed", "failed"
    progress: int  # 0-100
    message: str
    error: Optional[str]
```

---

## Troubleshooting

### Issue 1: Backend Won't Start

**Error:** `ModuleNotFoundError: No module named 'fastapi'`

**Solution:**
```bash
cd backend
uv sync
uv run python -m uvicorn main:app --reload
```

### Issue 2: Frontend Can't Connect to Backend

**Error:** WebSocket connection fails at `/ws/{task_id}`

**Verify:**
1. Backend is running on port 8000
2. Frontend API URL in `.env.local` is correct
3. No firewall blocking port 8000
4. CORS enabled in FastAPI `main.py`

**Solution:**
```python
# main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue 3: SSH Connection Fails

**Error:** `paramiko.ssh_exception.AuthenticationException`

**Causes:**
1. Wrong username/password
2. SSH key not configured
3. Port 22 blocked

**Solution:**
```bash
# Test connection manually
ssh -v root@192.168.1.100

# Check backend logs for detailed error
# In WebSocket: detailed error message is streamed
```

### Issue 4: Installation Hangs

**Error:** Installation progress stuck at same percentage

**Solutions:**
1. Check target server disk space: `df -h /u01`
2. Check logs: `ps aux | grep java`
3. Increase WebSocket timeout: Edit `main.py`
4. Kill hung processes: `pkill -f osc.sh`

### Issue 5: ECM Installation Fails

**Error:** Step 15 (setup.sh) fails

**Recovery:**
1. System automatically restores BD state via backup/restore
2. Check database schemas: `sqlplus sys/<pass> @get_user_status.sql`
3. Retry with `resume_from_checkpoint: true`
4. If persists, manual cleanup required (see Backup & Recovery section)

### Issue 6: XML Patching Errors

**Error:** "Invalid XML syntax" during configuration

**Check:**
1. XML file exists in repo: `ls backup_Restore/OFS_*_SCHEMA_IN.xml`
2. XML is well-formed: `xml_lint OFS_BD_SCHEMA_IN.xml`
3. All required fields are in request

**Debug:**
```bash
# View patched XML before apply
cat /tmp/OFS_BD_SCHEMA_IN.xml.patch

# Manually verify patch worked
grep "<Driver>" OFS_BD_SCHEMA_IN.xml
```

### Issue 7: Port Already in Use

**Error:** `Address already in use: [Errno 48]`

**Solution - Find Process:**
```bash
# On Windows
netstat -ano | findstr :8000

# On Linux/Mac
lsof -i :8000
```

**Solution - Kill Process:**
```bash
# Windows
taskkill /PID <PID> /F

# Linux
kill -9 <PID>
```

### Issue 8: Permission Denied on Target Server

**Error:** `permission denied` during installation

**Causes:**
1. SSH user is not root/sudoer
2. /u01 directory not writable
3. Oracle user doesn't exist yet

**Solution:**
```bash
# Create /u01 with permissions
sudo mkdir -p /u01
sudo chmod 777 /u01

# Or add user to sudoers
sudo visudo
# Add: username ALL=(ALL) NOPASSWD:ALL
```

---

## Development Workflow

### Creating a Feature

1. **Backend Change**: Edit service in `backend/services/`
2. **Update Schema**: Add fields to `backend/schemas/installation.py`
3. **Update Router**: Add logic to `backend/routers/installation.py`
4. **Frontend Form**: Add fields to `frontend/src/components/InstallationForm.tsx`
5. **Test**: Use WebSocket `/ws/{task_id}` to monitor execution
6. **Commit**: Push to Git with meaningful message

### Testing Installation Locally

```bash
# Test connection without running full install
curl -X POST http://localhost:8000/api/installation/test-connection \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.100",
    "username": "root",
    "password": "password"
  }'
```

### Debugging WebSocket Issues

```bash
# Browser console
const ws = new WebSocket('ws://localhost:8000/ws/task-id');
ws.onmessage = (e) => console.log('MSG:', JSON.parse(e.data));
ws.onerror = (e) => console.error('ERROR:', e);
```

---

## Performance Optimization

### Backend Optimization
1. **Async/Await**: All I/O operations use async
2. **Connection Pooling**: SSH connections reused
3. **Caching**: XML patches cached in memory
4. **Parallel Steps**: Independent steps run in parallel (where applicable)

### Frontend Optimization
1. **Code Splitting**: Components lazy-loaded
2. **Image Optimization**: Next.js Image component used
3. **CSS Purging**: Tailwind unused styles removed
4. **WebSocket Buffering**: Log messages batched

### Network Optimization
1. **Compression**: GZIP enabled for all responses
2. **Keep-alive**: WebSocket persistent connection
3. **Timeout**: 3600s for long-running scripts

---

## Security Checklist

- [ ] SSH credentials never logged
- [ ] Database passwords passed via environment only
- [ ] CORS whitelist configured for frontend domain
- [ ] WebSocket validates task_id before sending logs
- [ ] No sensitive data in git commits (use .env files)
- [ ] TLS/SSL enabled for production deployment
- [ ] Rate limiting enabled on `/api/installation/start`
- [ ] Input validation on all request fields
- [ ] XML patches escape special characters

---

## Production Deployment

### Pre-Deployment

```bash
# Build frontend
cd frontend && npm run build

# Test backend with production settings
export DEBUG=0
uv run python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Using PM2 for Process Management

```bash
# Start services
pm2 start ecosystem.config.js

# Monitor
pm2 logs
pm2 monit

# Auto-restart on reboot
pm2 startup
pm2 save
```

### Docker Deployment (Optional)

```dockerfile
# Dockerfile
FROM python:3.9 as backend
WORKDIR /app
COPY backend/pyproject.toml .
RUN pip install uv && uv sync
COPY backend . 
CMD ["uv", "run", "python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0"]

FROM node:18 as frontend
WORKDIR /app
COPY frontend .
RUN npm install && npm run build
CMD ["npm", "start"]
```

---

## Common Commands Reference

### Backend
```bash
# Activate environment
cd backend && source .venv/bin/activate  # Linux/Mac
cd backend && .venv\Scripts\activate.ps1 # Windows

# Run dev server
uv sync && uv run python -m uvicorn main:app --reload

# Run tests
uv run pytest

# Format code
uv run black .

# Lint
uv run pylint backend/
```

### Frontend
```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev

# Build
npm run build

# Lint
npm run lint

# Format
npx prettier --write src/
```

### Database
```bash
# Connect via sqlplus
sqlplus sys/<password>@<host>:<port>/<service> as sysdba

# List schemas
SELECT username FROM dba_users WHERE oracle_maintained='N';

# Check tablespaces
SELECT tablespace_name FROM dba_tablespaces;
```

### System
```bash
# Monitor installation on target
ssh root@<target> "tail -f /tmp/ofsaa_install.log"

# Check processes
ssh root@<target> "ps aux | grep java"

# Disk space
ssh root@<target> "df -h /u01"
```

---

## Documentation Files

- **AGENTS.md** - Architecture, API contracts, module design
- **DEPLOY.md** - Production deployment procedures
- **SANC_INSTALLATION_GUIDE.md** - SANC module specifications
- **README.md** - Project overview and quick start
- **agent.md** (This File) - Complete setup and workflow guide

---

## Contact & Support

For issues, questions, or contributions:
1. Check troubleshooting section above
2. Review AGENTS.md for architecture details
3. Check WebSocket logs in browser console
4. Enable debug logging in backend (set DEBUG=1)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-07 | Initial agent.md - Complete setup guide |
| 1.0 (BD Pack) | Earlier | BD Pack 10-step installation |
| 1.0 (ECM) | Earlier | ECM 4-step installation with backup/restore |

---

**Last Updated**: April 7, 2026
**Status**: Production Ready (BD Pack + ECM)
**Next Phase**: SANC Pack Implementation
