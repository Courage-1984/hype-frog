"""Summary tab and Issue Inventory row builders for Excel export."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import Any

from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.core import get_logger
from hype_frog.rules import IssueRule, owner_for_issue, stable_issue_id

logger = get_logger(__name__)

_LEGACY_TO_MERGED_REFERENCE_TAB: dict[str, str] = {
    "Technical": "Technical Diagnostics",
    "Indexability": "Technical Diagnostics",
    "Links": "Link Intelligence",
    "AEO": "Content & AI Readiness",
    "Schema & Metadata": "Content & AI Readiness",
    "Pattern and Template Issues": "Template & Duplication Risks",
}


def reference_tab_for_merged_workbook(legacy_tab: str) -> str:
    """Map pre-merge tab labels to current worksheet names for hyperlinks / INDIRECT."""
    key = str(legacy_tab or "").strip()
    return _LEGACY_TO_MERGED_REFERENCE_TAB.get(key, key)


def safe_rule(rule_fn: Callable[..., Any], row: Mapping[str, Any]) -> bool:
    try:
        return bool(rule_fn(row))
    except Exception as exc:
        logger.debug("Issue rule evaluation failed: %s", exc)
        return False


def build_summary_rows(
    summary_rules: list[IssueRule],
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
    for rule in summary_rules:
        affected_urls = [
            row.values.get("URL")
            for row in extra_rows
            if safe_rule(rule.fn, row.values)
        ]
        summary_rows.append(
            {
                "Section": "Issue Counts",
                "Severity": rule.severity,
                "Issue": rule.name,
                "Affected URL Count": len(affected_urls),
                "Reference Tab": reference_tab_for_merged_workbook(
                    "Indexability"
                    if "Canonical" in rule.name or "Noindex" in rule.name
                    else "Links"
                    if "Links" in rule.name
                    else "AEO"
                    if "AEO" in rule.name
                    or "Question" in rule.name
                    or "FAQ" in rule.name
                    else "Technical"
                ),
                "Affected URLs (sample)": " | ".join([u for u in affected_urls[:25] if u])
                + " || Full list: see Technical Diagnostics / Link Intelligence tabs",
            }
        )
    summary_rows.append(
        {
            "Section": "AEO Opportunities",
            "Severity": None,
            "Issue": None,
            "Affected URL Count": None,
            "Affected URLs (sample)": "Detailed rows: see Content & AI Readiness tab",
        }
    )
    for rule in summary_rules:
        if rule.name not in aeo_issue_names:
            continue
        affected_urls = [
            row.values.get("URL")
            for row in extra_rows
            if safe_rule(rule.fn, row.values)
        ]
        summary_rows.append(
            {
                "Section": "AEO Opportunities",
                "Severity": rule.severity,
                "Issue": rule.name,
                "Affected URL Count": len(affected_urls),
                "Reference Tab": reference_tab_for_merged_workbook("AEO"),
                "Affected URLs (sample)": " | ".join([u for u in affected_urls[:25] if u])
                + " || Full list: see Content & AI Readiness tab",
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
                "Reference Tab": reference_tab_for_merged_workbook(
                    "Pattern and Template Issues"
                ),
                "Affected URLs (sample)": None,
            }
        )
    return summary_rows


def _inventory_reference_tab(issue_name: str) -> str:
    legacy_ref = (
        "Indexability"
        if ("Canonical" in issue_name or "Noindex" in issue_name)
        else "Links"
        if ("Links" in issue_name or "Anchor" in issue_name)
        else "AEO"
        if ("AEO" in issue_name or "Question" in issue_name or "FAQ" in issue_name)
        else "Technical"
    )
    return reference_tab_for_merged_workbook(legacy_ref)


def _aggregate_inventory_url_label(scope: str) -> str:
    if scope == "site":
        return "(site-wide)"
    if scope == "server":
        return "(server config)"
    return f"({scope})"


def _aggregate_stable_issue_key(scope: str) -> str:
    if scope == "site":
        return "site"
    if scope == "server":
        return "server"
    return scope


def build_issue_inventory_rows(
    summary_rules: list[IssueRule],
    extra_rows: list[ExtraRowPayload],
    main_rows: list[MainRowPayload] | None = None,
) -> list[dict[str, object]]:
    """Flatten matched issues per URL for the IssueInventory sheet."""
    del main_rows
    critical_names = {rule.name for rule in summary_rules if rule.severity == "Critical"}
    warning_names = {rule.name for rule in summary_rules if rule.severity == "Warning"}
    aggregate_issue_names = {rule.name for rule in summary_rules if rule.scope != "url"}
    rows: list[dict[str, object]] = []

    for rule in summary_rules:
        if rule.scope == "url":
            continue
        affected = [row for row in extra_rows if safe_rule(rule.fn, row.values)]
        if not affected:
            continue
        rows.append(
            {
                "URL": _aggregate_inventory_url_label(rule.scope),
                "Issue": rule.name,
                "Stable Issue ID": stable_issue_id(
                    _aggregate_stable_issue_key(rule.scope),
                    rule.name,
                ),
                "Severity": rule.severity,
                "Affected URL Count": len(affected),
                "Reference Tab": _inventory_reference_tab(rule.name),
                "Owner": owner_for_issue(rule.name, rule.severity),
                "Sprint": "",
                "Status": "Open",
            }
        )

    for row in extra_rows:
        row_values = row.values
        url = row_values.get("URL")
        for issue in str(row_values.get("Matched Issues") or "").split(" | "):
            if not issue or issue in aggregate_issue_names:
                continue
            issue_severity = (
                "Critical"
                if issue in critical_names
                else "Warning"
                if issue in warning_names
                else "Observation"
            )
            rows.append(
                {
                    "URL": url,
                    "Issue": issue,
                    "Stable Issue ID": stable_issue_id(url, issue),
                    "Severity": issue_severity,
                    "Affected URL Count": None,
                    "Reference Tab": _inventory_reference_tab(issue),
                    "Owner": owner_for_issue(issue, issue_severity),
                    "Sprint": "",
                    "Status": "Open",
                }
            )
    return rows


__all__ = [
    "build_issue_inventory_rows",
    "build_summary_rows",
    "reference_tab_for_merged_workbook",
    "safe_rule",
]
