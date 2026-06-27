"""Runtime setup contract for entrypoint orchestration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from hype_frog.core import configure_logging, get_logger, get_user_config
from hype_frog.core.run_config import ResumeCheckpointMode, RunConfig

logger = get_logger(__name__)


def _parse_competitor_domains(raw: str) -> tuple[str, ...]:
    parts = [
        piece.strip().lower().replace("https://", "").replace("http://", "").strip("/")
        for piece in str(raw or "").split(",")
    ]
    return tuple(part for part in parts if part)


def _resolve_competitor_domains_env() -> tuple[str, ...]:
    return _parse_competitor_domains(os.getenv("HF_COMPETITORS", ""))


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y"}


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
    check_og_images: bool = False
    check_content_images: bool = False
    bfs_max_depth: int | None = None
    gsc_url_inspection: str | None = None
    max_memory_mb: int | None = None
    streaming: bool = False
    competitor_domains: tuple[str, ...] = ()


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
            check_og_images=run.check_og_images,
            check_content_images=run.check_content_images,
            bfs_max_depth=run.bfs_max_depth,
            gsc_url_inspection=run.gsc_url_inspection,
            max_memory_mb=run.max_memory_mb,
            streaming=run.streaming,
            competitor_domains=tuple(run.competitor_domains),
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
        check_og_images,
    ) = get_user_config()
    if not check_og_images:
        check_og_images = _env_flag("CHECK_OG_IMAGES")
    check_content_images = _env_flag("CHECK_CONTENT_IMAGES")
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
        check_og_images=check_og_images,
        check_content_images=check_content_images,
        bfs_max_depth=None,
        gsc_url_inspection=_resolve_gsc_url_inspection_env(),
        max_memory_mb=_resolve_max_memory_mb_env(),
        streaming=_env_flag("HF_STREAMING"),
        competitor_domains=_resolve_competitor_domains_env(),
    )


def _resolve_gsc_url_inspection_env() -> str | None:
    mode = os.getenv("GSC_URL_INSPECTION", "").strip().lower()
    if mode in {"1", "true", "yes", "limited"}:
        return "limited"
    if mode in {"full", "all"}:
        return "full"
    return None


def _resolve_max_memory_mb_env() -> int | None:
    raw = os.getenv("HF_MAX_MEMORY_MB", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None
