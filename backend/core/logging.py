import logging
import time
from functools import wraps
from typing import Callable, Any, List
from core.config import Config

def setup_logging(log_level: str = "INFO") -> None:
    """Setup application logging with optimized file handling"""
    # Only create log file if not in optimized mode
    handlers = [logging.StreamHandler()]
    
    if not Config.CLEANUP_TEMP_FILES:
        handlers.append(logging.FileHandler('installation.log'))
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

def truncate_logs(logs: List[str], max_lines: int = None) -> List[str]:
    """Truncate logs to prevent memory issues"""
    max_lines = max_lines or Config.MAX_LOG_LINES
    if len(logs) > max_lines:
        # Keep first 10% and last 90% of logs
        keep_start = int(max_lines * 0.1)
        keep_end = max_lines - keep_start
        truncated = logs[:keep_start] + [f"... ({len(logs) - max_lines} lines truncated) ..."] + logs[-keep_end:]
        return truncated
    return logs

def log_execution_time(func: Callable) -> Callable:
    """Decorator to log function execution time"""
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        logger = logging.getLogger(func.__module__)
        
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} executed in {execution_time:.2f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.2f} seconds: {str(e)}")
            raise
    
    return wrapper

def sanitize_log_message(message: str) -> str:
    """Sanitize log messages to remove sensitive information"""
    # Remove password-like patterns
    import re
    # Hide passwords in commands
    message = re.sub(r'password=\S+', 'password=***', message)
    message = re.sub(r'-p\s+\S+', '-p ***', message)
    return message

class TaskLogger:
    """Logger for installation tasks"""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.logger = logging.getLogger(f"task.{task_id[:8]}")
    
    def info(self, message: str) -> None:
        """Log info message"""
        safe_message = sanitize_log_message(message)
        self.logger.info(f"[{self.task_id[:8]}] {safe_message}")
    
    def error(self, message: str) -> None:
        """Log error message"""
        safe_message = sanitize_log_message(message)
        self.logger.error(f"[{self.task_id[:8]}] {safe_message}")
    
    def debug(self, message: str) -> None:
        """Log debug message"""
        safe_message = sanitize_log_message(message)
        self.logger.debug(f"[{self.task_id[:8]}] {safe_message}")
    
    def warning(self, message: str) -> None:
        """Log warning message"""
        safe_message = sanitize_log_message(message)
        self.logger.warning(f"[{self.task_id[:8]}] {safe_message}")