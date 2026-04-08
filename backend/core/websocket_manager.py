import asyncio
import json
from typing import Dict, Optional, Callable

from fastapi import WebSocket


class WebSocketManager:
    """Manage task-scoped WebSocket connections and input queues."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, WebSocket] = {}
        self.input_queues: Dict[str, asyncio.Queue[str]] = {}
        self.on_connect_callback: Optional[Callable] = None  # Called when client connects to send historical logs

    async def connect(self, task_id: str, websocket: WebSocket, on_connect_callback: Optional[Callable] = None) -> None:
        await websocket.accept()
        self.active_connections[task_id] = websocket
        self.input_queues.setdefault(task_id, asyncio.Queue())
        
        # Call callback to send historical logs to newly connected client
        if on_connect_callback:
            await on_connect_callback(task_id, websocket)

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

    async def send_historical_logs(self, task_id: str, logs: list[str]) -> None:
        """Send cached historical logs to a newly connected WebSocket client."""
        websocket = self.active_connections.get(task_id)
        if websocket is None or not logs:
            return
        # Send logs as a bulk batch so client receives full history before continuing
        await websocket.send_text(json.dumps({"type": "historical_logs", "data": logs}))

    async def wait_for_user_input(self, task_id: str, timeout: Optional[int] = None) -> str:
        queue = self.input_queues.setdefault(task_id, asyncio.Queue())
        if timeout:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        return await queue.get()

    def enqueue_user_input(self, task_id: str, text: str) -> None:
        queue = self.input_queues.setdefault(task_id, asyncio.Queue())
        queue.put_nowait(text)
