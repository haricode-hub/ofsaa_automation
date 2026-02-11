# BD_PACK Full Code Walkthrough

This document explains the complete BD_PACK backend flow in this repository, from UI submission to installer execution on the remote host.

## 1. High-Level Architecture

The BD_PACK flow spans these layers:

1. Frontend form submits installation payload.
2. API router starts a background task for installation.
3. Orchestrator (`InstallationService`) delegates to feature services.
4. `InstallerService` performs BD_PACK-specific actions on remote Linux host over SSH.
5. WebSocket streams live output/prompts/status back to UI.

Primary files:

- `frontend/src/components/InstallationForm.tsx`
- `backend/routers/installation.py`
- `backend/services/installation_service.py`
- `backend/services/installer.py`
- `backend/services/ssh_service.py`
- `backend/core/websocket_manager.py`
- `backend/core/config.py`

## 2. Runtime Sequence (BD_PACK Path)

Main orchestrator function:

- `backend/routers/installation.py` -> `run_installation_process(...)`

BD_PACK-relevant phases:

1. Step 8: installer kit prep + environment check.
2. Step 9: apply UI config into 4 BD files + run `osc.sh`.
3. Step 10: run `setup.sh SILENT`.

If any step fails, `handle_failure(...)` marks task failed, writes errors to logs, and pushes failed status via WebSocket.

### 2.1 Complete Ordered Workflow (actual router execution)

Source: `backend/routers/installation.py` -> `run_installation_process(...)`

0. Initialize task state and websocket status.
1. SSH pre-check with up to 3 retries (`test_connection`).
2. Abort if SSH fails after attempt 3.
3. Step 1: create `oracle` user and `oinstall` group.
4. Step 2: create mount point `/u01`.
5. Step 3: install packages (`ksh`, `git`, `unzip`).
6. Step 4: create `.profile`.
7. Step 5: install Java.
8. Step 5.1: update JAVA profile if Java path returned.
9. Step 6: create OFSAA directory structure.
10. Step 7: check Oracle client and update profile.
11. Step 8:
    - download/extract installer kit
    - set installer permissions
    - log profile sourcing marker
    - run envCheck with interactive prompt handling
12. Step 9:
    - patch 4 BD config files from UI values
    - copy patched files into extracted kit paths
    - optional git commit/push
    - run `osc.sh` with interactive prompt handling
13. Step 10:
    - run `setup.sh SILENT` with interactive prompt handling
14. Optional ECM post-BD flow (`if request.install_ecm`):
    - validate mode is `fresh`
    - extract ECM installer
    - apply ECM config files
    - run ECM `osc.sh`
    - run ECM `setup.sh SILENT`
15. Mark task completed and append final success logs.
    - `[OK] osc.sh completed`
    - `[OK] setup.sh SILENT completed`
    - `[OK] Schema creation completed`
    - ECM enabled only:
      - `[OK] ECM installer extraction and config update completed`
      - `[OK] ECM osc.sh completed`
      - `[OK] ECM setup.sh SILENT completed`
16. Exception exits:
    - timeout -> `Installation timed out`
    - unexpected exception -> `Installation failed`
17. Fresh-mode auto-cleanup on Step 8+ failure:
    - remove:
      - `/u01/installer_kit`
      - `/u01/INSTALLER_KIT`
      - `/u01/INSTALLER_KIT_AUTOMATION`
      - `/u01/Installation_Kit`
      - `/u01/OFSAA/FICHOME`
      - `/u01/OFSAA/FTPSHARE`
    - run `/u01/drop_ofsaa_objects.sh` as oracle context when present.

## 3. Configuration Inputs and Defaults

Config is read from environment through `backend/core/config.py`:

- `OFSAA_REPO_URL` -> git URL used for clone/pull.
- `OFSAA_REPO_DIR` -> repo clone path on target host.
- `OFSAA_INSTALLER_ZIP_NAME` -> optional explicit zip name in `BD_PACK`.
- `OFSAA_FAST_CONFIG_APPLY` -> skip pull during config step when enabled.
- `OFSAA_ENABLE_CONFIG_PUSH` -> commit/push patched files when enabled.
- `OFSAA_GIT_USERNAME` / `OFSAA_GIT_PASSWORD` -> optional non-interactive git auth.

