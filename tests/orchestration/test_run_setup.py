"""Run setup resolution for preset and interactive entrypoints."""

from __future__ import annotations

from hype_frog.core.env_vars import get_hf_gsc_url_inspection
from hype_frog.core.run_config import RunConfig, quick_test_run_config
from hype_frog.orchestration import run_setup
from hype_frog.orchestration.run_setup import (
    _parse_competitor_domains,
    _resolve_max_memory_mb,
    resolve_run_setup,
)


def test_parse_competitor_domains_strips_scheme_and_blanks() -> None:
    parsed = _parse_competitor_domains("https://A.com/, http://b.org , , c.net/")
    assert parsed == ("a.com", "b.org", "c.net")
    assert _parse_competitor_domains("") == ()


def test_resolve_gsc_url_inspection_env(monkeypatch) -> None:
    monkeypatch.setenv("GSC_URL_INSPECTION", "limited")
    assert get_hf_gsc_url_inspection() == "limited"
    monkeypatch.setenv("GSC_URL_INSPECTION", "full")
    assert get_hf_gsc_url_inspection() == "full"
    monkeypatch.setenv("GSC_URL_INSPECTION", "off")
    assert get_hf_gsc_url_inspection() is None
    monkeypatch.delenv("GSC_URL_INSPECTION", raising=False)
    assert get_hf_gsc_url_inspection() is None


def test_resolve_max_memory_mb_env(monkeypatch) -> None:
    monkeypatch.setenv("HF_MAX_MEMORY_MB", "2048")
    assert _resolve_max_memory_mb() == 2048
    monkeypatch.setenv("HF_MAX_MEMORY_MB", "0")
    assert _resolve_max_memory_mb() is None
    monkeypatch.setenv("HF_MAX_MEMORY_MB", "not-a-number")
    assert _resolve_max_memory_mb() is None
    monkeypatch.delenv("HF_MAX_MEMORY_MB", raising=False)
    assert _resolve_max_memory_mb() is None


def test_resolve_run_setup_maps_preset_fields() -> None:
    config = quick_test_run_config()
    setup = resolve_run_setup(config)

    assert setup.target_input == config.target_input
    assert setup.max_urls == config.max_urls
    assert setup.workers_preset == config.workers
    assert setup.request_delay_preset == config.request_delay
    assert setup.full_suite_preset is True
    assert setup.resume_checkpoint_mode == "no"
    assert setup.bfs_max_depth == config.bfs_max_depth
    assert setup.crawl_mode == "accurate"


def test_resolve_run_setup_preset_carries_competitors() -> None:
    config = RunConfig(
        target_input="https://s.test/sitemap.xml",
        max_urls=5,
        max_psi_urls=0,
        high_value_slugs=[],
        crawl_mode="fast",
        render_wait_ms=1000,
        selector_wait_ms=500,
        workers=3,
        request_delay=0.5,
        full_suite=False,
        previous_audit_path="",
        checkpoint_every=0,
        resume_checkpoint="no",
        check_external_link_status=False,
        competitor_domains=("rival.com",),
    )
    setup = resolve_run_setup(config)
    assert setup.competitor_domains == ("rival.com",)
    assert setup.full_suite_preset is False


def test_resolve_run_setup_interactive_reads_env(monkeypatch) -> None:
    monkeypatch.setattr(
        run_setup,
        "get_user_config",
        lambda: (
            "https://interactive.test/",
            20,
            3,
            ["pricing"],
            "fast",
            4000,
            3000,
            True,
            False,
        ),
    )
    monkeypatch.setenv("CHECK_OG_IMAGES", "1")
    monkeypatch.setenv("HF_STREAMING", "yes")
    monkeypatch.setenv("HF_COMPETITORS", "rival.com")
    monkeypatch.delenv("GSC_URL_INSPECTION", raising=False)
    monkeypatch.delenv("HF_MAX_MEMORY_MB", raising=False)
    monkeypatch.delenv("CHECK_CONTENT_IMAGES", raising=False)

    setup = resolve_run_setup(None)

    assert setup.target_input == "https://interactive.test/"
    assert setup.max_urls == 20
    assert setup.check_og_images is True  # from env override
    assert setup.streaming is True
    assert setup.competitor_domains == ("rival.com",)
    assert setup.resume_checkpoint_mode == "prompt"
    assert setup.workers_preset is None
