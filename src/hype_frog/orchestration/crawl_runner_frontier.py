"""BFS frontier helpers — URL eligibility, CMS exclusions, internal link discovery."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from hype_frog.config import EXCLUDED_CMS_ACTION_QUERY_PARAMS
from hype_frog.core.url_normalization import normalize_url_key
from hype_frog.core.models import CrawlRowPayload

_NON_HTML_PATH_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        ".ico",
        ".bmp",
        ".tif",
        ".tiff",
        ".avif",
        ".pdf",
        ".zip",
        ".rar",
        ".7z",
        ".gz",
        ".tar",
        ".mp3",
        ".wav",
        ".ogg",
        ".m4a",
        ".mp4",
        ".mov",
        ".avi",
        ".wmv",
        ".mkv",
        ".webm",
        ".doc",
        ".docx",
        ".ppt",
        ".pptx",
        ".xls",
        ".xlsx",
        ".csv",
        ".json",
        ".xml",
        ".txt",
        ".js",
        ".css",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".map",
    }
)

_EXCLUDED_CMS_QUERY_KEYS_LOWER: frozenset[str] = frozenset(
    key.lower() for key in EXCLUDED_CMS_ACTION_QUERY_PARAMS
)


@dataclass(frozen=True)
class ExcludedCmsActionUrl:
    """A URL withheld from the crawl queue because of CMS action query parameters."""

    url: str
    excluded_query_params: tuple[str, ...]
    discovered_on_url: str
    exclusion_reason: str = (
        "CMS / WooCommerce action parameter — not crawled as a distinct page"
    )


def cms_action_exclusion_keys(url: str) -> frozenset[str]:
    """Return matched CMS action query-parameter names, or an empty set."""
    parsed = urlparse(str(url or "").strip())
    if not parsed.query:
        return frozenset()
    query_keys = {str(key).lower() for key in parse_qs(parsed.query).keys()}
    return frozenset(
        key for key in query_keys if key in _EXCLUDED_CMS_QUERY_KEYS_LOWER
    )


def register_cms_exclusion(
    registry: dict[str, ExcludedCmsActionUrl],
    url: str,
    discovered_on_url: str,
) -> None:
    keys = cms_action_exclusion_keys(url)
    if not keys:
        return
    normalized = normalize_url_key(url)
    if not normalized or normalized in registry:
        return
    registry[normalized] = ExcludedCmsActionUrl(
        url=normalized,
        excluded_query_params=tuple(sorted(keys)),
        discovered_on_url=discovered_on_url,
    )


def is_crawlable_html_candidate(url: str) -> bool:
    """Allow likely HTML document URLs and exclude binary/static assets."""
    parsed = urlparse(str(url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return False
    if cms_action_exclusion_keys(url):
        return False
    path = (parsed.path or "").strip().lower()
    if not path:
        return True
    return not any(path.endswith(ext) for ext in _NON_HTML_PATH_EXTENSIONS)


def candidate_internal_links(
    row: CrawlRowPayload,
    cms_exclusions: dict[str, ExcludedCmsActionUrl] | None = None,
) -> list[str]:
    links = row.extra.values.get("Internal Links List Full") or []
    if not isinstance(links, list):
        return []
    parent_url = str(row.main.values.get("URL") or row.extra.values.get("URL") or "")
    out: list[str] = []
    for link in links:
        normalized = normalize_url_key(link)
        if not normalized:
            continue
        if cms_action_exclusion_keys(normalized):
            if cms_exclusions is not None:
                register_cms_exclusion(
                    cms_exclusions,
                    normalized,
                    parent_url or "Internal link",
                )
            continue
        if is_crawlable_html_candidate(normalized):
            out.append(normalized)
    return out
