# Backup Restore Automation Plan

## Core Rule

- BD: do not take a pre-install backup.
- ECM and SANC: take a new backup only when the latest eligible backup is missing, incomplete, stale, or incompatible.
- No manual cleanup or manual restore path should exist in the normal workflow.

## What Counts As A Proper Backup

A backup is `proper` only if all of these are true:

1. Application backup archive exists and is non-empty.
2. Database dump set exists and is non-empty.
3. Restore metadata SQL exists and is non-empty.
4. Backup manifest exists and is marked `complete`.
5. Manifest values match the current target:
   - pack tag: `BD`, `ECM`, or `SANC`
   - database host/port/service
   - schema names expected for that pack
   - application path/version fingerprint
6. Checksums or file sizes in manifest match the stored artifacts.
7. Backup age is within the allowed freshness window.

## Metadata Clarification

There should be two metadata artifacts in the backup flow:

1. `restore metadata SQL`
   - SQL used before import to recreate database structures needed by restore.
   - This is part of the restore pipeline.
2. `backup manifest`
   - JSON file created by automation.
   - Records tag, timestamp, schemas, DB target, file paths, file sizes, checksums, and backup status.
   - This is what the system should validate before deciding whether a backup is already proper.

## Backup Decision Logic

Before ECM or SANC starts:

1. Find the latest eligible restore point.
2. Validate its manifest and all backup artifacts.
3. If validation passes, reuse the backup and do not take a new one.
4. If validation fails, take a fresh backup automatically.
5. If fresh backup also fails validation, stop the installation and mark state as `backup_invalid`.

## Plan By Scenario

### Plan 1: BD Failure

1. Persist last completed BD step to disk.
2. If BD fails or connection is lost, trigger `BD auto-cleanup`.
3. `BD auto-cleanup` must do all of these automatically:
   - kill Java processes started by OFSAA/WebLogic scope
   - remove installer directories
   - remove partial OFSAA application directories
   - drop BD schemas/tablespaces using automation
   - clear temp/cache if required
4. Run `post-cleanup verification`.
5. If verification fails, retry cleanup a limited number of times.
6. If still not clean, mark task as `cleanup_failed` and block restart.

### Plan 2: ECM Start / ECM Failure

Before ECM starts:

1. Validate the latest BD backup.
2. If BD backup is proper, reuse it.
3. If BD backup is not proper, create a fresh BD backup.
4. Validate the fresh backup before allowing ECM to start.

If ECM fails:

1. Detect stable restore point = `BD`.
2. Run automated rollback:
   - stop relevant processes
   - restore application backup
   - run restore metadata SQL
   - run `impdp` for BD dump set
   - verify schemas, objects, paths, and services
3. Retry rollback automatically if verification fails.
4. If rollback cannot be validated, mark task as `rollback_failed` and block ECM retry.

### Plan 3: SANC Start / SANC Failure

Before SANC starts:

1. Prefer latest ECM backup if ECM is the current stable state.
2. Otherwise use latest BD backup.
3. Validate the chosen backup.
4. If chosen backup is not proper, take a fresh backup for the current stable state.
5. Validate the fresh backup before allowing SANC to start.

If SANC fails:

1. Detect restore point priority:
   - ECM if valid
   - else BD
2. Run automated rollback:
   - stop relevant processes
   - restore application backup for selected tag
   - run restore metadata SQL for selected tag
   - run DB import for selected tag
   - verify final state
3. Retry rollback automatically if needed.
4. If rollback remains invalid, mark task as `rollback_failed` and block SANC retry.

### Plan 4: Connection Loss / Backend Restart

1. Persist state after every major step.
2. Persist these fields:
   - module in progress
   - step in progress
   - last successful checkpoint
   - selected restore point tag
   - backup manifest path
   - cleanup status
   - rollback status
3. On reconnect or backend restart, load state and decide automatically:
   - resume if safe
   - cleanup if BD partial state exists
   - rollback to BD for ECM failure state
   - rollback to ECM or BD for SANC failure state
4. Never allow a new run while state is unknown.

### Plan 5: Backup Policy

1. BD: no pre-backup.
2. ECM: backup gate always runs before ECM starts.
3. SANC: backup gate always runs before SANC starts.
4. Backup is reused only when it is verified as proper.
5. Otherwise backup is recreated automatically.

## Agent Hierarchy

These are not separate AI systems. They are code-level orchestration roles aligned to the current router and service structure.

### Main Agent

`BackupRestoreGovernor`

Purpose:

1. One main orchestration role for backup gating, restore-point selection, cleanup gating, and rollback gating.
2. It should be the single decision-maker for `reuse backup`, `create backup`, `restore backup`, `block retry`, and `mark invalid state`.

Recommended code placement:

1. New file: `services/backup_restore_governor.py`
2. Called from the installation flow in `routers/installation.py`
3. Exposed through `InstallationService` the same way other services are exposed today

### Sub Agents

#### 1. `BackupQualificationAgent`

Purpose:

1. Check whether the latest backup is proper.
2. Decide whether a fresh backup is required.

Recommended code alignment:

1. Extend `services/backup.py`
2. Add manifest validation helpers there or in a small helper file used by backup service

#### 2. `BackupManifestAgent`

Purpose:

1. Write and validate the backup manifest.
2. Track file sizes, checksums, tag, schemas, DB target, and completion state.

Recommended code alignment:

1. New file: `services/backup_manifest.py`
2. Used by `services/backup.py`
3. Also used by restore validation before rollback starts

#### 3. `RestorePointSelectorAgent`

Purpose:

