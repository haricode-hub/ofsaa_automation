# FICHOME Deployment Workflow - Complete Guide

## Overview
This document outlines the complete deployment workflow for FICHOME to the WebLogic domain. The workflow includes extracting WebLogic domain configuration, building FICHOME with ant.sh, and deploying to the applications directory.

---

## Prerequisites

### Required Files & Directories
- **installconfig.xml**: `/u01/Installation_Kit/BD_PACK_INSTALLATION_KIT/OFS_BD_PACK/OFS_AAI/conf/OFSAAI_InstallConfig.xml`
- **Oracle Middleware**: `/u01/Oracle/Middleware`
- **FICHOME Build Directory**: `/u01/OFSAA/FICHOME/ficweb`
- **ant.sh Script**: `/u01/OFSAA/FICHOME/ficweb/ant.sh`

### Verification Commands
```bash
# Verify installconfig.xml exists
test -f /u01/Installation_Kit/BD_PACK_INSTALLATION_KIT/OFS_BD_PACK/OFS_AAI/conf/OFSAAI_InstallConfig.xml

# Verify Oracle Middleware exists
test -d /u01/Oracle/Middleware

# Verify ficweb directory exists
test -d /u01/OFSAA/FICHOME/ficweb
```

---

## Deployment Steps (17 Total Steps)

### STEP 1: Grant Database Privileges

**Objective**: Execute SQL scripts from Git to grant table and sequence privileges to ATOMIC and CONFIG schema users

**Required Parameters from UI**:
- `db_sys_password`: Oracle SYS user password for database connection
- Schema names based on **last installed module**:
  - If **BD-only**: `schema_config_schema_name` + `schema_atomic_schema_name`
  - If **BD+ECM**: `ecm_schema_config_schema_name` + `ecm_schema_atomic_schema_name`
  - If **BD+ECM+SANC**: `sanc_schema_config_schema_name` + `sanc_schema_atomic_schema_name`

**SQL Files Location**:
- Git Path: `ofsaa_auto_installation/configuration/`
- File 1: `privileges_atomic_user.sql` (grants privileges to ATOMIC schema user)
- File 2: `privileges_config_user.sql` (grants privileges to CONFIG schema user)

**Execution Steps**:

**Step 1a: Grant ATOMIC User Privileges**

```bash
# Fetch SQL file from Git
cat <REPO_DIR>/ofsaa_auto_installation/configuration/privileges_atomic_user.sql

# Replace {SCHEMA_NAME} placeholder with ATOMIC schema name from UI
# Execute via sqlplus
sqlplus "sys/<db_sys_password>@<db_jdbc_host>:<db_jdbc_port>/<db_jdbc_service> as sysdba" <<'EOGRANT'
  [SQL content with ATOMIC schema name]
  EXIT;
EOGRANT
```

**Step 1b: Grant CONFIG User Privileges**

```bash
# Fetch SQL file from Git
cat <REPO_DIR>/ofsaa_auto_installation/configuration/privileges_config_user.sql

# Replace {SCHEMA_NAME} placeholder with CONFIG schema name from UI
# Execute via sqlplus
sqlplus "sys/<db_sys_password>@<db_jdbc_host>:<db_jdbc_port>/<db_jdbc_service> as sysdba" <<'EOGRANT'
  [SQL content with CONFIG schema name]
  EXIT;
EOGRANT
```

**Important Notes**:
- SQL files fetched from Git repo (same location as installer kits)
- Placeholder replacement: `{SCHEMA_NAME}` → actual schema name from UI
- Connection: SYS user with db_sys_password (same as used for backup/restore)
- Host/Port: Same as `db_jdbc_host` / `db_jdbc_port` / `db_jdbc_service`
- Error Handling: **Non-blocking** - shows [WARN] if SQL files not found or execution fails, but does NOT stop deployment

**Result**:
- ATOMIC user privileges granted for schema operations
- CONFIG user privileges granted for configuration management
- Installation continues even if privilege grant fails

---

### STEP 2: Extract WEBLOGIC_DOMAIN_HOME from installconfig.xml

**Objective**: Dynamically get the WebLogic domain path from the configuration file

