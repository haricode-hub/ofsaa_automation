"""
Reusable prompt-callback factories for interactive SSH commands.

Eliminates the 4x-duplicated Y/N pattern across BD/ECM/SANC prompt callbacks.
"""

from typing import Callable, Awaitable, Optional

from core.task_manager import TaskManager

# Common Y/N confirmation patterns (lowercase)
YN_PATTERNS = [
    "(y/n)", "(y/y)", "(n/n)", "(n/y)",
    "(y)", "(n)",
    "y/y", "n/n", "y/n", "n/y",
    "enter (y", "enter (n", "enter y", "enter n",
    "to proceed",
    "y to", "n to",
    "y or n", "yes or no",
    "(yes/no)", "yes/no",
    "to change the selection",
]


def is_yn_prompt(prompt: str) -> bool:
    prompt_lower = prompt.lower()
    return any(p in prompt_lower for p in YN_PATTERNS)


async def _forward_to_user(
    tm: TaskManager,
    task_id: str,
    prompt: str,
) -> str:
    """Forward a prompt to the user via WebSocket and wait for input."""
    task = tm.get_task(task_id)
    current_step = task.current_step if task else None
    await tm.append_output(task_id, f"[PROMPT] {prompt}")
    await tm.ws.send_prompt(task_id, prompt)
    await tm.update_status(task_id, "waiting_input", current_step)
    response = await tm.ws.wait_for_user_input(task_id, timeout=3600)
    await tm.update_status(task_id, "running", current_step)
    return response


def make_osc_prompt_callback(
    tm: TaskManager,
    task_id: str,
    db_password: str,
) -> Callable[[str], Awaitable[str]]:
    """Create a prompt callback for osc.sh (BD/ECM/SANC).

    Auto-answers:
        - SYSDBA username -> "SYS AS SYSDBA"
        - Password prompts -> db_password
        - Y/N confirmations -> "Y"
    Forwards everything else to the user.
    """

    async def callback(prompt: str) -> str:
        prompt_lower = prompt.lower()

        # SYSDBA username
        if "db user name" in prompt_lower or (
            "oracle" in prompt_lower and "user name" in prompt_lower
        ):
            await tm.append_output(task_id, f"[AUTO-ANSWER] {prompt} -> SYS AS SYSDBA")
            return "SYS AS SYSDBA"

        # Password
        if (
            "user password" in prompt_lower
            or "enter the password" in prompt_lower
            or "enter password" in prompt_lower
        ):
            await tm.append_output(task_id, f"[AUTO-ANSWER] {prompt} -> ********")
            return db_password

        # Y/N
        if is_yn_prompt(prompt):
            await tm.append_output(task_id, f"[AUTO-ANSWER Y] {prompt}")
            return "Y"

        return await _forward_to_user(tm, task_id, prompt)

    return callback


def make_envcheck_prompt_callback(
    tm: TaskManager,
    task_id: str,
    db_password: str,
    oracle_sid: str,
) -> Callable[[str], Awaitable[str]]:
    """Create a prompt callback for BD envCheck.

    Auto-answers DB username, password, Oracle SID, and Y/N.
    """

    async def callback(prompt: str) -> str:
        prompt_lower = prompt.lower()

        # DB username
        if "db user name" in prompt_lower or (
            "oracle" in prompt_lower and "user name" in prompt_lower
        ):
            await tm.append_output(task_id, f"[AUTO-ANSWER] {prompt} -> SYS AS SYSDBA")
            return "SYS AS SYSDBA"

        # Password
        if (
            "enter password" in prompt_lower
            or "enter the password" in prompt_lower
            or prompt_lower.strip().startswith("please enter password")
        ):
            await tm.append_output(task_id, f"[AUTO-ANSWER] {prompt} -> ********")
            return db_password

        # Oracle SID / service name
        if ("oracle sid" in prompt_lower or "service name" in prompt_lower) and "enter" in prompt_lower:
            await tm.append_output(task_id, f"[AUTO-ANSWER] {prompt} -> {oracle_sid}")
            return oracle_sid

        # Y/N
        if is_yn_prompt(prompt):
            await tm.append_output(task_id, f"[AUTO-ANSWER Y] {prompt}")
            return "Y"

        return await _forward_to_user(tm, task_id, prompt)

    return callback


def make_setup_prompt_callback(
    tm: TaskManager,
    task_id: str,
    sftp_password: Optional[str] = None,
) -> Callable[[str], Awaitable[str]]:
    """Create a prompt callback for setup.sh SILENT.

    Auto-answers:
        - SFTP password -> sftp_password (if configured)
        - Y/N confirmations -> "Y"
    Forwards everything else to the user.
    """

    async def callback(prompt: str) -> str:
        prompt_lower = prompt.lower()

        # SFTP password (BD Pack step 10 only)
        if "please enter infrastructure ftp/sftp password" in prompt_lower:
            if sftp_password:
                await tm.append_output(task_id, f"[AUTO-ANSWER SFTP] {prompt} -> ********")
                return sftp_password
            return await _forward_to_user(tm, task_id, prompt)

        # Y/N
        if is_yn_prompt(prompt):
            await tm.append_output(task_id, f"[AUTO-ANSWER Y] {prompt}")
            return "Y"

        return await _forward_to_user(tm, task_id, prompt)

    return callback
