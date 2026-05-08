from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


def _fallback_keyword(url: str, h1_text: str) -> str:
    """Build a simple keyword fallback from URL slug or heading text."""
    slug_parts = [part for part in urlparse(url).path.strip("/").split("/") if part]
    if slug_parts:
        slug = slug_parts[-1].replace("-", " ").replace("_", " ").strip()
        slug = re.sub(r"\s+", " ", slug)
        if slug:
            return slug.title()
    heading = str(h1_text or "").strip()
    return heading


def compute_content_cluster_id(
    url: Any, *, title: str = "", h1_or_structure: str = ""
) -> str:
    """Derive a stable topical cluster id from URL path and content hints."""
    raw_title = str(title or "").strip().lower()
    if not raw_title:
        raw_title = _fallback_keyword(str(url or ""), str(h1_or_structure or "")).lower()
    title_pattern = re.sub(r"\d+", "{n}", raw_title)[:24] if raw_title else "untitled"
    segments = [part for part in urlparse(str(url or "")).path.strip("/").split("/") if part]
    return f"{(segments[0] if segments else 'home')}-{title_pattern}".replace(" ", "-")
