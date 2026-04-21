import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class TaskStateStore:
    def __init__(self, state_dir: Optional[str] = None) -> None:
        base_dir = Path(state_dir) if state_dir else Path(tempfile.gettempdir()) / "ofsaa_task_state"
        self.state_dir = base_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, task_id: str) -> Path:
        return self.state_dir / f"{task_id}.json"

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)

    def save(self, task_id: str, payload: dict[str, Any]) -> str:
        enriched = dict(payload)
        enriched["persisted_at"] = datetime.utcnow().isoformat() + "Z"
        path = self._path_for(task_id)
        self._write_json_atomic(path, enriched)
        return str(path)

    def load(self, task_id: str) -> Optional[dict[str, Any]]:
        path = self._path_for(task_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_all(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.state_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["state_path"] = str(path)
                items.append(payload)
            except Exception:
                continue
        return items

    def delete(self, task_id: str) -> None:
        path = self._path_for(task_id)
        if path.exists():
            path.unlink()