"""Build DeltaFromPreviousRun sheet rows and resolved-issue frames."""

from __future__ import annotations

from typing import Any

import pandas as pd

from hype_frog.analysis.delta_loader import snapshot_from_current_run
from hype_frog.analysis.delta_models import (
    BASELINE_DELTA_NOTE,
    METRIC_FIELDS,
    RunSnapshot,
    blank_delta_row,
    days_between,
    direction_for_change,
    format_trend_cell,
    section_title_row,
)
from hype_frog.rules.registry import IssueRule

def build_delta_sheet_rows(
    *,
    current: RunSnapshot,
    previous: RunSnapshot | None,
    baseline_report: bool,
    summary_rules: list[IssueRule],
) -> list[dict[str, Any]]:
    """Build multi-section DeltaFromPreviousRun rows."""
    rows: list[dict[str, Any]] = []
    if baseline_report or previous is None:
        rows.append(section_title_row("Summary"))
        rows.append(
            blank_delta_row("Summary")
            | {
                "Issue": "Report Status",
                "Current Value": BASELINE_DELTA_NOTE,
                "Notes": BASELINE_DELTA_NOTE,
            }
        )
        rows.append(
            blank_delta_row("Summary")
            | {
                "Issue": "Current Issues (baseline inventory)",
                "Current Value": len(current.issue_ids),
            }
        )
        rows.extend(build_health_trend_section(current))
        return rows

    current_ids = current.issue_ids
    previous_ids = previous.issue_ids
    new_ids = current_ids - previous_ids
    resolved_ids = previous_ids - current_ids
    unchanged_ids = current_ids & previous_ids
    reopened_ids = current_ids & previous.fixed_issue_ids

    rows.append(section_title_row("Summary"))
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
                blank_delta_row("Summary")
                | {
                    "Issue": label,
                    "Previous Value": prev_val,
                    "Current Value": curr_val,
                    "Change": change,
                    "Direction": direction_for_change(float(change)),
                }
            )
        else:
            rows.append(
                blank_delta_row("Summary")
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
            blank_delta_row("Summary")
            | {
                "Issue": f"Issue Delta: {issue_name}",
                "Previous Value": prev_count,
                "Current Value": current_count,
                "Change": delta,
                "Direction": direction_for_change(float(delta)),
            }
        )

    rows.append(section_title_row("New Issues"))
    if not new_ids:
        rows.append(
            blank_delta_row("New Issues")
            | {"Notes": "No new issues compared with the previous run."}
        )
    else:
        for stable_id in sorted(new_ids):
            record = current.issues.get(stable_id)
            if record is None:
                continue
            rows.append(
                blank_delta_row("New Issues")
                | {
                    "Stable Issue ID": stable_id,
                    "URL": record.url,
                    "Issue": record.issue,
                    "Severity": record.severity,
                    "First Seen": record.first_seen or current.run_date,
                }
            )

    rows.append(section_title_row("Resolved Issues"))
    if not resolved_ids:
        rows.append(
            blank_delta_row("Resolved Issues")
            | {"Notes": "No resolved issues compared with the previous run."}
        )
    else:
        for stable_id in sorted(resolved_ids):
            record = previous.issues.get(stable_id)
            if record is None:
                continue
            days_open = days_between(record.first_seen, previous.run_date)
            rows.append(
                blank_delta_row("Resolved Issues")
                | {
                    "Stable Issue ID": stable_id,
                    "URL": record.url,
                    "Issue": record.issue,
                    "Severity": record.severity,
                    "Last Seen": previous.run_date,
                    "Days Open": days_open if days_open is not None else "",
                    "First Seen": record.first_seen or "",
                }
            )

    rows.extend(build_metric_change_section(current, previous))
    rows.extend(build_health_trend_section(current))
    return rows


def build_metric_change_section(
    current: RunSnapshot,
    previous: RunSnapshot,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [section_title_row("Metric Changes")]
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
                blank_delta_row("Metric Changes")
                | {
                    "URL": url,
                    "Issue": metric_name,
                    "Previous Value": prev_val,
                    "Current Value": curr_val,
                    "Change": change,
                    "Direction": direction_for_change(change),
                }
            )
    if not changes_found:
        rows.append(
            blank_delta_row("Metric Changes")
            | {"Notes": "No metric changes detected for tracked KPIs."}
        )
    return rows


def build_health_trend_section(current: RunSnapshot) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [section_title_row("SEO Health Trend")]
    trend_rows = 0
    for url in sorted(current.health_trend):
        points = current.health_trend[url]
        if not points:
            continue
        padded = (points + [None, None, None])[:3]
        rows.append(
            blank_delta_row("SEO Health Trend")
            | {
                "URL": url,
                "Trend Run 1": format_trend_cell(padded[0]),
                "Trend Run 2 (populated on run 2+)": format_trend_cell(padded[1]),
                "Trend Run 3 (populated on run 3+)": format_trend_cell(padded[2]),
            }
        )
        trend_rows += 1
    if trend_rows == 0:
        rows.append(
            blank_delta_row("SEO Health Trend")
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
        days_open = days_between(record.first_seen, previous.run_date)
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
        summary_rules=summary_rules,
    )
    resolved_df = build_resolved_issues_dataframe(
        current=current_snapshot,
        previous=previous_snapshot,
        baseline_report=baseline_report,
    )
    return delta_rows, resolved_df, current_snapshot
