"""Shared helpers (path-aware for src layout)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, urlsplit, urlunsplit

from hype_frog.config import REPORTS_LATEST_DIR


def normalize_url(url: object, keep_query: bool = True) -> str:
    """Same behavior as ``core.url_normalization.normalize_url`` (inlined for src bootstrap)."""
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
    except Exception:
        return raw.rstrip("/")


def readability_flesch(words: int, sentences: int) -> float | None:
    if words <= 0 or sentences <= 0:
        return None
    return round(206.835 - 1.015 * (words / sentences), 2)


def normalize_text_hash(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def normalize_url_key(url: object, keep_query: bool = True) -> str:
    return normalize_url(url, keep_query=keep_query)


def status_class(status_code: object) -> str:
    if isinstance(status_code, int):
        return f"{status_code // 100}xx"
    return str(status_code)


def url_depth(url: str) -> int:
    path = urlparse(url).path.strip("/")
    if not path:
        return 0
    return len([p for p in path.split("/") if p])


def word_count_band(count: int) -> str:
    if count < 300:
        return "Thin"
    if count < 800:
        return "OK"
    return "Strong"


def image_extension(src_url: str) -> str:
    path = urlparse(src_url).path.lower()
    for ext in [".webp", ".avif", ".jpg", ".jpeg", ".png", ".gif", ".svg"]:
        if path.endswith(ext):
            return ext.replace(".", "")
    return "other"


def looks_generic_image_filename(src_url: str) -> bool:
    name = Path(urlparse(src_url).path).name.lower()
    if not name:
        return False
    return bool(re.match(r"^(img|image|dsc|photo|pic)[-_]?\d+\.[a-z0-9]+$", name))


def to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def sanitize_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(value or "").strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned or "audit"


def build_output_filename(source_label: str, full_suite: bool = True) -> str:
    """Return path string under `reports/latest/` (directory created if needed)."""
    parsed = urlparse(source_label if "://" in source_label else f"https://{source_label}")
    source = sanitize_filename_part(parsed.netloc or source_label)
    REPORTS_LATEST_DIR.mkdir(parents=True, exist_ok=True)

    _ = full_suite  # retained for API parity with legacy callers
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base_name = f"SEO_AEO_Audit_{source}_{timestamp}"
    candidate = REPORTS_LATEST_DIR / f"{base_name}.xlsx"

    counter = 1
    while candidate.exists():
        candidate = REPORTS_LATEST_DIR / f"{base_name}_{counter}.xlsx"
        counter += 1

    return str(candidate.resolve())
