# OFSAA Automation Flow (Step‑by‑Step)

This document explains how the automated OFSAA setup runs from Step 1 through envCheck, and where each step is implemented.

## Entry Point
- **API endpoint**: `POST /api/installation/start`
- **Backend orchestrator**: `backend/routers/installation.py` → `run_installation_process(...)`
- **SSH execution**: `backend/services/ssh_service.py`

## Step 1 — Oracle User + Group
- **Purpose**: Ensure `oinstall` group and `oracle` user exist.
- **Code**: `backend/services/oracle_user_setup.py`
- **Behavior**:
  - If group/user exists → skip
  - Uses `groupadd -f oinstall` to avoid failure if group exists

## Step 2 — Mount Point `/u01`
- **Purpose**: Ensure `/u01` and base subdirs exist.
- **Code**: `backend/services/mount_point.py`
- **Behavior**:
  - If `/u01` and subdirs exist → skip ownership changes
  - Creates `/u01/OFSAA/FICHOME`, `/u01/OFSAA/FTPSHARE`, `/u01/installer_kit` if missing

## Step 3 — Packages
- **Purpose**: Ensure `ksh`, `git`, `unzip` exist.
- **Code**: `backend/services/packages.py`
- **Behavior**:
  - Checks each package
  - Installs only missing ones

## Step 4 — Oracle `.profile`
- **Purpose**: Create `/home/oracle/.profile` with standard template.
- **Code**: `backend/services/profile.py`
- **Behavior**:
  - If profile exists → skip
  - If profile contains stray `EOF` → rebuild

## Step 5 — Java
- **Purpose**: Ensure Java 11 is installed under `/u01/jdk-11.0.16`
- **Code**: `backend/services/java.py`
- **Behavior**:
  - If already installed → skip download
  - Updates `JAVA_HOME` and `JAVA_BIN` in profile

## Step 6 — OFSAA Directories
- **Purpose**: Ensure OFSAA directory structure exists.
- **Code**: `backend/services/java.py` → `create_ofsaa_directories(...)`
- **Behavior**:
  - If `/u01/OFSAA/FICHOME` + `/u01/OFSAA/FTPSHARE` exist → skip

## Step 7 — Oracle Client Detection
- **Purpose**: Detect client and set `ORACLE_HOME` / `TNS_ADMIN`.
- **Code**: `backend/services/oracle_client.py`
- **Behavior**:
  - If profile already has valid ORACLE_HOME and sqlplus exists → skip
  - Prefer `/u01/app/oracle/product/19.0.0/client_1` if present

## Step 8 — Installer Kit + envCheck
- **Purpose**: Ensure installer kit is present and run `envCheck.sh`.
- **Code**: `backend/services/installer.py`
- **Flow**:
  1. If `OFS_BD_PACK` already exists → skip download/unzip
  2. Enforce permissions `chmod -R 775 /u01/installer_kit/OFS_BD_PACK`
  3. Fix `.profile` (remove stray `EOF`)
  4. Force `ORACLE_HOME` + `TNS_ADMIN`
  5. Build sqlplus wrapper to force SYSDBA if `SYS` is used
  6. Run envCheck in a pseudo‑TTY (via `script -q -c`) to satisfy `stty`

### DB Credential Handling
Before envCheck runs, the backend asks for DB credentials in the UI:
- Username
- Password
- SID/Service

These are piped into envCheck automatically to avoid prompt timing issues.

## Step 9 — Profile Overrides
- **Purpose**: Apply UI overrides for `FIC_HOME`, `JAVA_HOME`, `JAVA_BIN`, `ORACLE_SID`
- **Code**: `backend/services/profile.py` → `update_profile_with_custom_variables(...)`

## Step 10 — Verify Profile
- **Purpose**: Source `.profile` and print environment summary.
- **Code**: `backend/services/profile.py` → `verify_profile_setup(...)`

---

## Common Failure Reasons (Observed)
1. **OS version check fails**  
   envCheck expects RHEL 7/8; RHEL 9 shows FAIL.

2. **SYS requires SYSDBA**  
   This is handled via sqlplus wrapper. If you still see ORA‑28009, verify wrapper path is in PATH.

3. **stty errors**  
   envCheck uses `stty`. Running via pseudo‑TTY avoids this.

---

## UI Behavior
- Live output: `frontend/src/app/logs/[taskId]/page.tsx`
- WebSocket: `ws://localhost:8000/ws/{task_id}`
- Prompts are shown in the UI input box, not the terminal.

---

If you want this guide expanded or updated, just say the word.
