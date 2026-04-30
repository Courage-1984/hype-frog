from __future__ import annotations

from typing import Any
from urllib.parse import quote, unquote, urlparse, urlsplit, urlunsplit
import re

import pandas as pd

from checkpoint.cache import AuditCache
from rules import owner_for_issue, workflow_metrics_for_issue

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
    ws = writer.book.create_sheet(title=_safe_sheet_name(sheet_name))
    writer.sheets[sheet_name] = ws
    ws.append(columns)
    for row in rows:
        ws.append([_sanitize_excel_value(row.get(col)) for col in columns])


def _sanitize_excel_url(url_value: Any) -> str:
    raw = str(url_value or "").strip()
    if not raw:
        return ""
    # Remove control characters and problematic quoting that can break formulas.
    raw = "".join(ch for ch in raw if ord(ch) >= 32).replace('"', "").replace("'", "")
    if not raw.startswith(("http://", "https://")):
        return raw
    try:
        parts = urlsplit(raw)
        cleaned_path = quote(unquote(parts.path), safe="/:@-._~!$&()*+,;=")
        cleaned_query = quote(unquote(parts.query), safe="=&:@-._~!$()*+,;/?")
        cleaned_fragment = quote(unquote(parts.fragment), safe=":@-._~!$&()*+,;=/?")
        return urlunsplit((parts.scheme, parts.netloc, cleaned_path, cleaned_query, cleaned_fragment))
    except Exception:
        return raw


def _fallback_keyword(url: str, h1_text: str) -> str:
    slug_parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
    if slug_parts:
        slug = slug_parts[-1].replace("-", " ").replace("_", " ").strip()
        slug = re.sub(r"\s+", " ", slug)
        if slug:
            return f"[Auto]: {slug}"
    h1_clean = re.sub(r"[^A-Za-z0-9\s]", " ", str(h1_text or "")).strip()
    h1_clean = re.sub(r"\s+", " ", h1_clean)
    if h1_clean:
        return f"[Auto]: {h1_clean}"
    return ""


def write_cached_sheet_chunked(
    writer,
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
    root_cause_resolver,
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
            r for r in extra_rows if issue_name in str(r.get("Matched Issues") or "").split(" | ")
        ]
        root_cause, recommended_fix = root_cause_resolver(issue_name)
        effort = default_effort_by_severity.get(severity, "S")
        workflow = workflow_metrics_for_issue(severity, effort)
        reference_tab = (
            "Indexability"
            if ("Canonical" in issue_name or "Noindex" in issue_name)
            else "Links"
            if ("Links" in issue_name or "Anchor" in issue_name)
            else "AEO"
            if ("AEO" in issue_name or "Question" in issue_name or "FAQ" in issue_name or "Answer" in issue_name)
            else "Technical"
        )
        affected_urls = [str(r.get("URL") or "") for r in affected if r.get("URL")]
        systemic_issue_tokens = ("CWV", "Schema", "Robots", "Compression", "Cache-Control", "ETag", "Canonical", "Redirect")
        resolution_type = "Global Template" if any(token.lower() in issue_name.lower() for token in systemic_issue_tokens) or len(affected_urls) > 10 else "Manual Content"
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
                "Revenue Risk": "High Risk" if severity == "Critical" and workflow["Priority Score"] >= 100 else "Medium Risk" if severity == "Warning" else "Monitor",
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
    columns = ["URL", "Heading (Question)", "Snippet (Answer)", "Word Count", "Snippet Preview Mockup"]
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
    main_by_url = {str(r.get("URL") or ""): r for r in main_rows if r.get("URL")}
    extra_by_url = {str(r.get("URL") or ""): r for r in extra_rows if r.get("URL")}
    manual_content_urls = {
        str(r.get("URL") or "").strip()
        for r in fixplan_rows
        if str(r.get("Resolution Type") or "").strip().lower() == "manual content" and str(r.get("URL") or "").strip()
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
        url = str(e.get("URL") or "").strip()
        issues = str(e.get("Matched Issues") or "").lower()
        if url and any(tok in issues for tok in content_issue_tokens):
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
        target_keywords = str(e.get("Meta Keywords") or m.get("Meta Keywords") or "").strip()
        if not target_keywords:
            target_keywords = _fallback_keyword(url, str(e.get("Current H-Tag Structure") or m.get("H1 Content") or ""))
        raw_title = str(m.get("Title") or "").strip().lower()
        title_pattern = re.sub(r"\d+", "{n}", raw_title)[:24] if raw_title else "untitled"
        seg = [s for s in urlparse(url).path.strip("/").split("/") if s]
        cluster_id = f"{(seg[0] if seg else 'home')}-{title_pattern}".replace(" ", "-")
        cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1
        draft_rows.append(
            {
                "Action Required": "Needs Copy",
                "Status": "To Do",
                "Assigned Owner": "Unassigned",
                "URL": url,
                "Elementor Builder Link": elementor_link,
                "Current Title": str(m.get("Title") or "").strip() or "MISSING TITLE",
                "Proposed Title (50-60 Chars)": "",
                "Title Count": "",
                "Current Meta Desc": str(m.get("Meta Description") or "").strip() or "MISSING DESCRIPTION",
                "Proposed Meta Desc (120-160 Chars)": "",
                "Desc Count": "",
                "Current H-Tag Structure": str(e.get("Current H-Tag Structure") or m.get("H1 Content") or "").strip(),
                "Current OG-Image URL": _sanitize_excel_url(e.get("OG Image")),
                "OG Image Preview": "",
                "Current Page Copy Snippet": str(e.get("Current Page Copy Snippet") or "").strip(),
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
        row["Batch Ready"] = "Yes" if cluster_counts.get(str(row.get("Content Cluster ID") or ""), 0) >= 5 else "No"
        rows.append(row)
    return rows
