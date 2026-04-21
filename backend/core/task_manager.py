"""
Centralized task state management.

All routers share a single TaskManager instance for:
- installation_tasks dict (in-memory task status)
- websocket_manager (WebSocket connections + input queues)
- log_persistence (disk-based log storage)
- append_output / update_status helpers
- cancel_events / asyncio_tasks for task cancellation
"""

import asyncio
import logging
from typing import Optional

from core.task_state_store import TaskStateStore
from core.websocket_manager import WebSocketManager
from schemas.installation import InstallationStatus
from services.log_persistence import LogPersistence

logger = logging.getLogger(__name__)

# Grace period (seconds) before treating a WebSocket disconnect as a cancel.
# Allows page refresh without killing the task.
WS_DISCONNECT_GRACE_SECONDS = 120


class TaskManager:
    """Single source of truth for task state shared across all routers."""

    def __init__(self) -> None:
        self.tasks: dict[str, InstallationStatus] = {}
        self.ws: WebSocketManager = WebSocketManager()
        self.logs: LogPersistence = LogPersistence()
        self.state_store: TaskStateStore = TaskStateStore()
        self.task_context: dict[str, dict] = {}

        # Cancellation infrastructure
        self.cancel_events: dict[str, asyncio.Event] = {}
        self.asyncio_tasks: dict[str, asyncio.Task] = {}
        self._disconnect_timers: dict[str, asyncio.TimerHandle] = {}

        # Cache for latest installation request (rollback after ENVCHECK failure)
        self.latest_request_cache: dict = {
            "request": None,
            "task_id": None,
            "error": None,
        }

        # Checkpoint cache for BD Pack completion (resume ECM from backup)
        self.bd_checkpoint: dict = {
            "completed": False,
            "request": None,
            "task_id": None,
            "host": None,
            "timestamp": None,
        }

    def register_task(self, task_id: str, status: InstallationStatus) -> None:
        self.tasks[task_id] = status
        self.cancel_events[task_id] = asyncio.Event()
        self.task_context[task_id] = {}
        self._persist_task_state(task_id)

    def register_asyncio_task(self, task_id: str, task: asyncio.Task) -> None:
        """Store the asyncio.Task reference so it can be cancelled."""
        self.asyncio_tasks[task_id] = task

    def is_cancelled(self, task_id: str) -> bool:
        """Check if a task has been cancelled."""
        ev = self.cancel_events.get(task_id)
        return ev.is_set() if ev else False

    async def cancel_task(self, task_id: str, reason: str = "Cancelled by user") -> bool:
        """Cancel a running task: set flag, kill SSH, cancel asyncio.Task."""
        task = self.tasks.get(task_id)
        if not task or task.status not in ("started", "running", "waiting_input"):
            return False

        logger.info("Cancelling task %s: %s", task_id, reason)

        # 1. Set cancel event flag (checked between steps)
        ev = self.cancel_events.get(task_id)
        if ev:
            ev.set()

        # 2. Force-close any active SSH connections for this task
        try:
            from services.ssh_service import ssh_service as _ssh
            _ssh.close_task_connections(task_id)
        except Exception as exc:
            logger.warning("Error closing SSH for task %s: %s", task_id, exc)

        # 3. Cancel the asyncio.Task
        atask = self.asyncio_tasks.get(task_id)
        if atask and not atask.done():
            atask.cancel()

        # 4. Update status
        await self.append_output(task_id, f"\n[CANCELLED] {reason}")
        await self.update_status(task_id, "failed", reason)
        self.save_task_context(task_id, cancellation_reason=reason)
        return True

    def cancel_disconnect_timer(self, task_id: str) -> None:
        """Cancel a pending disconnect grace timer (e.g. on reconnect)."""
        handle = self._disconnect_timers.pop(task_id, None)
        if handle is not None:
            handle.cancel()
            logger.info("Disconnect grace timer cancelled for task %s (client reconnected)", task_id)

    def start_disconnect_timer(self, task_id: str) -> None:
        """Start a grace timer; if no reconnect within the window, cancel the task."""
        task = self.tasks.get(task_id)
        if not task or task.status not in ("started", "running", "waiting_input"):
            return  # nothing to cancel

        # Cancel any existing timer first
        self.cancel_disconnect_timer(task_id)

        loop = asyncio.get_event_loop()

        def _fire() -> None:
            self._disconnect_timers.pop(task_id, None)
            # Only cancel if still running AND no active WebSocket (client didn't reconnect)
            ws = self.ws.active_connections.get(task_id)
            t = self.tasks.get(task_id)
            if t and t.status in ("started", "running", "waiting_input") and ws is None:
                logger.info("Grace period expired for task %s — cancelling", task_id)
                asyncio.ensure_future(self.cancel_task(task_id, "Browser disconnected (no reconnect within 2 min)"))

        handle = loop.call_later(WS_DISCONNECT_GRACE_SECONDS, _fire)
        self._disconnect_timers[task_id] = handle
        logger.info("Disconnect grace timer started for task %s (%ss)", task_id, WS_DISCONNECT_GRACE_SECONDS)

    def get_task(self, task_id: str) -> Optional[InstallationStatus]:
        return self.tasks.get(task_id)

    async def append_output(self, task_id: str, text: str) -> None:
        """Send output to WebSocket + persist to disk."""
        if not text:
            return
        task = self.tasks.get(task_id)
        lines = [line for line in text.splitlines() if line.strip()]
        if task:
            task.logs.extend(lines)
        # Send each line as a separate WebSocket message for proper alignment
        for line in lines:
            await self.ws.send_output(task_id, line)
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
        self._persist_task_state(task_id)

    def save_task_context(self, task_id: str, **fields) -> None:
        context = self.task_context.setdefault(task_id, {})
        context.update(fields)
        self._persist_task_state(task_id)

    def _status_to_dict(self, task: InstallationStatus) -> dict:
        if hasattr(task, "model_dump"):
            return task.model_dump()
        return task.dict()

    def _persist_task_state(self, task_id: str) -> None:
        task = self.tasks.get(task_id)
        if task is None:
            return
        payload = self._status_to_dict(task)
        payload["context"] = self.task_context.get(task_id, {})
        self.state_store.save(task_id, payload)

    def clear_bd_checkpoint(self) -> None:
        self.bd_checkpoint.update(
            completed=False,
            request=None,
            task_id=None,
            host=None,
            timestamp=None,
        )

    def restore_persisted_tasks(self) -> list[dict]:
        restored: list[dict] = []
        for payload in self.state_store.list_all():
            task_id = payload.get("task_id")
            if not task_id or task_id in self.tasks:
                continue
            task_payload = {
                "task_id": task_id,
                "status": payload.get("status", "failed"),
                "current_step": payload.get("current_step"),
                "current_module": payload.get("current_module"),
                "progress": payload.get("progress", 0),
                "logs": payload.get("logs", []),
                "error": payload.get("error"),
            }
            task = InstallationStatus(**task_payload)
            if task.status in ("started", "running", "waiting_input"):
                task.status = "interrupted"
                task.error = task.error or "Backend restarted during execution"
            self.tasks[task_id] = task
            self.cancel_events[task_id] = asyncio.Event()
            self.task_context[task_id] = payload.get("context", {})
            restored.append(payload)
        return restored


# ── Module-level singleton ──────────────────────────────────────────────────
task_manager = TaskManager()
