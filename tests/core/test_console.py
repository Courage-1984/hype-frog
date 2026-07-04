"""Tests for `core/console.py` — rich console banners/panels used between pipeline phases.

Before this file, `log_phase_banner`, `log_stage_timer`, `log_startup_panel`, and
`log_completion_panel` had zero test coverage. `console` is a real
`rich.console.Console` instance (`core/logger.py`), so its own `.capture()`
context manager is used to assert real printed content rather than just "did
not raise."
"""

from __future__ import annotations

from pathlib import Path

from hype_frog.core.console import (
    log_completion_panel,
    log_phase_banner,
    log_stage_timer,
    log_startup_panel,
)
from hype_frog.core.logger import console


def test_log_phase_banner_prints_title() -> None:
    with console.capture() as capture:
        log_phase_banner("EXPORT: Building workbook")
    output = capture.get()
    assert "EXPORT: Building workbook" in output


def test_log_stage_timer_yields_and_logs_start_and_completion(caplog) -> None:
    body_ran = False
    with log_stage_timer("Test stage"):
        body_ran = True
    assert body_ran is True
    log_messages = " ".join(record.getMessage() for record in caplog.records)
    assert "Test stage" in log_messages
    assert "started" in log_messages
    assert "completed" in log_messages


def test_log_stage_timer_propagates_exceptions_from_body() -> None:
    class _Boom(Exception):
        pass

    try:
        with log_stage_timer("Failing stage"):
            raise _Boom("kaboom")
    except _Boom:
        pass
    else:
        raise AssertionError("log_stage_timer must not swallow exceptions from its body")


def test_log_startup_panel_prints_key_config_values() -> None:
    with console.capture() as capture:
        log_startup_panel(
            target_input="https://example.com/sitemap.xml",
            url_count=42,
            workers=4,
            request_delay=1.5,
            mode="Full Suite",
            crawl_mode="accurate",
            output_filename="audit.xlsx",
        )
    output = capture.get()
    assert "https://example.com/sitemap.xml" in output
    assert "42" in output
    assert "Full Suite" in output
    assert "accurate" in output
    assert "audit.xlsx" in output


def test_log_completion_panel_prints_summary_without_pdf() -> None:
    with console.capture() as capture:
        log_completion_panel(
            output_filename="audit.xlsx",
            url_count=10,
            elapsed_seconds=125.0,
        )
    output = capture.get()
    assert "10 URLs" in output
    assert "2m 5s" in output
    assert "audit.xlsx" in output
    assert "PDF" not in output


def test_log_completion_panel_includes_pdf_row_when_provided() -> None:
    with console.capture() as capture:
        log_completion_panel(
            output_filename="audit.xlsx",
            url_count=10,
            elapsed_seconds=30.0,
            pdf_filename="audit_executive_summary.pdf",
        )
    output = capture.get()
    assert "0m" not in output  # under a minute renders as "30s", not "0m 30s"
    assert "30s" in output
    assert "audit_executive_summary.pdf" in output


def test_log_completion_panel_handles_missing_output_file_gracefully() -> None:
    # Use a short relative path (not tmp_path) so the rich Panel doesn't
    # truncate it with an ellipsis before the assertion below can see it.
    missing_path = "missing_output.xlsx"
    with console.capture() as capture:
        log_completion_panel(output_filename=missing_path, url_count=1, elapsed_seconds=1.0)
    output = capture.get()
    assert missing_path in output
    assert "MB" not in output  # no file size suffix when the file can't be stat'd


def test_log_completion_panel_includes_file_size_when_file_exists(tmp_path: Path) -> None:
    real_path = tmp_path / "real.xlsx"
    real_path.write_bytes(b"0" * 2_097_152)  # 2 MB
    with console.capture() as capture:
        log_completion_panel(output_filename=str(real_path), url_count=1, elapsed_seconds=1.0)
    output = capture.get()
    assert "MB" in output
