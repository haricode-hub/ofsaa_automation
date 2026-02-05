# OFSAA Installer Backend: Flow After Java Installation

This document explains the backend workflow and code locations for all steps that occur **after Java installation** in the OFSAA automated installer system.

---

## 1. Main Workflow Location
- **File:** `backend/routers/installation.py`
- **Function:** `run_installation_process`
- **Purpose:** Orchestrates the entire installation process, including all steps after Java installation.

---

## 2. Steps After Java Installation

### a. OFSAA Directory Structure Creation
- **Code Location:**
  - `run_installation_process` (routers/installation.py)
  - Calls: `installation_service.create_ofsaa_directories(...)`
- **Purpose:**
  - Creates `/u01/OFSAA/FICHOME`, `/u01/OFSAA/FTPSHARE`, and related directories.

### b. Oracle Client Check
- **Code Location:**
  - `run_installation_process` (routers/installation.py)
  - Calls: `installation_service.check_existing_oracle_client_and_update_profile(...)`
- **Purpose:**
  - Scans for existing Oracle client installations and updates environment/profile if found.

### c. OFSAA Installer Download & Extraction
- **Code Location:**
  - `run_installation_process` (routers/installation.py)
  - Calls: `installation_service.download_and_extract_installer(...)`
  - Streams output to frontend via WebSocket callback.
- **Purpose:**
  - Downloads the OFSAA installer kit from Git, copies, and extracts it to `/u01/installer_kit`.
  - Skips extraction if already present.

### d. Environment Check (envCheck.sh)
- **Code Location:**
  - `run_installation_process` (routers/installation.py)
  - Calls: `installation_service.run_environment_check(...)`
  - Implementation: `InstallerService.run_environment_check` (services/installer.py)
- **Purpose:**
  - Runs `/u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin/envCheck.sh -s` with correct permissions.
  - Streams all output and prompts to the frontend.

### e. Profile Update with Custom Variables
- **Code Location:**
  - `run_installation_process` (routers/installation.py)
  - Calls: `installation_service.update_profile_with_custom_variables(...)`
- **Purpose:**
  - Updates `/home/oracle/.profile` with FIC_HOME, JAVA_HOME, ORACLE_SID, etc.

### f. Profile Verification
- **Code Location:**
  - `run_installation_process` (routers/installation.py)
  - Calls: `installation_service.verify_profile_setup(...)`
- **Purpose:**
  - Verifies that the Oracle and OFSAA environment variables are set correctly.

---

## 3. Key Service Implementations

- **Directory Creation:** `services/java.py`, `services/installer.py`
- **Installer Download/Extraction:** `services/installer.py` (`download_and_extract_installer`)
- **Environment Check:** `services/installer.py` (`run_environment_check`)
- **Profile Management:** `services/profile.py`
- **Oracle Client:** `services/oracle_client.py`

---

## 4. Output Streaming
- All major steps after Java installation stream their output to the frontend logs UI via the WebSocket callback defined in `run_installation_process`.
- Interactive prompts (e.g., from envCheck.sh) are also handled and shown in the frontend.

---

## 5. Debugging
- Debug logs are sent before and after key steps (especially before and after running envCheck.sh) to help trace the workflow in the frontend logs.

---

## 6. Summary Table
| Step | Main Function | Service/Method | Output Streamed? |
|------|---------------|----------------|------------------|
| OFSAA Dir Creation | run_installation_process | create_ofsaa_directories | Yes |
| Oracle Client Check | run_installation_process | check_existing_oracle_client_and_update_profile | Yes |
| Installer Download | run_installation_process | download_and_extract_installer | Yes |
| Environment Check | run_installation_process | run_environment_check | Yes |
| Profile Update | run_installation_process | update_profile_with_custom_variables | Yes |
| Profile Verification | run_installation_process | verify_profile_setup | Yes |

---

**For any changes, always update both the workflow in `routers/installation.py` and the relevant service in `services/`.**
