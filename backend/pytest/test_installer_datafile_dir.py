from unittest.mock import AsyncMock

import pytest

from services.installer import InstallerService


def build_service() -> InstallerService:
    return InstallerService(AsyncMock(), AsyncMock())


def test_validate_datafile_dir_accepts_linux_path():
    service = build_service()

    normalized = service._validate_datafile_dir(
        "/u01/app/oracle/oradata/OFSAA/OFSAADB/",
        label="SANC schema datafile directory",
    )

    assert normalized == "/u01/app/oracle/oradata/OFSAA/OFSAADB"


def test_validate_datafile_dir_rejects_sqlplus_connection_string():
    service = build_service()

    with pytest.raises(ValueError, match="filesystem path"):
        service._validate_datafile_dir(
            "sqlplus OFSCONFIG1/oracle123@OFSAAPDB2",
            label="SANC schema datafile directory",
        )