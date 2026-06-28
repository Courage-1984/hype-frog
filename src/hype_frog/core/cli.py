from __future__ import annotations

from dataclasses import dataclass

from hype_frog.core.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class UserConfig:
    """Interactive CLI prompts resolved to typed crawl/export settings."""

    target_input: str
    max_urls: int | None
    max_psi_urls: int | None
    high_value_slugs: list[str]
    crawl_mode: str
    render_wait_ms: int
    selector_wait_ms: int
    check_external_link_status: bool
    check_og_images: bool


def _resolve_crawl_engine(raw: str) -> str:
    """Map CLI choice to fetcher crawl_mode; invalid non-empty input defaults to Precise (2)."""
    choice = raw.strip()
    if choice == "1":
        return "fast"
    if choice == "2":
        return "accurate"
    if choice:
        logger.warning("Invalid input; defaulting to Precise (Javascript Rendering).")
    return "accurate"


def get_user_config() -> UserConfig:
    target_input = input("Target URL or Sitemap Path: ").strip()
    max_urls_raw = input(
        "Crawl Limit (Max URLs) [leave blank for No Limit]: "
    ).strip()
    psi_limit_raw = input(
        "PSI Performance Limit (Max URLs) [leave blank for all]: "
    ).strip()
    high_value_slugs_raw = input(
        "High-Priority URL Substrings (comma-separated) [leave blank to skip]: "
    ).strip()
    crawl_mode_raw = input(
        "Crawl Engine: [1] Fast (HTTP) | [2] Precise (Javascript Rendering): "
    ).strip()
    render_wait_raw = input("Network Idle Timeout (ms) [default 4000]: ").strip()
    selector_wait_raw = input("Selector Render Wait (ms) [default 3000]: ").strip()
    external_checks_raw = input(
        "Perform External Link Status Checks? [y/N, blank skip]: "
    ).strip().lower()
    check_external_link_status = external_checks_raw in {"y", "yes"}
    og_image_checks_raw = input(
        "Verify OG image URLs (status + dimensions)? [y/N, blank skip]: "
    ).strip().lower()
    check_og_images = og_image_checks_raw in {"y", "yes"}

    max_urls: int | None = None
    max_psi_urls: int | None = None
    high_value_slugs: list[str] = []
    crawl_mode = _resolve_crawl_engine(crawl_mode_raw)
    render_wait_ms = 4000
    selector_wait_ms = 3000

    if max_urls_raw:
        try:
            parsed_limit = int(max_urls_raw)
            if parsed_limit > 0:
                max_urls = parsed_limit
        except ValueError:
            logger.warning("Invalid max URL limit '%s'. Proceeding with no limit.", max_urls_raw)

    if psi_limit_raw:
        try:
            parsed_psi = int(psi_limit_raw)
            if parsed_psi == 0:
                max_psi_urls = 0
            elif parsed_psi > 0:
                max_psi_urls = parsed_psi
        except ValueError:
            logger.warning("Invalid PSI limit '%s'. Checking all crawled URLs.", psi_limit_raw)

    if high_value_slugs_raw and high_value_slugs_raw.strip() != "0":
        high_value_slugs = [
            slug.strip().lower()
            for slug in high_value_slugs_raw.split(",")
            if slug.strip()
        ]

    if render_wait_raw:
        try:
            render_wait_ms = max(500, int(render_wait_raw))
        except ValueError:
            logger.warning("Invalid render wait '%s'. Using default 4000ms.", render_wait_raw)
    if selector_wait_raw:
        try:
            selector_wait_ms = max(500, int(selector_wait_raw))
        except ValueError:
            logger.warning(
                "Invalid selector wait '%s'. Using default 3000ms.",
                selector_wait_raw,
            )

    return UserConfig(
        target_input=target_input,
        max_urls=max_urls,
        max_psi_urls=max_psi_urls,
        high_value_slugs=high_value_slugs,
        crawl_mode=crawl_mode,
        render_wait_ms=render_wait_ms,
        selector_wait_ms=selector_wait_ms,
        check_external_link_status=check_external_link_status,
        check_og_images=check_og_images,
    )
