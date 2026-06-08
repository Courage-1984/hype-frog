"""Runtime setup contract for entrypoint orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from dotenv import load_dotenv

from hype_frog.core import configure_logging, get_logger, get_user_config
from hype_frog.core.run_config import ResumeCheckpointMode, RunConfig

logger = get_logger(__name__)


@dataclass(frozen=True)
class RunSetup:
    target_input: str
    max_urls: int | None
    max_psi_urls: int | None
    high_value_slugs: list[str]
    crawl_mode: str
    render_wait_ms: int
    selector_wait_ms: int
    workers_preset: int | None
    request_delay_preset: float | None
    full_suite_preset: bool | None
    previous_audit_path_preset: str | None
    checkpoint_every_preset: int | None
    resume_checkpoint_mode: ResumeCheckpointMode
    check_external_link_status: bool
    bfs_max_depth: int | None = None


def resolve_run_setup(run: RunConfig | None) -> RunSetup:
    """Resolve startup configuration for interactive and preset runs."""
    configure_logging()
    load_dotenv()
    logger.info("=== Python Technical SEO Auditor ===")

    if run is not None:
        logger.info("Non-interactive run preset active (e.g. --quick-test).")
        return RunSetup(
            target_input=run.target_input,
            max_urls=run.max_urls,
            max_psi_urls=run.max_psi_urls,
            high_value_slugs=list(run.high_value_slugs),
            crawl_mode=run.crawl_mode,
            render_wait_ms=run.render_wait_ms,
            selector_wait_ms=run.selector_wait_ms,
            workers_preset=run.workers,
            request_delay_preset=run.request_delay,
            full_suite_preset=run.full_suite,
            previous_audit_path_preset=run.previous_audit_path,
            checkpoint_every_preset=run.checkpoint_every,
            resume_checkpoint_mode=run.resume_checkpoint,
            check_external_link_status=run.check_external_link_status,
            bfs_max_depth=run.bfs_max_depth,
        )

    (
        target_input,
        max_urls,
        max_psi_urls,
        high_value_slugs,
        crawl_mode,
        render_wait_ms,
        selector_wait_ms,
        check_external_link_status,
    ) = get_user_config()
    return RunSetup(
        target_input=target_input,
        max_urls=max_urls,
        max_psi_urls=max_psi_urls,
        high_value_slugs=high_value_slugs,
        crawl_mode=crawl_mode,
        render_wait_ms=render_wait_ms,
        selector_wait_ms=selector_wait_ms,
        workers_preset=None,
        request_delay_preset=None,
        full_suite_preset=None,
        previous_audit_path_preset=None,
        checkpoint_every_preset=None,
        resume_checkpoint_mode="prompt",
        check_external_link_status=check_external_link_status,
        bfs_max_depth=None,
    )
