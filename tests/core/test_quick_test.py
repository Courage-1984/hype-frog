"""Quick-test preset and gate helpers."""

from __future__ import annotations

from hype_frog.core.run_config import (
    QUICK_TEST_BFS_MAX_DEPTH,
    QUICK_TEST_MAX_URLS,
    QUICK_TEST_SITEMAP_URL,
    quick_test_run_config,
)
from hype_frog.reporter.workbook_audit import REQUIRED_FULL_SUITE_SHEETS


def test_quick_test_uses_page_sitemap_seed() -> None:
    config = quick_test_run_config()
    assert config.target_input == QUICK_TEST_SITEMAP_URL
    assert config.target_input.lower().endswith(".xml")


def test_quick_test_caps_urls_and_enables_bfs() -> None:
    config = quick_test_run_config()
    assert config.max_urls == QUICK_TEST_MAX_URLS
    assert config.bfs_max_depth == QUICK_TEST_BFS_MAX_DEPTH
    assert config.full_suite is True
    assert config.crawl_mode == "accurate"


def test_quick_test_psi_cap_when_key_present(monkeypatch) -> None:
    monkeypatch.setenv("PSI_API_KEY", "test-key")
    assert quick_test_run_config().max_psi_urls == 3


def test_quick_test_psi_disabled_without_key(monkeypatch) -> None:
    monkeypatch.delenv("PSI_API_KEY", raising=False)
    assert quick_test_run_config().max_psi_urls == 0


def test_workbook_audit_requires_core_tabs() -> None:
    assert "Table of Contents" in REQUIRED_FULL_SUITE_SHEETS
    assert "Main" in REQUIRED_FULL_SUITE_SHEETS