**Command**:
```bash
WEBLOGIC_DOMAIN_HOME=$(grep -i 'WEBLOGIC_DOMAIN_HOME' /u01/Installation_Kit/BD_PACK_INSTALLATION_KIT/OFS_BD_PACK/OFS_AAI/conf/OFSAAI_InstallConfig.xml | \
sed -n 's/.*<InteractionVariable[^>]*name["'"'"']*WEBLOGIC_DOMAIN_HOME["'"'"']*[^>]*>\([^<]*\)<.*/\1/ip' | head -n 1)

echo "Extracted WEBLOGIC_DOMAIN_HOME: $WEBLOGIC_DOMAIN_HOME"
```

**Expected Output**:
```
Extracted WEBLOGIC_DOMAIN_HOME: /u01/Oracle/Middleware/Oracle_Home/user_projects/domains/DEMO_OFSAA_DOMAIN
```

**Purpose**: 
- Dynamically retrieve the WebLogic domain location
- Store in variable for use in all subsequent steps
- Avoids hardcoding paths, supports multiple domain configurations

**Error Handling**:
- If variable is empty, stop deployment with error message
- Log: `[ERROR] WEBLOGIC_DOMAIN_HOME not found or empty in installconfig.xml`

---

### STEP 3: Navigate to FICHOME Build Directory

**Objective**: Move to the deployment source directory

**Command**:
```bash
cd /u01/OFSAA/FICHOME/ficweb
```

**Purpose**:
- Change to directory containing FICHOME source and ant.sh
- All subsequent build operations use this location

---

### STEP 4: Backup Existing EAR & WAR Files

**Objective**: Backup current deployable files before rebuilding

**Commands**:
```bash
cd /u01/OFSAA/FICHOME/ficweb

# Backup existing FICHOME.ear if it exists
[ -f FICHOME.ear ] && mv FICHOME.ear FICHOME.ear_bkp || true

# Backup existing FICHOME.war if it exists
[ -f FICHOME.war ] && mv FICHOME.war FICHOME.war_bkp || true
```

**Example Output**:
```
/u01/OFSAA/FICHOME/ficweb>mv FICHOME.ear FICHOME.ear_bkp
/u01/OFSAA/FICHOME/ficweb>mv FICHOME.war FICHOME.war_bkp
```

**Important Notes**:
- Only backup if files exist (using `[ -f filename ]` checks)
- Backup naming: Simple names with `_bkp` suffix
- `|| true` ensures step doesn't fail if files don't exist

---

### STEP 5: Rebuild Application using ant.sh

**Objective**: Generate fresh EAR and WAR files from source

**Command**:
```bash
cd /u01/OFSAA/FICHOME/ficweb
./ant.sh
```

**Expected Output**:
```
BUILD SUCCESSFUL
Total time: 10-20 minutes
```

**Timeout**: 20 minutes (1200 seconds)

**Build Artifacts Created**:
- `/u01/OFSAA/FICHOME/ficweb/FICHOME.ear` (Enterprise Archive)
- `/u01/OFSAA/FICHOME/ficweb/FICHOME.war` (Web Archive)

**Error Handling**:
- If ant.sh fails: Log error and stop deployment
- If build artifacts not found: Stop with error

---

### STEP 6: Set Permissions on Generated Files

**Objective**: Ensure proper access permissions for newly generated files

**Commands**:
```bash
cd /u01/OFSAA/FICHOME/ficweb
chmod -R 777 FICHOME.war FICHOME.ear
```

**Permission Details**:
- **777** = `rwxrwxrwx` (read, write, execute for all)
- Ensures oracle user and others can access files

---

### STEP 7: Navigate to WebLogic Domain Directory

**Objective**: Move to deployment target location

**Command**:
```bash
cd $WEBLOGIC_DOMAIN_HOME
```

**Expands to**:
```bash
cd /u01/Oracle/Middleware/Oracle_Home/user_projects/domains/DEMO_OFSAA_DOMAIN
```

**Purpose**:
- Change to WebLogic domain root directory
- Prepare for applications folder creation

---

### STEP 8: Create Applications Directory Structure for Deployment

**Objective**: Prepare deployment folder for FICHOME extraction

