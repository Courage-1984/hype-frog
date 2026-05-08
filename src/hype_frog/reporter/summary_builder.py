"""Summary tab and Issue Inventory row builders for Excel export."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import Any

from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.rules import owner_for_issue, stable_issue_id


def safe_rule(rule_fn: Callable[..., Any], row: Mapping[str, Any]) -> bool:
    try:
        return bool(rule_fn(row))
    except Exception:
        return False


def build_summary_rows(
    summary_rules: list[tuple[str, str, Any]],
    extra_rows: list[ExtraRowPayload],
    template_issue_counts: defaultdict[str, defaultdict[str, int]],
    value_or_default: Callable[[object, float], float],
    main_rows: list[MainRowPayload] | None = None,
) -> list[dict[str, object]]:
    """Build rows for the Summary sheet (issue counts, AEO block, top URLs, templates)."""
    aeo_issue_names = {
        "Low AEO Readiness Score",
        "Missing FAQ/QA Schema",
        "No Question Headings",
        "No Answer-Friendly Structure",
        "No 40-60 Word Answer Paragraphs",
    }
    summary_rows: list[dict[str, object]] = []
    summary_rows.append(
        {
            "Section": "Issue Counts",
            "Severity": None,
            "Issue": None,
            "Affected URL Count": None,
            "Affected URLs (sample)": None,
        }
    )
    del main_rows
    for severity, issue_name, rule_fn in summary_rules:
        affected_urls = [
            row.values.get("URL")
            for row in extra_rows
            if safe_rule(rule_fn, row.values)
        ]
        summary_rows.append(
            {
                "Section": "Issue Counts",
                "Severity": severity,
                "Issue": issue_name,
                "Affected URL Count": len(affected_urls),
                "Reference Tab": "Indexability"
                if "Canonical" in issue_name or "Noindex" in issue_name
                else "Links"
                if "Links" in issue_name
                else "AEO"
                if "AEO" in issue_name
                or "Question" in issue_name
                or "FAQ" in issue_name
                else "Technical",
                "Affected URLs (sample)": " | ".join([u for u in affected_urls[:25] if u])
                + " || Full list: see Technical/Links/Indexability tabs",
            }
        )
    summary_rows.append(
        {
            "Section": "AEO Opportunities",
            "Severity": None,
            "Issue": None,
            "Affected URL Count": None,
            "Affected URLs (sample)": "Detailed rows: see AEO tab",
        }
    )
    for severity, issue_name, rule_fn in summary_rules:
        if issue_name not in aeo_issue_names:
            continue
        affected_urls = [
            row.values.get("URL")
            for row in extra_rows
            if safe_rule(rule_fn, row.values)
        ]
        summary_rows.append(
            {
                "Section": "AEO Opportunities",
                "Severity": severity,
                "Issue": issue_name,
                "Affected URL Count": len(affected_urls),
                "Reference Tab": "AEO",
                "Affected URLs (sample)": " | ".join([u for u in affected_urls[:25] if u])
                + " || Full list: see AEO tab",
            }
        )
    severity_order = {"Critical": 0, "Warning": 1, "Observation": 2}
    summary_rows = sorted(
        summary_rows,
        key=lambda x: (
            x.get("Section", ""),
            severity_order.get(str(x.get("Severity") or ""), 99),
            -(x.get("Affected URL Count") or 0),
            x.get("Issue", ""),
        ),
    )
    summary_rows.append(
        {
            "Section": "Top 10 Critical URLs",
            "Severity": None,
            "Issue": None,
            "Affected URL Count": None,
            "Affected URLs (sample)": None,
        }
    )
    critical_urls = sorted(
        [
            r
            for r in extra_rows
            if value_or_default(r.values.get("Critical Issues Count"), 0.0) > 0
        ],
        key=lambda r: (
            -value_or_default(r.values.get("Critical Issues Count"), 0.0),
            value_or_default(r.values.get("SEO Health Score"), 100.0),
        ),
    )[:10]
    for idx, row in enumerate(critical_urls, start=1):
        row_values = row.values
        summary_rows.append(
            {
                "Section": "Top 10 Critical URLs",
                "Severity": "Critical",
                "Issue": f"#{idx} {row_values.get('URL')}",
                "Affected URL Count": row_values.get("Critical Issues Count"),
                "Reference Tab": "Priority URLs",
                "Affected URLs (sample)": row_values.get("Matched Issues"),
            }
        )
    summary_rows.append(
        {
            "Section": "Top Issues by Template",
            "Severity": None,
            "Issue": None,
            "Affected URL Count": None,
            "Affected URLs (sample)": None,
        }
    )
    top_template_issues = sorted(
        [
            (seg, issue_name, issue_count)
            for seg, issues in template_issue_counts.items()
            for issue_name, issue_count in issues.items()
        ],
        key=lambda x: x[2],
        reverse=True,
    )[:20]
    for seg, issue_name, issue_count in top_template_issues:
        summary_rows.append(
            {
                "Section": "Top Issues by Template",
                "Severity": "Observation",
                "Issue": f"{seg} -> {issue_name}",
                "Affected URL Count": issue_count,
                "Reference Tab": "Pattern and Template Issues",
                "Affected URLs (sample)": None,
            }
        )
    return summary_rows


def build_issue_inventory_rows(
    summary_rules: list[tuple[str, str, Any]],
    extra_rows: list[ExtraRowPayload],
    main_rows: list[MainRowPayload] | None = None,
) -> list[dict[str, object]]:
    """Flatten matched issues per URL for the IssueInventory sheet."""
    del main_rows
    critical_names = {i[1] for i in summary_rules if i[0] == "Critical"}
    warning_names = {i[1] for i in summary_rules if i[0] == "Warning"}
    rows: list[dict[str, object]] = []
    for row in extra_rows:
        row_values = row.values
        url = row_values.get("URL")
        for issue in str(row_values.get("Matched Issues") or "").split(" | "):
            if not issue:
                continue
            issue_severity = (
                "Critical"
                if issue in critical_names
                else "Warning"
                if issue in warning_names
                else "Observation"
            )
            reference_tab = (
                "Indexability"
                if ("Canonical" in issue or "Noindex" in issue)
                else "Links"
                if ("Links" in issue or "Anchor" in issue)
                else "AEO"
                if ("AEO" in issue or "Question" in issue or "FAQ" in issue)
                else "Technical"
            )
            rows.append(
                {
                    "URL": url,
                    "Issue": issue,
                    "Stable Issue ID": stable_issue_id(url, issue),
                    "Severity": issue_severity,
                    "Reference Tab": reference_tab,
                    "Owner": owner_for_issue(issue, issue_severity),
                    "Sprint": "",
                    "Status": "Open",
                }
            )
    return rows


__all__ = [
    "build_issue_inventory_rows",
    "build_summary_rows",
    "safe_rule",
]
