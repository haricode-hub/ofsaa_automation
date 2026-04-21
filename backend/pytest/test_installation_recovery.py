import asyncio
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from types import MethodType
from unittest.mock import patch

from core.task_manager import task_manager as tm
from core.task_state_store import TaskStateStore
from core.websocket_manager import WebSocketManager
from routers import installation as installation_router
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
        "install_ecm": True,
        "install_sanc": True,
    }
    payload.update(overrides)
    return payload


class FakeService:
    def __init__(self, call_log):
        self.call_log = call_log

    async def cleanup_failed_fresh_installation(self, host, username, password):
        self.call_log.append({"method": "cleanup_failed_fresh_installation", "host": host})
        return {"success": True, "logs": ["cleanup-ran"]}

    async def verify_fresh_cleanup(self, host, username, password):
        self.call_log.append({"method": "verify_fresh_cleanup", "host": host})
        return {"success": True, "logs": ["cleanup-verified"], "remaining_paths": []}

    async def select_restore_manifest(self, request, restore_tags, **kwargs):
        self.call_log.append({"method": "select_restore_manifest", "host": request.host, "restore_tags": restore_tags})
        chosen_tag = restore_tags[0]
        return {
            "success": True,
            "manifest_path": f"/tmp/{chosen_tag.lower()}_manifest.json",
            "manifest": {
                "tag": chosen_tag,
                "db_service": request.schema_jdbc_service or request.sanc_schema_jdbc_service or "PDB1",
                "schemas": ["OFSATOMIC", "OFSCONFIG"],
                "app_backup": {"path": f"/u01/OFSAA_BKP_{chosen_tag}.tar.gz"},
                "db_backup": {"dump_prefix": f"ofsaa_{chosen_tag.lower()}", "metadata_path": f"/u01/{chosen_tag.lower()}.sql"},
            },
        }

    async def full_restore_from_manifest(self, host, username, password, **kwargs):
        manifest = kwargs["manifest"]
        self.call_log.append({"method": "full_restore_from_manifest", "host": host, "tag": manifest["tag"]})
        return {"success": True, "logs": [f"restored-{manifest['tag']}"], "failed_steps": [], "restored_tag": manifest["tag"]}


@contextmanager
def isolated_recovery_state():
    original = {
        "state_store": tm.state_store,
        "tasks": tm.tasks,
        "task_context": tm.task_context,
        "cancel_events": tm.cancel_events,
        "asyncio_tasks": tm.asyncio_tasks,
        "disconnect_timers": tm._disconnect_timers,
        "append_output": tm.append_output,
        "update_status": tm.update_status,
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
            tm.append_output = original["append_output"]
            tm.update_status = original["update_status"]
            tm.logs = original["logs"]
            tm.ws = original["ws"]


def test_recover_interrupted_tasks_restores_bd_ecm_and_sanc_paths():
    call_log = []

    with isolated_recovery_state():
        async def fake_append_output(self, task_id, text):
            task = self.tasks.get(task_id)
            if task and text:
                task.logs.extend([line for line in text.splitlines() if line.strip()])

        async def fake_update_status(self, task_id, status=None, step=None, progress=None, module=None):
            task = self.tasks.get(task_id)
            if task is None:
                return
            if status:
                task.status = status
            if step:
                task.current_step = step
            if progress is not None:
                task.progress = progress
            if module:
                task.current_module = module
            self._persist_task_state(task_id)

        tm.append_output = MethodType(fake_append_output, tm)
        tm.update_status = MethodType(fake_update_status, tm)

        persisted = [
            {
                "task_id": "task-bd",
                "status": "running",
                "current_step": "Running BD step",
                "current_module": "BD_PACK",
                "progress": 42,
                "logs": [],
                "context": {"request": build_request_payload(install_ecm=False, install_sanc=False)},
            },
            {
                "task_id": "task-ecm",
                "status": "running",
                "current_step": "Running ECM step",
                "current_module": "ECM_PACK",
                "progress": 67,
                "logs": [],
                "context": {"request": build_request_payload(install_sanc=False)},
            },
            {
                "task_id": "task-sanc",
                "status": "running",
                "current_step": "Running SANC step",
                "current_module": "SANC_PACK",
                "progress": 83,
                "logs": [],
                "context": {"request": build_request_payload(sanc_schema_jdbc_service="SANCPDB1")},
            },
        ]
        for payload in persisted:
            tm.state_store.save(payload["task_id"], payload)

        with patch.object(installation_router, "create_installation_service", lambda: FakeService(call_log)):
            asyncio.run(installation_router.recover_interrupted_tasks())

        assert tm.get_task("task-bd").error == "Recovered after backend restart; retry BD if needed"
        assert tm.task_context["task-bd"]["cleanup_status"] == "completed"
        assert tm.get_task("task-ecm").error == "Recovered after backend restart; retry ECM if needed"
        assert tm.task_context["task-ecm"]["rollback_target"] == "BD"
        assert tm.get_task("task-sanc").error == "Recovered after backend restart; retry SANC if needed"
        assert tm.task_context["task-sanc"]["rollback_target"] == "ECM"
        assert [entry["method"] for entry in call_log] == [
            "cleanup_failed_fresh_installation",
            "verify_fresh_cleanup",
            "select_restore_manifest",
            "full_restore_from_manifest",
            "select_restore_manifest",
            "full_restore_from_manifest",
        ]


def test_recover_interrupted_tasks_skips_non_fresh_bd_cleanup():
    call_log = []

    with isolated_recovery_state():
        async def fake_append_output(self, task_id, text):
            return None

        async def fake_update_status(self, task_id, status=None, step=None, progress=None, module=None):
            task = self.tasks.get(task_id)
            if task is None:
                return
            if status:
                task.status = status
            if step:
                task.current_step = step
            self._persist_task_state(task_id)

        tm.append_output = MethodType(fake_append_output, tm)
        tm.update_status = MethodType(fake_update_status, tm)
        tm.state_store.save(
            "task-addon-bd",
            {
                "task_id": "task-addon-bd",
                "status": "running",
                "current_step": "Running BD step",
                "current_module": "BD_PACK",
                "progress": 42,
                "logs": [],
                "context": {"request": build_request_payload(installation_mode="addon", install_ecm=False, install_sanc=False)},
            },
        )

        with patch.object(installation_router, "create_installation_service", lambda: FakeService(call_log)):
            asyncio.run(installation_router.recover_interrupted_tasks())

        assert tm.get_task("task-addon-bd").error == "Backend restarted during BD task; no auto-cleanup for non-fresh install"
        assert call_log == []