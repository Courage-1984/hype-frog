"""Featured snippet and PAA opportunity scoring (B3)."""

from __future__ import annotations

import re
from typing import Any

SNIPPET_OPPORTUNITY_COLUMNS: tuple[str, ...] = (
    "URL",
    "Current GSC Position",
    "GSC Clicks",
    "GSC Impressions",
    "Snippet Type Detected",
    "Featured Snippet Readiness",
    "Recommended Restructuring",
    "Effort",
)

_DEFINITION_RE = re.compile(
    r"^\s*\w[\w\s\-]{0,60}\s+is\s+(?:a|an)\b",
    re.IGNORECASE | re.MULTILINE,
)
_LIST_RE = re.compile(
    r"^\s*(?:\d+[\).\]]\s+|\*\s+|-\s+)(?:add|create|install|open|click|select|choose|set|use)\b",
    re.IGNORECASE | re.MULTILINE,
)


def detect_featured_snippet_type(row: dict[str, Any]) -> str:
    """Classify the most likely featured-snippet format for a page."""
    question_count = int(row.get("Question Heading Count") or 0)
    has_faq_schema = bool(row.get("QAPage/FAQ Schema Present"))
    has_table = bool(row.get("List/Table Answer Signal")) and _row_has_table(row)
    has_list = bool(row.get("List/Table Answer Signal")) and not has_table
    body = str(row.get("Current Page Copy Snippet") or row.get("Body Text Excerpt") or "")

    if question_count > 0 and (has_faq_schema or bool(row.get("aeo_snippets"))):
        return "FAQ"
    if has_table:
        return "Table"
    if has_list or _LIST_RE.search(body):
        return "List"
    if _DEFINITION_RE.search(body):
        return "Definition"
    if question_count > 0:
        return "FAQ"
    return "None"


def _row_has_table(row: dict[str, Any]) -> bool:
    types = str(row.get("Schema Types Found") or "").lower()
    if "table" in types:
        return True
    return bool(row.get("Has HTML Table"))


def compute_snippet_readiness(row: dict[str, Any], snippet_type: str) -> int:
    """Score 0–10 for how well the page is structured for snippet extraction."""
    if snippet_type == "None":
        return 0
    score = 3
    if snippet_type == "Definition":
        score += 3
    if snippet_type in {"List", "Table"}:
        score += 2
    if snippet_type == "FAQ":
        score += 2
    if int(row.get("Question Heading Count") or 0) > 0:
        score += 1
    if int(row.get("Paragraphs 40-60 Words Count") or 0) > 0:
        score += 1
    if bool(row.get("QAPage/FAQ Schema Present")):
        score += 1
    if bool(row.get("List/Table Answer Signal")):
        score += 1
    return min(10, score)


def _gsc_position(row: dict[str, Any]) -> float | None:
    raw = row.get("GSC Avg Position")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def gsc_position_opportunity(row: dict[str, Any], readiness: int) -> bool:
    position = _gsc_position(row)
    if position is None:
        return False
    return 4.0 <= position <= 20.0 and readiness > 5


def _restructuring_advice(snippet_type: str) -> tuple[str, str]:
    mapping = {
        "Definition": (
            "Lead with a concise 'X is a…' definition block directly under the H1.",
            "S",
        ),
        "List": (
            "Convert steps into a numbered list with imperative verbs in each line.",
            "S",
        ),
        "Table": (
            "Add a comparison table with clear column headers and scannable rows.",
            "M",
        ),
        "FAQ": (
            "Mirror each question heading with a 40–60 word direct answer paragraph.",
            "S",
        ),
    }
    return mapping.get(snippet_type, ("Add structured answer blocks under question headings.", "M"))


def enrich_snippet_opportunity_fields(extra_rows: list[Any]) -> None:
    for row in extra_rows:
        values = row if isinstance(row, dict) else row.values
        snippet_type = detect_featured_snippet_type(values)
        readiness = compute_snippet_readiness(values, snippet_type)
        advice, _effort = _restructuring_advice(snippet_type)
        values["Featured Snippet Type"] = snippet_type
        values["Featured Snippet Readiness"] = readiness
        values["GSC Position Opportunity"] = gsc_position_opportunity(values, readiness)
        values["Snippet Restructuring Advice"] = advice


def build_snippet_opportunity_rows(extra_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in extra_rows:
        readiness = int(row.get("Featured Snippet Readiness") or 0)
        if readiness <= 5:
            continue
        if not row.get("GSC Position Opportunity"):
            continue
        snippet_type = str(row.get("Featured Snippet Type") or "None")
        advice, effort = _restructuring_advice(snippet_type)
        position = _gsc_position(row)
        rows.append(
            {
                "URL": row.get("URL"),
                "Current GSC Position": round(position, 1) if position is not None else "",
                "GSC Clicks": int(float(row.get("GSC Clicks") or 0)),
                "GSC Impressions": int(float(row.get("GSC Impressions") or 0)),
                "Snippet Type Detected": snippet_type,
                "Featured Snippet Readiness": readiness,
                "Recommended Restructuring": advice,
                "Effort": effort,
            }
        )
    rows.sort(
        key=lambda item: (
            -int(item.get("Featured Snippet Readiness") or 0),
            float(item.get("Current GSC Position") or 99),
        )
    )
    return rows
