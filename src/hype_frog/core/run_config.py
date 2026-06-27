"""Non-interactive run configuration for CLI presets (e.g. --quick-test)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

ResumeCheckpointMode = Literal["prompt", "yes", "no"]

# Fixed smoke target: page sitemap on a stable public property (10 URL cap in preset).
QUICK_TEST_SITEMAP_URL: str = (
    "https://africanmarketingconfederation.org/page-sitemap.xml"
)
QUICK_TEST_MAX_URLS: int = 10
QUICK_TEST_BFS_MAX_DEPTH: int = 2
QUICK_TEST_MAX_PSI_URLS: int = 3


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


def _quick_test_max_psi_urls() -> int:
    if os.getenv("PSI_API_KEY", "").strip():
        return QUICK_TEST_MAX_PSI_URLS
    return 0


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
