import asyncio
import json
from typing import Dict, Optional

from fastapi import WebSocket


class WebSocketManager:
    """Manage task-scoped WebSocket connections and input queues."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, WebSocket] = {}
        self.input_queues: Dict[str, asyncio.Queue[str]] = {}

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[task_id] = websocket
        self.input_queues.setdefault(task_id, asyncio.Queue())

    def disconnect(self, task_id: str) -> None:
        self.active_connections.pop(task_id, None)

    async def send_output(self, task_id: str, text: str) -> None:
        websocket = self.active_connections.get(task_id)
        if websocket is None:
            return
        await websocket.send_text(json.dumps({"type": "output", "data": text}))

    async def send_prompt(self, task_id: str, prompt: str) -> None:
        websocket = self.active_connections.get(task_id)
        if websocket is None:
            return
        await websocket.send_text(json.dumps({"type": "prompt", "data": prompt}))

    async def send_status(
        self,
        task_id: str,
        status: str,
        step: Optional[str] = None,
        progress: Optional[int] = None,
    ) -> None:
        websocket = self.active_connections.get(task_id)
        if websocket is None:
            return
        payload: dict[str, object] = {"status": status}
        if step is not None:
            payload["step"] = step
        if progress is not None:
            payload["progress"] = progress
        await websocket.send_text(json.dumps({"type": "status", "data": payload}))

    async def wait_for_user_input(self, task_id: str, timeout: Optional[int] = None) -> str:
        queue = self.input_queues.setdefault(task_id, asyncio.Queue())
        if timeout:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        return await queue.get()

    def enqueue_user_input(self, task_id: str, text: str) -> None:
        queue = self.input_queues.setdefault(task_id, asyncio.Queue())
        queue.put_nowait(text)
