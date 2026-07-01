"""Delta comparison models, constants, and shared row helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from hype_frog.core.numeric_utils import safe_int
from hype_frog.core.path_utils import path_exists

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
    "Trend Run 2 (populated on run 2+)",
    "Trend Run 3 (populated on run 3+)",
    "Notes",
)
def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def optional_float(value: object) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def direction_for_change(change: float | None) -> str:
    if change is None:
        return ""
    if change > 0:
        return "↑"
    if change < 0:
        return "↓"
    return "→"


def parse_run_timestamp(raw: object) -> str | None:
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
def blank_delta_row(section: str = "") -> dict[str, Any]:
    return {column: "" for column in DELTA_SHEET_COLUMNS} | {"Section": section}


def section_title_row(title: str) -> dict[str, Any]:
    row = blank_delta_row(title)
    row["Notes"] = title
    return row


def format_trend_cell(point: TrendPoint | None) -> str:
    if point is None:
        return ""
    return f"{point.score:.1f} ({point.run_date})"
def delta_summary_path_for_workbook(workbook_path: str) -> str:
    base = workbook_path.replace(".xlsx", "")
    return f"{base}{DELTA_SUMMARY_SUFFIX}"


def companion_summary_path(path: str) -> str:
    """JSON sidecar for an xlsx path, if it exists."""
    if path.lower().endswith(".json"):
        return path
    candidate = delta_summary_path_for_workbook(path)
    return candidate if path_exists(candidate) else ""

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
            first_seen=optional_str(raw.get("first_seen")),
            last_seen=optional_str(raw.get("last_seen")),
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
                    key: optional_float(metrics.get(key)) for key in METRIC_FIELDS
                }
        fixed_raw = raw.get("fixed_issue_ids") or []
        fixed_issue_ids = {
            str(value).strip() for value in fixed_raw if str(value).strip()
        }
        counts_raw = raw.get("issue_counts_by_name") or {}
        issue_counts = (
            {str(k): safe_int(v) for k, v in counts_raw.items()}
            if isinstance(counts_raw, dict)
            else {}
        )
        return cls(
            run_date=str(raw.get("run_date") or "").strip() or utc_now_iso(),
            source_path=str(raw.get("source_path") or "").strip(),
            issues=issues,
            metrics_by_url=metrics_by_url,
            health_trend=health_trend,
            issue_counts_by_name=issue_counts,
            fixed_issue_ids=fixed_issue_ids,
        )
