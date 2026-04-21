from typing import Any, Callable, Awaitable, Optional

from services.backup_manifest import BackupManifestService
from services.recovery_service import RecoveryService


class BackupRestoreGovernorService:
    def __init__(self, recovery_service: RecoveryService) -> None:
        self.recovery = recovery_service
        self.manifests = BackupManifestService()

    def _resolve_backup_target(self, request, module_name: str) -> dict[str, Any]:
        if module_name == "ECM":
            return {
                "tag": "BD",
                "db_service": request.schema_jdbc_service,
                "schema_config": request.schema_config_schema_name,
                "schema_atomic": request.schema_atomic_schema_name,
            }

        if module_name == "SANC":
            if getattr(request, "install_ecm", False):
                return {
                    "tag": "ECM",
                    "db_service": request.ecm_schema_jdbc_service or request.schema_jdbc_service,
                    "schema_config": request.ecm_schema_config_schema_name or request.schema_config_schema_name,
                    "schema_atomic": request.ecm_schema_atomic_schema_name or request.schema_atomic_schema_name,
                }
            return {
                "tag": "BD",
                "db_service": request.schema_jdbc_service,
                "schema_config": request.schema_config_schema_name,
                "schema_atomic": request.schema_atomic_schema_name,
            }

        raise ValueError(f"Unsupported module for backup gating: {module_name}")

    def _resolve_tag_target(self, request, backup_tag: str) -> dict[str, Any]:
        if backup_tag == "BD":
            return {
                "tag": "BD",
                "db_service": request.schema_jdbc_service,
                "schema_config": request.schema_config_schema_name,
                "schema_atomic": request.schema_atomic_schema_name,
            }
        if backup_tag == "ECM":
            return {
                "tag": "ECM",
                "db_service": request.ecm_schema_jdbc_service or request.schema_jdbc_service,
                "schema_config": request.ecm_schema_config_schema_name or request.schema_config_schema_name,
                "schema_atomic": request.ecm_schema_atomic_schema_name or request.schema_atomic_schema_name,
            }
        if backup_tag == "SANC":
            return {
                "tag": "SANC",
                "db_service": request.sanc_schema_jdbc_service or request.ecm_schema_jdbc_service or request.schema_jdbc_service,
                "schema_config": request.sanc_schema_config_schema_name or request.ecm_schema_config_schema_name or request.schema_config_schema_name,
                "schema_atomic": request.sanc_schema_atomic_schema_name or request.ecm_schema_atomic_schema_name or request.schema_atomic_schema_name,
            }
        raise ValueError(f"Unsupported backup tag: {backup_tag}")

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

        db_host = getattr(request, "db_ssh_host", None) or request.host
        db_username = getattr(request, "db_ssh_username", None) or request.username
        db_password = getattr(request, "db_ssh_password", None) or request.password

        for tag in restore_tags:
            manifest = self.manifests.load_latest_manifest(request.host, tag)
            if not manifest:
                await log(f"[BACKUP-GOVERNOR] No manifest found for restore tag={tag}")
                continue

            target = self._resolve_tag_target(request, tag)
            expected_schemas = [schema for schema in [target["schema_atomic"], target["schema_config"]] if schema]
            validation = await self.manifests.validate_manifest(
                manifest,
                ssh_service=self.recovery.ssh_service,
                app_ssh_host=request.host,
                app_ssh_username=request.username,
                app_ssh_password=request.password,
                db_ssh_host=db_host,
                db_ssh_username=db_username,
                db_ssh_password=db_password,
                expected_tag=tag,
                expected_db_service=target["db_service"],
                expected_schemas=expected_schemas,
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

        target = self._resolve_backup_target(request, module_name)
        backup_tag = target["tag"]
        db_service = target["db_service"]
        schema_config = target["schema_config"]
        schema_atomic = target["schema_atomic"]
        expected_schemas = [schema for schema in [schema_atomic, schema_config] if schema]

        if not db_service:
            await log(f"[BACKUP-GOVERNOR] Cannot validate {backup_tag} backup: DB service is missing")
            return {"success": False, "logs": logs, "error": "DB service missing for backup validation"}

        manifest = self.manifests.load_latest_manifest(request.host, backup_tag)
        db_host = getattr(request, "db_ssh_host", None) or request.host
        db_username = getattr(request, "db_ssh_username", None) or request.username
        db_password = getattr(request, "db_ssh_password", None) or request.password

        if manifest:
            await log(
                f"[BACKUP-GOVERNOR] Found latest {backup_tag} manifest: {manifest.get('manifest_path', 'unknown path')}"
            )
            validation = await self.manifests.validate_manifest(
                manifest,
                ssh_service=self.recovery.ssh_service,
                app_ssh_host=request.host,
                app_ssh_username=request.username,
                app_ssh_password=request.password,
                db_ssh_host=db_host,
                db_ssh_username=db_username,
                db_ssh_password=db_password,
                expected_tag=backup_tag,
                expected_db_service=db_service,
                expected_schemas=expected_schemas,
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

        if not request.db_sys_password:
            await log("[BACKUP-GOVERNOR] Cannot create backup: db_sys_password is missing")
            return {"success": False, "logs": logs, "error": "db_sys_password missing for backup creation"}

        app_result = await self.recovery.backup_application(
            request.host,
            request.username,
            request.password,
            backup_tag=backup_tag,
        )
        for entry in app_result.get("logs", []):
            await log(entry)
        if not app_result.get("success"):
            return {"success": False, "logs": logs, "error": app_result.get("error") or "Application backup failed"}

        db_result = await self.recovery.backup_db_schemas(
            request.host,
            request.username,
            request.password,
            db_sys_password=request.db_sys_password,
            db_jdbc_service=db_service,
            db_oracle_sid=getattr(request, "oracle_sid", None) or "OFSAADB",
            schema_config_schema_name=schema_config,
            schema_atomic_schema_name=schema_atomic,
            db_ssh_host=getattr(request, "db_ssh_host", None),
            db_ssh_username=getattr(request, "db_ssh_username", None),
            db_ssh_password=getattr(request, "db_ssh_password", None),
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
            app_host=request.host,
            db_host=db_host,
            tag=backup_tag,
            db_service=db_service,
            schemas=expected_schemas,
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