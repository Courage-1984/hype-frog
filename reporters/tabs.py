from __future__ import annotations

from typing import Any

import pandas as pd

from checkpoint.cache import AuditCache
from rules import owner_for_issue, workflow_metrics_for_issue


def load_cached_rows(cache: AuditCache) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    main_rows: list[dict[str, Any]] = []
    extra_rows: list[dict[str, Any]] = []
    for result in cache.iter_results():
        main_rows.append(result["main"])
        extra_rows.append(result["extra"])
    return main_rows, extra_rows


def build_core_dataframes(cache: AuditCache) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
    main_rows, extra_rows = load_cached_rows(cache)
    return pd.DataFrame(main_rows), pd.DataFrame(extra_rows), main_rows, extra_rows


def write_dict_rows_sheet(writer, sheet_name: str, columns: list[str], rows: list[dict[str, Any]]) -> None:
    ws = writer.book.create_sheet(title=sheet_name)
    writer.sheets[sheet_name] = ws
    ws.append(columns)
    for row in rows:
        ws.append([row.get(col) for col in columns])


def write_cached_sheet_chunked(
    writer,
    cache: AuditCache,
    sheet_name: str,
    columns: list[str],
    payload_key: str,
    chunk_size: int = 500,
) -> None:
    ws = writer.book.create_sheet(title=sheet_name)
    writer.sheets[sheet_name] = ws
    ws.append(columns)
    for chunk in cache.iter_results_chunked(chunk_size):
        for result in chunk:
            payload = result.get(payload_key, {})
            ws.append([payload.get(col) for col in columns])


def build_fixplan_rows(
    summary_rules: list[tuple[str, str, Any]],
    extra_rows: list[dict[str, Any]],
    aeo_issue_names: set[str],
    root_cause_resolver,
    default_effort_by_severity: dict[str, str],
    default_owner_by_severity: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    status_by_severity = {
        "Critical": "To Do",
        "Warning": "To Do",
        "Info": "In Review",
    }
    for severity, issue_name, _ in summary_rules:
        affected = [
            r for r in extra_rows if issue_name in str(r.get("Matched Issues") or "").split(" | ")
        ]
        root_cause, recommended_fix = root_cause_resolver(issue_name)
        effort = default_effort_by_severity.get(severity, "S")
        workflow = workflow_metrics_for_issue(severity, effort)
        rows.append(
            {
                "Category": "AEO" if issue_name in aeo_issue_names else "SEO",
                "Issue Type": issue_name,
                "Severity": severity,
                "Affected Count": len(affected),
                "Likely Root Cause": root_cause,
                "Recommended Fix": recommended_fix,
                "Owner": owner_for_issue(issue_name, severity),
                "URL": affected[0].get("URL") if affected else "",
                "Affected URLs": "\n".join([str(r.get("URL") or "") for r in affected if r.get("URL")][:50]),
                "Effort": effort,
                "Action Needed": "Yes" if severity in {"Critical", "Warning"} else "No",
                "Sprint": "",
                "Status": status_by_severity.get(severity, "To Do"),
                "Agency Owner": owner_for_issue(issue_name, severity),
                "Jump to Details": "Open in Main Tab",
                "Est. Sprint Points": workflow["Est. Sprint Points"],
                "Est. Hours": workflow["Est. Hours"],
                "Priority Score": workflow["Priority Score"],
                "Aging/Priority": workflow["Aging/Priority"],
            }
        )
    return rows


def write_snippet_candidates_chunked(
    writer,
    cache: AuditCache,
    sheet_name: str = "SnippetCandidates",
    chunk_size: int = 500,
) -> None:
    columns = ["URL", "Heading (Question)", "Snippet (Answer)", "Word Count"]
    ws = writer.book.create_sheet(title=sheet_name)
    writer.sheets[sheet_name] = ws
    ws.append(columns)
    has_rows = False
    for chunk in cache.iter_results_chunked(chunk_size):
        for result in chunk:
            extra = result.get("extra", {})
            url = extra.get("URL")
            for snippet in extra.get("aeo_snippets", []) or []:
                ws.append(
                    [
                        url,
                        snippet.get("heading"),
                        snippet.get("snippet"),
                        snippet.get("word_count"),
                    ]
                )
                has_rows = True
    if not has_rows:
        ws.append(
            [
                "https://example.com/sample-answer-page",
                "What is technical SEO and why does it matter?",
                "Technical SEO improves crawlability, indexation, and page performance so search engines can understand and rank your pages correctly.",
                19,
            ]
        )
