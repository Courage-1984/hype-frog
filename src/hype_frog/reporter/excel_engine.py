"""
Monolithic Excel / openpyxl engine: workbook helpers, tab builders, conditional
formatting helpers, and strict export guardrails (Action Required, TOC, freeze).
"""

from __future__ import annotations

from typing import Any

from hype_frog.reporter.engine_formatting import (
    apply_fixplan_workflow_formatting,
    apply_global_conditional_formatting,
    ensure_auto_filter,
    ensure_freeze_header,
)
from hype_frog.reporter.engine_guardrails import (
    apply_action_required_guardrails,
    apply_freeze_c2_data_sheets,
    apply_header_tooltips,
    apply_workbook_export_guardrails,
    friendly_toc_description,
    refresh_toc_descriptions_dynamic,
)
from hype_frog.reporter.engine_io import (
    build_core_dataframes,
    load_cached_rows,
    write_cached_sheet_chunked,
    write_dict_rows_sheet,
)
from hype_frog.reporter.engine_rows import (
    build_content_optimisation_hub_rows,
    build_content_optimization_hub_rows,
    build_fixplan_rows,
    write_snippet_candidates_chunked,
)

# ---------------------------------------------------------------------------
# Facades into sheets implementation (avoid circular import at module load)
# ---------------------------------------------------------------------------


def adjust_sheet_format(writer: Any, sheet_name: str) -> Any:
    from hype_frog.reporter.sheets.tables_impl import adjust_sheet_format as _impl

    return _impl(writer, sheet_name)


def apply_tab_hyperlinks(writer: Any, *, hide_advanced_tabs: bool = True) -> Any:
    from hype_frog.reporter.sheets.tables_impl import apply_tab_hyperlinks as _impl

    return _impl(writer, hide_advanced_tabs=hide_advanced_tabs)


__all__ = [
    "adjust_sheet_format",
    "apply_tab_hyperlinks",
    "apply_fixplan_workflow_formatting",
    "ensure_auto_filter",
    "ensure_freeze_header",
    "apply_global_conditional_formatting",
    "load_cached_rows",
    "build_core_dataframes",
    "write_dict_rows_sheet",
    "write_cached_sheet_chunked",
    "build_fixplan_rows",
    "write_snippet_candidates_chunked",
    "build_content_optimisation_hub_rows",
    "build_content_optimization_hub_rows",
    "apply_action_required_guardrails",
    "apply_freeze_c2_data_sheets",
    "apply_workbook_export_guardrails",
    "refresh_toc_descriptions_dynamic",
    "friendly_toc_description",
    "apply_header_tooltips",
]
