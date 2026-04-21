import asyncio

from services.backup_manifest import BackupManifestService


class FakeSSHService:
    def __init__(self, responses):
        self.responses = list(responses)
        self.commands = []

    async def execute_command(self, host, username, password, command, **kwargs):
        self.commands.append({
            "host": host,
            "username": username,
            "command": command,
        })
        return self.responses.pop(0)


def test_manifest_build_write_and_load_latest(tmp_path):
    service = BackupManifestService(str(tmp_path))
    old_manifest = service.build_manifest(
        app_host="10.0.0.10",
        db_host="10.0.0.20",
        tag="BD",
        db_service="FLEXPDB1",
        schemas=["ofsatomic", "ofsconfig"],
        app_backup_path="/u01/OFSAA_BKP_BD_old.tar.gz",
        dump_prefix="ofsaa_bd_old",
        dump_timestamp="20260101_120000",
        metadata_path="/u01/backup/ofsaa/restore_metadata_BD_20260101_120000.sql",
    )
    new_manifest = service.build_manifest(
        app_host="10.0.0.10",
        db_host="10.0.0.20",
        tag="BD",
        db_service="FLEXPDB1",
        schemas=["OFSATOMIC", "OFSCONFIG"],
        app_backup_path="/u01/OFSAA_BKP_BD_new.tar.gz",
        dump_prefix="ofsaa_bd_new",
        dump_timestamp="20260102_120000",
        metadata_path="/u01/backup/ofsaa/restore_metadata_BD_20260102_120000.sql",
    )

    first_path = service.write_manifest("10.0.0.10", "BD", old_manifest)
    second_path = service.write_manifest("10.0.0.10", "BD", new_manifest)
    latest = service.load_latest_manifest("10.0.0.10", "BD")
    explicit = service.load_manifest(first_path)

    assert second_path.endswith("BD_20260102_120000.json")
    assert latest is not None
    assert latest["app_backup"]["path"] == "/u01/OFSAA_BKP_BD_new.tar.gz"
    assert latest["manifest_path"].endswith("BD_20260102_120000.json")
    assert explicit["manifest_path"] == first_path
    assert explicit["schemas"] == ["OFSATOMIC", "OFSCONFIG"]


def test_validate_manifest_accepts_complete_backup_set(tmp_path):
    service = BackupManifestService(str(tmp_path))
    manifest = service.build_manifest(
        app_host="10.0.0.10",
        db_host="10.0.0.20",
        tag="ECM",
        db_service="FLEXPDB1",
        schemas=["OFSATOMIC", "OFSCONFIG"],
        app_backup_path="/u01/OFSAA_BKP_ECM.tar.gz",
        dump_prefix="ofsaa_ecm",
        dump_timestamp="20260102_120000",
        metadata_path="/u01/backup/ofsaa/restore_metadata_ECM_20260102_120000.sql",
    )
    ssh_service = FakeSSHService(
        [
            {"success": True, "stdout": "120\n"},
            {"success": True, "stdout": "64\n"},
            {"success": True, "stdout": "2\n"},
        ]
    )

    result = asyncio.run(
        service.validate_manifest(
            manifest,
            ssh_service=ssh_service,
            app_ssh_host="10.0.0.10",
            app_ssh_username="root",
            app_ssh_password="secret",
            db_ssh_host="10.0.0.20",
            db_ssh_username="oracle",
            db_ssh_password="dbsecret",
            expected_tag="ECM",
            expected_db_service="FLEXPDB1",
            expected_schemas=["OFSATOMIC", "OFSCONFIG"],
        )
    )

    assert result["valid"] is True
    assert result["manifest"]["validated_at"].endswith("Z")
    assert len(ssh_service.commands) == 3


def test_validate_manifest_rejects_schema_mismatch(tmp_path):
    service = BackupManifestService(str(tmp_path))
    manifest = service.build_manifest(
        app_host="10.0.0.10",
        db_host="10.0.0.20",
        tag="BD",
        db_service="FLEXPDB1",
        schemas=["OFSATOMIC", "OFSCONFIG"],
        app_backup_path="/u01/OFSAA_BKP_BD.tar.gz",
        dump_prefix="ofsaa_bd",
        dump_timestamp="20260102_120000",
        metadata_path="/u01/backup/ofsaa/restore_metadata_BD_20260102_120000.sql",
    )

    result = asyncio.run(
        service.validate_manifest(
            manifest,
            ssh_service=FakeSSHService([]),
            app_ssh_host="10.0.0.10",
            app_ssh_username="root",
            app_ssh_password="secret",
            db_ssh_host="10.0.0.20",
            db_ssh_username="oracle",
            db_ssh_password="dbsecret",
            expected_tag="BD",
            expected_db_service="FLEXPDB1",
            expected_schemas=["OTHERCONFIG", "OTHERATOMIC"],
        )
    )

    assert result["valid"] is False
    assert "schema mismatch" in result["logs"][0].lower()