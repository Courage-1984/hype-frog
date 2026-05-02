"""
Monolithic Excel / openpyxl engine: workbook helpers, tab builders, conditional
formatting helpers, and strict export guardrails (Action Required, TOC, freeze).
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, unquote, urlparse, urlsplit, urlunsplit

import pandas as pd
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule, FormulaRule
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from hype_frog.checkpoint.cache import AuditCache
from hype_frog.rules import owner_for_issue, workflow_metrics_for_issue
from hype_frog.utils import normalize_url_key

# ---------------------------------------------------------------------------
# Legacy formatting (formerly formatting.py)
# ---------------------------------------------------------------------------


def apply_fixplan_workflow_formatting(worksheet: Worksheet) -> None:
    headers = [cell.value for cell in worksheet[1]]
    header_to_col = {str(h): i + 1 for i, h in enumerate(headers) if h is not None}
    priority_col = header_to_col.get("Priority Score")
    points_col = header_to_col.get("Est. Sprint Points")
    aging_col = header_to_col.get("Aging/Priority")
    critical_fill = PatternFill(start_color="F4CCCC", end_color="F4CCCC", fill_type="solid")
    warning_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    good_fill = PatternFill(start_color="D9EAD3", end_color="D9EAD3", fill_type="solid")
    edge_fill = PatternFill(start_color="D9D2E9", end_color="D9D2E9", fill_type="solid")
    for row_idx in range(2, worksheet.max_row + 1):
        if priority_col:
            cell = worksheet.cell(row=row_idx, column=priority_col)
            try:
                score = int(cell.value or 0)
                if score >= 100:
                    cell.fill = critical_fill
                elif score >= 65:
                    cell.fill = warning_fill
                else:
                    cell.fill = edge_fill
            except Exception:
                pass
        if points_col:
            cell = worksheet.cell(row=row_idx, column=points_col)
            try:
                points = int(cell.value or 0)
                if points >= 8:
                    cell.fill = critical_fill
                elif points >= 5:
                    cell.fill = warning_fill
                else:
                    cell.fill = good_fill
            except Exception:
                pass
        if aging_col:
            cell = worksheet.cell(row=row_idx, column=aging_col)
            value = str(cell.value or "").lower()
            if "immediate" in value:
                cell.fill = critical_fill
            elif "next sprint" in value:
                cell.fill = warning_fill
            elif "backlog" in value:
                cell.fill = edge_fill


def _legacy_sheet_header_index(worksheet: Worksheet) -> dict[str, int]:
    return {str(cell.value): idx for idx, cell in enumerate(worksheet[1], start=1) if cell.value}


def ensure_auto_filter(worksheet: Worksheet) -> None:
    if worksheet.title not in {"Main", "Dashboard"} and (
        worksheet.max_row < 10 or worksheet.max_column < 5
    ):
        worksheet.auto_filter.ref = None
        return

    header_row = 2 if worksheet.title == "Content Optimization Hub" else 1
    if worksheet.max_row >= header_row + 1 and worksheet.max_column >= 1:
        worksheet.auto_filter.ref = (
            f"A{header_row}:{get_column_letter(worksheet.max_column)}{worksheet.max_row}"
        )
    else:
        worksheet.auto_filter.ref = None


def _clear_orphaned_selection(worksheet: Worksheet) -> None:
    try:
        worksheet.views.sheetView[0].selection = []
    except Exception:
        pass


def ensure_freeze_header(worksheet: Worksheet) -> None:
    if worksheet.title not in {"Main", "Dashboard"} and (
        worksheet.max_row < 10 or worksheet.max_column < 5
    ):
        worksheet.freeze_panes = None
        _clear_orphaned_selection(worksheet)
        return
    if worksheet.max_row > 1 and worksheet.max_column >= 1:
        worksheet.freeze_panes = "A2"
    else:
        worksheet.freeze_panes = None
        _clear_orphaned_selection(worksheet)


def apply_global_conditional_formatting(worksheet: Worksheet) -> None:
    if worksheet.max_row <= 1:
        return
    headers = _legacy_sheet_header_index(worksheet)
    last_row = worksheet.max_row
    status_col = headers.get("Status Code") or headers.get("Target Status (if crawled)")
    if status_col:
        col = get_column_letter(status_col)
        rng = f"{col}2:{col}{last_row}"
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(operator="equal", formula=["200"], fill=PatternFill("solid", fgColor="C6EFCE")),
        )
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(operator="between", formula=["300", "399"], fill=PatternFill("solid", fgColor="FFEB9C")),
        )
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(operator="greaterThanOrEqual", formula=["400"], fill=PatternFill("solid", fgColor="FFC7CE")),
        )

    for load_header in ("Load Time (s)", "Load Time", "TTFB (ms)"):
        load_col = headers.get(load_header)
        if load_col:
            col = get_column_letter(load_col)
            rng = f"{col}2:{col}{last_row}"
            worksheet.conditional_formatting.add(
                rng,
                ColorScaleRule(
                    start_type="min",
                    start_color="63BE7B",
                    mid_type="percentile",
                    mid_value=50,
                    mid_color="FFEB84",
                    end_type="max",
                    end_color="F8696B",
                ),
            )
            worksheet.conditional_formatting.add(
                rng,
                DataBarRule(
                    start_type="min",
                    end_type="max",
                    color="638EC6",
                    showValue=True,
                ),
            )
            break

    for wc_header in ("Word Count", "Word Count (Body)"):
        wc_col = headers.get(wc_header)
        if wc_col:
            col = get_column_letter(wc_col)
            rng = f"{col}2:{col}{last_row}"
            worksheet.conditional_formatting.add(
                rng,
                ColorScaleRule(
                    start_type="min",
                    start_color="F8696B",
                    mid_type="percentile",
                    mid_value=50,
                    mid_color="FFEB84",
                    end_type="max",
                    end_color="63BE7B",
                ),
            )
            worksheet.conditional_formatting.add(
                rng,
                DataBarRule(
                    start_type="min",
                    end_type="max",
                    color="63BE7B",
                    showValue=True,
                ),
            )
            break

    priority_col = headers.get("Priority Score")
    if priority_col:
        col = get_column_letter(priority_col)
        rng = f"{col}2:{col}{last_row}"
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="greaterThanOrEqual",
                formula=["85"],
                font=Font(color="9C0006", bold=True),
                fill=PatternFill("solid", fgColor="FFC7CE"),
            ),
        )
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(
                operator="between",
                formula=["65", "84"],
                font=Font(color="9C5700", bold=True),
                fill=PatternFill("solid", fgColor="FFEB9C"),
            ),
        )

    seo_score_col = headers.get("SEO Health Score")
    if seo_score_col:
        col = get_column_letter(seo_score_col)
        worksheet.conditional_formatting.add(
            f"{col}2:{col}{last_row}",
            ColorScaleRule(
                start_type="min",
                start_color="F8696B",
                mid_type="percentile",
                mid_value=50,
                mid_color="FFEB84",
                end_type="max",
                end_color="63BE7B",
            ),
        )

    aeo_score_col = headers.get("AEO Readiness Score")
    if aeo_score_col:
        col = get_column_letter(aeo_score_col)
        worksheet.conditional_formatting.add(
            f"{col}2:{col}{last_row}",
            ColorScaleRule(
                start_type="min",
                start_color="F8696B",
                mid_type="percentile",
                mid_value=50,
                mid_color="FFEB84",
                end_type="max",
                end_color="63BE7B",
            ),
        )

    for score_header in ("Desktop Score", "Mobile Score"):
        score_col = headers.get(score_header)
        if score_col:
            col = get_column_letter(score_col)
            rng = f"{col}2:{col}{last_row}"
            worksheet.conditional_formatting.add(
                rng,
                CellIsRule(operator="between", formula=["90", "100"], fill=PatternFill("solid", fgColor="C6EFCE")),
            )
            worksheet.conditional_formatting.add(
                rng,
                CellIsRule(operator="between", formula=["50", "89"], fill=PatternFill("solid", fgColor="FFEB9C")),
            )
            worksheet.conditional_formatting.add(
                rng,
                CellIsRule(operator="between", formula=["0", "49"], fill=PatternFill("solid", fgColor="FFC7CE")),
            )

    lcp_col = headers.get("Mobile LCP")
    if lcp_col:
        col = get_column_letter(lcp_col)
        rng = f"{col}2:{col}{last_row}"
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(operator="lessThan", formula=["2.5"], fill=PatternFill("solid", fgColor="C6EFCE")),
        )
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(operator="greaterThan", formula=["4.0"], fill=PatternFill("solid", fgColor="FFC7CE")),
        )

    answer_para_col = headers.get("Paragraphs 40-60 Words Count")
    if answer_para_col:
        col = get_column_letter(answer_para_col)
        rng = f"{col}2:{col}{last_row}"
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(operator="equal", formula=["0"], fill=PatternFill("solid", fgColor="FFC7CE")),
        )
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(operator="between", formula=["1", "2"], fill=PatternFill("solid", fgColor="FFEB9C")),
        )
        worksheet.conditional_formatting.add(
            rng,
            CellIsRule(operator="greaterThanOrEqual", formula=["3"], fill=PatternFill("solid", fgColor="C6EFCE")),
        )

    action_col = headers.get("Action Needed")
    if action_col:
        col = get_column_letter(action_col)
        rng = f"{col}2:{col}{last_row}"
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(formula=[f'LOWER({col}2)="yes"'], stopIfTrue=True, fill=PatternFill("solid", fgColor="FFC7CE")),
        )
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(formula=[f'LOWER({col}2)="no"'], stopIfTrue=True, fill=PatternFill("solid", fgColor="C6EFCE")),
        )

    severity_badge_col = headers.get("Severity Badge")
    if severity_badge_col:
        col = get_column_letter(severity_badge_col)
        rng = f"{col}2:{col}{last_row}"
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(formula=[f'LOWER({col}2)="critical"'], stopIfTrue=True, fill=PatternFill("solid", fgColor="FFC7CE")),
        )
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(formula=[f'LOWER({col}2)="warning"'], stopIfTrue=True, fill=PatternFill("solid", fgColor="FFCC99")),
        )
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(formula=[f'OR(LOWER({col}2)="pass",LOWER({col}2)="observation")'], stopIfTrue=True, fill=PatternFill("solid", fgColor="C6EFCE")),
        )

    status_text_col = headers.get("Status")
    if status_text_col:
        col = get_column_letter(status_text_col)
        rng = f"{col}2:{col}{last_row}"
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(formula=[f'LOWER({col}2)="done"'], stopIfTrue=True, fill=PatternFill("solid", fgColor="D9EAD3")),
        )
        worksheet.conditional_formatting.add(
            rng,
            FormulaRule(
                formula=[f'OR(LOWER({col}2)="to do",LOWER({col}2)="in progress",LOWER({col}2)="in review")'],
                stopIfTrue=True,
                fill=PatternFill("solid", fgColor="FFF2CC"),
            ),
        )


# ---------------------------------------------------------------------------
# Tab / hub row builders (formerly tabs.py)
# ---------------------------------------------------------------------------

_ILLEGAL_XLSX_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_INVALID_SHEET_CHARS_RE = re.compile(r"[:\\/*?\[\]]")


def _safe_sheet_name(name: str) -> str:
    cleaned = _INVALID_SHEET_CHARS_RE.sub("_", str(name or "Sheet"))
    cleaned = cleaned[:31]
    return cleaned or "Sheet"


def _sanitize_excel_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str):
        return _ILLEGAL_XLSX_CHARS_RE.sub("", value)
    return value


def load_cached_rows(
    cache: AuditCache,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    main_rows: list[dict[str, Any]] = []
    extra_rows: list[dict[str, Any]] = []
    for result in cache.iter_results():
        main_rows.append(result["main"])
        extra_rows.append(result["extra"])
    return main_rows, extra_rows


def build_core_dataframes(
    cache: AuditCache,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
    main_rows, extra_rows = load_cached_rows(cache)
    return pd.DataFrame(main_rows), pd.DataFrame(extra_rows), main_rows, extra_rows


def write_dict_rows_sheet(
    writer: Any, sheet_name: str, columns: list[str], rows: list[dict[str, Any]]
) -> None:
    ws = writer.book.create_sheet(title=_safe_sheet_name(sheet_name))
    writer.sheets[sheet_name] = ws
    ws.append(columns)
    for row in rows:
        ws.append([_sanitize_excel_value(row.get(col)) for col in columns])


def _sanitize_excel_url(url_value: Any) -> str:
    raw = str(url_value or "").strip()
    if not raw:
        return ""
    raw = "".join(ch for ch in raw if ord(ch) >= 32).replace('"', "").replace("'", "")
    if not raw.startswith(("http://", "https://")):
        return raw
    try:
        parts = urlsplit(raw)
        cleaned_path = quote(unquote(parts.path), safe="/:@-._~!$&()*+,;=")
        cleaned_query = quote(unquote(parts.query), safe="=&:@-._~!$()*+,;/?")
        cleaned_fragment = quote(unquote(parts.fragment), safe=":@-._~!$&()*+,;=/?")
        return urlunsplit(
            (parts.scheme, parts.netloc, cleaned_path, cleaned_query, cleaned_fragment)
        )
    except Exception:
        return raw


def _normalize_url_for_match(url_value: Any) -> str:
    return normalize_url_key(_sanitize_excel_url(url_value))


def _fallback_keyword(url: str, h1_text: str) -> str:
    slug_parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
    if slug_parts:
        slug = slug_parts[-1].replace("-", " ").replace("_", " ").strip()
        slug = re.sub(r"\s+", " ", slug)
        if slug:
            return slug.title()
    return ""


def write_cached_sheet_chunked(
    writer: Any,
    cache: AuditCache,
    sheet_name: str,
    columns: list[str],
    payload_key: str,
    chunk_size: int = 500,
) -> None:
    ws = writer.book.create_sheet(title=_safe_sheet_name(sheet_name))
    writer.sheets[sheet_name] = ws
    ws.append(columns)
    for chunk in cache.iter_results_chunked(chunk_size):
        for result in chunk:
            payload = result.get(payload_key, {})
            ws.append([_sanitize_excel_value(payload.get(col)) for col in columns])


def build_fixplan_rows(
    summary_rules: list[tuple[str, str, Any]],
    extra_rows: list[dict[str, Any]],
    aeo_issue_names: set[str],
    root_cause_resolver: Any,
    default_effort_by_severity: dict[str, str],
    default_owner_by_severity: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    status_by_severity = {
        "Critical": "To Do",
        "Warning": "To Do",
        "Observation": "In Review",
    }
    for severity, issue_name, _ in summary_rules:
        affected = [
            r
            for r in extra_rows
            if issue_name in str(r.get("Matched Issues") or "").split(" | ")
        ]
        root_cause, recommended_fix = root_cause_resolver(issue_name)
        effort = default_effort_by_severity.get(severity, "S")
        workflow = workflow_metrics_for_issue(severity, effort)
        reference_tab = (
            "Indexability"
            if ("Canonical" in issue_name or "Noindex" in issue_name)
            else (
                "Links"
                if ("Links" in issue_name or "Anchor" in issue_name)
                else (
                    "AEO"
                    if (
                        "AEO" in issue_name
                        or "Question" in issue_name
                        or "FAQ" in issue_name
                        or "Answer" in issue_name
                    )
                    else "Technical"
                )
            )
        )
        affected_urls = [str(r.get("URL") or "") for r in affected if r.get("URL")]
        systemic_issue_tokens = (
            "CWV",
            "Schema",
            "Robots",
            "Compression",
            "Cache-Control",
            "ETag",
            "Canonical",
            "Redirect",
        )
        resolution_type = (
            "Global Template"
            if any(
                token.lower() in issue_name.lower() for token in systemic_issue_tokens
            )
            or len(affected_urls) > 10
            else "Manual Content"
        )
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
                "Affected URLs": (
                    f"SEE DETAILS IN {reference_tab}"
                    if len(affected_urls) > 10
                    else "\n".join(affected_urls[:50])
                ),
                "Detail Reference Tab": reference_tab,
                "Resolution Type": resolution_type,
                "Effort": effort,
                "Action Needed": "Yes" if severity in {"Critical", "Warning"} else "No",
                "Sprint": "",
                "Status": status_by_severity.get(severity, "To Do"),
                "Verified By": "",
                "Date Resolved": "",
                "Revenue Risk": (
                    "High Risk"
                    if severity == "Critical" and workflow["Priority Score"] >= 100
                    else "Medium Risk" if severity == "Warning" else "Monitor"
                ),
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
    writer: Any,
    cache: AuditCache,
    sheet_name: str = "SnippetCandidates",
    chunk_size: int = 500,
) -> None:
    columns = [
        "URL",
        "Heading (Question)",
        "Snippet (Answer)",
        "Word Count",
        "Snippet Preview Mockup",
    ]
    ws = writer.book.create_sheet(title=_safe_sheet_name(sheet_name))
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
                        f"{snippet.get('heading') or ''}\n{snippet.get('snippet') or ''}".strip(),
                    ]
                )
                has_rows = True
    if not has_rows:
        ws.append(["", "", "", 0, ""])


def build_content_optimization_hub_rows(
    main_rows: list[dict[str, Any]],
    extra_rows: list[dict[str, Any]],
    fixplan_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    main_by_url = {
        _normalize_url_for_match(r.get("URL")): r for r in main_rows if r.get("URL")
    }
    extra_by_url = {
        _normalize_url_for_match(r.get("URL")): r for r in extra_rows if r.get("URL")
    }
    manual_content_urls = {
        _normalize_url_for_match(r.get("URL"))
        for r in fixplan_rows
        if str(r.get("Resolution Type") or "").strip().lower() == "manual content"
        and _normalize_url_for_match(r.get("URL"))
    }
    content_issue_tokens = (
        "title",
        "meta",
        "h1",
        "content",
        "question",
        "answer",
        "faq",
        "alt",
        "regional authority",
    )
    for e in extra_rows:
        url = _normalize_url_for_match(e.get("URL"))
        issues = str(e.get("Matched Issues") or "").lower()
        if url and any(tok in issues for tok in content_issue_tokens):
            manual_content_urls.add(url)

    if not manual_content_urls:
        scored_urls: list[tuple[float, str]] = []
        for e in extra_rows:
            raw_url = _normalize_url_for_match(e.get("URL"))
            if not raw_url:
                continue
            try:
                score = float(e.get("SEO Health Score") or 0.0)
            except Exception:
                score = 0.0
            scored_urls.append((score, raw_url))
        scored_urls.sort(key=lambda item: item[0])
        for _score, url in scored_urls[:15]:
            manual_content_urls.add(url)

    rows: list[dict[str, Any]] = []
    cluster_counts: dict[str, int] = {}
    draft_rows: list[dict[str, Any]] = []
    for url in sorted(manual_content_urls):
        m = main_by_url.get(url, {})
        e = extra_by_url.get(url, {})
        score = float(e.get("SEO Health Score") or 0)
        priority = "High" if score < 60 else "Med" if score < 80 else "Low"
        post_id = e.get("WordPress Post ID")
        try:
            post_id = int(post_id) if post_id is not None else None
        except Exception:
            post_id = None
        elementor_link = None
        if post_id:
            parsed = urlparse(url)
            if parsed.scheme and parsed.netloc:
                elementor_link = f"{parsed.scheme}://{parsed.netloc}/wp-admin/post.php?post={post_id}&action=elementor"
        target_keywords = str(
            e.get("Meta Keywords") or m.get("Meta Keywords") or ""
        ).strip()
        if not target_keywords:
            target_keywords = _fallback_keyword(
                url, str(e.get("Current H-Tag Structure") or m.get("H1 Content") or "")
            )
        raw_title = str(m.get("Title") or "").strip().lower()
        title_pattern = (
            re.sub(r"\d+", "{n}", raw_title)[:24] if raw_title else "untitled"
        )
        seg = [s for s in urlparse(url).path.strip("/").split("/") if s]
        cluster_id = f"{(seg[0] if seg else 'home')}-{title_pattern}".replace(" ", "-")
        cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1
        draft_rows.append(
            {
                "Action Required": "Needs Copy",
                "Status": "To Do",
                "Assigned Owner": "Unassigned",
                "URL": url,
                "Current SEO Score": score,
                "Projected SEO Score": "",
                "Elementor Builder Link": elementor_link,
                "Current Title": str(m.get("Title") or "").strip() or "MISSING TITLE",
                "Proposed Title (50-60 Chars)": "",
                "Title Count": "",
                "Current Meta Desc": str(m.get("Meta Description") or "").strip()
                or "MISSING DESCRIPTION",
                "Proposed Meta Desc (120-160 Chars)": "",
                "Desc Count": "",
                "Current H-Tag Structure": str(
                    e.get("Current H-Tag Structure") or m.get("H1 Content") or ""
                ).strip(),
                "Current OG-Image URL": _sanitize_excel_url(e.get("OG Image")),
                "OG Image Preview": "",
                "Current Page Copy Snippet": str(
                    e.get("Current Page Copy Snippet") or ""
                ).strip(),
                "Social Share Note": "",
                "Proposed H-Tag Fixes": "",
                "AEO Answer Block Draft": "",
                "FAQ/QA Draft": "",
                "Content Cluster ID": cluster_id,
                "Priority": priority,
                "Target Keywords": target_keywords,
            }
        )
    for row in draft_rows:
        row["Assigned Owner"] = "Unassigned"
        row["Batch Ready"] = (
            "Yes"
            if cluster_counts.get(str(row.get("Content Cluster ID") or ""), 0) >= 5
            else "No"
        )
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Strict export guardrails (Action Required, TOC, freeze)
# ---------------------------------------------------------------------------

_BANNED_TOC_FALLBACK = "Detailed URL diagnostic data"
_ACTION_REQUIRED_FILL = PatternFill(
    start_color="FF0000",
    end_color="FF0000",
    fill_type="solid",
)
_ACTION_REQUIRED_FONT = Font(bold=True, color="FFFFFF")


def _action_header_map(ws: Worksheet, header_row: int = 1) -> dict[str, int]:
    out: dict[str, int] = {}
    for cell in ws[header_row]:
        val = cell.value
        if val is None:
            continue
        key = str(val).strip()
        if key:
            out[key] = cell.column
    return out


def _describe_sheet_from_headers(ws: Worksheet, *, max_labels: int = 10, max_chars: int = 220) -> str:
    labels: list[str] = []
    for cell in ws[1]:
        v = cell.value
        if v is None:
            continue
        s = str(v).strip()
        if s:
            labels.append(s)
        if len(labels) >= max_labels:
            break
    if not labels:
        return "Row-level metrics for this tab (no header row detected)."
    body = ", ".join(labels)
    text = f"Primary columns: {body}"
    if len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text


def apply_action_required_guardrails(ws: Worksheet, *, header_row: int = 1) -> None:
    """
    For column **Action Required**: any non-empty data cell becomes literal
    ``Needs Copy`` with bold white text on solid ``#FF0000`` fill.
    """
    headers = _action_header_map(ws, header_row)
    col = headers.get("Action Required")
    if not col:
        return
    for r in range(header_row + 1, ws.max_row + 1):
        cell = ws.cell(row=r, column=col)
        raw = cell.value
        if raw is None:
            continue
        if isinstance(raw, str) and not raw.strip():
            continue
        cell.value = "Needs Copy"
        cell.font = _ACTION_REQUIRED_FONT
        cell.fill = _ACTION_REQUIRED_FILL


def refresh_toc_descriptions_dynamic(wb: Workbook) -> None:
    """Rewrite TOC column C from each target sheet's header row (no generic fallback)."""
    if "Table of Contents" not in wb.sheetnames:
        return
    toc = wb["Table of Contents"]
    row = 3
    while row <= toc.max_row:
        name_cell = toc.cell(row=row, column=1)
        desc_cell = toc.cell(row=row, column=3)
        sheet_name = name_cell.value
        if not sheet_name:
            row += 1
            continue
        name = str(sheet_name).strip()
        if name not in wb.sheetnames:
            row += 1
            continue
        target = wb[name]
        desc_cell.value = _describe_sheet_from_headers(target)
        cur = str(desc_cell.value or "")
        if _BANNED_TOC_FALLBACK.lower() in cur.lower():
            desc_cell.value = _describe_sheet_from_headers(target)
        row += 1


