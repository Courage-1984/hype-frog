"""Targeted tests for :mod:`hype_frog.analysis.delta_loader` internals not
already exercised by ``tests/analysis/test_delta_engine.py``'s facade-level
coverage (JSON/xlsx dispatch, sidecar preference, malformed-input handling,
health-trend merge truncation).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from hype_frog.analysis.delta_loader import (
    load_run_snapshot,
    load_snapshot_json,
    load_snapshot_xlsx,
    merge_health_trend,
    save_run_snapshot_json,
)
from hype_frog.analysis.delta_models import RunSnapshot, TrendPoint

# ---------------------------------------------------------------------------
# load_run_snapshot dispatch
# ---------------------------------------------------------------------------


def test_load_run_snapshot_blank_path_returns_none() -> None:
    assert load_run_snapshot("") is None


def test_load_run_snapshot_nonexistent_path_returns_none(tmp_path: Path) -> None:
    assert load_run_snapshot(str(tmp_path / "missing.xlsx")) is None


def test_load_run_snapshot_prefers_json_sidecar_over_xlsx(tmp_path: Path) -> None:
    """When an xlsx path is given but a JSON delta-summary sidecar already
    exists alongside it, the cheap JSON load must win over re-parsing the
    (much slower) xlsx workbook."""
    xlsx_path = tmp_path / "audit.xlsx"
    xlsx_path.write_bytes(b"not a real xlsx file")
    sidecar_path = tmp_path / "audit_delta_summary.json"
    snapshot = RunSnapshot(run_date="2026-06-01", source_path=str(xlsx_path))
    save_run_snapshot_json(str(sidecar_path), snapshot)

    loaded = load_run_snapshot(str(xlsx_path))
    assert loaded is not None
    assert loaded.run_date == "2026-06-01"


# ---------------------------------------------------------------------------
# load_snapshot_json
# ---------------------------------------------------------------------------


def test_load_snapshot_json_malformed_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert load_snapshot_json(str(path)) is None


def test_load_snapshot_json_non_dict_payload_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_snapshot_json(str(path)) is None


def test_load_snapshot_json_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_snapshot_json(str(tmp_path / "nope.json")) is None


def test_load_snapshot_json_backfills_missing_source_path(tmp_path: Path) -> None:
    """A hand-edited/older sidecar with no ``source_path`` field must still
    load, with ``source_path`` backfilled from the path it was read from."""
    path = tmp_path / "sidecar.json"
    path.write_text(
        '{"run_date": "2026-06-01", "issues": [], "metrics_by_url": {}}',
        encoding="utf-8",
    )
    snapshot = load_snapshot_json(str(path))
    assert snapshot is not None
    assert snapshot.source_path == str(path)


# ---------------------------------------------------------------------------
# load_snapshot_xlsx
# ---------------------------------------------------------------------------


def test_load_snapshot_xlsx_corrupt_file_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.xlsx"
    path.write_bytes(b"this is not a real xlsx workbook")
    assert load_snapshot_xlsx(str(path)) is None


def test_load_snapshot_xlsx_marks_fixed_and_closed_statuses(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    register = wb.active
    register.title = "IssueInventory"
    register.append(["URL", "Issue", "Severity", "Stable Issue ID", "Status"])
    register.append(
        ["https://example.com/a", "Missing Title", "Critical", "a::missing-title", "Fixed"]
    )
    register.append(
        ["https://example.com/b", "Missing H1", "Warning", "b::missing-h1", "Closed"]
    )
    register.append(
        ["https://example.com/c", "Thin Content", "Warning", "c::thin-content", "Open"]
    )
    path = str(tmp_path / "audit.xlsx")
    wb.save(path)

    snapshot = load_snapshot_xlsx(path)
    assert snapshot is not None
    assert "a::missing-title" in snapshot.fixed_issue_ids
    assert "b::missing-h1" in snapshot.fixed_issue_ids
    assert "c::thin-content" not in snapshot.fixed_issue_ids


def test_load_snapshot_xlsx_reads_run_timestamp_from_audit_run_details(
    tmp_path: Path,
) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    details = wb.active
    details.title = "Audit Run Details"
    details.append(["Key", "Value"])
    details.append(["Run Timestamp", "2026-03-15 08:00:00"])
    path = str(tmp_path / "audit.xlsx")
    wb.save(path)

    snapshot = load_snapshot_xlsx(path)
    assert snapshot is not None
    assert "2026-03-15" in snapshot.run_date


# ---------------------------------------------------------------------------
# merge_health_trend
# ---------------------------------------------------------------------------


def test_merge_health_trend_appends_new_point() -> None:
    previous = {
        "https://example.com/": [TrendPoint(run_date="2026-05-01", score=50.0)],
    }
    merged = merge_health_trend(
        previous,
        [{"URL": "https://example.com/", "SEO Health Score": 60.0}],
        "2026-06-01",
    )
    trail = merged["https://example.com/"]
    assert [p.score for p in trail] == [50.0, 60.0]


def test_merge_health_trend_same_run_date_overwrites_last_point() -> None:
    """Re-running the delta merge for the same run_date (e.g. a rerun of
    the export step) must update the existing point in place, not create a
    duplicate entry for that date."""
    previous = {
        "https://example.com/": [TrendPoint(run_date="2026-06-01", score=50.0)],
    }
    merged = merge_health_trend(
        previous,
        [{"URL": "https://example.com/", "SEO Health Score": 65.0}],
        "2026-06-01",
    )
    trail = merged["https://example.com/"]
    assert len(trail) == 1
    assert trail[0].score == 65.0


def test_merge_health_trend_truncates_to_max_points() -> None:
    previous = {
        "https://example.com/": [
            TrendPoint(run_date="2026-04-01", score=40.0),
            TrendPoint(run_date="2026-05-01", score=50.0),
        ],
    }
    merged = merge_health_trend(
        previous,
        [{"URL": "https://example.com/", "SEO Health Score": 60.0}],
        "2026-06-01",
        max_points=2,
    )
    trail = merged["https://example.com/"]
    assert len(trail) == 2
    assert [p.score for p in trail] == [50.0, 60.0]


def test_merge_health_trend_skips_rows_with_no_score_or_url() -> None:
    merged = merge_health_trend(
        {},
        [{"URL": "", "SEO Health Score": 60.0}, {"URL": "https://example.com/"}],
        "2026-06-01",
    )
    assert merged == {}


# ---------------------------------------------------------------------------
# save_run_snapshot_json
# ---------------------------------------------------------------------------


def test_save_run_snapshot_json_creates_parent_directories(tmp_path: Path) -> None:
    nested_path = tmp_path / "reports" / "nested" / "delta.json"
    snapshot = RunSnapshot(run_date="2026-06-01", source_path="audit.xlsx")
    save_run_snapshot_json(str(nested_path), snapshot)
    assert nested_path.exists()
