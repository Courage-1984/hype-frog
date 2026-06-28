"""Run-to-run delta comparison for IssueInventory and URL metrics (C1)."""

from __future__ import annotations

from hype_frog.analysis.delta_loader import (
    load_run_snapshot,
    save_run_snapshot_json,
    snapshot_from_current_run,
)
from hype_frog.analysis.delta_models import (  # noqa: F401 — _safe_int re-exported for tests
    BASELINE_DELTA_NOTE,
    DELTA_SHEET_COLUMNS,
    IssueRecord,
    RunSnapshot,
    TrendPoint,
    companion_summary_path,
    days_between,
    delta_summary_path_for_workbook,
)
from hype_frog.core.numeric_utils import safe_int as _safe_int  # noqa: F401 — re-exported
from hype_frog.analysis.delta_sheet_builder import (
    build_delta_sheet_rows,
    build_delta_workbook_output,
    build_resolved_issues_dataframe,
)

__all__ = [
    "BASELINE_DELTA_NOTE",
    "DELTA_SHEET_COLUMNS",
    "IssueRecord",
    "RunSnapshot",
    "TrendPoint",
    "build_delta_sheet_rows",
    "build_delta_workbook_output",
    "build_resolved_issues_dataframe",
    "companion_summary_path",
    "days_between",
    "delta_summary_path_for_workbook",
    "load_run_snapshot",
    "save_run_snapshot_json",
    "snapshot_from_current_run",
]

