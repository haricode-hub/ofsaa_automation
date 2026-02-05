from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
from routers.installation import router as installation_router, websocket_manager
from core.logging import setup_logging

# Setup application logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OFSAA Installation API",
    description="Backend API for Oracle Financial Services installation automation",
    version="1.0.0"
)

logger.info("Starting OFSAA Installation API...")

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(installation_router, prefix="/api/installation", tags=["installation"])

@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time installation updates and interactive prompts"""
    await websocket_manager.connect(task_id, websocket)
    try:
        while True:
            # Receive user input responses
            data = await websocket.receive_json()
            
            if data.get("type") == "user_input":
                # Handle user input for interactive prompts
                await websocket_manager.handle_user_input(task_id, data.get("input", ""))
                
    except WebSocketDisconnect:
        websocket_manager.disconnect(task_id)
        logger.info(f"WebSocket disconnected for task {task_id}")

@app.get("/")
async def root():
    return {"message": "OFSAA Installation API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ofsaa-installation-backend"}

if __name__ == "__main__":
    logger.info("Starting Uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")