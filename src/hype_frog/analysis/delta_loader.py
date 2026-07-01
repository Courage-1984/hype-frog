"""Load and persist run snapshots from JSON sidecars or legacy workbooks."""

from __future__ import annotations

import json
from hype_frog.core.path_utils import path_exists
from pathlib import Path
from typing import Any

import pandas as pd

from hype_frog.analysis.delta_models import (
    METRIC_FIELDS,
    IssueRecord,
    RunSnapshot,
    TrendPoint,
    companion_summary_path,
    optional_float,
    parse_run_timestamp,
    safe_int,
    utc_now_iso,
)

def load_run_snapshot(path: str) -> RunSnapshot | None:
    """Load a prior run from compact JSON or legacy xlsx export."""
    if not path or not path_exists(path):
        return None
    lowered = path.lower()
    if lowered.endswith(".json"):
        return load_snapshot_json(path)
    sidecar = companion_summary_path(path)
    if sidecar:
        loaded = load_snapshot_json(sidecar)
        if loaded is not None:
            return loaded
    return load_snapshot_xlsx(path)


def load_snapshot_json(path: str) -> RunSnapshot | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    snapshot = RunSnapshot.from_dict(payload)
    if not snapshot.source_path:
        snapshot = RunSnapshot(
            run_date=snapshot.run_date,
            source_path=path,
            issues=snapshot.issues,
            metrics_by_url=snapshot.metrics_by_url,
            health_trend=snapshot.health_trend,
            issue_counts_by_name=snapshot.issue_counts_by_name,
            fixed_issue_ids=snapshot.fixed_issue_ids,
        )
    return snapshot


def _issue_records_from_dataframe(
    df: pd.DataFrame,
    *,
    run_date: str,
) -> tuple[dict[str, IssueRecord], set[str]]:
    issues: dict[str, IssueRecord] = {}
    fixed_issue_ids: set[str] = set()
    for _, row in df.iterrows():
        stable_id = str(row.get("Stable Issue ID") or "").strip()
        if not stable_id:
            continue
        status = str(row.get("Status") or "Open").strip()
        record = IssueRecord(
            stable_issue_id=stable_id,
            url=str(row.get("URL") or "").strip(),
            issue=str(row.get("Issue") or "").strip(),
            severity=str(row.get("Severity") or "").strip(),
            last_seen=run_date,
            status=status,
        )
        issues[stable_id] = record
        if status.lower() in {"fixed", "done", "closed"}:
            fixed_issue_ids.add(stable_id)
    return issues, fixed_issue_ids


def _load_issue_records_from_workbook(
    workbook: pd.ExcelFile,
    *,
    run_date: str,
) -> tuple[dict[str, IssueRecord], set[str]]:
    if "Issue Register" in workbook.sheet_names:
        register = pd.read_excel(workbook, sheet_name="Issue Register")
        if "Section" in register.columns:
            per_url = register[
                register["Section"].astype(str).str.strip() == "Issue Inventory"
            ]
            if not per_url.empty:
                register = per_url
            elif "URL" in register.columns:
                register = register[
                    register["URL"].astype(str).str.strip().astype(bool)
                    & register["Stable Issue ID"].astype(str).str.strip().astype(bool)
                ]
        return _issue_records_from_dataframe(register, run_date=run_date)
    if "IssueInventory" in workbook.sheet_names:
        inventory = pd.read_excel(workbook, sheet_name="IssueInventory")
        return _issue_records_from_dataframe(inventory, run_date=run_date)
    return {}, set()


def load_snapshot_xlsx(path: str) -> RunSnapshot | None:
    try:
        workbook = pd.ExcelFile(path)
    except Exception:
        return None
    run_date = utc_now_iso()
    if "Audit Run Details" in workbook.sheet_names:
        details = pd.read_excel(workbook, sheet_name="Audit Run Details")
        for _, row in details.iterrows():
            if str(row.get("Key", "")).strip() == "Run Timestamp":
                run_date = parse_run_timestamp(row.get("Value")) or run_date
                break

    issues, fixed_issue_ids = _load_issue_records_from_workbook(
        workbook,
        run_date=run_date,
    )

    metrics_by_url: dict[str, dict[str, float | None]] = {}
    if "Main" in workbook.sheet_names:
        main_df = pd.read_excel(workbook, sheet_name="Main")
        for _, row in main_df.iterrows():
            url = str(row.get("URL") or "").strip()
            if not url:
                continue
            metrics_by_url[url] = {
                field_name: optional_float(row.get(field_name))
                for field_name in METRIC_FIELDS
                if field_name in main_df.columns
            }
            if "Mobile PSI Score" not in main_df.columns:
                metrics_by_url[url]["Mobile PSI Score"] = optional_float(
                    row.get("Mobile PSI Score")
                )

    if "AEO" in workbook.sheet_names:
        aeo_df = pd.read_excel(workbook, sheet_name="AEO")
        for _, row in aeo_df.iterrows():
            url = str(row.get("URL") or "").strip()
            if not url:
                continue
            bucket = metrics_by_url.setdefault(url, {})
            bucket["AEO Readiness Score"] = optional_float(
                row.get("AEO Readiness Score")
            )

    issue_counts: dict[str, int] = {}
    if "Summary" in workbook.sheet_names:
        summary = pd.read_excel(workbook, sheet_name="Summary")
        for _, row in summary.iterrows():
            if str(row.get("Section", "")).strip() == "Issue Counts":
                issue_counts[str(row.get("Issue", ""))] = safe_int(
                    row.get("Affected URL Count")
                )

    health_trend: dict[str, list[TrendPoint]] = {}
    for url, metrics in metrics_by_url.items():
        score = metrics.get("SEO Health Score")
        if score is not None:
            health_trend[url] = [TrendPoint(run_date=run_date, score=score)]

    return RunSnapshot(
        run_date=run_date,
        source_path=path,
        issues=issues,
        metrics_by_url=metrics_by_url,
        health_trend=health_trend,
        issue_counts_by_name=issue_counts,
        fixed_issue_ids=fixed_issue_ids,
    )
