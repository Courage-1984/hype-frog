from __future__ import annotations

from openpyxl.comments import Comment
from openpyxl.worksheet.worksheet import Worksheet


SEMANTIC_AEO_HEADER_TOOLTIPS: dict[str, str] = {
    "Entity Density (%)": (
        "Description: The percentage of the page content identified as Named "
        "Entities (People, Orgs, Places).\n"
        "Calculation: (Entities / Total Words) * 100."
    ),
    "Top Entities": (
        "Description: The 3 most frequent Named Entities found on the page. "
        "Used for semantic relevance."
    ),
    "Citation Candidate Count": (
        "Description: Number of 40-60 word snippets that start with "
        "answer-engine triggers (e.g., 'is', 'means')."
    ),
    "Semantic AEO Score": (
        "Description: A weighted score (0-100) based on entity density and "
        "citation readiness."
    ),
}


def apply_semantic_aeo_tooltips(
    worksheet: Worksheet,
    *,
    header_row: int = 1,
) -> None:
    """Attach comments for semantic AEO metrics without touching guardrails."""
    for col_idx in range(1, worksheet.max_column + 1):
        cell = worksheet.cell(row=header_row, column=col_idx)
        header = str(cell.value or "").strip()
        tooltip = SEMANTIC_AEO_HEADER_TOOLTIPS.get(header)
        if tooltip:
            cell.comment = Comment(tooltip, "hype-frog")


__all__ = ["SEMANTIC_AEO_HEADER_TOOLTIPS", "apply_semantic_aeo_tooltips"]
