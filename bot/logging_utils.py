"""Centralized logging: file + STDOUT, Persian-friendly error handling."""
import logging
import sys
from pathlib import Path

from core.config import LOGS_DIR


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / "bot_errors.log"
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt))
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(fmt))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(stdout_handler)
    # Reduce noise from libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telethon").setLevel(logging.WARNING)
    # Always print log file location
    print(f"Log file: {log_file.resolve()}", flush=True)
    logging.getLogger(__name__).info("Log file: %s", log_file.resolve())


def log_exception(logger: logging.Logger, message: str, exc: BaseException) -> None:
    logger.exception("%s: %s", message, exc)
