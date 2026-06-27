from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

_LOGGING_CONFIGURED = False

# Shared console — import from here for progress bars, panels, and status spinners.
# legacy_windows=False forces ANSI mode; avoids the legacy Win32 renderer that
# cannot encode non-CP1252 characters in modern Windows Terminal / pwsh sessions.
console = Console(legacy_windows=False)


def configure_logging() -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "crawler_runtime.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Console: rich coloured output — short timestamps, no module path clutter.
    # markup=False prevents URLs / bracket chars in log messages being misread as tags.
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        log_time_format="%H:%M:%S",
        rich_tracebacks=True,
        markup=False,
    )
    rich_handler.setLevel(logging.INFO)

    # File: plain text, full detail, rotating (5 MB × 3 backups).
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(rich_handler)
    root_logger.addHandler(file_handler)

    _LOGGING_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    if not _LOGGING_CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
