from __future__ import annotations

import logging
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _hype_frog_test_logging(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    """Bootstrap hype_frog logging so caplog assertions work across the suite."""
    from hype_frog.core.logger import configure_logging, reset_logging_for_tests

    reset_logging_for_tests()
    configure_logging(log_dir=tmp_path / "run_logs", console_level=logging.CRITICAL)
    caplog.set_level(logging.DEBUG, logger="hype_frog")
    yield
    reset_logging_for_tests()


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def empty_page_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "empty_page.html").read_text(encoding="utf-8")


@pytest.fixture
def hreflang_cluster_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "hreflang_cluster.html").read_text(encoding="utf-8")


@pytest.fixture
def malformed_schema_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "malformed_schema.html").read_text(encoding="utf-8")


@pytest.fixture
def aeo_content_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "aeo_content.html").read_text(encoding="utf-8")


@pytest.fixture
def sample_page_html(fixtures_dir: Path) -> str:
    return (fixtures_dir / "sample_page.html").read_text(encoding="utf-8")