## 4. Step 8: Download and Extract Installer

Method:

- `backend/services/installer.py` -> `download_and_extract_installer(...)`

Flow:

1. Ensures `/u01/installer_kit` exists.
2. If `/u01/installer_kit/OFS_BD_PACK` already exists, extraction is skipped (existing kit reused).
3. Prepares repo on remote host:
   - pull if repo exists
   - clone if repo missing
4. Resolves zip from `${REPO_DIR}/BD_PACK`:
   - exact match if `OFSAA_INSTALLER_ZIP_NAME` set
   - else latest `*.zip`
5. Extracts zip into `/u01/installer_kit` as `oracle` user.

Notes:

- Uses `bsdtar` if available, otherwise `unzip`.
- Non-`oracle` login user path uses `sudo -u oracle bash -lc ...` or `su - oracle -c ...`.

## 5. Step 8: Environment Check

Method:

- `backend/services/installer.py` -> `run_environment_check(...)`

Profile sourcing note:

- In router flow (`backend/routers/installation.py`), the system logs:
  - `[INFO] Sourcing /home/oracle/.profile before envCheck`
- In execution command, it actually runs:
  - `source /home/oracle/.profile >/dev/null 2>&1; ...; ./envCheck.sh -s`

Flow:

1. Uses `/u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin/envCheck.sh`.
2. Preflight patches `VerInfo.txt` Linux compatibility to `Linux_VERSION=7,8,9`.
3. Executes `./envCheck.sh -s` in interactive mode.
4. Streams output and prompts live.
5. Treats lines containing `ERROR` or `FAIL` as failure.

Why preflight exists:

- Many kits ship with Linux version list `7,8`; this breaks on OEL/RHEL 9.

## 6. Step 9: Apply UI Config to BD Files

Method:

- `backend/services/installer.py` -> `apply_config_files_from_repo(...)`

This method synchronizes four files using UI payload values, then copies them to kit locations.

### 6.1 Source of truth for patching

Files are patched in repo clone first (under `${REPO_DIR}/BD_PACK`), then copied to extracted kit path:

1. `OFS_BD_SCHEMA_IN.xml`
2. `OFS_BD_PACK.xml`
3. `default.properties`
4. `OFSAAI_InstallConfig.xml`

### 6.2 Destination paths in extracted kit

- `OFS_BD_SCHEMA_IN.xml` -> `/u01/installer_kit/OFS_BD_PACK/schema_creator/conf/OFS_BD_SCHEMA_IN.xml`
- `OFS_BD_PACK.xml` -> `/u01/installer_kit/OFS_BD_PACK/conf/OFS_BD_PACK.xml`
- `default.properties` -> `/u01/installer_kit/OFS_BD_PACK/OFS_AML/conf/default.properties`
- `OFSAAI_InstallConfig.xml` -> `/u01/installer_kit/OFS_BD_PACK/OFS_AAI/conf/OFSAAI_InstallConfig.xml`

Each copy sets:

- owner: `oracle:oinstall`
- mode: `664`

### 6.3 Patch handlers

Used helpers:

- `_patch_ofs_bd_schema_in_repo(...)`
- `_patch_ofs_bd_pack_xml_repo(...)`
- `_patch_default_properties_repo(...)`
- `_patch_ofsaai_install_config_repo(...)`

Each helper:

1. Reads current repo file from target host.
2. Applies regex/text update rules.
3. Compares patched vs original.
4. If changed, writes updated content (after timestamped backup).
5. Returns `changed=True/False` and logs.

### 6.4 Sync summary logging

After all 4 patchers run, logs include one line:

- `UI sync summary: <file>=UPDATED/UNCHANGED ...`

This tells exactly which file changed during that run.

## 7. Step 9: Optional Git Commit/Push

Method:

- `_commit_and_push_repo_changes(...)`

Behavior:

1. Checks if working tree has changes for configured pathspec (`BD_PACK`).
2. If no diff: logs `Repo push skipped: no config changes`.
3. If diff exists:
   - `git add -u -- BD_PACK`
   - commit with predefined message
   - push to origin

Important:

