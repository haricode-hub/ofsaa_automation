from core.task_state_store import TaskStateStore


def test_task_state_store_save_load_list_and_delete(tmp_path):
    store = TaskStateStore(str(tmp_path))
    payload = {
        "task_id": "task-1",
        "status": "running",
        "current_step": "Testing",
        "context": {"module": "BD"},
    }

    saved_path = store.save("task-1", payload)
    loaded = store.load("task-1")
    listed = store.list_all()

    assert saved_path.endswith("task-1.json")
    assert loaded is not None
    assert loaded["task_id"] == "task-1"
    assert loaded["status"] == "running"
    assert loaded["context"] == {"module": "BD"}
    assert len(listed) == 1
    assert listed[0]["task_id"] == "task-1"
    assert listed[0]["state_path"].endswith("task-1.json")

    store.delete("task-1")

    assert store.load("task-1") is None
    assert store.list_all() == []