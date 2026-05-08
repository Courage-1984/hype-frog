from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from hype_frog.models import ExtraRowPayload, MainRowPayload, SummaryMetricsPayload


class FixPlanRowPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    issue_type: str = Field(default="", alias="Issue Type")
    affected_count: int = Field(default=0, alias="Affected Count")
    owner: str = Field(default="Unassigned", alias="Owner")
    severity: str = Field(default="", alias="Severity")
    priority_score: int = Field(default=0, alias="Priority Score")
    source_row: int = Field(default=0, ge=0)


class OwnerRollup(BaseModel):
    issue_rows: int = 0
    affected_urls: int = 0
    critical: int = 0
    warning: int = 0
    info: int = 0


class TopIssueRow(BaseModel):
    issue_name: str
    affected_urls: int
    source_row: int


class DashboardComputationResult(BaseModel):
    status_buckets: dict[str, int]
    pass_urls: int
    critical_urls: int
    warning_urls: int
    avg_ttfb_ms: float
    schema_urls: int
    broken_links_total: int
    crawl_denominator: int
    error_count: int
    success_count: int
    pass_rate_pct: float
    critical_rate_pct: float
    warning_rate_pct: float
    avg_health_score: float | None
    overall_health: float
    projected_pass_rate_pct: float
    projected_health_pct: float
    b7_pass_display: float
    top_issue_name: str
    top_issue_affected: int
    owner_rollup: dict[str, OwnerRollup]
    severity_counts: dict[str, int]
    severity_distribution_pct: dict[str, float]
    top_issue_rows: list[TopIssueRow]
    traditional_score: float
    aeo_readiness: float