def snapshot_from_current_run(
    *,
    issue_inventory_df: pd.DataFrame,
    main_rows: list[dict[str, Any]],
    extra_rows: list[dict[str, Any]],
    source_path: str,
    run_date: str | None = None,
    previous_snapshot: RunSnapshot | None = None,
) -> RunSnapshot:
    """Build a compact snapshot for the current export."""
    run_stamp = run_date or utc_now_iso()
    issues: dict[str, IssueRecord] = {}
    if not issue_inventory_df.empty and "Stable Issue ID" in issue_inventory_df.columns:
        for _, row in issue_inventory_df.iterrows():
            stable_id = str(row.get("Stable Issue ID") or "").strip()
            if not stable_id:
                continue
            prior = (
                previous_snapshot.issues.get(stable_id) if previous_snapshot else None
            )
            first_seen = prior.first_seen if prior and prior.first_seen else run_stamp
            issues[stable_id] = IssueRecord(
                stable_issue_id=stable_id,
                url=str(row.get("URL") or "").strip(),
                issue=str(row.get("Issue") or "").strip(),
                severity=str(row.get("Severity") or "").strip(),
                first_seen=first_seen,
                last_seen=run_stamp,
                status=str(row.get("Status") or "Open").strip() or "Open",
            )

    extra_by_url = {
        str(row.get("URL") or "").strip(): row for row in extra_rows if row.get("URL")
    }
    metrics_by_url: dict[str, dict[str, float | None]] = {}
    for row in main_rows:
        url = str(row.get("URL") or "").strip()
        if not url:
            continue
        extra = extra_by_url.get(url, {})
        metrics_by_url[url] = {
            "SEO Health Score": optional_float(row.get("SEO Health Score")),
            "AEO Readiness Score": optional_float(extra.get("AEO Readiness Score")),
            "Mobile PSI Score": optional_float(row.get("Mobile PSI Score")),
            "Technical Health": optional_float(row.get("Technical Health")),
        }

    issue_counts: dict[str, int] = {}
    if not issue_inventory_df.empty and "Issue" in issue_inventory_df.columns:
        grouped = issue_inventory_df.groupby("Issue").size()
        issue_counts = {str(name): safe_int(count) for name, count in grouped.items()}

    health_trend = merge_health_trend(
        previous_snapshot.health_trend if previous_snapshot else {},
        main_rows,
        run_stamp,
    )

    return RunSnapshot(
        run_date=run_stamp,
        source_path=source_path,
        issues=issues,
        metrics_by_url=metrics_by_url,
        health_trend=health_trend,
        issue_counts_by_name=issue_counts,
        fixed_issue_ids=set(),
    )


def merge_health_trend(
    previous: dict[str, list[TrendPoint]],
    main_rows: list[dict[str, Any]],
    run_date: str,
    *,
    max_points: int = 3,
) -> dict[str, list[TrendPoint]]:
    merged: dict[str, list[TrendPoint]] = {
        url: list(points[-max_points + 1 :]) for url, points in previous.items()
    }
    for row in main_rows:
        url = str(row.get("URL") or "").strip()
        score = optional_float(row.get("SEO Health Score"))
        if not url or score is None:
            continue
        trail = merged.setdefault(url, [])
        if trail and trail[-1].run_date == run_date:
            trail[-1] = TrendPoint(run_date=run_date, score=score)
        else:
            trail.append(TrendPoint(run_date=run_date, score=score))
        merged[url] = trail[-max_points:]
    return merged


def save_run_snapshot_json(path: str, snapshot: RunSnapshot) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
