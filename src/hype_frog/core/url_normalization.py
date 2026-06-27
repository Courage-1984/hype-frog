from __future__ import annotations

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

