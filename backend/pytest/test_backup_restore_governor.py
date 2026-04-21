import asyncio
from pathlib import Path

from schemas.installation import InstallationRequest
from services.backup_manifest import BackupManifestService
from services.backup_restore_governor import BackupRestoreGovernorService


def build_request(**overrides):
    payload = {
        "host": "10.0.0.10",
        "username": "root",
        "password": "secret",
        "db_sys_password": "dbsecret",
        "schema_jdbc_service": "FLEXPDB1",
        "schema_jdbc_host": "10.0.0.20",
        "schema_config_schema_name": "OFSCONFIG",
        "schema_atomic_schema_name": "OFSATOMIC",
        "ecm_schema_jdbc_service": "ECMPDB1",
        "ecm_schema_config_schema_name": "ECMCONFIG",
        "ecm_schema_atomic_schema_name": "ECMATOMIC",
        "sanc_schema_jdbc_service": "SANCPDB1",
        "sanc_schema_config_schema_name": "SANCCONFIG",
        "sanc_schema_atomic_schema_name": "SANCATOMIC",
        "install_bdpack": True,
        "install_ecm": True,
        "install_sanc": True,
    }
    payload.update(overrides)
    return InstallationRequest(**payload)


class FakeRecoveryService:
    def __init__(self):
        self.ssh_service = object()
        self.application_backups = []
        self.db_backups = []

    async def backup_application(self, host, username, password, **kwargs):
        self.application_backups.append({"host": host, **kwargs})
        return {
            "success": True,
            "logs": ["application-backup"],
            "backup_path": f"/u01/OFSAA_BKP_{kwargs['backup_tag']}.tar.gz",
        }

    async def backup_db_schemas(self, host, username, password, **kwargs):
        self.db_backups.append({"host": host, **kwargs})
        return {
            "success": True,
            "logs": ["db-backup"],
            "timestamp": "20260102_120000",
            "dump_prefix": f"ofsaa_{kwargs['backup_tag'].lower()}",
        }


def test_ensure_valid_backup_reuses_latest_verified_manifest(tmp_path):
    recovery = FakeRecoveryService()
    governor = BackupRestoreGovernorService(recovery)
    governor.manifests = BackupManifestService(str(tmp_path))
    request = build_request()
    manifest = governor.manifests.build_manifest(
        app_host=request.host,
        db_host=request.host,
        tag="BD",
        db_service=request.schema_jdbc_service,
        schemas=[request.schema_atomic_schema_name, request.schema_config_schema_name],
        app_backup_path="/u01/OFSAA_BKP_BD.tar.gz",
        dump_prefix="ofsaa_bd",
        dump_timestamp="20260101_120000",
        metadata_path="/u01/backup/ofsaa/restore_metadata_BD_20260101_120000.sql",
    )
    governor.manifests.write_manifest(request.host, "BD", manifest)

    async def fake_validate_manifest(*args, **kwargs):
        return {"valid": True, "logs": ["validated"]}

    governor.manifests.validate_manifest = fake_validate_manifest

    result = asyncio.run(governor.ensure_valid_backup_before_module("task-1", request, "ECM"))

    assert result["success"] is True
    assert result["decision"] == "backup_reused"
    assert recovery.application_backups == []
    assert recovery.db_backups == []


def test_ensure_valid_backup_creates_new_backup_when_missing(tmp_path):
    recovery = FakeRecoveryService()
    governor = BackupRestoreGovernorService(recovery)
    governor.manifests = BackupManifestService(str(tmp_path))
    request = build_request(install_ecm=False)

    result = asyncio.run(governor.ensure_valid_backup_before_module("task-2", request, "SANC"))

    assert result["success"] is True
    assert result["decision"] == "backup_created"
    assert len(recovery.application_backups) == 1
    assert len(recovery.db_backups) == 1
    assert Path(result["manifest_path"]).exists()


def test_select_restore_manifest_falls_back_to_next_valid_tag(tmp_path):
    recovery = FakeRecoveryService()
    governor = BackupRestoreGovernorService(recovery)
    governor.manifests = BackupManifestService(str(tmp_path))
    request = build_request()
    ecm_manifest = governor.manifests.build_manifest(
        app_host=request.host,
        db_host=request.host,
        tag="ECM",
        db_service=request.ecm_schema_jdbc_service,
        schemas=[request.ecm_schema_atomic_schema_name, request.ecm_schema_config_schema_name],
        app_backup_path="/u01/OFSAA_BKP_ECM.tar.gz",
        dump_prefix="ofsaa_ecm",
        dump_timestamp="20260101_120000",
        metadata_path="/u01/backup/ofsaa/restore_metadata_ECM_20260101_120000.sql",
    )
    bd_manifest = governor.manifests.build_manifest(
        app_host=request.host,
        db_host=request.host,
        tag="BD",
        db_service=request.schema_jdbc_service,
        schemas=[request.schema_atomic_schema_name, request.schema_config_schema_name],
        app_backup_path="/u01/OFSAA_BKP_BD.tar.gz",
        dump_prefix="ofsaa_bd",
        dump_timestamp="20260102_120000",
        metadata_path="/u01/backup/ofsaa/restore_metadata_BD_20260102_120000.sql",
    )
    governor.manifests.write_manifest(request.host, "ECM", ecm_manifest)
    governor.manifests.write_manifest(request.host, "BD", bd_manifest)

    async def fake_validate_manifest(manifest, **kwargs):
        if manifest["tag"] == "ECM":
            return {"valid": False, "logs": ["ecm-invalid"]}
        return {"valid": True, "logs": ["bd-valid"]}

    governor.manifests.validate_manifest = fake_validate_manifest

    result = asyncio.run(governor.select_restore_manifest(request, ["ECM", "BD"]))

    assert result["success"] is True
    assert result["manifest"]["tag"] == "BD"


def test_record_backup_manifest_writes_manifest(tmp_path):
    recovery = FakeRecoveryService()
    governor = BackupRestoreGovernorService(recovery)
    governor.manifests = BackupManifestService(str(tmp_path))
    request = build_request()

    result = governor.record_backup_manifest(
        request=request,
        backup_tag="SANC",
        app_backup_path="/u01/OFSAA_BKP_SANC.tar.gz",
        dump_prefix="ofsaa_sanc",
        dump_timestamp="20260103_120000",
        db_service="SANCPDB1",
        schemas=["SANCATOMIC", "SANCCONFIG"],
    )

    assert result["success"] is True
    assert Path(result["manifest_path"]).exists()