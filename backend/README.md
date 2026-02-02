# OFSAA Installation Backend

FastAPI backend for Oracle Financial Services installation automation via SSH.

## Features

- **SSH Command Execution**: Secure remote command execution using sshpass
- **Installation Automation**: Complete OFSAA setup process automation
- **Real-time Status**: Background task processing with status polling
- **Error Handling**: Comprehensive error handling and logging

## Installation Commands

The backend executes these SSH commands in sequence:

1. **Oracle User Setup**:
   ```bash
   groupadd -f oinstall; id -u oracle &>/dev/null || useradd -g oinstall oracle; mkdir -p /u01/OFSAA/FICHOME /u01/OFSAA/FTPSHARE /u01/installer_kit; chown -R oracle:oinstall /u01
   ```

2. **Package Installation**:
   ```bash
   yum install -y ksh unzip git
   ```

3. **Installer Extraction**:
   ```bash
   sudo -u oracle bash -c 'cd /u01/installer_kit && unzip -o *.zip'
   ```

## Quick Start

```bash
# Create and activate UV virtual environment
uv venv
# On Windows
.venv\Scripts\activate
# On Linux/Mac
source .venv/bin/activate

# Install dependencies with UV
uv pip install -r requirements.txt

# Or install from pyproject.toml
uv pip install -e .

# Start development server
python main.py

# Or with uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or using the project script
uv run start
```

## API Endpoints

- `POST /api/installation/start` - Start installation process
- `GET /api/installation/status/{task_id}` - Get installation status
- `GET /api/installation/tasks` - List all installation tasks
- `GET /health` - Health check

## Prerequisites

- Python 3.8+
- UV package manager (`pip install uv`)
- **Cross-platform SSH**: Uses paramiko library (no external SSH client required)
- SSH access to target servers
- Root privileges on target servers

## SSH Implementation

The backend now uses **paramiko** library for reliable cross-platform SSH connections:

- ✅ **Windows**: No external dependencies required
- ✅ **Linux/Mac**: No sshpass needed
- ✅ **Consistent behavior** across all platforms
- ✅ **Better error handling** and timeout management
- ✅ **Secure password authentication**

## Project Structure

```
backend/
├── main.py                    # FastAPI application entry point
├── requirements.txt           # Python dependencies
├── routers/                   # FastAPI route handlers
│   └── installation.py       # Installation endpoints
└── services/                  # Business logic layer
    ├── ssh_service.py         # SSH connection and command execution
    └── installation_service.py # OFSAA installation logic
```