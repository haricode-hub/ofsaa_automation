# AGENTS.md

## Purpose
This repository currently has a stable **BD Pack module** implementation. Treat it as the baseline.

When adding new modules (for example ECM, SANC, future packs), do not break existing BD Pack behavior, API contracts, or file layout.

## Baseline Module (Do Not Break)
- Module name: `BD Pack`
- Backend entry API: `/api/installation/*`
- Main orchestration flow lives in:
  - `backend/routers/installation.py`
  - `backend/services/installation_service.py`
  - `backend/services/installer.py`
- Frontend primary form:
  - `frontend/src/components/InstallationForm.tsx`

## Current Code Structure

### Backend
- App bootstrap: `backend/main.py`
- Core:
  - `backend/core/config.py`
  - `backend/core/logging.py`
  - `backend/core/websocket_manager.py`
- Router:
  - `backend/routers/installation.py`
- Schemas:
  - `backend/schemas/installation.py`
- Services:
  - `backend/services/installation_service.py`
  - `backend/services/installer.py`
  - `backend/services/ssh_service.py`
  - `backend/services/validation.py`
  - `backend/services/java.py`
  - `backend/services/packages.py`
  - `backend/services/profile.py`
  - `backend/services/mount_point.py`
  - `backend/services/oracle_client.py`
  - `backend/services/oracle_user_setup.py`
  - `backend/services/utils.py`

### Frontend
- App shell:
  - `frontend/src/app/layout.tsx`
  - `frontend/src/app/page.tsx`
  - `frontend/src/app/globals.css`
- Main install UI:
  - `frontend/src/components/InstallationForm.tsx`
- Other components:
  - `frontend/src/components/BackgroundMatrix.tsx`
  - `frontend/src/components/OracleClientTerraformForm.tsx`

## Contract Rules
1. Keep existing endpoints and payload keys backward compatible.
2. Keep BD Pack default behavior unchanged unless explicitly requested.
3. New module fields must be additive and module-scoped (no global side effects).
4. Preserve existing installation flow ordering in router/service unless intentionally versioned.
5. Do not rename or remove existing schema fields used by BD Pack clients.
6. If a new module needs different XML/property handling, gate it by module flags (example: `install_ecm`, `install_sanc`).

## Extension Pattern for New Modules
1. Add module flag(s) in `backend/schemas/installation.py`.
2. Pass new fields through `backend/routers/installation.py` -> `backend/services/installation_service.py`.
3. Implement module-specific patch/copy logic in `backend/services/installer.py`.
4. Add UI sections in `frontend/src/components/InstallationForm.tsx` that render only when module flag is enabled.
5. Keep shared fields isolated; avoid changing BD Pack mapping logic for unrelated modules.

## Safety Checklist Before Merge
- BD Pack-only run still works with existing payload.
- Existing frontend fields for BD Pack still submit as before.
- New module section appears only when that module is checked.
- No breaking changes to `/api/installation/start`, `/status/{task_id}`, `/tasks`, `/test-connection`.

## Notes
- Prefer adding new helper functions/classes over modifying shared code paths directly.
- If a shared path must change, include explicit guards and regression checks for BD Pack mode.
