"""Run-to-run delta comparison for IssueInventory and URL metrics (C1)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from hype_frog.core.models import ExtraRowPayload
from hype_frog.rules.registry import IssueRule

SNAPSHOT_VERSION = 1
BASELINE_DELTA_NOTE = "No previous run found — this is a baseline report."
DELTA_SUMMARY_SUFFIX = "_delta_summary.json"

METRIC_FIELDS: tuple[str, ...] = (
    "SEO Health Score",
    "AEO Readiness Score",
    "Mobile PSI Score",
    "Technical Health",
)

DELTA_SHEET_COLUMNS: tuple[str, ...] = (
    "Section",
    "URL",
    "Issue",
    "Severity",
    "Previous Value",
    "Current Value",
    "Change",
    "Direction",
    "First Seen",
    "Last Seen",
    "Days Open",
    "Trend Run 1",
    "Trend Run 2",
    "Trend Run 3",
    "Notes",
)


@dataclass
class IssueRecord:
    stable_issue_id: str
    url: str
    issue: str
    severity: str
    first_seen: str | None = None
    last_seen: str | None = None
    status: str = "Open"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stable_issue_id": self.stable_issue_id,
            "url": self.url,
            "issue": self.issue,
            "severity": self.severity,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> IssueRecord:
        return cls(
            stable_issue_id=str(raw.get("stable_issue_id") or "").strip(),
            url=str(raw.get("url") or "").strip(),
            issue=str(raw.get("issue") or "").strip(),
            severity=str(raw.get("severity") or "").strip(),
            first_seen=_optional_str(raw.get("first_seen")),
            last_seen=_optional_str(raw.get("last_seen")),
            status=str(raw.get("status") or "Open").strip() or "Open",
        )


@dataclass
class TrendPoint:
    run_date: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {"run_date": self.run_date, "score": self.score}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TrendPoint:
        return cls(
            run_date=str(raw.get("run_date") or "").strip(),
            score=float(raw.get("score") or 0.0),
        )


@dataclass
class RunSnapshot:
    run_date: str
    source_path: str
    issues: dict[str, IssueRecord] = field(default_factory=dict)
    metrics_by_url: dict[str, dict[str, float | None]] = field(default_factory=dict)
    health_trend: dict[str, list[TrendPoint]] = field(default_factory=dict)
    issue_counts_by_name: dict[str, int] = field(default_factory=dict)
    fixed_issue_ids: set[str] = field(default_factory=set)

    @property
    def issue_ids(self) -> set[str]:
        return {key for key in self.issues if key}

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SNAPSHOT_VERSION,
            "run_date": self.run_date,
            "source_path": self.source_path,
            "issues": [issue.to_dict() for issue in self.issues.values()],
            "metrics_by_url": self.metrics_by_url,
            "health_trend": {
                url: [point.to_dict() for point in points]
                for url, points in self.health_trend.items()
            },
            "issue_counts_by_name": self.issue_counts_by_name,
            "fixed_issue_ids": sorted(self.fixed_issue_ids),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RunSnapshot:
        issues = {
            record.stable_issue_id: record
            for record in (
                IssueRecord.from_dict(item)
                for item in raw.get("issues") or []
                if isinstance(item, dict)
            )
            if record.stable_issue_id
        }
        health_trend: dict[str, list[TrendPoint]] = {}
        for url, points in (raw.get("health_trend") or {}).items():
            if not isinstance(points, list):
                continue
            health_trend[str(url)] = [
                TrendPoint.from_dict(point)
                for point in points
                if isinstance(point, dict)
            ]
        metrics_raw = raw.get("metrics_by_url") or {}
        metrics_by_url: dict[str, dict[str, float | None]] = {}
        if isinstance(metrics_raw, dict):
            for url, metrics in metrics_raw.items():
                if not isinstance(metrics, dict):
                    continue
                metrics_by_url[str(url)] = {
                    key: _optional_float(metrics.get(key)) for key in METRIC_FIELDS
                }
        fixed_raw = raw.get("fixed_issue_ids") or []
        fixed_issue_ids = {
            str(value).strip() for value in fixed_raw if str(value).strip()
        }
        counts_raw = raw.get("issue_counts_by_name") or {}
        issue_counts = (
            {str(k): _safe_int(v) for k, v in counts_raw.items()}
            if isinstance(counts_raw, dict)
            else {}
        )
        return cls(
            run_date=str(raw.get("run_date") or "").strip() or _utc_now_iso(),
            source_path=str(raw.get("source_path") or "").strip(),
            issues=issues,
            metrics_by_url=metrics_by_url,
            health_trend=health_trend,
            issue_counts_by_name=issue_counts,
            fixed_issue_ids=fixed_issue_ids,
        )


def delta_summary_path_for_workbook(workbook_path: str) -> str:
    base = workbook_path.replace(".xlsx", "")
    return f"{base}{DELTA_SUMMARY_SUFFIX}"


def companion_summary_path(path: str) -> str:
    """JSON sidecar for an xlsx path, if it exists."""
    if path.lower().endswith(".json"):
        return path
    candidate = delta_summary_path_for_workbook(path)
    return candidate if os.path.exists(candidate) else ""


def _utc_now_iso() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _safe_int(value: object) -> int:
    if value is None:
        return 0
    try:
        num = float(value)
        if num != num:  # NaN
            return 0
        return int(num)
    except (TypeError, ValueError):
        return 0


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_float(value: object) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _direction_for_change(change: float | None) -> str:
    if change is None:
        return ""
    if change > 0:
        return "↑"
    if change < 0:
        return "↓"
    return "→"


def _parse_run_timestamp(raw: object) -> str | None:
    text = str(raw or "").strip()
    return text or None


def _days_between(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            start_dt = datetime.strptime(start[:19], fmt)
            end_dt = datetime.strptime(end[:19], fmt)
            return max(0, (end_dt - start_dt).days)
        except ValueError:
            continue
    return None


def days_between(start: str | None, end: str | None) -> int | None:
    """Return whole days between two ISO-like timestamps."""
    return _days_between(start, end)


def _blank_delta_row(section: str = "") -> dict[str, Any]:
    return {column: "" for column in DELTA_SHEET_COLUMNS} | {"Section": section}


def _section_title_row(title: str) -> dict[str, Any]:
    row = _blank_delta_row(title)
    row["Notes"] = title
    return row


def _format_trend_cell(point: TrendPoint | None) -> str:
    if point is None:
        return ""
    return f"{point.score:.1f} ({point.run_date})"


def load_run_snapshot(path: str) -> RunSnapshot | None:
    """Load a prior run from compact JSON or legacy xlsx export."""
    if not path or not os.path.exists(path):
        return None
    lowered = path.lower()
    if lowered.endswith(".json"):
        return _load_snapshot_json(path)
    sidecar = companion_summary_path(path)
    if sidecar:
        loaded = _load_snapshot_json(sidecar)
        if loaded is not None:
            return loaded
    return _load_snapshot_xlsx(path)


def _load_snapshot_json(path: str) -> RunSnapshot | None:
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


def _load_snapshot_xlsx(path: str) -> RunSnapshot | None:
    try:
        workbook = pd.ExcelFile(path)
    except Exception:
        return None
    run_date = _utc_now_iso()
    if "Audit Run Details" in workbook.sheet_names:
        details = pd.read_excel(path, sheet_name="Audit Run Details")
        for _, row in details.iterrows():
            if str(row.get("Key", "")).strip() == "Run Timestamp":
                run_date = _parse_run_timestamp(row.get("Value")) or run_date
                break

    issues: dict[str, IssueRecord] = {}
    fixed_issue_ids: set[str] = set()
    if "IssueInventory" in workbook.sheet_names:
        inventory = pd.read_excel(path, sheet_name="IssueInventory")
        for _, row in inventory.iterrows():
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

    metrics_by_url: dict[str, dict[str, float | None]] = {}
    if "Main" in workbook.sheet_names:
        main_df = pd.read_excel(path, sheet_name="Main")
        for _, row in main_df.iterrows():
            url = str(row.get("URL") or "").strip()
            if not url:
                continue
            metrics_by_url[url] = {
                field_name: _optional_float(row.get(field_name))
                for field_name in METRIC_FIELDS
                if field_name in main_df.columns
            }
            if "Mobile PSI Score" not in main_df.columns:
                metrics_by_url[url]["Mobile PSI Score"] = _optional_float(
                    row.get("Mobile PSI Score")
                )

    if "AEO" in workbook.sheet_names:
        aeo_df = pd.read_excel(path, sheet_name="AEO")
        for _, row in aeo_df.iterrows():
            url = str(row.get("URL") or "").strip()
            if not url:
                continue
            bucket = metrics_by_url.setdefault(url, {})
            bucket["AEO Readiness Score"] = _optional_float(
                row.get("AEO Readiness Score")
            )

    issue_counts: dict[str, int] = {}
    if "Summary" in workbook.sheet_names:
        summary = pd.read_excel(path, sheet_name="Summary")
        for _, row in summary.iterrows():
            if str(row.get("Section", "")).strip() == "Issue Counts":
                issue_counts[str(row.get("Issue", ""))] = _safe_int(
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
    run_stamp = run_date or _utc_now_iso()
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
            "SEO Health Score": _optional_float(row.get("SEO Health Score")),
            "AEO Readiness Score": _optional_float(extra.get("AEO Readiness Score")),
            "Mobile PSI Score": _optional_float(row.get("Mobile PSI Score")),
            "Technical Health": _optional_float(row.get("Technical Health")),
        }

    issue_counts: dict[str, int] = {}
    if not issue_inventory_df.empty and "Issue" in issue_inventory_df.columns:
        grouped = issue_inventory_df.groupby("Issue").size()
        issue_counts = {str(name): _safe_int(count) for name, count in grouped.items()}

    health_trend = _merge_health_trend(
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


def _merge_health_trend(
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
        score = _optional_float(row.get("SEO Health Score"))
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


def build_delta_sheet_rows(
    *,
    current: RunSnapshot,
    previous: RunSnapshot | None,
    baseline_report: bool,
    typed_extra_rows: list[ExtraRowPayload],
    summary_rules: list[IssueRule],
) -> list[dict[str, Any]]:
    """Build multi-section DeltaFromPreviousRun rows."""
    del typed_extra_rows  # issue-count deltas use snapshot counts
    rows: list[dict[str, Any]] = [_blank_delta_row() | dict(zip(DELTA_SHEET_COLUMNS, DELTA_SHEET_COLUMNS))]
    if baseline_report or previous is None:
        rows.append(_section_title_row("Summary"))
        rows.append(
            _blank_delta_row("Summary")
            | {
                "Issue": "Report Status",
                "Current Value": BASELINE_DELTA_NOTE,
                "Notes": BASELINE_DELTA_NOTE,
            }
        )
        rows.append(
            _blank_delta_row("Summary")
            | {
                "Issue": "Current Issues (baseline inventory)",
                "Current Value": len(current.issue_ids),
            }
        )
        rows.extend(_build_health_trend_section(current))
        return rows

    current_ids = current.issue_ids
    previous_ids = previous.issue_ids
    new_ids = current_ids - previous_ids
    resolved_ids = previous_ids - current_ids
    unchanged_ids = current_ids & previous_ids
    reopened_ids = current_ids & previous.fixed_issue_ids

    rows.append(_section_title_row("Summary"))
    summary_metrics = [
        ("Total Issues", len(previous_ids), len(current_ids)),
        ("New Issues", 0, len(new_ids)),
        ("Resolved Issues", 0, len(resolved_ids)),
        ("Unchanged Issues", 0, len(unchanged_ids)),
        ("Previously Fixed But Reopened", 0, len(reopened_ids)),
    ]
    for label, prev_val, curr_val in summary_metrics:
        if label == "Total Issues":
            change = curr_val - prev_val
            rows.append(
                _blank_delta_row("Summary")
                | {
                    "Issue": label,
                    "Previous Value": prev_val,
                    "Current Value": curr_val,
                    "Change": change,
                    "Direction": _direction_for_change(float(change)),
                }
            )
        else:
            rows.append(
                _blank_delta_row("Summary")
                | {
                    "Issue": label,
                    "Current Value": curr_val,
                }
            )

    for rule in summary_rules:
        issue_name = rule.name
        current_count = int(current.issue_counts_by_name.get(issue_name, 0))
        prev_count = int(previous.issue_counts_by_name.get(issue_name, 0))
        delta = current_count - prev_count
        if delta == 0:
            continue
        rows.append(
            _blank_delta_row("Summary")
            | {
                "Issue": f"Issue Delta: {issue_name}",
                "Previous Value": prev_count,
                "Current Value": current_count,
                "Change": delta,
                "Direction": _direction_for_change(float(delta)),
            }
        )

    rows.append(_section_title_row("New Issues"))
    if not new_ids:
        rows.append(
            _blank_delta_row("New Issues")
            | {"Notes": "No new issues compared with the previous run."}
        )
    else:
        for stable_id in sorted(new_ids):
            record = current.issues.get(stable_id)
            if record is None:
                continue
            rows.append(
                _blank_delta_row("New Issues")
                | {
                    "URL": record.url,
                    "Issue": record.issue,
                    "Severity": record.severity,
                    "First Seen": record.first_seen or current.run_date,
                }
            )

    rows.append(_section_title_row("Resolved Issues"))
    if not resolved_ids:
        rows.append(
            _blank_delta_row("Resolved Issues")
            | {"Notes": "No resolved issues compared with the previous run."}
        )
    else:
        for stable_id in sorted(resolved_ids):
            record = previous.issues.get(stable_id)
            if record is None:
                continue
            days_open = _days_between(record.first_seen, previous.run_date)
            rows.append(
                _blank_delta_row("Resolved Issues")
                | {
                    "URL": record.url,
                    "Issue": record.issue,
                    "Severity": record.severity,
                    "Last Seen": previous.run_date,
                    "Days Open": days_open if days_open is not None else "",
                    "First Seen": record.first_seen or "",
                }
            )

    rows.extend(_build_metric_change_section(current, previous))
    rows.extend(_build_health_trend_section(current))
    return rows


def _build_metric_change_section(
    current: RunSnapshot,
    previous: RunSnapshot,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [_section_title_row("Metric Changes")]
    changes_found = False
    shared_urls = sorted(set(current.metrics_by_url) & set(previous.metrics_by_url))
    for url in shared_urls:
        current_metrics = current.metrics_by_url.get(url, {})
        previous_metrics = previous.metrics_by_url.get(url, {})
        for metric_name in METRIC_FIELDS:
            prev_val = previous_metrics.get(metric_name)
            curr_val = current_metrics.get(metric_name)
            if prev_val is None or curr_val is None:
                continue
            change = round(curr_val - prev_val, 2)
            if change == 0:
                continue
            changes_found = True
            rows.append(
                _blank_delta_row("Metric Changes")
                | {
                    "URL": url,
                    "Issue": metric_name,
                    "Previous Value": prev_val,
                    "Current Value": curr_val,
                    "Change": change,
                    "Direction": _direction_for_change(change),
                }
            )
    if not changes_found:
        rows.append(
            _blank_delta_row("Metric Changes")
            | {"Notes": "No metric changes detected for tracked KPIs."}
        )
    return rows


def _build_health_trend_section(current: RunSnapshot) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [_section_title_row("SEO Health Trend")]
    trend_rows = 0
    for url in sorted(current.health_trend):
        points = current.health_trend[url]
        if not points:
            continue
        padded = (points + [None, None, None])[:3]
        rows.append(
            _blank_delta_row("SEO Health Trend")
            | {
                "URL": url,
                "Trend Run 1": _format_trend_cell(padded[0]),
                "Trend Run 2": _format_trend_cell(padded[1]),
                "Trend Run 3": _format_trend_cell(padded[2]),
            }
        )
        trend_rows += 1
    if trend_rows == 0:
        rows.append(
            _blank_delta_row("SEO Health Trend")
            | {"Notes": "Trend builds across successive runs once delta summaries are saved."}
        )
    return rows


def build_resolved_issues_dataframe(
    *,
    current: RunSnapshot,
    previous: RunSnapshot | None,
    baseline_report: bool,
) -> pd.DataFrame:
    if baseline_report or previous is None:
        return pd.DataFrame(
            [
                {
                    "Stable Issue ID": "",
                    "Issue": BASELINE_DELTA_NOTE,
                    "URL": "",
                    "Severity": "",
                    "Last Seen": "",
                    "Days Open": "",
                }
            ]
        )

    resolved_ids = previous.issue_ids - current.issue_ids
    if not resolved_ids:
        return pd.DataFrame(
            [
                {
                    "Stable Issue ID": "",
                    "Issue": "No resolved issues identified for this comparison run.",
                    "URL": "",
                    "Severity": "",
                    "Last Seen": "",
                    "Days Open": "",
                }
            ]
        )

    resolved_rows: list[dict[str, Any]] = []
    for stable_id in sorted(resolved_ids):
        record = previous.issues.get(stable_id)
        if record is None:
            continue
        days_open = _days_between(record.first_seen, previous.run_date)
        resolved_rows.append(
            {
                "Stable Issue ID": stable_id,
                "Issue": record.issue,
                "URL": record.url,
                "Severity": record.severity,
                "Last Seen": previous.run_date,
                "Days Open": days_open if days_open is not None else "",
                "First Seen": record.first_seen or "",
            }
        )
    return pd.DataFrame(resolved_rows)


def build_delta_workbook_output(
    *,
    issue_inventory_df: pd.DataFrame,
    main_rows: list[dict[str, Any]],
    extra_rows: list[dict[str, Any]],
    typed_extra_rows: list[ExtraRowPayload],
    summary_rules: list[IssueRule],
    previous_snapshot: RunSnapshot | None,
    baseline_report: bool,
    output_path: str,
    run_date: str | None = None,
) -> tuple[list[dict[str, Any]], pd.DataFrame, RunSnapshot]:
    current_snapshot = snapshot_from_current_run(
        issue_inventory_df=issue_inventory_df,
        main_rows=main_rows,
        extra_rows=extra_rows,
        source_path=output_path,
        run_date=run_date,
        previous_snapshot=previous_snapshot,
    )
    delta_rows = build_delta_sheet_rows(
        current=current_snapshot,
        previous=previous_snapshot,
        baseline_report=baseline_report,
        typed_extra_rows=typed_extra_rows,
        summary_rules=summary_rules,
    )
    resolved_df = build_resolved_issues_dataframe(
        current=current_snapshot,
        previous=previous_snapshot,
        baseline_report=baseline_report,
    )
    return delta_rows, resolved_df, current_snapshot


__all__ = [
    "BASELINE_DELTA_NOTE",
    "DELTA_SHEET_COLUMNS",
    "RunSnapshot",
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
