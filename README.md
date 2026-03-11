# OFSAA Installation Automation System

Complete automation system for Oracle Financial Services products (OFSAA, Flexcube, etc.) with intelligent SSH-based installation management.

## 🚀 Quick Start

### 1. Start Backend (Terminal 1)
```bash
cd backend
uv sync                          # Install dependencies from pyproject.toml
uv run python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Or use the start script:**
```bash
cd backend
start.bat                       # Runs uv sync + uv run uvicorn automatically
```

### 2. Start Frontend (Terminal 2)  
```bash
cd frontend
bun install                     # Install dependencies
bun dev                        # Starts on http://localhost:3000
```

**Or use the start script:**
```bash
cd frontend
start.bat
```

### 3. Access the Application
- **Frontend UI**: http://localhost:3000
- **Backend API**: http://localhost:8000  
- **API Documentation**: http://localhost:8000/docs

## 🎯 Features

### Frontend (Next.js)
- **Tokyo Night Theme**: Distinctive design with IBM Plex Mono typography
- **Real-time Updates**: Live progress tracking and log streaming
- **Responsive Design**: Works on desktop and mobile devices
- **Framer Motion**: Smooth animations and micro-interactions

### Backend (FastAPI)
- **SSH Automation**: Secure remote command execution
- **Background Tasks**: Async installation processing with status tracking
- **Error Handling**: Comprehensive error reporting and recovery
- **Cross-platform**: Windows/Linux SSH support

## 📋 OFSAA Installation Steps

The system executes these SSH commands automatically in sequence:

1. **Oracle User Setup**:
   ```bash
   groupadd -f oinstall && (id -u oracle &>/dev/null || useradd -g oinstall oracle)
   ```

2. **Mount Point Creation**:
   ```bash
   mkdir -p /u01/OFSAA/FICHOME /u01/OFSAA/FTPSHARE /u01/BD_Installer_Kit && chown -R oracle:oinstall /u01 && chmod -R 755 /u01
   ```

3. **Package Installation**:
   ```bash
   yum install -y ksh git unzip
   ```

4. **Profile File Creation**:
   ```bash
   mkdir -p /home/oracle && touch /home/oracle/.profile && chown oracle:oinstall /home/oracle/.profile
   ```

5. **Java Installation**:
   ```bash
   yum install -y java-1.8.0-openjdk-devel
   # Updates .profile with JAVA_HOME and JAVA_BIN
   ```

6. **Oracle Client Setup**:
   ```bash
   mkdir -p /opt/oracle/instantclient_19_8 /opt/oracle/network/admin
   # Updates .profile with ORACLE_HOME, TNS_ADMIN, ORACLE_SID
   ```

7. **Profile Variables Update**:
   - FIC_HOME (configurable via UI)
   - JAVA_HOME (auto-detected or custom)
   - JAVA_BIN (auto-detected or custom)  
   - ORACLE_SID (configurable via UI)

## 🎛️ Profile Configuration

The installation form includes fields for customizing environment variables:

- **FIC_HOME**: OFSAA installation directory (default: `/u01/OFSAA/FICHOME`)
- **JAVA_HOME**: Java installation path (auto-detected if left empty)
- **JAVA_BIN**: Java binaries path (auto-detected if left empty)
- **ORACLE_SID**: Oracle System Identifier (default: `ORCL`)

## 🛡️ Backup, Restore & Failure Handling

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

## 🏗️ Project Structure

```
installation_workspace/
├── backend/                    # FastAPI Python backend
│   ├── main.py                    # Application entry point
│   ├── pyproject.toml            # UV project config (deps, scripts)
│   ├── start.bat                 # Windows start: uv sync + uv run uvicorn
│   ├── .env                      # Environment variables
│   ├── routers/
│   │   └── installation.py           # API routes, backup/restore orchestration
│   ├── schemas/
│   │   └── installation.py           # Pydantic models (InstallationRequest)
│   └── services/
│       ├── installation_service.py   # Service composition
│       ├── installer.py              # Git ops, XML patching, scripts
│       ├── recovery_service.py       # Backup, restore, cleanup
│       ├── ssh_service.py            # SSH connection management
│       ├── validation.py             # Directory/file checks
│       ├── java.py                   # Java installation
│       ├── packages.py               # Package installation (ksh, git)
│       ├── profile.py                # .profile creation/updates
│       ├── mount_point.py            # /u01 mount point setup
│       ├── oracle_client.py          # Oracle client detection
│       ├── oracle_user_setup.py      # Oracle user/group creation
│       └── utils.py                  # Shell escape, helpers
│
├── frontend/                   # Next.js React frontend  
│   ├── src/
│   │   ├── app/                       # Next.js App Router
│   │   │   ├── page.tsx                   # Main page
│   │   │   ├── layout.tsx                 # Root layout
│   │   │   ├── globals.css                # Global styles
│   │   │   └── logs/[taskId]/page.tsx     # Real-time log viewer
│   │   └── components/
│   │       ├── InstallationForm.tsx      # Main form (BD + ECM)
│   │       ├── EcmPackForm.tsx           # ECM config fields
│   │       ├── EcmPackPage.tsx           # ECM section wrapper
│   │       ├── EcmPackPreview.tsx        # ECM review component
│   │       └── BackgroundMatrix.tsx      # Animated background
│   ├── package.json              # Node.js dependencies
│   ├── tailwind.config.js        # Tailwind CSS config
│   └── start.bat                 # Windows start script
│
└── README.md                   # This file
```

## 🛠️ Prerequisites

### Backend
- Python 3.8+
- UV package manager (see https://docs.astral.sh/uv/)
- SSH client (OpenSSH for Windows, or sshpass for Linux)

### Frontend  
- Node.js 18+
- Bun package manager (or npm/yarn as fallback)

### Target Servers
- SSH access with root privileges
- CentOS/RHEL/similar Linux distribution
- Network connectivity for package installation

## 🔧 Development

### Backend Development
```bash
cd backend
uv sync                          # Install/sync all deps from pyproject.toml
uv run python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Development  
```bash
cd frontend
bun install
bun dev
```

## 🚨 Troubleshooting

**Backend Issues**:
- Ensure UV is installed: `pip install uv`
- Check if port 8000 is available
- For Windows SSH: Install PowerShell SSH or Posh-SSH module

**Frontend Issues**:
- If bun is not available, use `npm install` and `npm run dev`
- Check if port 3000 is available (Next.js will auto-assign if not)
- Ensure backend is running before submitting forms

**Connection Issues**:
- Verify SSH credentials and network connectivity
- Check firewall rules for SSH access (port 22)
- Ensure target servers have Python and package managers available

## 📝 Usage

1. **Start both services** using the commands above
2. **Open frontend** at http://localhost:3000
3. **Enter credentials**: Target host IP, root username, and password
4. **Submit form** to start installation
5. **Monitor progress** with real-time updates and logs
6. **Check API logs** at http://localhost:8000/docs for detailed information

The system provides a complete end-to-end automation solution for OFSAA installations with professional UI/UX and robust backend processing.