**Commands**:
```bash
cd $WEBLOGIC_DOMAIN_HOME

# Create FICHOME.ear directory structure
mkdir -p applications/FICHOME.ear

# Set permissions on applications directory
chmod -R 777 applications
```

**Result**:
```
${WEBLOGIC_DOMAIN_HOME}/applications/
└── FICHOME.ear/        (directory for extracted EAR contents)
```

---

### STEP 9: Copy EAR File to WebLogic Domain

**Objective**: Move newly generated EAR into WebLogic domain

**Command**:
```bash
cp /u01/OFSAA/FICHOME/ficweb/FICHOME.ear $WEBLOGIC_DOMAIN_HOME/applications/FICHOME.ear
```

**Expands to**:
```bash
cp /u01/OFSAA/FICHOME/ficweb/FICHOME.ear /u01/Oracle/Middleware/Oracle_Home/user_projects/domains/DEMO_OFSAA_DOMAIN/applications/FICHOME.ear
```

**Purpose**:
- Copy EAR archive from build location to domain
- Note: Overwrites the directory created in STEP 7

---

### STEP 10: Extract EAR File Contents

**Objective**: Unpack EAR archive for modification and deployment

**Commands**:
```bash
cd $WEBLOGIC_DOMAIN_HOME/applications/FICHOME.ear

# Extract all EAR contents using jar command
jar -xvf FICHOME.ear
```

**Result**:
```
${WEBLOGIC_DOMAIN_HOME}/applications/FICHOME.ear/
├── FICHOME.ear                (archive file)
├── FICHOME.war                (extracted web archive)
├── META-INF/                  (EAR metadata)
└── [other extracted contents]
```

**Purpose**:
- Unpack nested WAR file within EAR
- Prepare for subsequent WAR extraction

---

### STEP 11: Remove Existing EAR & WAR Archives

**Objective**: Clean old packaged files before creating new structure

**Commands**:
```bash
cd $WEBLOGIC_DOMAIN_HOME/applications/FICHOME.ear

# Remove the archive files (keep extracted contents)
rm -rf FICHOME.ear FICHOME.war
```

**Purpose**:
- Remove archive files after extraction
- Prepare for fresh WAR file from source

---

### STEP 12: Create WAR Directory

**Objective**: Prepare folder for WAR extraction

**Command**:
```bash
mkdir FICHOME.war
```

**Purpose**:
- Create directory to hold extracted WAR contents
- Will contain the web application files

---

### STEP 13: Copy New WAR File

**Objective**: Place updated WAR inside EAR structure

**Command**:
```bash
cp /u01/OFSAA/FICHOME/ficweb/FICHOME.war $WEBLOGIC_DOMAIN_HOME/applications/FICHOME.ear/FICHOME.war
```

**Expands to**:
```bash
cp /u01/OFSAA/FICHOME/ficweb/FICHOME.war /u01/Oracle/Middleware/Oracle_Home/user_projects/domains/DEMO_OFSAA_DOMAIN/applications/FICHOME.ear/FICHOME.war
```

**Purpose**:
- Copy newly built WAR into extracted EAR directory

---

### STEP 14: Extract WAR File Contents

**Objective**: Unpack WAR archive for deployment

**Commands**:
```bash
cd $WEBLOGIC_DOMAIN_HOME/applications/FICHOME.ear/FICHOME.war

# Extract WAR contents
jar -xvf FICHOME.war
```

**Result**:
```
${WEBLOGIC_DOMAIN_HOME}/applications/FICHOME.ear/FICHOME.war/
├── FICHOME.war                (archive file)
├── WEB-INF/                   (web application metadata)
├── jsp/                       (JSP files)
├── classes/                   (compiled classes)
└── [other web resources]
```

**Purpose**:
- Unpack web application files for WebLogic deployment
- Makes application ready for server startup

---

### STEP 15: Set Final Permissions

**Objective**: Ensure proper permissions for deployment and WebLogic access

**Commands**:
```bash
cd $WEBLOGIC_DOMAIN_HOME/applications

# Set full permissions on entire FICHOME application structure
chmod -R 777 FICHOME.ear
```

