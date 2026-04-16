"""
FastAPI dependency injection helpers.

Usage in routers:
    from core.dependencies import get_task_manager, get_installation_service

    @router.post("/start")
    async def start(request: ..., tm: TaskManager = Depends(get_task_manager)):
        ...
"""

from core.task_manager import TaskManager, task_manager
from services.installation_service import InstallationService
from services.ssh_service import SSHService


def get_task_manager() -> TaskManager:
    """Return the singleton TaskManager (shared across all routers)."""
    return task_manager


def create_installation_service() -> InstallationService:
    """Create a fresh per-request InstallationService (each task gets its own SSH)."""
    ssh_service = SSHService()
    return InstallationService(ssh_service)
