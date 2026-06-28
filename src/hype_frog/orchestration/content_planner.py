"""Content Planner sheet: nav/footer hierarchy + workflow sign-off columns."""

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


def build_content_planner_rows(
    typed_extra_rows: list[ExtraRowPayload],
    root_url: str,
) -> list[dict[str, object]]:
    root_key = normalize_url_key(root_url)
    homepage_row = next(
        (r for r in typed_extra_rows if normalize_url_key(r.values.get("URL") or "") == root_key),
        None,
    )
    if homepage_row is None:
        return []

    nav_footer: list[dict[str, object]] = homepage_row.values.get("Nav Footer Link Details") or []
    seen: set[str] = set()
    unique_links: list[dict[str, object]] = []
    for link in nav_footer:
        target = str(link.get("Target URL") or "")
        if target and target not in seen:
            seen.add(target)
            unique_links.append(link)

    unique_links.sort(key=lambda lnk: urlparse(str(lnk.get("Target URL") or "")).path)

    rows: list[dict[str, object]] = []
    for link in unique_links:
        url = str(link.get("Target URL") or "")
        cols = _level_columns(url)
        rows.append(
            {
                **cols,
                "Page link": url,
                "Copy Doc": None,
                **{col: "Not signed off" for col in CONTENT_PLANNER_SIGNOFF_COLUMNS},
            }
        )
    return rows


__all__ = [
    "CONTENT_PLANNER_COLUMNS",
    "CONTENT_PLANNER_SIGNOFF_COLUMNS",
    "build_content_planner_rows",
]
