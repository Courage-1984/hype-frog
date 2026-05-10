"""Non-interactive run configuration for CLI presets (e.g. --quick-test)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ResumeCheckpointMode = Literal["prompt", "yes", "no"]


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


def quick_test_run_config() -> RunConfig:
    """10-URL single-seed BFS crawl preset: Playwright, faster profile, full suite, no PSI, no checkpoint resume prompt."""
    return RunConfig(
        target_input="https://africanmarketingconfederation.org/",
        max_urls=10,
        max_psi_urls=0,
        high_value_slugs=[],
        crawl_mode="accurate",
        render_wait_ms=4000,
        selector_wait_ms=3000,
        workers=4,
        request_delay=1.5,
        full_suite=True,
        previous_audit_path="",
        checkpoint_every=0,
        resume_checkpoint="no",
        check_external_link_status=False,
    )
