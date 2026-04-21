from unittest.mock import patch

from fastapi.testclient import TestClient

import main


def test_root_and_health_endpoints_run_startup_recovery_once():
    calls = {"count": 0}

    async def fake_recover_interrupted_tasks() -> None:
        calls["count"] += 1

    with patch.object(main, "recover_interrupted_tasks", fake_recover_interrupted_tasks):
        with TestClient(main.app) as client:
            root_response = client.get("/")
            health_response = client.get("/health")

    assert root_response.status_code == 200
    assert root_response.json() == {"message": "OFSAA Installation API is running"}
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "healthy"}
    assert calls["count"] == 1