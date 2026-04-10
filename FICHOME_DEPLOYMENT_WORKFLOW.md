# Deployment Workflow

## Overview
The **Deployment** tab provides two independent actions on a single page with shared SSH connection:

1. **EAR Creation & Exploding** — Builds FICHOME EAR/WAR and deploys as exploded archives to the WebLogic domain
2. **WebLogic Datasource Creation** — Creates JDBC datasources in WebLogic via WLST

Each section has a checkbox toggle and its own submit button. Both share the same SSH connection fields.

---

## Prerequisites

- **FICHOME Build Directory**: `/u01/OFSAA/FICHOME/ficweb`
- **ant.sh Script**: `/u01/OFSAA/FICHOME/ficweb/ant.sh`
- **WebLogic Domain**: Provided via UI field `weblogic_domain_home`

---

## API

**Endpoint**: `POST /api/installation/deploy-fichome`

**Required Fields**:
| Field | Description |
|-------|-------------|
| `host` | Target server IP |
| `username` | SSH username (typically root) |
| `password` | SSH password |
| `db_sys_password` | Oracle SYS password for sqlplus |
| `db_jdbc_service` | Database service name (e.g., FLEXPDB1) |
| `config_schema_name` | CONFIG schema name (from last installed module) |
| `atomic_schema_name` | ATOMIC schema name (from last installed module) |
| `weblogic_domain_home` | WebLogic domain home path (from UI) |

**Optional Fields**:
| Field | Default | Description |
|-------|---------|-------------|
| `db_jdbc_host` | Same as `host` | Database host |
| `db_jdbc_port` | 1521 | Database port |

---

## Steps (4 Steps)

### STEP 1: Grant Database Privileges

Executes SQL scripts from Git to grant privileges to ATOMIC and CONFIG schema users.

- SQL files: `<REPO_DIR>/ofsaa_auto_installation/configuration/privileges_atomic_user.sql` and `privileges_config_user.sql`
- Replaces `{SCHEMA_NAME}` placeholder with actual schema name
- Connection: `sqlplus "sys/<db_sys_password>@<host>:<port>/<service> as sysdba"`
- **Non-blocking**: Shows `[WARN]` if files not found or execution fails, does NOT stop deployment

---

### STEP 2: Run EAR Creation & Exploding Script

A single bash script is written to `/tmp/fichome_deploy.sh` and executed as `oracle` user via SSH. The script does:

```bash
#!/bin/bash
set -e

FICWEB="/u01/OFSAA/FICHOME/ficweb"
DOMAIN="<weblogic_domain_home from UI>"
APP_DIR="${DOMAIN}/applications"
EAR_DIR="${APP_DIR}/FICHOME.ear"
WAR_DIR="${EAR_DIR}/FICHOME.war"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Step 1: Timestamped backup of existing EAR/WAR in ficweb
cd ${FICWEB}
[ -f FICHOME.ear ] && mv FICHOME.ear FICHOME.ear_bkp_${TIMESTAMP}
[ -f FICHOME.war ] && mv FICHOME.war FICHOME.war_bkp_${TIMESTAMP}

# Step 2: Rebuild with ant.sh
source /home/oracle/.profile >/dev/null 2>&1 || true
./ant.sh
chmod -R 777 FICHOME.war FICHOME.ear

# Step 3: Delete existing EAR directory in domain (if exists)
if [ -d "${EAR_DIR}" ]; then
    rm -rf "${EAR_DIR}"
fi

# Step 4: Create exploded EAR directory
mkdir -p ${EAR_DIR}
chmod -R 777 ${APP_DIR}

# Step 5: Extract EAR contents
cp ${FICWEB}/FICHOME.ear ${EAR_DIR}/
cd ${EAR_DIR}
jar -xvf FICHOME.ear
rm -rf FICHOME.ear FICHOME.war

# Step 6: Extract WAR into exploded WAR directory
mkdir -p ${WAR_DIR}
cp ${FICWEB}/FICHOME.war ${WAR_DIR}/
cd ${WAR_DIR}
jar -xvf FICHOME.war
rm -f FICHOME.war

# Step 7: Final permissions
chmod -R 777 ${EAR_DIR}
```