1. Choose the right restore point after ECM or SANC failure.
2. Priority rules:
   - ECM failure -> BD only
   - SANC failure -> ECM first, else BD

Recommended code alignment:

1. Keep this logic inside `services/recovery_service.py`
2. Move router-level restore-point decisions into the governor plus recovery service

#### 4. `RestoreExecutionAgent`

Purpose:

1. Execute application restore, metadata replay, and Data Pump import.
2. Return a structured restore result for verification.

Recommended code alignment:

1. Keep DB restore execution in `services/restore.py`
2. Keep app restore coordination in `services/recovery_service.py`

#### 5. `CleanupVerificationAgent`

Purpose:

1. Verify BD cleanup completed fully.
2. Verify post-restore target state is usable.

Recommended code alignment:

1. Reuse `services/recovery_service.py`
2. Reuse `services/installer.py` cleanup helpers for filesystem residue
3. Add verification methods rather than embedding verification in router code

#### 6. `CheckpointStateAgent`

Purpose:

1. Persist task state, selected restore point, and chosen manifest path.
2. Recover state after disconnect or backend restart.

Recommended code alignment:

1. Keep live task tracking in `core/task_manager.py`
2. Add persistent state storage in a new file such as `core/task_state_store.py`
3. Let the governor read and write through that store

## Main Agent Contract

### Agent Name

`BackupRestoreGovernor`

### Responsibilities

1. Validate latest eligible backup before ECM or SANC starts.
2. Decide `reuse backup` vs `take fresh backup`.
3. Persist backup manifest after successful backup.
4. Select restore point after ECM or SANC failure.
5. Trigger automated restore pipeline.
6. Verify restored state before marking recovery successful.
7. Block install retry when cleanup or rollback is not validated.

### Inputs

1. Current module: `BD`, `ECM`, `SANC`
2. Last successful checkpoint
3. DB connection target
4. Expected schema names
5. Backup storage paths
6. App install paths
7. Persisted task state

### Outputs

1. `backup_reused`
2. `backup_created`
3. `backup_invalid`
4. `rollback_started`
5. `rollback_completed`
6. `rollback_failed`
7. `cleanup_completed`
8. `cleanup_failed`

## Code Structure Alignment

Use the current project structure instead of inventing a parallel framework.

### Router Layer

File: `routers/installation.py`

Role:

1. Remains the top-level workflow coordinator.
2. Should call the governor before ECM and SANC start.
3. Should call the governor after ECM and SANC failures.
4. Should not contain detailed backup validation or restore-point selection logic.

### Service Facade Layer

File: `services/installation_service.py`

Role:

1. Continue as the single service entry point used by the router.
2. Add governor exposure here, similar to `installer` and `recovery`.

Recommended addition:

1. `self.backup_restore_governor = BackupRestoreGovernorService(...)`

### Backup Layer

File: `services/backup.py`

Role:

1. Keep DB backup creation here.
2. Add backup validation support here or through `services/backup_manifest.py`.
3. Do not move orchestration decisions here.

### Restore Layer

File: `services/restore.py`

Role:

1. Keep DB restore execution here.
2. Do not make restore-point decisions here.

### Recovery Layer

File: `services/recovery_service.py`

Role:

1. Keep app backup, app restore, cleanup, and rollback execution helpers here.
2. Let the governor call into this service for action execution.
3. Keep restore-point selection helper methods here if they are service-level, not router-level.

### Installer Layer

File: `services/installer.py`

Role:

1. Keep installer execution and filesystem cleanup helpers here.
2. Reuse its cleanup methods from recovery or governor instead of duplicating shell logic elsewhere.

### Core State Layer

Files: `core/task_manager.py` and new `core/task_state_store.py`

Role:

1. `task_manager.py` stays responsible for live in-memory task state and websocket updates.
2. `task_state_store.py` should hold durable state needed for restart recovery.

## Recommended Naming In This Repo

To match the current naming style, these names fit better than generic agent-only names:

1. Main service: `BackupRestoreGovernorService`
2. Manifest helper: `BackupManifestService`
3. Persistent state helper: `TaskStateStore`
4. Backup validation method: `validate_backup_artifacts`
5. Backup gate method: `ensure_valid_backup_before_module`
6. Restore selection method: `select_restore_point`
7. Rollback method: `recover_to_last_stable_state`

## Task Assignment

### Main Agent

`BackupRestoreGovernor`

Tasks:

1. Discover latest candidate backup.
2. Ask `BackupQualificationAgent` whether it is proper.
3. Create fresh backup only if candidate is not proper.
4. Publish selected manifest path to task state.
5. Select restore point after failure.
6. Trigger restore and verification.
7. Block retry when verification fails.

### Sub Agent Responsibilities

`BackupQualificationAgent`

1. Validate candidate backup artifacts.
2. Return exact failure reason for invalid backup.

`BackupManifestAgent`

1. Create manifest after backup completes.
2. Validate manifest integrity before reuse.

`RestorePointSelectorAgent`

1. Pick BD or ECM restore point based on last stable module and manifest validity.

`RestoreExecutionAgent`

1. Run app restore.
2. Run metadata SQL.
3. Run DB import.

`CleanupVerificationAgent`

1. Verify residue cleanup.
2. Verify rollback target state.

`CheckpointStateAgent`

1. Persist selected restore point, selected manifest, and recovery status.
2. Rehydrate state after restart.

## Suggested Implementation Order

1. Add backup manifest generation and validation.
2. Add backup quality gate before ECM and SANC start.
3. Persist restore point and manifest path in task state.
4. Move rollback selection logic behind the plan agent.
5. Add post-cleanup and post-restore verification gates.
6. Block retries unless verification passes.