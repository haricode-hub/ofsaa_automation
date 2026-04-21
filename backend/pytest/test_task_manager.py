from core.task_manager import TaskManager
from core.task_state_store import TaskStateStore
from schemas.installation import InstallationStatus


def test_save_task_context_persists_task_metadata(tmp_path):
    manager = TaskManager()
    manager.state_store = TaskStateStore(str(tmp_path / "state"))

    manager.register_task(
        "task-ctx",
        InstallationStatus(
            task_id="task-ctx",
            status="started",
            current_step="Init",
            current_module="BD_PACK",
            progress=0,
            logs=[],
        ),
    )
    manager.save_task_context("task-ctx", backup_tag="BD", cleanup_status="started")

    persisted = manager.state_store.load("task-ctx")

    assert persisted is not None
    assert persisted["context"] == {"backup_tag": "BD", "cleanup_status": "started"}


def test_restore_persisted_tasks_marks_active_tasks_interrupted(tmp_path):
    manager = TaskManager()
    manager.state_store = TaskStateStore(str(tmp_path / "state"))
    manager.state_store.save(
        "task-running",
        {
            "task_id": "task-running",
            "status": "running",
            "current_step": "Installing",
            "current_module": "ECM_PACK",
            "progress": 65,
            "logs": ["line-1"],
            "context": {"request": {"host": "10.0.0.10"}},
        },
    )
    manager.state_store.save(
        "task-complete",
        {
            "task_id": "task-complete",
            "status": "completed",
            "current_step": "Done",
            "current_module": "BD_PACK",
            "progress": 100,
            "logs": [],
            "context": {},
        },
    )

    restored = manager.restore_persisted_tasks()

    assert {item["task_id"] for item in restored} == {"task-running", "task-complete"}
    assert manager.tasks["task-running"].status == "interrupted"
    assert manager.tasks["task-running"].error == "Backend restarted during execution"
    assert manager.task_context["task-running"] == {"request": {"host": "10.0.0.10"}}
    assert manager.tasks["task-complete"].status == "completed"