import asyncio
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import main
from core.task_manager import task_manager as tm
from core.task_state_store import TaskStateStore
from core.websocket_manager import WebSocketManager
from schemas.installation import InstallationStatus
from services.log_persistence import LogPersistence


def build_request_payload(**overrides):
    payload = {
        "host": "10.0.0.10",
        "username": "root",
        "password": "secret",
        "db_sys_password": "dbsecret",
        "schema_jdbc_service": "FLEXPDB1",
        "schema_jdbc_host": "10.0.0.20",
        "schema_config_schema_name": "OFSCONFIG",
        "schema_atomic_schema_name": "OFSATOMIC",
        "installation_mode": "fresh",
        "install_bdpack": True,
        "install_ecm": False,
        "install_sanc": False,
    }
    payload.update(overrides)
    return payload


@contextmanager
def isolated_task_manager():
    original = {
        "state_store": tm.state_store,
        "tasks": tm.tasks,
        "task_context": tm.task_context,
        "cancel_events": tm.cancel_events,
        "asyncio_tasks": tm.asyncio_tasks,
        "disconnect_timers": tm._disconnect_timers,
        "latest_request_cache": dict(tm.latest_request_cache),
        "bd_checkpoint": dict(tm.bd_checkpoint),
        "logs": tm.logs,
        "ws": tm.ws,
    }
    with TemporaryDirectory() as temp_dir:
        tm.state_store = TaskStateStore(temp_dir)
        tm.tasks = {}
        tm.task_context = {}
        tm.cancel_events = {}
        tm.asyncio_tasks = {}
        tm._disconnect_timers = {}
        tm.latest_request_cache = {"request": None, "task_id": None, "error": None}
        tm.bd_checkpoint = {
            "completed": False,
            "request": None,
            "task_id": None,
            "host": None,
            "timestamp": None,
        }
        tm.logs = LogPersistence(temp_dir)
        tm.ws = WebSocketManager()
        try:
            yield
        finally:
            tm.state_store = original["state_store"]
            tm.tasks = original["tasks"]
            tm.task_context = original["task_context"]
            tm.cancel_events = original["cancel_events"]
            tm.asyncio_tasks = original["asyncio_tasks"]
            tm._disconnect_timers = original["disconnect_timers"]
            tm.latest_request_cache = original["latest_request_cache"]
            tm.bd_checkpoint = original["bd_checkpoint"]
            tm.logs = original["logs"]
            tm.ws = original["ws"]


@contextmanager
def api_client():
    async def fake_recover_interrupted_tasks() -> None:
        return None

    with patch.object(main, "recover_interrupted_tasks", fake_recover_interrupted_tasks):
        with TestClient(main.app) as client:
            yield client


def test_start_installation_registers_task_and_request_context():
    async def fake_run_installation_process(task_id, request):
        return None

    with isolated_task_manager():
        with patch("routers.installation.run_installation_process", fake_run_installation_process):
            with api_client() as client:
                response = client.post("/api/installation/start", json=build_request_payload())

        assert response.status_code == 200
        task_id = response.json()["task_id"]
        assert task_id in tm.tasks
        assert tm.task_context[task_id]["request"]["host"] == "10.0.0.10"


def test_status_rollback_and_checkpoint_endpoints():
    with isolated_task_manager():
        tm.register_task(
            "task-123",
            InstallationStatus(
                task_id="task-123",
                status="running",
                current_step="Testing",
                current_module="BD_PACK",
                progress=20,
                logs=[],
            ),
        )
        tm.latest_request_cache["request"] = build_request_payload()
        tm.latest_request_cache["error"] = "previous failure"
        tm.bd_checkpoint.update(
            completed=True,
            request=build_request_payload(),
            task_id="task-123",
            host="10.0.0.10",
            timestamp="2026-04-21T10:00:00",
        )

        with api_client() as client:
            status_response = client.get("/api/installation/status/task-123")
            rollback_response = client.get("/api/installation/rollback")
            checkpoint_response = client.get("/api/installation/checkpoint")
            clear_response = client.delete("/api/installation/checkpoint")

        assert status_response.status_code == 200
        assert status_response.json()["current_module"] == "BD_PACK"
        assert rollback_response.status_code == 200
        assert rollback_response.json()["previous_error"] == "previous failure"
        assert checkpoint_response.status_code == 200
        assert checkpoint_response.json()["bd_pack_completed"] is True
        assert clear_response.status_code == 200
        assert tm.bd_checkpoint["completed"] is False


def test_cancel_endpoint_delegates_to_task_manager():
    with isolated_task_manager():
        tm.register_task(
            "task-cancel",
            InstallationStatus(
                task_id="task-cancel",
                status="running",
                current_step="Testing",
                current_module="ECM_PACK",
                progress=50,
                logs=[],
            ),
        )
        cancel_mock = AsyncMock(return_value=True)

        with patch.object(tm, "cancel_task", cancel_mock):
            with api_client() as client:
                response = client.delete("/api/installation/tasks/task-cancel/cancel")

        assert response.status_code == 200
        assert response.json()["success"] is True
        cancel_mock.assert_awaited_once_with("task-cancel", "Cancelled by user")