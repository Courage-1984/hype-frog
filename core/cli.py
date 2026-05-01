from __future__ import annotations

from core.logger import get_logger

logger = get_logger(__name__)


def get_user_config() -> tuple[str, int | None, int | None, list[str], str, int, int]:
    target_input = input("Enter the target URL or Sitemap: ").strip()
    max_urls_raw = input("Enter Max URLs to crawl (leave blank for no limit): ").strip()
    psi_limit_raw = input(
        "Enter Max URLs for PageSpeed Insights check (PSI is slow; enter a number to limit, or leave blank to check all): "
    ).strip()
    high_value_slugs_raw = input(
        "Enter high-value URL substrings for this client, comma-separated (e.g., pricing, services). Enter 0 or leave blank to skip: "
    ).strip()
    crawl_mode_raw = input("Crawl mode - 1) Fast HTTP  2) Accurate Rendered (Playwright): ").strip()
    render_wait_raw = input("Accurate mode network-idle wait ms (default 4000): ").strip()
    selector_wait_raw = input("Accurate mode SEO selector wait ms (default 3000): ").strip()

    max_urls: int | None = None
    max_psi_urls: int | None = None
    high_value_slugs: list[str] = []
    crawl_mode = "accurate" if crawl_mode_raw == "2" else "fast"
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
        high_value_slugs = [slug.strip().lower() for slug in high_value_slugs_raw.split(",") if slug.strip()]

    if render_wait_raw:
        try:
            render_wait_ms = max(500, int(render_wait_raw))
        except ValueError:
            logger.warning("Invalid render wait '%s'. Using default 4000ms.", render_wait_raw)
    if selector_wait_raw:
        try:
            selector_wait_ms = max(500, int(selector_wait_raw))
        except ValueError:
            logger.warning("Invalid selector wait '%s'. Using default 3000ms.", selector_wait_raw)

    return target_input, max_urls, max_psi_urls, high_value_slugs, crawl_mode, render_wait_ms, selector_wait_ms
