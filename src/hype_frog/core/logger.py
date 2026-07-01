from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from rich.console import Console
from rich.logging import RichHandler
from structlog.stdlib import BoundLogger, LoggerFactory, ProcessorFormatter
from structlog.types import EventDict, Processor

from hype_frog.core.env_vars import (
    get_hf_console_log_level,
    get_hf_log_level,
    get_hf_run_id,
)

_LOGGER_ROOT = "hype_frog"
_LOGGING_CONFIGURED = False
_RUN_ID = ""

_LEVEL_MAP: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Shared console — import from here for progress bars, panels, and status spinners.
# legacy_windows=False forces ANSI mode; avoids the legacy Win32 renderer that
# cannot encode non-CP1252 characters in modern Windows Terminal / pwsh sessions.
console = Console(legacy_windows=False)


def _parse_level(name: str, *, default: str) -> int:
    return _LEVEL_MAP.get(name.strip().upper(), _LEVEL_MAP[default])


def _generate_run_id() -> str:
    explicit = get_hf_run_id()
    if explicit:
        return explicit
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{uuid.uuid4().hex[:8]}"


def get_run_id() -> str:
    """Return the active process run correlation ID (empty until configure_logging)."""
    return _RUN_ID


def _add_run_id_processor(
    _logger: logging.Logger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    if _RUN_ID:
        event_dict["run_id"] = _RUN_ID
    return event_dict


def _shared_processors() -> list[Processor]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_run_id_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def _default_logs_dir() -> Path:
    from hype_frog.config import LOGS_DIR  # lazy: avoids config ↔ core import cycle

    return LOGS_DIR


def configure_logging(
    *,
    run_id: str | None = None,
    console_level: int | str | None = None,
    file_level: int | str | None = None,
    log_dir: Path | None = None,
) -> str:
    """Bootstrap structured logging for the hype_frog logger tree.

    Returns the active ``run_id``. Idempotent — safe to call multiple times.
    """
    global _LOGGING_CONFIGURED, _RUN_ID
    if _LOGGING_CONFIGURED:
        return _RUN_ID

    _RUN_ID = run_id or _generate_run_id()

    resolved_console = (
        _parse_level(str(console_level), default="INFO")
        if isinstance(console_level, str)
        else int(console_level)
        if console_level is not None
        else _parse_level(get_hf_console_log_level(), default="INFO")
    )
    resolved_file = (
        _parse_level(str(file_level), default="DEBUG")
        if isinstance(file_level, str)
        else int(file_level)
        if file_level is not None
        else _parse_level(get_hf_log_level(), default="DEBUG")
    )

    base_dir = log_dir or _default_logs_dir()
    base_dir.mkdir(parents=True, exist_ok=True)
    log_file = base_dir / f"crawler_{_RUN_ID}.log"

    pre_chain = _shared_processors()

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *pre_chain,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=LoggerFactory(),
        wrapper_class=BoundLogger,
        cache_logger_on_first_use=True,
    )

    json_formatter = ProcessorFormatter(
        foreign_pre_chain=pre_chain,
        processors=[
            ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(resolved_file)
    file_handler.setFormatter(json_formatter)

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
    rich_handler.setLevel(resolved_console)
    rich_formatter = ProcessorFormatter(
        foreign_pre_chain=pre_chain,
        processors=[
            ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
    )
    rich_handler.setFormatter(rich_formatter)

    app_logger = logging.getLogger(_LOGGER_ROOT)
    app_logger.handlers.clear()
    app_logger.setLevel(logging.DEBUG)
    app_logger.propagate = True
    app_logger.addHandler(rich_handler)
    app_logger.addHandler(file_handler)

    _LOGGING_CONFIGURED = True
    return _RUN_ID


def get_logger(name: str) -> BoundLogger:
    """Return a structlog logger under the ``hype_frog`` namespace."""
    qual_name = name if name.startswith(f"{_LOGGER_ROOT}.") else f"{_LOGGER_ROOT}.{name}"
    return structlog.get_logger(qual_name)


def reset_logging_for_tests() -> None:
    """Test-only helper to allow reconfiguration between test cases."""
    global _LOGGING_CONFIGURED, _RUN_ID
    app_logger = logging.getLogger(_LOGGER_ROOT)
    for handler in list(app_logger.handlers):
        handler.close()
        app_logger.removeHandler(handler)
    _LOGGING_CONFIGURED = False
    _RUN_ID = ""


def resolve_console_level_from_cli(*, verbose: bool, quiet: bool) -> int:
    """Map CLI verbosity flags to a console log level."""
    if verbose and quiet:
        msg = "Cannot combine --verbose and --quiet."
        raise ValueError(msg)
    if verbose:
        return logging.DEBUG
    if quiet:
        return logging.WARNING
    return _parse_level(get_hf_console_log_level(), default="INFO")
