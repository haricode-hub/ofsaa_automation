"""
Centralized task state management.

All routers share a single TaskManager instance for:
- installation_tasks dict (in-memory task status)
- websocket_manager (WebSocket connections + input queues)
- log_persistence (disk-based log storage)
- append_output / update_status helpers
"""

import logging
from typing import Optional

from core.websocket_manager import WebSocketManager
from schemas.installation import InstallationStatus
from services.log_persistence import LogPersistence

logger = logging.getLogger(__name__)


class TaskManager:
    """Single source of truth for task state shared across all routers."""

    def __init__(self) -> None:
        self.tasks: dict[str, InstallationStatus] = {}
        self.ws: WebSocketManager = WebSocketManager()
        self.logs: LogPersistence = LogPersistence()

        # Cache for latest installation request (rollback after ENVCHECK failure)
        self.latest_request_cache: dict = {
            "request": None,
            "task_id": None,
            "error": None,
        }

        # Checkpoint cache for BD Pack completion (resume ECM from backup)
        self.bd_checkpoint: dict = {
            "completed": False,
            "backup_taken": False,
            "request": None,
            "task_id": None,
            "host": None,
            "timestamp": None,
        }

    def register_task(self, task_id: str, status: InstallationStatus) -> None:
        self.tasks[task_id] = status

    def get_task(self, task_id: str) -> Optional[InstallationStatus]:
        return self.tasks.get(task_id)

    async def append_output(self, task_id: str, text: str) -> None:
        """Send output to WebSocket + persist to disk."""
        if not text:
            return
        task = self.tasks.get(task_id)
        if task:
            lines = [line for line in text.splitlines() if line.strip()]
            task.logs.extend(lines)
        await self.ws.send_output(task_id, text)
        await self.logs.append_log(task_id, text)

    async def update_status(
        self,
        task_id: str,
        status: Optional[str] = None,
        step: Optional[str] = None,
        progress: Optional[int] = None,
        module: Optional[str] = None,
    ) -> None:
        """Update in-memory task status and push via WebSocket."""
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
        await self.ws.send_status(
            task_id, task.status, task.current_step, task.progress, task.current_module
        )

    def clear_bd_checkpoint(self) -> None:
        self.bd_checkpoint.update(
            completed=False,
            backup_taken=False,
            request=None,
            task_id=None,
            host=None,
            timestamp=None,
        )


# ── Module-level singleton ──────────────────────────────────────────────────
task_manager = TaskManager()