**Permission Details**:
- **777** = `rwxrwxrwx` (read, write, execute for all)
- WebLogic server can access all files for deployment

---

### STEP 16: Run startofsaa.sh

**Objective**: Copy and execute post-deployment startup script from Git repository

**Script Source**:
- Git Path: `<REPO_DIR>/ofsaa_auto_installation/configuration/startofsaa.sh`
- Destination: `/u01/startofsaa.sh`
- Execution User: `oracle`

**Execution Flow**:
1. Check if script exists in Git repository
2. Copy script to `/u01/startofsaa.sh`
3. Set executable permissions (`chmod 755`)
4. Execute as `oracle` user: `sudo -u oracle bash /u01/startofsaa.sh`
5. Stream full output to WebSocket (real-time logs)

**Error Handling**:
- **BLOCKING**: If script file not found, execution fails, or returns error code → deployment stops
- Returns error message and logs to user via WebSocket
- Cannot be skipped or continued - must fix script issues and retry

**Timeout**: 600 seconds (10 minutes)

**Typical Output**:
```
[FICHOME] STEP 16: Running startofsaa.sh
[OK] startofsaa.sh copied to /u01
[FICHOME] STEP 16: <output from script>
[OK] STEP 16: startofsaa.sh executed successfully
```

---

### STEP 17: Run checkofsaa.sh

**Objective**: Copy and execute post-deployment health check script from Git repository

**Script Source**:
- Git Path: `<REPO_DIR>/ofsaa_auto_installation/configuration/checkofsaa.sh`
- Destination: `/u01/checkofsaa.sh`
- Execution User: `oracle`

**Execution Flow**:
1. Check if script exists in Git repository
2. Copy script to `/u01/checkofsaa.sh`
3. Set executable permissions (`chmod 755`)
4. Execute as `oracle` user: `sudo -u oracle bash /u01/checkofsaa.sh`
5. Stream full output to WebSocket (real-time logs)

**Error Handling**:
- **BLOCKING**: If script file not found, execution fails, or returns error code → deployment stops
- Returns error message and logs to user via WebSocket
- Cannot be skipped or continued - must fix script issues and retry

**Timeout**: 600 seconds (10 minutes)

**Typical Output**:
```
[FICHOME] STEP 17: Running checkofsaa.sh
[OK] checkofsaa.sh copied to /u01
[FICHOME] STEP 17: <output from script>
[OK] STEP 17: checkofsaa.sh executed successfully
```

---

## Deployment Summary

**Total Steps**: 17

| Phase | Steps | Purpose |
|-------|-------|---------|
| **Database Setup** | 1 | Grant privileges for schema users |
| **Build & Prepare** | 2-6 | Extract config, backup, rebuild, set permissions |
| **WebLogic Deploy** | 7-15 | Deploy EAR/WAR to domain, extract, finalize |
| **Post-Deployment** | 16-17 | Startup and health verification scripts |

**Success Criteria**:
- ✅ All 17 steps complete without errors
- ✅ Both post-deployment scripts (16-17) execute successfully
- ✅ Full output logged to WebSocket
- ✅ FICHOME.ear/FICHOME.war properly deployed to WebLogic domain

**Failure Recovery**:
- If any step fails (blocking), deployment stops immediately
- User receives error message and logs of failed step
- Examine error, fix root cause, retry deployment
- First retry attempt is automatic; second retry if needed requires manual intervention

**Purpose**:
- Ensure WebLogic server can read and deploy extracted application
- Allow all users to modify files if needed during operation

---

