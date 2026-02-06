import logging
import time
from contextlib import contextmanager


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


@contextmanager
def log_execution_time(logger: logging.Logger, message: str):
    start = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start
        logger.info("%s (%.2fs)", message, elapsed)


class TaskLogger:
    """Simple helper for task-scoped log accumulation."""

    def __init__(self) -> None:
        self.logs: list[str] = []

    def add(self, line: str) -> None:
        self.logs.append(line)
