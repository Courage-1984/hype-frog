"""Non-interactive run configuration for CLI presets (e.g. --quick-test)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from hype_frog.core.env_vars import (
    get_hf_full_smoke_url_count,
    get_hf_test_sitemap_url,
    get_psi_api_key,
)

ResumeCheckpointMode = Literal["prompt", "yes", "no"]

# Fixed smoke target: page sitemap on a stable public property (10 URL cap in preset).
# Override with HF_TEST_SITEMAP_URL env var to avoid flaky CI when the default site is down.
_DEFAULT_SMOKE_SITEMAP_URL: str = (
    "https://africanmarketingconfederation.org/page-sitemap.xml"
)
QUICK_TEST_SITEMAP_URL: str = get_hf_test_sitemap_url(_DEFAULT_SMOKE_SITEMAP_URL)
QUICK_TEST_MAX_URLS: int = 10
QUICK_TEST_BFS_MAX_DEPTH: int = 2
QUICK_TEST_MAX_PSI_URLS: int = 3

# Full-smoke: production-like sitemap volume without a URL cap (network mocked in gate).
FULL_SMOKE_SITEMAP_URL: str = QUICK_TEST_SITEMAP_URL
FULL_SMOKE_SYNTHETIC_URL_COUNT: int = 80
FULL_SMOKE_BFS_MAX_DEPTH: int = 1


@dataclass(frozen=True)
class RunConfig:
    """Full set of user choices for one audit run (interactive or preset)."""

    target_input: str
    max_urls: int | None
    max_psi_urls: int | None
    high_value_slugs: list[str]
    crawl_mode: str
    render_wait_ms: int
    selector_wait_ms: int
    workers: int
    request_delay: float
    full_suite: bool
    previous_audit_path: str
    checkpoint_every: int
    resume_checkpoint: ResumeCheckpointMode
    check_external_link_status: bool
    check_og_images: bool = False
    check_content_images: bool = False
    bfs_max_depth: int | None = None
    gsc_url_inspection: str | None = None
    max_memory_mb: int | None = None
    streaming: bool = False
    competitor_domains: tuple[str, ...] = ()
    output_filename: str | None = None
    export_pdf: bool = False
    hide_advanced_tabs: bool = True


@dataclass(frozen=True)
class CliRunOverrides:
    """Explicit CLI flag overrides for interactive runs (avoids os.environ mutation)."""

    competitors: str | None = None
    benchmarks: bool = False
    export_pdf: bool = False
    check_og_images: bool = False
    check_content_images: bool = False
    previous_run: str | None = None
    gsc_url_inspection: str | None = None
    max_memory_mb: int | None = None
    streaming: bool = False
    regen_report: bool = False
    snapshot_id: str | None = None
    re_enrich: bool = False
    verbose: bool = False
    quiet: bool = False
    show_all_tabs: bool = False


def _quick_test_max_psi_urls() -> int:
    if get_psi_api_key():
        return QUICK_TEST_MAX_PSI_URLS
    return 0


def _full_smoke_url_count() -> int:
    return max(20, get_hf_full_smoke_url_count(FULL_SMOKE_SYNTHETIC_URL_COUNT))


def full_smoke_run_config() -> RunConfig:
    """Pre-export gate: uncapped sitemap seeds, full suite, PSI on all URLs when key is set."""
    psi_enabled = bool(get_psi_api_key())
    return RunConfig(
        target_input=FULL_SMOKE_SITEMAP_URL,
        max_urls=None,
        max_psi_urls=None if psi_enabled else 0,
        high_value_slugs=["about", "contact", "membership", "awards"],
        crawl_mode="accurate",
        render_wait_ms=2000,
        selector_wait_ms=1500,
        workers=6,
        request_delay=0.0,
        full_suite=True,
        previous_audit_path="",
        checkpoint_every=0,
        resume_checkpoint="no",
        check_external_link_status=True,
        check_og_images=True,
        check_content_images=False,
        bfs_max_depth=FULL_SMOKE_BFS_MAX_DEPTH,
    )


def quick_test_run_config() -> RunConfig:
    """Comprehensive smoke preset: sitemap seeds, BFS depth 2, Playwright, full suite, limited PSI."""
    return RunConfig(
        target_input=QUICK_TEST_SITEMAP_URL,
        max_urls=QUICK_TEST_MAX_URLS,
        max_psi_urls=_quick_test_max_psi_urls(),
        high_value_slugs=["about", "contact", "membership"],
        crawl_mode="accurate",
        render_wait_ms=4000,
        selector_wait_ms=3000,
        workers=4,
        request_delay=1.0,
        full_suite=True,
        previous_audit_path="",
        checkpoint_every=0,
        resume_checkpoint="no",
        check_external_link_status=True,
        check_og_images=False,
        bfs_max_depth=QUICK_TEST_BFS_MAX_DEPTH,
    )
