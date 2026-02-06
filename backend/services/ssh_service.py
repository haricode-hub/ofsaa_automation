import asyncio
import time
from typing import Any, Callable, Dict, Iterable, Optional

import paramiko


class SSHService:
    """Handles SSH connections and command execution."""

    def __init__(self) -> None:
        self._client = None

    def _connect(self, host: str, username: str, password: str, timeout: int = 10) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=host,
            username=username,
            password=password,
            timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        return client

    def _execute_command_sync(
        self,
        host: str,
        username: str,
        password: str,
        command: str,
        timeout: int = 600,
        get_pty: bool = False,
    ) -> Dict[str, Any]:
        client = self._connect(host, username, password, timeout=timeout)
        try:
            stdin, stdout, stderr = client.exec_command(command, get_pty=get_pty, timeout=timeout)
            out = stdout.read().decode(errors="ignore")
            err = stderr.read().decode(errors="ignore")
            exit_status = stdout.channel.recv_exit_status()
            return {
                "success": exit_status == 0,
                "stdout": out.strip(),
                "stderr": err.strip(),
                "returncode": exit_status,
            }
        finally:
            client.close()

    async def execute_command(
        self,
        host: str,
        username: str,
        password: str,
        command: str,
        timeout: int = 600,
        get_pty: bool = False,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._execute_command_sync,
            host,
            username,
            password,
            command,
            timeout,
            get_pty,
        )

    async def test_connection(self, host: str, username: str, password: str) -> Dict[str, Any]:
        try:
            result = await self.execute_command(host, username, password, "echo connected", timeout=10)
            if result["success"]:
                return {"success": True, "message": "SSH connection successful"}
            return {"success": False, "error": result.get("stderr") or "SSH connection failed"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def execute_interactive_command(
        self,
        host: str,
        username: str,
        password: str,
        command: str,
        on_output_callback: Optional[Callable[[str], Any]] = None,
        on_prompt_callback: Optional[Callable[[str], Any]] = None,
        timeout: int = 1800,
        prompt_patterns: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await asyncio.to_thread(
            self._execute_interactive_sync,
            host,
            username,
            password,
            command,
            on_output_callback,
            on_prompt_callback,
            timeout,
            prompt_patterns,
            loop,
        )

    def _execute_interactive_sync(
        self,
        host: str,
        username: str,
        password: str,
        command: str,
        on_output_callback: Optional[Callable[[str], Any]],
        on_prompt_callback: Optional[Callable[[str], Any]],
        timeout: int,
        prompt_patterns: Optional[Iterable[str]],
        loop: asyncio.AbstractEventLoop,
    ) -> Dict[str, Any]:
        patterns = list(prompt_patterns or [
            "Enter", "enter", "Input", "input", "Type", "type",
            "Please", "please",
            "Password", "password", "Continue", "Proceed", "[Y/n]", "[y/N]",
            "SID", "sid", "Username", "username",
        ])

        def schedule_output(text: str) -> None:
            if on_output_callback is None:
                return
            try:
                result = on_output_callback(text)
                if asyncio.iscoroutine(result):
                    asyncio.run_coroutine_threadsafe(result, loop)
            except Exception:
                # Ignore streaming errors
                pass

        def prompt_for_input(prompt_text: str) -> Optional[str]:
            if on_prompt_callback is None:
                return None
            try:
                result = on_prompt_callback(prompt_text)
                if asyncio.iscoroutine(result):
                    future = asyncio.run_coroutine_threadsafe(result, loop)
                    return future.result()
                return result
            except Exception:
                return None

        client = self._connect(host, username, password, timeout=10)
        channel = None
        try:
            channel = client.get_transport().open_session()
            channel.get_pty()
            channel.exec_command(command)
            channel.settimeout(1.0)

            buffer = ""
            last_prompt = None
            start_time = time.time()

            while True:
                if time.time() - start_time > timeout:
                    raise TimeoutError("Interactive command timed out")

                if channel.recv_ready():
                    data = channel.recv(4096).decode(errors="ignore")
                    if data:
                        buffer += data
                        schedule_output(data)

                        last_line = buffer.splitlines()[-1] if buffer.splitlines() else buffer
                        # Be strict: only treat output as a prompt if it contains known prompt keywords.
                        # This avoids false prompts like "[INFO] VerInfo ...:" getting routed to the UI input box.
                        is_prompt = any(p in last_line for p in patterns)

                        if is_prompt and last_line.strip() and last_line != last_prompt:
                            last_prompt = last_line
                            response = prompt_for_input(last_line.strip())
                            if response is not None:
                                channel.send(str(response).rstrip("\n") + "\n")
                                buffer = ""

                if channel.exit_status_ready():
                    if not channel.recv_ready() and not channel.recv_stderr_ready():
                        break
                time.sleep(0.1)

            exit_status = channel.recv_exit_status()
            return {"success": exit_status == 0, "returncode": exit_status}
        finally:
            if channel is not None:
                channel.close()
            client.close()
