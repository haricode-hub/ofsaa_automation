from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
from routers.installation import router as installation_router
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

@app.get("/")
async def root():
    return {"message": "OFSAA Installation API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ofsaa-installation-backend"}

if __name__ == "__main__":
    logger.info("Starting Uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")