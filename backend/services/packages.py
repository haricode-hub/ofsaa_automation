from typing import List

from .ssh_service import SSHService
from .validation import ValidationService


class PackageService:
    """Install required OS packages."""

    def __init__(self, ssh_service: SSHService, validation: ValidationService) -> None:
        self.ssh_service = ssh_service
        self.validation = validation

    async def ensure_packages(
        self,
        host: str,
        username: str,
        password: str,
        packages: List[str],
    ) -> dict:
        logs: list[str] = []
        missing: list[str] = []

        for pkg in packages:
            status = await self.validation.check_package_installed(host, username, password, pkg)
            if status.get("installed"):
                logs.append(f"[OK] {pkg} already installed")
            else:
                missing.append(pkg)

        if not missing:
            return {"success": True, "logs": logs}

        pkg_list = " ".join(missing)
        install_cmd = (
            "if command -v dnf >/dev/null 2>&1; then "
            f"dnf install -y {pkg_list}; "
            "elif command -v yum >/dev/null 2>&1; then "
            f"yum install -y {pkg_list}; "
            "else echo 'No supported package manager found' && exit 1; fi"
        )
        result = await self.ssh_service.execute_command(
            host, username, password, install_cmd, timeout=1800, get_pty=True
        )
        if not result["success"]:
            return {
                "success": False,
                "logs": logs,
                "error": result.get("stderr") or "Package installation failed",
            }
        logs.append(f"[OK] Installed packages: {pkg_list}")
        return {"success": True, "logs": logs}
