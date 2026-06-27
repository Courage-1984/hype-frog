"""Plain-language Content Hub recommendations without blocking LLM calls (C3)."""

from __future__ import annotations

import re
from typing import Any

_GENERIC_ANCHOR_RE = re.compile(
    r"\b(click here|read more|learn more|here|more)\b", re.IGNORECASE
)


def _shorten(text: str, limit: int = 120) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _top_entity(row: dict[str, Any]) -> str:
    entities = str(row.get("Top Entities") or "").split(",")
    for entity in entities:
        label = entity.strip()
        if label:
            return label
    return ""


def build_hub_recommended_action(main: dict[str, Any], extra: dict[str, Any]) -> str:
    """Return a specific, writer-friendly recommendation for a Hub row."""
    h1 = _shorten(str(extra.get("Primary H1 Content") or main.get("H1 Content") or main.get("Title") or ""))
    entity = _top_entity(extra)
    entity_clause = f", focusing on {entity}" if entity else ""

    title = str(main.get("Title") or "").strip()
    if not title or bool(extra.get("Title Missing")):
        return (
            f"Add a page title (currently missing). Aim for 50–60 characters summarising "
            f"the page topic: {h1 or 'your primary heading'}{entity_clause}."
        )

    meta = str(main.get("Meta Description") or "").strip()
    if not meta or bool(extra.get("Meta Description Missing")):
        return (
            f"Add a meta description (currently missing). Aim for 120–155 characters "
            f"summarising: {h1 or title}{entity_clause}."
        )

    h1_count = int(float(extra.get("H1 Count") or 0))
    if h1_count == 0:
        return (
            f"Add a single H1 heading that states the page topic clearly"
            f"{f' — e.g. {h1}' if h1 else ''}{entity_clause}."
        )
    if h1_count > 1:
        return (
            "Reduce to one H1 per page. Keep the strongest topical H1 and demote "
            "the others to H2 so crawlers see a single primary topic."
        )

    if int(float(extra.get("Images Missing Alt") or 0)) > 0:
        missing = int(float(extra.get("Images Missing Alt") or 0))
        return (
            f"Add descriptive alt text to {missing} image(s) on this page. "
            "Describe what the image shows in plain language, not just the filename."
        )

    if int(float(extra.get("Paragraphs 40-60 Words Count") or 0)) == 0:
        return (
            "Add a concise 40–60 word answer paragraph directly under a question-style "
            f"heading to improve AEO extractability for: {h1 or title}."
        )

    if str(extra.get("Featured Snippet Type") or "None") not in {"", "None"}:
        snippet_type = str(extra.get("Featured Snippet Type"))
        return (
            f"Restructure content for a {snippet_type.lower()} featured snippet: "
            f"use a direct answer block, scannable list, or FAQ schema as appropriate "
            f"for “{h1 or title}”."
        )

    seo = float(extra.get("SEO Health Score") or main.get("SEO Health Score") or 0)
    if seo < 60:
        return (
            f"Improve on-page fundamentals for “{h1 or title}”: align title, meta, and H1, "
            "tighten internal links, and resolve matched technical issues on the Main tab."
        )

    return (
        f"Polish copy and metadata for “{h1 or title}”: keep title and meta within "
        f"recommended lengths and reinforce the primary topic{entity_clause}."
    )


def build_hub_priority_reason(main: dict[str, Any], extra: dict[str, Any]) -> str:
    """Explain why this URL appears in the Content Hub priority set."""
    reasons: list[str] = []
    impressions = extra.get("GSC Impressions") or main.get("GSC Impressions")
    try:
        imp_val = int(float(impressions or 0))
    except (TypeError, ValueError):
        imp_val = 0
    if imp_val >= 100:
        reasons.append(f"high GSC impressions ({imp_val:,})")

    clicks = extra.get("GSC Clicks") or main.get("GSC Clicks")
    try:
        click_val = int(float(clicks or 0))
    except (TypeError, ValueError):
        click_val = 0
    if click_val >= 20 and imp_val > 0:
        reasons.append(f"meaningful clicks ({click_val:,})")

    if int(float(extra.get("Paragraphs 40-60 Words Count") or 0)) == 0:
        reasons.append("missing answer paragraphs")

    if str(extra.get("Search Intent") or "").strip() not in {"", "Unknown"}:
        reasons.append(f"search intent: {extra.get('Search Intent')}")

    if str(extra.get("GSC Position Opportunity") or "").lower() == "yes":
        reasons.append("mid-page ranking snippet opportunity")

    matched = str(extra.get("Matched Issues") or "")
    if matched:
        issue_count = len([part for part in matched.split(" | ") if part.strip()])
        if issue_count:
            reasons.append(f"{issue_count} open content/SEO issue(s)")

    instant = str(extra.get("Instant Priority") or "")
    if instant and instant not in {"", "Low"}:
        reasons.append(f"instant priority: {instant}")

    if not reasons:
        return "Included for editorial review based on low SEO health score or content gaps."

    joined = " + ".join(reasons)
    return f"Prioritised because of {joined}."
