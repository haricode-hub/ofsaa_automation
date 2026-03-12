# SANC Pack Installation Guide

SANC Pack installs after BD Pack completes successfully, following the same execution pattern as ECM Pack.

## Prerequisites
- BD Pack installation is already completed.
- Oracle user setup is already completed.
- Mount point and directory setup are already completed.
- Required packages (ksh, git, and related dependencies) are already completed.
- Java setup and profile updates are already completed.
- Environment checks are already completed.

## Installer Kit Details
- Sanction pack version: V1022110-01
- Module: SANCTION PACK
- Source: Git repository
- Extract location: /u01/SANC_INSTALLER_KIT_AUTOMATION/

## Folder Structure
```text
/u01/SANC_INSTALLER_KIT_AUTOMATION/OFS_SANC_PACK/
├── schema_creator/conf/
│   └── OFS_SANC_SCHEMA_IN.xml
├── OFS_AAI/conf/
│   └── OFSAAI_InstallConfig.xml
├── OFS_CS/conf/
│   └── default.properties
└── OFS_TFLT/conf/
    └── default.properties
```

## Step-by-Step Flow

| Step | Action | What Happens | Example Progress |
|------|--------|--------------|------------------|
| 1 | Download & Extract | Download SANC installer kit from Git and unzip into `/u01/SANC_INSTALLER_KIT_AUTOMATION/OFS_SANC_PACK` | 82% |
| 2 | Set Permissions | Apply required permissions on SANC kit directories and scripts | 86% |
| 3 | Patch Configuration Files | Patch `OFS_SANC_SCHEMA_IN.xml`, copy BD `OFSAAI_InstallConfig.xml`, then map Git `default.properties_CS` -> `OFS_CS/conf/default.properties` and Git `default.properties_TFLT` -> `OFS_TFLT/conf/default.properties` | 90% |
| 4 | Run `osc.sh` | Execute schema creator script for SANC schemas | 95% |
| 5 | Run `setup.sh SILENT` | Execute silent installer for SANC module | 100% |

## Configuration Files
1. `/u01/SANC_INSTALLER_KIT_AUTOMATION/OFS_SANC_PACK/schema_creator/conf/OFS_SANC_SCHEMA_IN.xml`
- Configure JDBC host, port, schema names, and passwords.

2. `/u01/SANC_INSTALLER_KIT_AUTOMATION/OFS_SANC_PACK/OFS_AAI/conf/OFSAAI_InstallConfig.xml`
- Copy from BD Pack configuration.

3. `/u01/SANC_INSTALLER_KIT_AUTOMATION/OFS_SANC_PACK/OFS_CS/conf/default.properties`
- Configure CS module properties.
- Git source file: `default.properties_CS` (must be applied only to CS).

4. `/u01/SANC_INSTALLER_KIT_AUTOMATION/OFS_SANC_PACK/OFS_TFLT/conf/default.properties`
- Configure TFLT module properties.
- Git source file: `default.properties_TFLT` (must be applied only to TFLT).

## Git Mapping for Default Properties
- `default.properties_CS` -> `/u01/SANC_INSTALLER_KIT_AUTOMATION/OFS_SANC_PACK/OFS_CS/conf/default.properties`
- `default.properties_TFLT` -> `/u01/SANC_INSTALLER_KIT_AUTOMATION/OFS_SANC_PACK/OFS_TFLT/conf/default.properties`

---

## UI Fields Required (for Coding Reference)

### 1. OFS_SANC_SCHEMA_IN.xml — Same fields as BD Pack Schema

> These use the prefix `sanc_schema_` in backend schema/UI.

