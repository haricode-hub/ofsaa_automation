import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from services.ssh_service import SSHService
from services.utils import shell_escape

# Default: <backend_root>/backup_manifests/ — survives backend restarts.
# Override with OFSAA_BACKUP_MANIFEST_DIR environment variable.
_DEFAULT_MANIFEST_DIR = Path(os.getenv("OFSAA_BACKUP_MANIFEST_DIR", "")) if os.getenv("OFSAA_BACKUP_MANIFEST_DIR") else Path(__file__).resolve().parent.parent / "backup_manifests"


class BackupManifestService:
    def __init__(self, manifest_dir: Optional[str] = None) -> None:
        base_dir = Path(manifest_dir) if manifest_dir else _DEFAULT_MANIFEST_DIR
        self.manifest_dir = base_dir
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

    def _host_dir(self, host: str) -> Path:
        safe_host = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in host)
        host_dir = self.manifest_dir / safe_host
        host_dir.mkdir(parents=True, exist_ok=True)
        return host_dir

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)

    def build_manifest(
        self,
        *,
        app_host: str,
        db_host: str,
        tag: str,
        db_service: str,
        schemas: list[str],
        app_backup_path: str,
        dump_prefix: str,
        dump_timestamp: str,
        metadata_path: str,
        app_backup_size: Optional[int] = None,
        metadata_size: Optional[int] = None,
    ) -> dict[str, Any]:
        return {
            "created_at": datetime.utcnow().isoformat() + "Z",
            "status": "complete",
            "tag": tag,
            "app_host": app_host,
            "db_host": db_host,
            "db_service": db_service,
            "schemas": sorted(schema.upper() for schema in schemas if schema),
            "app_backup": {
                "path": app_backup_path,
                "size": app_backup_size,
            },
            "db_backup": {
                "dump_prefix": dump_prefix,
                "dump_timestamp": dump_timestamp,
                "metadata_path": metadata_path,
                "metadata_size": metadata_size,
            },
        }

    def write_manifest(self, host: str, tag: str, manifest: dict[str, Any]) -> str:
        timestamp = manifest.get("db_backup", {}).get("dump_timestamp") or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = self._host_dir(host) / f"{tag}_{timestamp}.json"
        self._write_json_atomic(path, manifest)
        return str(path)

    def load_latest_manifest(self, host: str, tag: str) -> Optional[dict[str, Any]]:
        host_dir = self._host_dir(host)
        matches = sorted(host_dir.glob(f"{tag}_*.json"), reverse=True)
        if not matches:
            return None
        data = json.loads(matches[0].read_text(encoding="utf-8"))
        data["manifest_path"] = str(matches[0])
        return data

    def load_manifest(self, manifest_path: str) -> dict[str, Any]:
        path = Path(manifest_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["manifest_path"] = str(path)
        return data

    def purge_manifests_for_tags(self, host: str, tags: list[str]) -> list[str]:
        """Delete all manifest files for the given tags on a host.

        Called after BD is force-reinstalled to invalidate stale ECM/SANC manifests
        that no longer represent the current server state.

        Returns list of deleted file paths.
        """
        host_dir = self._host_dir(host)
        deleted: list[str] = []
        for tag in tags:
            for path in host_dir.glob(f"{tag}_*.json"):
                path.unlink(missing_ok=True)
                deleted.append(str(path))
        return deleted

    async def validate_manifest(
        self,
        manifest: dict[str, Any],
        *,
        ssh_service: SSHService,
        app_ssh_host: str,
        app_ssh_username: str,
        app_ssh_password: str,
        db_ssh_host: str,
        db_ssh_username: str,
        db_ssh_password: str,
        expected_tag: str,
    ) -> dict[str, Any]:
        logs: list[str] = []

        if manifest.get("status") != "complete":
            logs.append("[BACKUP-GOVERNOR] Manifest status is not complete")
            return {"valid": False, "logs": logs}

        if manifest.get("tag") != expected_tag:
            logs.append(f"[BACKUP-GOVERNOR] Manifest tag mismatch: expected {expected_tag}, found {manifest.get('tag')}")
            return {"valid": False, "logs": logs}

        app_path = manifest.get("app_backup", {}).get("path")
        if not app_path:
            logs.append("[BACKUP-GOVERNOR] Manifest missing application backup path")
            return {"valid": False, "logs": logs}

        app_check = await ssh_service.execute_command(
            app_ssh_host,
            app_ssh_username,
            app_ssh_password,
            f"test -s {shell_escape(app_path)} && stat --format='%s' {shell_escape(app_path)}",
        )
        app_size = (app_check.get("stdout") or "").strip()
        if not app_check.get("success") or not app_size.isdigit() or int(app_size) <= 0:
            logs.append(f"[BACKUP-GOVERNOR] Application backup is missing or empty: {app_path}")
            return {"valid": False, "logs": logs}
        logs.append(f"[BACKUP-GOVERNOR] Application backup verified: {app_path}")

        metadata_path = manifest.get("db_backup", {}).get("metadata_path")
        dump_prefix = manifest.get("db_backup", {}).get("dump_prefix")
        if not metadata_path or not dump_prefix:
            logs.append("[BACKUP-GOVERNOR] Manifest missing DB backup metadata or dump prefix")
            return {"valid": False, "logs": logs}

        metadata_check = await ssh_service.execute_command(
            db_ssh_host,
            db_ssh_username,
            db_ssh_password,
            f"test -s {shell_escape(metadata_path)} && stat --format='%s' {shell_escape(metadata_path)}",
        )
        metadata_size = (metadata_check.get("stdout") or "").strip()
        if not metadata_check.get("success") or not metadata_size.isdigit() or int(metadata_size) <= 0:
            logs.append(f"[BACKUP-GOVERNOR] Restore metadata is missing or empty: {metadata_path}")
            return {"valid": False, "logs": logs}
        logs.append(f"[BACKUP-GOVERNOR] Restore metadata verified: {metadata_path}")

        dump_check_cmd = (
            f"count=$(ls -1 /u01/backup/ofsaa/{dump_prefix}_*.dmp 2>/dev/null | wc -l); "
            f"if [ \"$count\" -gt 0 ]; then echo $count; else exit 1; fi"
        )
        dump_check = await ssh_service.execute_command(
            db_ssh_host,
            db_ssh_username,
            db_ssh_password,
            dump_check_cmd,
        )
        dump_count = (dump_check.get("stdout") or "").strip()
        if not dump_check.get("success") or not dump_count.isdigit() or int(dump_count) <= 0:
            logs.append(f"[BACKUP-GOVERNOR] No dump files found for prefix: {dump_prefix}")
            return {"valid": False, "logs": logs}
        logs.append(f"[BACKUP-GOVERNOR] DB dump files verified: prefix={dump_prefix}, count={dump_count}")

        manifest["validated_at"] = datetime.utcnow().isoformat() + "Z"
        return {"valid": True, "logs": logs, "manifest": manifest}