## Complete Workflow Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: Extract WEBLOGIC_DOMAIN_HOME from installconfig.xml         │
│ Result: $WEBLOGIC_DOMAIN_HOME variable set                          │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: Navigate to FICHOME Build Directory                         │
│ cd /u01/OFSAA/FICHOME/ficweb                                        │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: Backup Existing EAR/WAR                                     │
│ mv FICHOME.ear → FICHOME.ear_bkp                                    │
│ mv FICHOME.war → FICHOME.war_bkp                                    │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: Rebuild with ant.sh                                         │
│ ./ant.sh (generates fresh FICHOME.ear & FICHOME.war)                │
│ Duration: 10-20 minutes                                              │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 5: Set Permissions on Generated Files                          │
│ chmod -R 777 FICHOME.war FICHOME.ear                                │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 6: Navigate to WebLogic Domain Directory                       │
│ cd $WEBLOGIC_DOMAIN_HOME                                            │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 7: Create Applications Directory Structure                     │
│ mkdir -p applications/FICHOME.ear                                   │
│ chmod -R 777 applications                                           │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 8: Copy EAR File to WebLogic Domain                            │
│ cp /u01/OFSAA/FICHOME/ficweb/FICHOME.ear                            │
│    → $WEBLOGIC_DOMAIN_HOME/applications/FICHOME.ear                 │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 9: Extract EAR File Contents                                   │
│ cd $WEBLOGIC_DOMAIN_HOME/applications/FICHOME.ear                   │
│ jar -xvf FICHOME.ear                                                │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 10: Remove Existing EAR & WAR Archives                         │
│ rm -rf FICHOME.ear FICHOME.war                                      │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 11: Create WAR Directory                                       │
│ mkdir FICHOME.war                                                   │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 12: Copy New WAR File                                          │
│ cp /u01/OFSAA/FICHOME/ficweb/FICHOME.war                            │
│    → $WEBLOGIC_DOMAIN_HOME/applications/FICHOME.ear/FICHOME.war     │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 13: Extract WAR File Contents                                  │
│ cd $WEBLOGIC_DOMAIN_HOME/applications/FICHOME.ear/FICHOME.war       │
│ jar -xvf FICHOME.war                                                │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 14: Set Final Permissions                                      │
│ cd $WEBLOGIC_DOMAIN_HOME/applications                                │
│ chmod -R 777 FICHOME.ear                                            │
└─────────────────────────────────────────────────────────────────────┘
                          ↓
                    ✅ EAR/WAR EXTRACTION & DEPLOYMENT COMPLETE
```

---

## Final Directory Structure

### Source Directory (Build Location)
```
/u01/OFSAA/FICHOME/ficweb/
├── ant.sh                          (build script)
├── build/                          (ant build output)
├── FICHOME.ear                     (✅ NEWLY BUILT)
├── FICHOME.war                     (✅ NEWLY BUILT)
├── FICHOME.ear_bkp                 (backup from previous build)
├── FICHOME.war_bkp                 (backup from previous build)
└── [source files...]
```

### Target Directory (Extracted & Deployed)
```
${WEBLOGIC_DOMAIN_HOME}/applications/
└── FICHOME.ear/                    (extracted EAR directory)
    ├── META-INF/                   (EAR metadata)
    ├── FICHOME.war/                (extracted WAR directory)
    │   ├── WEB-INF/
    │   ├── jsp/
    │   ├── classes/
    │   └── [web resources]
    └── [other extracted EAR contents]
```

**Example Full Paths**:
```
Source:
/u01/OFSAA/FICHOME/ficweb/FICHOME.ear
/u01/OFSAA/FICHOME/ficweb/FICHOME.war

Target (Extracted):
/u01/Oracle/Middleware/Oracle_Home/user_projects/domains/DEMO_OFSAA_DOMAIN/applications/FICHOME.ear/
/u01/Oracle/Middleware/Oracle_Home/user_projects/domains/DEMO_OFSAA_DOMAIN/applications/FICHOME.ear/FICHOME.war/
```

---

## Error Handling & Recovery

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `WEBLOGIC_DOMAIN_HOME not found` | installconfig.xml missing or invalid | Verify file exists and contains WEBLOGIC_DOMAIN_HOME |
| `Oracle Middleware not found` | WebLogic not installed | Install Oracle Middleware at `/u01/Oracle/Middleware` |
| `ant.sh build failed` | Source code issues or missing dependencies | Check build logs, resolve Java/classpath issues |
| `dist/FICHOME.ear not found` | Build did not complete successfully | Re-run ant.sh, check for build errors |
| `Permission denied` when copying | Incorrect file permissions | Run as oracle user or with appropriate sudo |

### Retry Logic

**Automatic Retry**: On first failure, entire deployment sequence (Steps 4-7) is retried once

**Conditions**:
- Step 4 (backup) fails → Retry entire sequence
- Step 5 (ant.sh build) fails → Retry entire sequence
- Step 6 (copy files) fails → Retry entire sequence
- Step 7 (permissions) fails → Continue anyway (non-blocking warning)

**After Second Failure**: Mark as [WARN], do NOT block installation

---

## Verification Commands

### Verify Deployment Success
```bash
# Check files exist in WebLogic domain
ls -lh ${WEBLOGIC_DOMAIN_HOME}/applications/FICHOME.*