def compute_dashboard_metrics(
    *,
    summary_metrics: SummaryMetricsPayload,
    technical_main_rows: list[MainRowPayload],
    technical_extra_rows: list[ExtraRowPayload],
    fixplan_rows: list[FixPlanRowPayload],
    aeo_rows: list[ExtraRowPayload],
) -> DashboardComputationResult:
    status_buckets = {
        "200 OK": 0,
        "3xx Redirects": 0,
        "4xx Errors": 0,
        "5xx Errors": 0,
        "Other": 0,
    }
    pass_urls = 0
    critical_urls = 0
    warning_urls = 0
    schema_urls = 0
    broken_links_total = 0
    ttfb_values: list[float] = []
    health_values: list[float] = []

    for idx, extra_payload in enumerate(technical_extra_rows):
        extra_row = extra_payload.to_dict()
        status_code_raw = extra_row.get("Status Code")
        try:
            code = int(float(status_code_raw)) if status_code_raw is not None else 0
        except (TypeError, ValueError):
            code = 0
        if 200 <= code < 300:
            status_buckets["200 OK"] += 1
        elif 300 <= code < 400:
            status_buckets["3xx Redirects"] += 1
        elif 400 <= code < 500:
            status_buckets["4xx Errors"] += 1
        elif 500 <= code < 600:
            status_buckets["5xx Errors"] += 1
        elif code:
            status_buckets["Other"] += 1

        sev = str(extra_row.get("Severity Badge") or "").strip().lower()
        if sev == "critical":
            critical_urls += 1
        elif sev == "warning":
            warning_urls += 1

        schema_urls += 1 if int(extra_row.get("Schema Types Count") or 0) > 0 else 0
        broken_links_total += int(extra_row.get("Broken Internal Links Count") or 0)

        raw_ttfb = extra_row.get("TTFB (ms)")
        try:
            if raw_ttfb is not None and str(raw_ttfb).strip() != "":
                ttfb_values.append(float(raw_ttfb))
        except (TypeError, ValueError):
            pass

        if idx < len(technical_main_rows):
            main_row = technical_main_rows[idx].to_dict()
            try:
                raw_health = main_row.get("SEO Health Score")
                if raw_health is not None and str(raw_health).strip() != "":
                    health_values.append(float(raw_health))
            except (TypeError, ValueError):
                pass

            crit_count = int(extra_row.get("Critical Issues Count") or 0)
            warn_count = int(extra_row.get("Warning Issues Count") or 0)
            if crit_count == 0 and warn_count == 0:
                pass_urls += 1
        elif sev in {"pass", "info"}:
            pass_urls += 1

    severity_counts: Counter[str] = Counter()
    owner_rollup: dict[str, OwnerRollup] = defaultdict(OwnerRollup)
    top_issue_name = "N/A"
    top_issue_affected = 0
    top_issue_rows: list[TopIssueRow] = []

    for row in fixplan_rows:
        affected = max(0, row.affected_count)
        sev = row.severity.strip().lower()
        if sev == "critical":
            severity_counts["Critical"] += 1
        elif sev in {"high", "warning"}:
            severity_counts["High"] += 1
        elif sev == "medium":
            severity_counts["Medium"] += 1
        else:
            severity_counts["Low"] += 1

        if affected > top_issue_affected:
            top_issue_affected = affected
            top_issue_name = row.issue_type or "N/A"

        owner_name = row.owner.strip() or "Unassigned"
        metrics = owner_rollup[owner_name]
        metrics.issue_rows += 1
        metrics.affected_urls += affected
        if sev == "critical":
            metrics.critical += 1
        elif sev in {"warning", "high", "medium"}:
            metrics.warning += 1
        else:
            metrics.info += 1

        if row.issue_type.strip():
            top_issue_rows.append(
                TopIssueRow(
                    issue_name=row.issue_type.strip(),
                    affected_urls=affected,
                    source_row=row.source_row,
                )
            )

    top_issue_rows.sort(key=lambda item: (-item.affected_urls, -item.source_row, item.issue_name))
    top_issue_rows = top_issue_rows[:5]

    status_total = sum(status_buckets.values())
    crawl_denominator = max(1, status_total or summary_metrics.urls_crawled)
    error_count = status_buckets["4xx Errors"] + status_buckets["5xx Errors"]
    success_count = status_buckets["200 OK"]
    pass_rate_pct = round((pass_urls / crawl_denominator) * 100, 2)
    critical_rate_pct = round((critical_urls / crawl_denominator) * 100, 2)
    warning_rate_pct = round((warning_urls / crawl_denominator) * 100, 2)
    avg_ttfb_ms = round(sum(ttfb_values) / len(ttfb_values), 2) if ttfb_values else 0.0
    avg_health_score = sum(health_values) / len(health_values) if health_values else None
    overall_health = float(
        summary_metrics.health_score_pct
        if summary_metrics.health_score_pct > 0
        else (avg_health_score if avg_health_score is not None else pass_rate_pct)
    )
    projected_pass_rate_pct = min(
        100.0,
        pass_rate_pct + ((critical_urls + (warning_urls * 0.75)) / max(1, crawl_denominator)) * 100.0,
    )
    projected_health_pct = min(100.0, min(100.0, overall_health) + ((100.0 - overall_health) * 0.6))
    b7_pass_display = summary_metrics.seo_pass_rate_pct if summary_metrics.seo_pass_rate_pct > 0 else pass_rate_pct

    aeo_scores: list[float] = []
    for row in aeo_rows:
        raw = row.to_dict().get("AEO Readiness Score")
        try:
            if raw is not None and str(raw).strip() != "":
                aeo_scores.append(float(raw))
        except (TypeError, ValueError):
            pass
    aeo_readiness = round(sum(aeo_scores) / len(aeo_scores), 2) if aeo_scores else 0.0

    traditional_score = max(0.0, min(100.0, (success_count / max(1, crawl_denominator)) * 100.0))
    if avg_health_score is not None:
        traditional_score = round((traditional_score * 0.4) + (avg_health_score * 0.6), 2)

    severity_total = max(1, sum(severity_counts.values()))
    severity_distribution_pct = {
        "Critical": round((severity_counts.get("Critical", 0) / severity_total) * 100, 2),
        "High": round((severity_counts.get("High", 0) / severity_total) * 100, 2),
        "Medium": round((severity_counts.get("Medium", 0) / severity_total) * 100, 2),
        "Low": round((severity_counts.get("Low", 0) / severity_total) * 100, 2),
    }

    return DashboardComputationResult(
        status_buckets=status_buckets,
        pass_urls=pass_urls,
        critical_urls=critical_urls,
        warning_urls=warning_urls,
        avg_ttfb_ms=avg_ttfb_ms,
        schema_urls=schema_urls,
        broken_links_total=broken_links_total,
        crawl_denominator=crawl_denominator,
        error_count=error_count,
        success_count=success_count,
        pass_rate_pct=pass_rate_pct,
        critical_rate_pct=critical_rate_pct,
        warning_rate_pct=warning_rate_pct,
        avg_health_score=avg_health_score,
        overall_health=overall_health,
        projected_pass_rate_pct=projected_pass_rate_pct,
        projected_health_pct=projected_health_pct,
        b7_pass_display=b7_pass_display,
        top_issue_name=top_issue_name,
        top_issue_affected=top_issue_affected,
        owner_rollup=dict(owner_rollup),
        severity_counts=dict(severity_counts),
        severity_distribution_pct=severity_distribution_pct,
        top_issue_rows=top_issue_rows,
        traditional_score=traditional_score,
        aeo_readiness=aeo_readiness,
    )


__all__ = [
    "DashboardComputationResult",
    "FixPlanRowPayload",
    "TopIssueRow",
    "compute_dashboard_metrics",
]
