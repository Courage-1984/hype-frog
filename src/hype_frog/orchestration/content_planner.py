"""Content Planner sheet: site URL inventory + workflow sign-off columns."""

from __future__ import annotations

from urllib.parse import urlparse

from hype_frog.core.models import ExtraRowPayload
from hype_frog.core.url_normalization import normalize_url_key

CONTENT_PLANNER_COLUMNS: tuple[str, ...] = (
    "Primary",
    "Secondary",
    "Tertiary",
    "Page link",
    "Copy Doc",
    "Copywriter Sign off",
    "Copy First Check",
    "2nd Revisions",
    "Client copy sign off",
    "Web design off",
    "UXI sign off",
    "Visual Design sign off",
    "Client final sign off",
    "Optimisations",
    "Desktop",
    "Tablet",
    "Mobile",
    "SEO",
    "Performance",
)

CONTENT_PLANNER_SIGNOFF_COLUMNS: frozenset[str] = frozenset(
    CONTENT_PLANNER_COLUMNS[5:]
)


def _level_columns(url: str) -> dict[str, str | None]:
    parts = [p for p in urlparse(url).path.split("/") if p]
    depth = len(parts)
    label = parts[-1] if parts else "Home"
    return {
        "Primary": label if depth <= 1 else None,
        "Secondary": label if depth == 2 else None,
        "Tertiary": label if depth >= 3 else None,
    }


def _planner_row(url: str) -> dict[str, object]:
    return {
        **_level_columns(url),
        "Page link": url,
        "Copy Doc": None,
        **{col: "Not signed off" for col in CONTENT_PLANNER_SIGNOFF_COLUMNS},
    }


def build_content_planner_rows(
    typed_extra_rows: list[ExtraRowPayload],
    root_url: str,
) -> list[dict[str, object]]:
    """Build one planner row per crawled URL (full domain inventory)."""
    del root_url  # retained for export API stability
    seen: set[str] = set()
    urls: list[str] = []
    for row in typed_extra_rows:
        url = str(row.values.get("URL") or "").strip()
        if not url:
            continue
        key = normalize_url_key(url)
        if key in seen:
            continue
        seen.add(key)
        urls.append(url)

    urls.sort(key=lambda item: urlparse(item).path)
    return [_planner_row(url) for url in urls]


__all__ = [
    "CONTENT_PLANNER_COLUMNS",
    "CONTENT_PLANNER_SIGNOFF_COLUMNS",
    "build_content_planner_rows",
]