def apply_freeze_c2_data_sheets(wb: Workbook, *, skip_names: frozenset[str] | None = None) -> None:
    """``freeze_panes = 'C2'`` on every sheet except skips (default: TOC only)."""
    skip = skip_names or frozenset({"Table of Contents"})
    for name in wb.sheetnames:
        if name in skip:
            continue
        wb[name].freeze_panes = "C2"


def apply_workbook_export_guardrails(wb: Workbook) -> None:
    """Apply Action Required styling, dynamic TOC blurbs, then C2 freezes."""
    for name in wb.sheetnames:
        if name == "Table of Contents":
            continue
        apply_action_required_guardrails(wb[name])
    refresh_toc_descriptions_dynamic(wb)
    apply_freeze_c2_data_sheets(wb)


# ---------------------------------------------------------------------------
# Facades into sheets implementation (avoid circular import at module load)
# ---------------------------------------------------------------------------


def adjust_sheet_format(writer: Any, sheet_name: str) -> Any:
    from hype_frog.reporter.sheets.tables_impl import adjust_sheet_format as _impl

    return _impl(writer, sheet_name)


def apply_tab_hyperlinks(writer: Any) -> Any:
    from hype_frog.reporter.sheets.tables_impl import apply_tab_hyperlinks as _impl

    return _impl(writer)


__all__ = [
    "adjust_sheet_format",
    "apply_tab_hyperlinks",
    "apply_fixplan_workflow_formatting",
    "ensure_auto_filter",
    "ensure_freeze_header",
    "apply_global_conditional_formatting",
    "load_cached_rows",
    "build_core_dataframes",
    "write_dict_rows_sheet",
    "write_cached_sheet_chunked",
    "build_fixplan_rows",
    "write_snippet_candidates_chunked",
    "build_content_optimization_hub_rows",
    "apply_action_required_guardrails",
    "apply_freeze_c2_data_sheets",
    "apply_workbook_export_guardrails",
    "refresh_toc_descriptions_dynamic",
]
