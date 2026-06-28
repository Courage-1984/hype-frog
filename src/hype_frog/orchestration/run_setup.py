"""Runtime setup contract for entrypoint orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from dotenv import load_dotenv

from hype_frog.core import configure_logging, get_logger, get_user_config
from hype_frog.core.env_vars import (
    get_check_content_images,
    get_check_og_images,
    get_hf_competitors,
    get_hf_gsc_url_inspection,
    get_hf_max_memory_mb,
    get_hf_streaming,
)
from hype_frog.core.run_config import CliRunOverrides, ResumeCheckpointMode, RunConfig

logger = get_logger(__name__)


def _parse_competitor_domains(raw: str) -> tuple[str, ...]:
    parts = [
        piece.strip().lower().replace("https://", "").replace("http://", "").strip("/")
        for piece in str(raw or "").split(",")
    ]
    return tuple(part for part in parts if part)


def _resolve_competitor_domains_env() -> tuple[str, ...]:
    return _parse_competitor_domains(get_hf_competitors())


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
    output_filename: str | None = None
    export_pdf: bool = False


def resolve_run_setup(
    run: RunConfig | None,
    cli_overrides: CliRunOverrides | None = None,
) -> RunSetup:
    """Resolve startup configuration for interactive and preset runs."""
    configure_logging()
    load_dotenv()

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
            output_filename=run.output_filename,
            export_pdf=run.export_pdf,
        )

    user = get_user_config()
    check_og_images = user.check_og_images
    if not check_og_images:
        check_og_images = get_check_og_images()
    check_content_images = get_check_content_images()
    gsc_url_inspection = get_hf_gsc_url_inspection()
    max_memory_mb = _resolve_max_memory_mb()
    streaming = get_hf_streaming()
    competitor_domains = _resolve_competitor_domains_env()
    previous_audit_path_preset: str | None = None
    export_pdf = False

    if cli_overrides is not None:
        if cli_overrides.check_og_images:
            check_og_images = True
        if cli_overrides.check_content_images:
            check_content_images = True
        if cli_overrides.previous_run:
            previous_audit_path_preset = cli_overrides.previous_run
        if cli_overrides.gsc_url_inspection:
            gsc_url_inspection = cli_overrides.gsc_url_inspection
        if cli_overrides.max_memory_mb is not None and cli_overrides.max_memory_mb > 0:
            max_memory_mb = cli_overrides.max_memory_mb
        if cli_overrides.streaming:
            streaming = True
        if cli_overrides.export_pdf:
            export_pdf = True
        if cli_overrides.competitors is not None:
            competitor_domains = _parse_competitor_domains(cli_overrides.competitors)
        elif cli_overrides.benchmarks:
            competitor_domains = ()

    return RunSetup(
        target_input=user.target_input,
        max_urls=user.max_urls,
        max_psi_urls=user.max_psi_urls,
        high_value_slugs=user.high_value_slugs,
        crawl_mode=user.crawl_mode,
        render_wait_ms=user.render_wait_ms,
        selector_wait_ms=user.selector_wait_ms,
        workers_preset=None,
        request_delay_preset=None,
        full_suite_preset=None,
        previous_audit_path_preset=previous_audit_path_preset,
        checkpoint_every_preset=None,
        resume_checkpoint_mode="prompt",
        check_external_link_status=user.check_external_link_status,
        check_og_images=check_og_images,
        check_content_images=check_content_images,
        bfs_max_depth=None,
        gsc_url_inspection=gsc_url_inspection,
        max_memory_mb=max_memory_mb,
        streaming=streaming,
        competitor_domains=competitor_domains,
        export_pdf=export_pdf,
    )


def _resolve_max_memory_mb() -> int | None:
    value = get_hf_max_memory_mb()
    return value if value is not None and value > 0 else None
