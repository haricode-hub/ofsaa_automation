# OFSAA Installation Backend

FastAPI backend for Oracle Financial Services (OFSAA) installation automation via SSH.

## Quick Start

```bash
# Install dependencies
uv sync

# Start development server
uv run python main.py

# Or with uvicorn directly (production)
uv run python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## Configuration

Copy `.env.example` to `.env` and update values:

```dotenv
ALLOWED_ORIGIN=http://<SERVER_IP>:3000   # CORS origin (empty = allow all for dev)
OFSAA_REPO_URL=https://...               # Git repo with installer kits
OFSAA_GIT_USERNAME=...
OFSAA_GIT_PASSWORD=...
```

Host/port defaults (`0.0.0.0:8000`) can be overridden via `BACKEND_HOST` and `BACKEND_PORT` env vars.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/installation/start` | Start BD/ECM/SANC installation |
| GET | `/api/installation/status/{task_id}` | Task status & progress |
| GET | `/api/installation/tasks` | List all tasks |
| GET | `/api/installation/logs/{task_id}/full` | Full log download |
| GET | `/api/installation/logs/{task_id}/tail` | Last N log lines |
| POST | `/api/installation/test-connection` | Test SSH connectivity |
| GET | `/api/installation/rollback` | Cached request for retry |
| GET | `/api/installation/checkpoint` | BD Pack checkpoint status |
| DELETE | `/api/installation/checkpoint` | Clear checkpoint |
| POST | `/api/installation/deploy-fichome` | EAR build + datasources + app deploy |
| GET | `/api/installation/deploy-fichome/status/{task_id}` | Deployment status |
| POST | `/api/installation/create-datasources` | Create WebLogic datasources |
| GET | `/api/installation/create-datasources/status/{task_id}` | DS creation status |
| WS | `/ws/{task_id}` | Real-time logs, status, prompts |

Interactive Swagger UI: `http://<host>:8000/docs`

## Project Structure

```
backend/
├── main.py                          # FastAPI app, CORS, WebSocket, routers
├── pyproject.toml                   # Dependencies (uv)
├── .env.example                     # Environment variable template
├── core/
│   ├── config.py                    # Env vars, step names, default paths
│   ├── logging.py                   # Logger setup
│   ├── task_manager.py              # Shared state (tasks, ws, logs)
│   ├── dependencies.py              # FastAPI DI helpers
│   ├── prompt_helpers.py            # Reusable prompt callback factories
│   └── websocket_manager.py         # WS connection manager, input queues
├── routers/
│   ├── installation.py              # BD/ECM/SANC installation endpoints
│   ├── deployment.py                # FICHOME deployment endpoints
│   └── datasource.py               # WebLogic datasource endpoints
├── schemas/
│   └── installation.py              # Pydantic request/response models
└── services/
    ├── installation_service.py      # Orchestrator facade
    ├── installer.py                 # Git ops, XML patching, script execution
    ├── ssh_service.py               # Paramiko SSH wrapper
    ├── recovery_service.py          # Backup/restore coordination
    ├── bd_backup.py                 # Oracle Data Pump export (expdp)
    ├── bd_restore.py                # Oracle Data Pump import (impdp)
    ├── log_persistence.py           # Disk-based log persistence per task
    ├── validation.py                # Pre-checks (user, group, dir, packages)
    ├── oracle_user_setup.py         # Create oracle user + oinstall group
    ├── mount_point.py               # Create /u01 mount point
    ├── packages.py                  # Install ksh, git, unzip
    ├── profile.py                   # Create/update .profile
    ├── java.py                      # Java installation
    ├── oracle_client.py             # Oracle client detection
    └── utils.py                     # shell_escape(), sed_escape()
```

## Prerequisites

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) package manager
- SSH access to target Linux servers
- Root privileges on target servers