| UI Field Name | XML Element | Description | Required |
|---|---|---|---|
| `sanc_schema_jdbc_host` | `JDBC_URL` (host part) | DB host for JDBC URL | Yes |
| `sanc_schema_jdbc_port` | `JDBC_URL` (port part) | DB port (default: 1521) | Yes |
| `sanc_schema_jdbc_service` | `JDBC_URL` (service part) | DB service name or SID | Yes |
| `sanc_schema_host` | `<HOST>` | Application server hostname or IP | Yes |
| `sanc_schema_setup_env` | `SETUPINFO NAME` | Environment label (DEV/SIT/UAT/PROD etc.) | Yes |
| `sanc_schema_apply_same_for_all` | `PASSWORD APPLYSAMEFORALL` | Apply same password for all schemas (Y/N) | Yes |
| `sanc_schema_default_password` | `PASSWORD DEFAULT` | Schema password | Yes |
| `sanc_schema_datafile_dir` | `TABLESPACE DATAFILE` (base path) | Base directory for all datafiles | Yes |
| `sanc_schema_tablespace_autoextend` | `TABLESPACE AUTOEXTEND` | ON or OFF for all tablespaces | Yes |
| `sanc_schema_external_directory_value` | `DIRECTORY VALUE` | External directory path for SANC inbox | Yes |
| `sanc_schema_config_schema_name` | `SCHEMA TYPE="CONFIG" NAME` | CONFIG schema name | Yes |
| `sanc_schema_atomic_schema_name` | `SCHEMA TYPE="ATOMIC" NAME` | ATOMIC schema name (shared across all ATOMICs) | Yes |

---

### 2. default.properties_CS — Only SWIFTINFO field

> Git source: `default.properties_CS` → placed at `OFS_CS/conf/default.properties`

| UI Field Name | Property Key | Description | Required |
|---|---|---|---|
| `sanc_cs_swiftinfo` | `SWIFTINFO` | SWIFT info value for CS module | Yes |

---

### 3. default.properties_TFLT — Only SWIFTINFO field

> Git source: `default.properties_TFLT` → placed at `OFS_TFLT/conf/default.properties`

| UI Field Name | Property Key | Description | Required |
|---|---|---|---|
| `sanc_tflt_swiftinfo` | `SWIFTINFO` | SWIFT info value for TFLT module | Yes |

---

### 4. OFSAAI_InstallConfig.xml — Conditional Behavior

| Scenario | Behavior |
|---|---|
| BD Pack is selected | Copy BD Pack's already-patched `OFSAAI_InstallConfig.xml` into SANC kit. No new UI fields needed. |
| BD Pack is NOT selected (SANC only) | Show the `OFSAAI_InstallConfig.xml` section in the UI with **default values pre-populated**. User can review and override before SANC runs. |

> **UI Rule**: The `OFSAAI_InstallConfig.xml` config section must be shown when either `install_bdpack` OR `install_sanc` is selected.
> Currently in `InstallationForm.tsx` the section is guarded by `formData.install_bdpack` — this must be updated to:
> ```
> (formData.install_bdpack || formData.install_sanc)
> ```

**Default values used when BD Pack is not selected** (same as existing backend schema defaults):

| Field | Default Value |
|---|---|
| `WEBAPPSERVERTYPE` | `3` |
| `SFTP_ENABLE` | `1` |
| `FILE_TRANSFER_PORT` | `22` |
| `JAVAPORT` | `9999` |
| `NATIVEPORT` | `6666` |
| `AGENTPORT` | `6510` |
| `ICCPORT` | `6507` |
| `ICCNATIVEPORT` | `6509` |
| `OLAPPORT` | `10101` |
| `MSGPORT` | `6501` |
| `ROUTERPORT` | `6502` |
| `AMPORT` | `6506` |
| `HTTPS_ENABLE` | `1` |
| `WEB_SERVER_PORT` | `7002` |
| `CONTEXT_NAME` | `FICHOME` |
| `WEB_LOCAL_PATH` | `/u01/OFSAA/FTPSHARE` |
| `OFSAAI_FTPSHARE_PATH` | `/u01/OFSAA/FTPSHARE` |
| `OFSAAI_SFTP_USER_ID` | `oracle` |
| `DBSERVER_IP` | *(user must fill)* |
| `ORACLE_SID` | *(user must fill)* |
| `WEB_SERVER_IP` | *(user must fill)* |
| `ABS_DRIVER_PATH` | *(user must fill)* |

---

## Execution Commands
```bash
/u01/SANC_INSTALLER_KIT_AUTOMATION/OFS_SANC_PACK/schema_creator/bin/osc.sh -s
/u01/SANC_INSTALLER_KIT_AUTOMATION/OFS_SANC_PACK/bin/setup.sh SILENT
```

## Installation Flow Diagram
```text
+-------------------+      +------------------+      +-------------------+
|  BD PACK COMPLETE | ---> |  AUTO BACKUP OK  | ---> |   SANC PACK RUN   |
+-------------------+      +------------------+      +-------------------+
```

## Progress Indicator Example
```text
82% -> 86% -> 90% -> 95% -> 100%
```
