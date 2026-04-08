import asyncio
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


class LogPersistence:
    """Persist task logs to disk for recovery across reconnects and backend restarts."""

    def __init__(self, log_dir: str = "/tmp/ofsaa_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.write_lock: dict[str, asyncio.Lock] = {}

    def get_lock(self, task_id: str) -> asyncio.Lock:
        """Get or create asyncio.Lock for a task to prevent concurrent writes."""
        if task_id not in self.write_lock:
            self.write_lock[task_id] = asyncio.Lock()
        return self.write_lock[task_id]

    def get_log_file(self, task_id: str) -> Path:
        """Get the file path for a task's logs."""
        return self.log_dir / f"{task_id}.log"

    async def append_log(self, task_id: str, text: str) -> None:
        """Append text to task log file asynchronously."""
        if not text or not text.strip():
            return
        
        lock = self.get_lock(task_id)
        log_file = self.get_log_file(task_id)
        
        async with lock:
            try:
                # Write to file with thread-safe async write
                lines = text.rstrip('\n').split('\n')
                timestamp = datetime.now().isoformat()
                content = '\n'.join([f"[{timestamp}] {line}" for line in lines]) + '\n'
                
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                print(f"[ERROR] Failed to write logs for task {task_id}: {e}")

    async def read_all_logs(self, task_id: str) -> list[str]:
        """Read all persisted logs for a task."""
        log_file = self.get_log_file(task_id)
        
        if not log_file.exists():
            return []
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                return f.readlines()
        except Exception as e:
            print(f"[ERROR] Failed to read logs for task {task_id}: {e}")
            return []

    async def read_last_n_logs(self, task_id: str, n: int = 50) -> list[str]:
        """Read last N lines from task logs (for quick page refresh recovery)."""
        log_file = self.get_log_file(task_id)
        
        if not log_file.exists():
            return []
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                return lines[-n:] if len(lines) > n else lines
        except Exception as e:
            print(f"[ERROR] Failed to read logs for task {task_id}: {e}")
            return []

    async def clear_logs(self, task_id: str) -> bool:
        """Delete log file for a completed task (cleanup)."""
        log_file = self.get_log_file(task_id)
        try:
            if log_file.exists():
                log_file.unlink()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to clear logs for task {task_id}: {e}")
            return False