# Check file permissions
stat ${WEBLOGIC_DOMAIN_HOME}/applications/FICHOME.ear
stat ${WEBLOGIC_DOMAIN_HOME}/applications/FICHOME.war

# Check ownership
ls -ln ${WEBLOGIC_DOMAIN_HOME}/applications/FICHOME.*
```

### Expected Output
```
-rw-r--r-- 1 oracle oinstall 245M Mar 23 15:35 /u01/Oracle/Middleware/Oracle_Home/user_projects/domains/DEMO_OFSAA_DOMAIN/applications/FICHOME.ear
-rw-r--r-- 1 oracle oinstall  85M Mar 23 15:36 /u01/Oracle/Middleware/Oracle_Home/user_projects/domains/DEMO_OFSAA_DOMAIN/applications/FICHOME.war
```

---

## Timeline & Duration

| Step | Task | Duration | Notes |
|------|------|----------|-------|
| 1 | Extract domain path | <1 sec | Parse XML, extract variable |
| 2 | Navigate to ficweb | <1 sec | Directory change |
| 3 | Backup EAR/WAR | 2 sec | Rename existing artifacts |
| 4 | Build ant.sh | 10-20 min | **LONGEST STEP** - compilation |
| 5 | Set permissions | 1 sec | chmod command |
| 6 | Navigate to domain | <1 sec | cd command |
| 7 | Create APP dir | 1 sec | mkdir + chmod |
| 8 | Copy EAR | 5 sec | File copy |
| 9 | Extract EAR | 3 sec | jar command |
| 10 | Remove archives | 1 sec | rm command |
| 11 | Create WAR dir | <1 sec | mkdir command |
| 12 | Copy WAR | 3 sec | File copy |
| 13 | Extract WAR | 2 sec | jar command |
| 14 | Set final perms | 1 sec | chmod command |
| **Total** | **Complete workflow** | **15-25 minutes** | Controlled by ant.sh build time |

---

## Integration Points

### When FICHOME Deployment is Triggered

**Scenario 1: BD-Only Installation**
```
BD Pack setup.sh → BD Backup → FICHOME Deployment
```

**Scenario 2: BD+ECM Installation**
```
BD Pack → ECM → ECM Backup → FICHOME Deployment
```

**Scenario 3: BD+SANC or BD+ECM+SANC**
```
Final Module (SANC) → SANC Backup → FICHOME Deployment
```

---

## Key Points Summary

✅ **Always extract WEBLOGIC_DOMAIN_HOME** before any directory operations  
✅ **Navigate to ficweb first** for backup and build operations  
✅ **Backup in ficweb directory** with simple naming (`_bkp` suffix)  
✅ **Build with ant.sh** generates fresh EAR/WAR files  
✅ **Set permissions 777** on newly generated files  
✅ **All subsequent operations use `${WEBLOGIC_DOMAIN_HOME}` variable**  
✅ **Copy EAR to domain** (copies to directory that will be extracted)  
✅ **Extract EAR using jar command** to access FICHOME.war inside  
✅ **Remove archive files** after extraction (keep extracted contents)  
✅ **Copy fresh WAR** into extracted EAR structure  
✅ **Extract WAR contents** to make web application ready for deployment  
✅ **Set final permissions 777** on entire FICHOME.ear directory  
✅ **Automatic single retry** on any step failure  
✅ **Non-blocking failure** - does not stop installation if FICHOME deployment fails  

---

## Support & Troubleshooting

For detailed troubleshooting, check:
- WebLogic domain logs: `${WEBLOGIC_DOMAIN_HOME}/servers/AdminServer/logs/`
- Installation logs: Installation task logs in WebSocket output
- Build logs: ant.sh build output in terminal console

