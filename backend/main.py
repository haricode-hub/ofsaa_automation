import json
import logging
import os

from dotenv import load_dotenv
load_dotenv()  # MUST run before any project imports so Config picks up .env values

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.logging import setup_logging
from routers.installation import router as installation_router, installation_tasks, websocket_manager, log_persistence
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OFSAA Installation API",
    description="Backend API for OFSAA installation automation",
    version="1.0.0",
)

# Base origins always allowed (local dev)
_base_origins = [
    "http://localhost:3000",
    "http://localhost",
    "http://127.0.0.1:3000",
]

# Add server origin from env if set (e.g. ALLOWED_ORIGIN=http://192.168.0.166)
_server_origin = os.getenv("ALLOWED_ORIGIN", "").strip()
if _server_origin:
    _allowed_origins = _base_origins + [
        _server_origin,
        f"{_server_origin}:3000",
    ]
else:
    _allowed_origins = _base_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(installation_router, prefix="/api/installation", tags=["installation"])


@app.get("/")
async def root():
    return {"message": "OFSAA Installation API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket_manager.connect(task_id, websocket)
    logger.info("WebSocket connected for task %s", task_id)

    # Push current status if task exists
    task = installation_tasks.get(task_id)
    if task:
        await websocket_manager.send_status(task_id, task.status, task.current_step, task.progress)
    
    # Send full historical logs from disk (not just last 20)
    persisted_logs = await log_persistence.read_all_logs(task_id)
    if persisted_logs:
        await websocket_manager.send_historical_logs(task_id, persisted_logs)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue

            if message.get("type") == "user_input":
                input_text = str(message.get("input", ""))
                websocket_manager.enqueue_user_input(task_id, input_text)
    except WebSocketDisconnect:
        websocket_manager.disconnect(task_id)
        logger.info("WebSocket disconnected for task %s", task_id)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
