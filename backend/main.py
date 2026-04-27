"""OFSAA Installation API — FastAPI application entry point."""

import json
import logging
import os

from dotenv import load_dotenv
load_dotenv()  # MUST run before any project imports so Config picks up .env values

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core.logging import setup_logging
from core.task_manager import task_manager as tm
from routers.installation import router as installation_router
from routers.installation import recover_interrupted_tasks
from routers.deployment import router as deployment_router
from routers.datasource import router as datasource_router

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OFSAA Installation API",
    description="Backend API for OFSAA installation automation",
    version="1.0.0",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
_allowed_origins: list[str] = []

_allowed_origin = os.getenv("ALLOWED_ORIGIN", "").strip()
if _allowed_origin:
    _allowed_origins.append(_allowed_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(installation_router, prefix="/api/installation", tags=["installation"])
app.include_router(deployment_router, prefix="/api/installation", tags=["deployment"])
app.include_router(datasource_router, prefix="/api/installation", tags=["datasource"])


@app.get("/")
async def root():
    return {"message": "OFSAA Installation API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_recovery() -> None:
    await recover_interrupted_tasks()


# ── WebSocket ────────────────────────────────────────────────────────────────
@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await tm.ws.connect(task_id, websocket)
    logger.info("WebSocket connected for task %s", task_id)

    task = tm.get_task(task_id)
    if task:
        await tm.ws.send_status(
            task_id, task.status, task.current_step, task.progress, task.current_module,
        )

    persisted_logs = await tm.logs.read_all_logs(task_id)
    if persisted_logs:
        await tm.ws.send_historical_logs(task_id, persisted_logs)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue

            if message.get("type") == "user_input":
                input_text = str(message.get("input", ""))
                tm.ws.enqueue_user_input(task_id, input_text)
    except WebSocketDisconnect:
        tm.ws.disconnect(task_id)
        logger.info("WebSocket disconnected for task %s", task_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("BACKEND_HOST", "0.0.0.0"),
        port=int(os.getenv("BACKEND_PORT", "8000")),
        reload=True,
        log_level="info",
    )
