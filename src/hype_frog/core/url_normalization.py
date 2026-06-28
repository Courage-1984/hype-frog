from __future__ import annotations

from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from hype_frog.core.logger import get_logger

logger = get_logger(__name__)


def normalize_url(url: object, keep_query: bool = True) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        return raw.rstrip("/")
    try:
        parts = urlsplit(raw)
        scheme = parts.scheme.lower()
        netloc = parts.netloc.lower()
        path = quote(unquote(parts.path or "/"), safe="/:@-._~!$&()*+,;=").rstrip("/")
        if not path:
            path = "/"
        query = quote(unquote(parts.query), safe="=&:@-._~!$()*+,;/?") if keep_query else ""
        return urlunsplit((scheme, netloc, path, query, ""))
    except Exception as exc:
        logger.debug("normalize_url failed for %r: %s", raw, exc)
        return raw.rstrip("/")


def normalize_url_key(url: object, keep_query: bool = True) -> str:
    """Canonical thin wrapper — import this everywhere instead of redefining it."""
    return normalize_url(url, keep_query=keep_query)


def get_row_url(row: dict[str, Any]) -> str:
    """Return the effective URL for a crawl row, preferring the post-redirect 'Final URL'."""
    return normalize_url(row.get("Final URL") or row.get("URL") or "")