- Push is controlled by `OFSAA_ENABLE_CONFIG_PUSH`.
- If disabled, no remote commit happens even if files are patched locally on host.

## 8. Step 9: Run `osc.sh` (Schema Creator)

Method:

- `run_osc_schema_creator(...)`

Current path candidate:

- `/u01/installer_kit/OFS_BD_PACK/schema_creator/bin/osc.sh`

Flow:

1. Resolves executable path.
2. Preflight scans entire active `OFS_BD_PACK` tree and patches all found `VerInfo.txt` to `Linux_VERSION=7,8,9`.
3. Runs:
   - `./osc.sh -s`
   - fallback `./osc.sh -S`
4. Interactive prompts are routed through WebSocket prompt callback.
5. After execution, reads latest schema_creator log and scans for `ERROR|FAIL` lines.

Special handling:

- Known "schema already exists" signatures are downgraded to warning and can continue.

## 9. Step 10: Run `setup.sh SILENT`

Method:

- `run_setup_silent(...)`

Path candidates (current):

1. `/u01/installer_kit/OFS_BD_PACK/bin/setup.sh`
2. `/u01/INSTALLER_KIT/OFS_BD_PACK/bin/setup.sh`

Execution:

- `./setup.sh SILENT` under oracle context.
- Interactive mode enabled for prompt capture.
- Timeout configured to `36000` seconds (10 hours).

After setup completes/fails:

- `_collect_installation_summary_after_setup(...)` gathers log counts and summary lines.

## 10. WebSocket and Prompt Handling

Router (`installation.py`) registers callbacks:

1. Output callback:
   - Appends live command output to task log.
2. Prompt callback:
   - Sends prompt event to frontend.
   - Sets task status to `waiting_input`.
   - Waits for UI input from queue.
   - Returns to `running` status after reply.

Transport:

- `backend/core/websocket_manager.py` manages task-scoped sockets and input queues.

Prompt detection:

- `backend/services/ssh_service.py` uses keyword + shape rules to classify prompt lines before requesting user input.

## 11. Failure Return to UI with Preserved Inputs

Frontend behavior:

1. Installation form state is persisted in browser localStorage (`ofsaa_install_form_v1`).
2. On page load, form values are restored from localStorage.
3. On logs page, when task status becomes `failed`, UI auto-redirects to `/`.
4. Because state is persisted, users return to form with previously entered values intact.

## 12. Frontend Payload Mapping

Frontend source:

- `frontend/src/components/InstallationForm.tsx`

Current behavior:

- Form fields are sent directly for schema/pack/properties/AAI config.
- `schema_host` is sent from `formData.schema_host` (not host field).
- `pack_app_enable` toggles map to `OFS_BD_PACK.xml` APP enable flags.

## 13. Correctness Guarantees and Boundaries

### What is guaranteed

1. Repo config files are patched from UI values.
2. Patched files are copied to expected kit locations.
3. Copy success is logged per file.
4. Git push is attempted only when enabled and when there is real diff.

### What is not guaranteed

1. A file will not show git update if resulting content is identical.
2. Downstream vendor scripts (`osc.sh`, `setup.sh`) may still fail due to runtime dependencies, DB auth, classpath, or installer internals.

## 14. Frequent Failure Modes and Meaning

1. `SP2-0306` during DB prompt usage:
   - usually malformed DB username input (`SYS AS SYSDBA` instead of `SYS`).
2. `ORA-01017`:
   - invalid credentials at script runtime.
3. `NoClassDefFoundError`:
   - missing/corrupt jar or classpath issue in extracted kit.
4. `Installation timed out`:
   - interactive process exceeded configured timeout.

## 15. Operational Checklist

Before run:

1. Validate repo env vars (`REPO_URL`, `REPO_DIR`).
2. Confirm installer zip exists in `${REPO_DIR}/BD_PACK`.
3. Confirm target host has required tools (`git`, `ksh`, unzip/tar, Java, Oracle client).

During run:

1. Watch for `[OK] Updated kit file: ...` for all 4 files.
2. Watch for `UI sync summary` line.
3. Reply correctly to prompts.

After run:

1. Confirm git push log if push enabled.
2. Inspect generated installer logs for fatal entries.
