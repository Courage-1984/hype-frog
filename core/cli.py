from __future__ import annotations

from core.logger import get_logger

logger = get_logger(__name__)


def get_user_config() -> tuple[str, int | None, int | None, list[str]]:
    target_input = input("Enter the target URL or Sitemap: ").strip()
    max_urls_raw = input("Enter Max URLs to crawl (leave blank for no limit): ").strip()
    psi_limit_raw = input(
        "Enter Max URLs for PageSpeed Insights check (PSI is slow; enter a number to limit, or leave blank to check all): "
    ).strip()
    high_value_slugs_raw = input(
        "Enter high-value URL substrings for this client, comma-separated (e.g., pricing, services). Enter 0 or leave blank to skip: "
    ).strip()

    max_urls: int | None = None
    max_psi_urls: int | None = None
    high_value_slugs: list[str] = []

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
            if parsed_psi > 0:
                max_psi_urls = parsed_psi
        except ValueError:
            logger.warning("Invalid PSI limit '%s'. Checking all crawled URLs.", psi_limit_raw)

    if high_value_slugs_raw and high_value_slugs_raw.strip() != "0":
        high_value_slugs = [slug.strip().lower() for slug in high_value_slugs_raw.split(",") if slug.strip()]

    return target_input, max_urls, max_psi_urls, high_value_slugs
