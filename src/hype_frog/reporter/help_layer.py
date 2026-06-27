from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from hype_frog.reporter.sheets.config import CONTENT_OPTIMISATION_HUB_SHEET

# Legacy export for tests and callers; canonical bodies live in validation.py.
SEMANTIC_AEO_HEADER_TOOLTIPS: frozenset[str] = frozenset(
    {
        "Entity Density (%)",
        "Top Entities",
        "Citation Candidate Count",
        "Semantic AEO Score",
    }
)


def apply_semantic_aeo_tooltips(
    worksheet: Worksheet,
    *,
    header_row: int = 1,
) -> None:
    """Attach semantic AEO header comments via the curated tooltip registry."""
    from hype_frog.reporter.sheets.validation import apply_curated_header_tooltips

    apply_curated_header_tooltips(
        worksheet,
        CONTENT_OPTIMISATION_HUB_SHEET,
        header_row=header_row,
        only_headers=SEMANTIC_AEO_HEADER_TOOLTIPS,
    )


__all__ = ["SEMANTIC_AEO_HEADER_TOOLTIPS", "apply_semantic_aeo_tooltips"]
