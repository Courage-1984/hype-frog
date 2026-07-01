"""Tests for structured logging bootstrap and JSONL output."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from hype_frog.core.logger import (
    configure_logging,
    get_logger,
    get_run_id,
    reset_logging_for_tests,
    resolve_console_level_from_cli,
)


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    reset_logging_for_tests()
    yield
    reset_logging_for_tests()


def test_configure_logging_writes_jsonl_with_run_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_RUN_ID", "test_run_001")
    run_id = configure_logging(log_dir=tmp_path)
    assert run_id == "test_run_001"
    assert get_run_id() == "test_run_001"

    logger = get_logger("tests.sample")
    logger.info("sample_event", url="https://example.com", status_code=200)

    log_files = list(tmp_path.glob("crawler_*.log"))
    assert len(log_files) == 1
    lines = log_files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["run_id"] == "test_run_001"
    assert payload["event"] == "sample_event"
    assert payload["url"] == "https://example.com"
    assert payload["status_code"] == 200
    assert payload["level"] == "info"
    assert "timestamp" in payload
    assert payload["logger"] == "hype_frog.tests.sample"


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    first = configure_logging(log_dir=tmp_path, run_id="stable_id")
    second = configure_logging(log_dir=tmp_path, run_id="other_id")
    assert first == second == "stable_id"
    assert len(list(tmp_path.glob("crawler_*.log"))) == 1


def test_named_logger_does_not_touch_root_logger(tmp_path: Path) -> None:
    root_handlers_before = len(logging.getLogger().handlers)
    configure_logging(log_dir=tmp_path)
    root_handlers_after = len(logging.getLogger().handlers)
    assert root_handlers_before == root_handlers_after

    app_logger = logging.getLogger("hype_frog")
    assert app_logger.propagate is True
    assert len(app_logger.handlers) == 2


def test_resolve_console_level_from_cli() -> None:
    assert resolve_console_level_from_cli(verbose=True, quiet=False) == logging.DEBUG
    assert resolve_console_level_from_cli(verbose=False, quiet=True) == logging.WARNING
    with pytest.raises(ValueError, match="Cannot combine"):
        resolve_console_level_from_cli(verbose=True, quiet=True)


def test_logger_exception_includes_exc_info_in_jsonl(tmp_path: Path) -> None:
    configure_logging(log_dir=tmp_path, run_id="exc_run")
    logger = get_logger("tests.exc")

    try:
        raise RuntimeError("boom")
    except RuntimeError:
        logger.exception("failure_event", phase="test")

    payload = json.loads(list(tmp_path.glob("crawler_*.log"))[0].read_text(encoding="utf-8").strip())
    assert payload["event"] == "failure_event"
    assert payload["level"] == "error"
    assert "exception" in payload
    assert "RuntimeError: boom" in payload["exception"]
