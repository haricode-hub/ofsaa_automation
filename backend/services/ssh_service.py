import asyncio
import logging
import socket
import time
from typing import Any, Callable, Dict, Iterable, Optional

import paramiko
from paramiko.ssh_exception import NoValidConnectionsError

logger = logging.getLogger(__name__)


class SSHService:
    """Handles SSH connections and command execution."""

    def __init__(self) -> None:
        self._client = None

    def _connect(self, host: str, username: str, password: str, timeout: int = 10) -> paramiko.SSHClient:
        attempts = 3
        connect_timeout = max(8, min(int(timeout), 30))
        banner_timeout = max(15, min(int(timeout), 45))
        auth_timeout = max(15, min(int(timeout), 45))
        backoff_seconds = [0.7, 1.5]

        last_exc: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(
                    hostname=host,
                    username=username,
                    password=password,
                    timeout=connect_timeout,
                    banner_timeout=banner_timeout,
                    auth_timeout=auth_timeout,
                    look_for_keys=False,
                    allow_agent=False,
                )
                return client
            except paramiko.AuthenticationException:
                client.close()
                raise
            except (socket.timeout, TimeoutError, paramiko.SSHException, NoValidConnectionsError, OSError) as exc:
                client.close()
                last_exc = exc
                logger.warning("SSH connect attempt %s/%s failed for %s: %s", attempt, attempts, host, exc)
                if attempt < attempts:
                    time.sleep(backoff_seconds[attempt - 1])
                    continue
                raise

        # Defensive fallback to satisfy type checker; loop always returns or raises.
        raise RuntimeError(str(last_exc) if last_exc else "SSH connection failed")

    def _execute_command_sync(
        self,
        host: str,
        username: str,
        password: str,
        command: str,
        timeout: int = 600,
        get_pty: bool = False,
    ) -> Dict[str, Any]:
        start_ts = time.time()
        cmd_preview = " ".join(command.strip().split())[:180]
        logger.info("SSH command start host=%s timeout=%ss pty=%s cmd=%s", host, timeout, get_pty, cmd_preview)
        client = self._connect(host, username, password, timeout=timeout)
        try:
            stdin, stdout, stderr = client.exec_command(command, get_pty=get_pty, timeout=timeout)
            out = stdout.read().decode(errors="ignore")
            err = stderr.read().decode(errors="ignore")
            exit_status = stdout.channel.recv_exit_status()
            elapsed = round(time.time() - start_ts, 2)
            logger.info(
                "SSH command end host=%s rc=%s elapsed=%ss cmd=%s",
                host,
                exit_status,
                elapsed,
                cmd_preview,
            )
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
        start_ts = time.time()
        cmd_preview = " ".join(command.strip().split())[:180]
        logger.info("SSH interactive start host=%s timeout=%ss cmd=%s", host, timeout, cmd_preview)
        patterns = list(prompt_patterns or [
            # Keep these fairly specific to avoid false prompts like:
            # "Validating the input XML file..." (contains 'input' but is not a prompt).
            "Please enter",
            "Enter ",
            "enter ",
            "Password",
            "password",
            "Username",
            "username",
            "SID",
            "sid",
            "Continue",
            "continue",
            "Proceed",
            "proceed",
            "[Y/n]",
            "[y/N]",
            # Common OFSAA scripts (envCheck/osc) prompts
            "Y/N", "(Y/N)", "(Y/y)", "(N/n)", "(y/n)",
            "Do you wish", "Do you want", "ONLINE mode",
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
        # Send SSH keep-alive packets every 60 seconds so the TCP connection
        # is never treated as idle by firewalls/routers during long quiet phases
        # of setup.sh (e.g. Oracle DB inserts that produce no output for 15+ min).
        transport = client.get_transport()
        if transport is not None:
            transport.set_keepalive(60)
        channel = None
        try:
            channel = transport.open_session() if transport is not None else client.get_transport().open_session()
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
                        stripped = last_line.strip()
                        # Be strict: consider it a prompt only when it both:
                        # 1) contains a known prompt keyword, AND
                        # 2) looks like an actual prompt line (ends with ':' or '?' or ')' or contains Y/N variants).
                        has_keyword = any(p in last_line for p in patterns)
                        # Check for Y/N pattern variants: (Y/N), Y/N, (Y/y), (N/n), etc.
                        has_yn_pattern = any(p in last_line for p in ["(Y/N)", "Y/N", "(Y/y)", "(N/n)", "(y/n)", "(y/N)"])
                        looks_like_prompt = stripped.endswith((':', '?', ')')) or has_yn_pattern
                        is_prompt = has_keyword and looks_like_prompt

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
            elapsed = round(time.time() - start_ts, 2)
            logger.info(
                "SSH interactive end host=%s rc=%s elapsed=%ss cmd=%s",
                host,
                exit_status,
                elapsed,
                cmd_preview,
            )
            return {"success": exit_status == 0, "returncode": exit_status}
        finally:
            if channel is not None:
                channel.close()
            client.close()