**Key behaviors**:
- Backups use timestamp: `FICHOME.ear_bkp_20260410_143022`
- Existing `EAR_DIR` in domain is **deleted** before fresh deploy
- Script runs as `oracle` user (`su - oracle -c 'bash /tmp/fichome_deploy.sh'`)
- Timeout: 1200 seconds (20 minutes, dominated by `ant.sh` build)
- Script is cleaned up after execution (`rm -f /tmp/fichome_deploy.sh`)
- Output streamed to WebSocket in real-time

---

### STEP 3: Run startofsaa.sh

Post-build startup script from Git repository.

- Source: `<REPO_DIR>/ofsaa_auto_installation/configuration/startofsaa.sh`
- Copied to: `/u01/startofsaa.sh`
- Executed as: `oracle` user
- **BLOCKING**: Failure stops deployment
- Timeout: 600 seconds

---

### STEP 4: Run checkofsaa.sh

Post-build health check script from Git repository.

- Source: `<REPO_DIR>/ofsaa_auto_installation/configuration/checkofsaa.sh`
- Copied to: `/u01/checkofsaa.sh`
- Executed as: `oracle` user
- **BLOCKING**: Failure stops deployment
- Timeout: 600 seconds

---

## Final Directory Structure

### Source (Build Location)
```
/u01/OFSAA/FICHOME/ficweb/
├── ant.sh
├── FICHOME.ear                     (newly built)
├── FICHOME.war                     (newly built)
├── FICHOME.ear_bkp_20260410_143022 (timestamped backup)
└── FICHOME.war_bkp_20260410_143022 (timestamped backup)
```

### Target (WebLogic Domain - Exploded)
```
${WEBLOGIC_DOMAIN_HOME}/applications/
└── FICHOME.ear/                    (exploded EAR)
    ├── META-INF/
    ├── FICHOME.war/                (exploded WAR)
    │   ├── WEB-INF/
    │   ├── jsp/
    │   └── [web resources]
    └── [other EAR contents]
```

---

## Timeline

| Step | Task | Duration |
|------|------|----------|
| 1 | Grant DB privileges | ~5 sec |
| 2 | EAR creation & exploding (backup + ant.sh + deploy) | 10-20 min |
| 3 | startofsaa.sh | 1-5 min |
| 4 | checkofsaa.sh | 1-5 min |
| **Total** | | **~15-25 minutes** |

---

## WebLogic Datasource Creation (Separate Endpoint)

Datasource creation is a **standalone feature** available as a separate tab in the UI. It creates JDBC datasources in WebLogic via WLST (WebLogic Scripting Tool).

### API

**Endpoint**: `POST /api/installation/create-datasources`  
**Status**: `GET /api/installation/create-datasources/status/{task_id}`  
**WebSocket**: `ws://{host}/ws/{task_id}` for real-time logs

### Request Schema

```json
{
  "host": "192.168.1.100",
  "username": "root",
  "password": "secret",
  "admin_url": "t3://localhost:7001",
  "weblogic_username": "weblogic",
  "weblogic_password": "Welcome#1",
  "datasources": [
    {
      "ds_name": "OFSAADataSource",
      "jndi_name": "jdbc/OFSAADataSource",
      "db_url": "jdbc:oracle:thin:@//dbhost:1521/FLEXPDB1",
      "db_user": "OFSCONFIG",
      "db_password": "Welcome#123",
      "targets": ["AdminServer", "ofsaa_server1"]
    }
  ]
}
```

### How It Works

For each datasource in the array:

1. **Generates WLST script** — bash wrapper + embedded Python WLST script written to `/tmp/create_ds_<ds_name>.sh`
2. **Connects to WebLogic Admin** — via `t3://` protocol using provided admin credentials
3. **Creates or updates datasource** — sets JNDI name, JDBC URL, credentials, targets
4. **Targets managed servers** — assigns datasource to specified WebLogic servers/clusters
5. **Activates changes** — commits via WLST `activate()`
6. **Cleanup** — removes temp script after execution

### Execution

- Script runs as `oracle` user on the target app server via SSH
- Each datasource is processed sequentially
- Progress tracked per datasource (e.g., `[2/5] OFSAADataSource`)
- Output streamed to WebSocket in real-time

### Frontend

Accessible via the **"Datasources"** tab in the main UI. Features:
- Separate SSH connection fields (host, username, password)
- WebLogic admin fields (admin URL, username, password)
- Dynamic datasource rows (add/remove)
- Each row: datasource name, JNDI name, DB URL, DB user, DB password, targets
- Independent submit — does not require installation to be running
- Redirects to log viewer on submit


