from typing import Any, Callable, Awaitable, Optional

from core.config import build_backup_params
from services.backup_manifest import BackupManifestService
from services.recovery_service import RecoveryService


class BackupRestoreGovernorService:
    def __init__(self, recovery_service: RecoveryService) -> None:
        self.recovery = recovery_service
        self.manifests = BackupManifestService()

    def _gate_tag_for_module(self, request, module_name: str) -> str:
        """Return the backup tag to validate/create before running module_name.

        ECM  always gates on BD.
        SANC gates on ECM if an ECM manifest exists on disk, otherwise on BD.
        In force_reinstall mode SANC always gates on BD (ECM state is gone).
        """
        if module_name == "ECM":
            return "BD"

        if module_name == "SANC":
            # force_reinstall: BD just wiped + reinstalled — any ECM manifest is stale
            if getattr(request, "installation_mode", "fresh") == "force_reinstall":
                return "BD"
            # Check for ECM manifest from a prior run (even if install_ecm=False this run)
            ecm_manifest = self.manifests.load_latest_manifest(request.host, "ECM")
            if ecm_manifest or getattr(request, "install_ecm", False):
                return "ECM"
            return "BD"

        raise ValueError(f"Unsupported module for backup gating: {module_name}")

    async def select_restore_manifest(
        self,
        request,
        restore_tags: list[str],
        on_log: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> dict[str, Any]:
        logs: list[str] = []

        async def log(message: str) -> None:
            logs.append(message)
            if on_log is not None:
                await on_log(message)

        for tag in restore_tags:
            manifest = self.manifests.load_latest_manifest(request.host, tag)
            if not manifest:
                await log(f"[BACKUP-GOVERNOR] No manifest found for restore tag={tag}")
                continue

            params = build_backup_params(request, tag)
            validation = await self.manifests.validate_manifest(
                manifest,
                ssh_service=self.recovery.ssh_service,
                app_ssh_host=params.app_host,
                app_ssh_username=params.app_username,
                app_ssh_password=params.app_password,
                db_ssh_host=params.effective_db_host,
                db_ssh_username=params.effective_db_username,
                db_ssh_password=params.effective_db_password,
                expected_tag=tag,
            )
            for entry in validation.get("logs", []):
                await log(entry)
            if validation.get("valid"):
                await log(f"[BACKUP-GOVERNOR] Selected restore manifest for tag={tag}: {manifest.get('manifest_path')}")
                return {"success": True, "logs": logs, "manifest": manifest, "manifest_path": manifest.get("manifest_path")}

        return {"success": False, "logs": logs, "error": "No valid manifest found for restore"}

    async def ensure_valid_backup_before_module(
        self,
        task_id: str,
        request,
        module_name: str,
        on_log: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> dict[str, Any]:
        logs: list[str] = []

        async def log(message: str) -> None:
            logs.append(message)
            if on_log is not None:
                await on_log(message)

        backup_tag = self._gate_tag_for_module(request, module_name)
        params = build_backup_params(request, backup_tag)

        if not params.db_service:
            await log(f"[BACKUP-GOVERNOR] Cannot validate {backup_tag} backup: DB service is missing")
            return {"success": False, "logs": logs, "error": "DB service missing for backup validation"}

        manifest = self.manifests.load_latest_manifest(request.host, backup_tag)

        if manifest:
            await log(f"[BACKUP-GOVERNOR] Found latest {backup_tag} manifest: {manifest.get('manifest_path', 'unknown path')}")
            validation = await self.manifests.validate_manifest(
                manifest,
                ssh_service=self.recovery.ssh_service,
                app_ssh_host=params.app_host,
                app_ssh_username=params.app_username,
                app_ssh_password=params.app_password,
                db_ssh_host=params.effective_db_host,
                db_ssh_username=params.effective_db_username,
                db_ssh_password=params.effective_db_password,
                expected_tag=backup_tag,
            )
            for entry in validation.get("logs", []):
                await log(entry)
            if validation.get("valid"):
                await log(f"[BACKUP-GOVERNOR] Reusing verified {backup_tag} backup before {module_name}")
                return {
                    "success": True,
                    "logs": logs,
                    "decision": "backup_reused",
                    "backup_tag": backup_tag,
                    "manifest_path": manifest.get("manifest_path"),
                }

        await log(f"[BACKUP-GOVERNOR] No proper {backup_tag} backup found. Taking a fresh backup.")

        if not params.db_sys_password:
            await log("[BACKUP-GOVERNOR] Cannot create backup: db_sys_password is missing")
            return {"success": False, "logs": logs, "error": "db_sys_password missing for backup creation"}

        app_result = await self.recovery.backup_application(
            params.app_host,
            params.app_username,
            params.app_password,
            backup_tag=backup_tag,
        )
        for entry in app_result.get("logs", []):
            await log(entry)
        if not app_result.get("success"):
            return {"success": False, "logs": logs, "error": app_result.get("error") or "Application backup failed"}

        db_result = await self.recovery.backup_db_schemas(
            params.app_host,
            params.app_username,
            params.app_password,
            db_sys_password=params.db_sys_password,
            db_jdbc_service=params.db_service,
            db_oracle_sid=params.oracle_sid,
            schema_config_schema_name=params.schema_config,
            schema_atomic_schema_name=params.schema_atomic,
            db_ssh_host=params.db_ssh_host,
            db_ssh_username=params.db_ssh_username,
            db_ssh_password=params.db_ssh_password,
            backup_tag=backup_tag,
        )
        for entry in db_result.get("logs", []):
            await log(entry)
        if not db_result.get("success"):
            return {"success": False, "logs": logs, "error": db_result.get("error") or "DB schema backup failed"}

        dump_timestamp = db_result.get("timestamp")
        dump_prefix = db_result.get("dump_prefix")
        if not dump_timestamp or not dump_prefix:
            await log("[BACKUP-GOVERNOR] DB backup returned incomplete metadata")
            return {"success": False, "logs": logs, "error": "DB backup metadata incomplete"}

        metadata_path = f"/u01/backup/ofsaa/restore_metadata_{backup_tag}_{dump_timestamp}.sql"
        manifest_payload = self.manifests.build_manifest(
            app_host=params.app_host,
            db_host=params.effective_db_host,
            tag=backup_tag,
            db_service=params.db_service,
            schemas=params.schemas,
            app_backup_path=app_result.get("backup_path", ""),
            dump_prefix=dump_prefix,
            dump_timestamp=dump_timestamp,
            metadata_path=metadata_path,
        )
        manifest_path = self.manifests.write_manifest(request.host, backup_tag, manifest_payload)
        await log(f"[BACKUP-GOVERNOR] Fresh {backup_tag} backup created and manifest saved: {manifest_path}")
        return {
            "success": True,
            "logs": logs,
            "decision": "backup_created",
            "backup_tag": backup_tag,
            "manifest_path": manifest_path,
        }

    def record_backup_manifest(
        self,
        *,
        request,
        backup_tag: str,
        app_backup_path: str,
        dump_prefix: str,
        dump_timestamp: str,
        db_service: str,
        schemas: list[str],
    ) -> dict[str, Any]:
        db_host = getattr(request, "db_ssh_host", None) or request.host
        metadata_path = f"/u01/backup/ofsaa/restore_metadata_{backup_tag}_{dump_timestamp}.sql"
        manifest_payload = self.manifests.build_manifest(
            app_host=request.host,
            db_host=db_host,
            tag=backup_tag,
            db_service=db_service,
            schemas=schemas,
            app_backup_path=app_backup_path,
            dump_prefix=dump_prefix,
            dump_timestamp=dump_timestamp,
            metadata_path=metadata_path,
        )
        manifest_path = self.manifests.write_manifest(request.host, backup_tag, manifest_payload)
        return {
            "success": True,
            "manifest_path": manifest_path,
            "backup_tag": backup_tag,
        }