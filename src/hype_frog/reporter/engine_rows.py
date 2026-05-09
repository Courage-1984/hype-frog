from __future__ import annotations

import math
import re
from typing import Any
from urllib.parse import urlparse

from openpyxl.utils import get_column_letter

from hype_frog.checkpoint.cache import AuditCache
from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.reporter.engine_io import (
    _normalize_url_for_match,
    _safe_sheet_name,
    _sanitize_excel_url,
)
from hype_frog.rules import owner_for_issue, workflow_metrics_for_issue
from hype_frog.reporter.sheets.layout import main_sheet_url_column_letter
from hype_frog.reporter.summary_builder import reference_tab_for_merged_workbook


def _hub_score_value(raw: object) -> float:
    """Normalize numeric SEO / Technical / Copy scores for Content Hub export."""
    if raw is None or raw == "":
        return 0.0
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(x) or math.isinf(x):
        return 0.0
    return round(x, 2)


def _heading_levels_from_h_tag_structure(structure: object) -> dict[int, list[str]]:
    """Parse ``Current H-Tag Structure`` lines like ``H2: text`` into level → texts."""
    out: dict[int, list[str]] = {1: [], 2: [], 3: [], 4: [], 5: [], 6: []}
    text = str(structure or "")
    for line in text.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        prefix, rest = line.split(":", 1)
        tag = prefix.strip().upper()
        if len(tag) == 2 and tag.startswith("H") and tag[1].isdigit():
            level = int(tag[1])
            heading_text = rest.strip()
            if 1 <= level <= 6 and heading_text:
                out[level].append(heading_text)
    return out


def _first_non_empty(mapping: dict[str, Any], *keys: str) -> str:
    """Return the first non-empty string value among candidate mapping keys."""
    for key in keys:
        val = mapping.get(key)
        text = str(val or "").strip()
        if text:
            return text
    return ""


def _join_pipe(values: list[str]) -> str:
    """Join heading values for display while preserving order and removing duplicates."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return " | ".join(out)


def _hyperlink_url_formula(display_url: str) -> str:
    """Excel HYPERLINK so the URL column is clickable (sanitized for formula quotes)."""
    s = str(display_url or "").strip()
    if not s:
        return ""
    safe = s.replace('"', '""')
    return f'=HYPERLINK("{safe}","{safe}")'


def _fallback_keyword(url: str, h1_text: str) -> str:
    slug_parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
    if slug_parts:
        slug = slug_parts[-1].replace("-", " ").replace("_", " ").strip()
        slug = re.sub(r"\s+", " ", slug)
        if slug:
            return slug.title()
    return ""


def build_fixplan_rows(
    summary_rules: list[tuple[str, str, Any]],
    extra_rows: list[ExtraRowPayload],
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
            if issue_name in str(r.values.get("Matched Issues") or "").split(" | ")
        ]
        root_cause, recommended_fix = root_cause_resolver(issue_name)
        effort = default_effort_by_severity.get(severity, "S")
        workflow = workflow_metrics_for_issue(severity, effort)
        legacy_reference = (
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
        reference_tab = reference_tab_for_merged_workbook(legacy_reference)
        affected_urls = [
            str(r.values.get("URL") or "") for r in affected if r.values.get("URL")
        ]
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
                "URL": affected[0].values.get("URL") if affected else "",
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


CONTENT_HUB_EXPORT_COLUMNS: tuple[str, ...] = (
    "Action Required",
    "On-Page Optimization Score",
    "SEO Score",
    "Technical Health",
    "Copy Score",
    "Status",
    "Assigned Owner",
    "URL",
    "Current Title",
    "Title Health",
    "Current Meta Desc",
    "Meta Health",
    "H1",
    "H1 Health",
    "H2",
    "H2 Health",
    "H3",
    "H3 Health",
    "H4",
    "H4 Health",
    "H5",
    "H5 Health",
    "H6",
    "H6 Health",
    "Elementor Builder Link",
    "URL Slug Normalization",
    "Current OG-Image URL",
    "OG Image Preview",
    "Open in Main",
)


def content_hub_column_letter(header: str) -> str:
    """Excel column letter for a Content Optimisation Hub header (row 2 layout)."""
    pos = CONTENT_HUB_EXPORT_COLUMNS.index(header) + 1
    return get_column_letter(pos)


def _content_hub_on_page_score_from_health_formula(row: int) -> str:
    """Weighted 0–100 score derived from live Title/Meta/H1–H6 *Health* formula columns."""
    th = content_hub_column_letter("Title Health")
    mh = content_hub_column_letter("Meta Health")
    h1 = content_hub_column_letter("H1 Health")
    h2 = content_hub_column_letter("H2 Health")
    h3 = content_hub_column_letter("H3 Health")
    h4 = content_hub_column_letter("H4 Health")
    h5 = content_hub_column_letter("H5 Health")
    h6 = content_hub_column_letter("H6 Health")
    r = row
    t_pts = (
        f'IF({th}{r}="",0,IF(LEFT({th}{r},7)="MISSING",0,'
        f'IF(ISNUMBER(SEARCH("OK",{th}{r})),100,IF(ISNUMBER(SEARCH("SHORT",{th}{r})),65,'
        f'IF(ISNUMBER(SEARCH("LONG",{th}{r})),50,70)))))'
    )
    m_pts = (
        f'IF({mh}{r}="",0,IF(LEFT({mh}{r},7)="MISSING",0,'
        f'IF(ISNUMBER(SEARCH("OK",{mh}{r})),100,IF(ISNUMBER(SEARCH("SHORT",{mh}{r})),65,'
        f'IF(ISNUMBER(SEARCH("LONG",{mh}{r})),50,70)))))'
    )
    h1_pts = (
        f'IF({h1}{r}="",0,IF(LEFT({h1}{r},2)="OK",100,0))'
    )

    def _h_pts(col: str) -> str:
        return f'IF({col}{r}="",0,IF(LEFT({col}{r},2)="OK",100,0))'

    h2p, h3p, h4p, h5p, h6p = (
        _h_pts(h2),
        _h_pts(h3),
        _h_pts(h4),
        _h_pts(h5),
        _h_pts(h6),
    )
    return (
        f"=MIN(100,ROUND(0.30*({t_pts})+0.25*({m_pts})+0.20*({h1_pts})+0.08*({h2p})+0.06*({h3p})"
        f"+0.05*({h4p})+0.03*({h5p})+0.03*({h6p}),0))"
    )


def _content_hub_open_in_main_formula(url_col_letter: str, row: int) -> str:
    """Cross-sheet jump to Main (URL column) with Technical Diagnostics fallback."""
    ml = main_sheet_url_column_letter()
    td = "Technical Diagnostics"
    u = url_col_letter
    r = row
    return (
        f'=IFERROR(HYPERLINK("#\'Main\'!{ml}"&MATCH(TRIM({u}{r}),'
        f'\'Main\'!{ml}:{ml},0),"Open in Main"),'
        f'IFERROR(HYPERLINK("#\'{td}\'!A"&MATCH(TRIM({u}{r}),'
        f'\'{td}\'!A:A,0),"Open in Technical"),"Not Found"))'
    )


def build_content_optimisation_hub_rows(
    main_rows: list[MainRowPayload],
    extra_rows: list[ExtraRowPayload],
    fixplan_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    main_by_url = {
        _normalize_url_for_match(r.values.get("URL")): r
        for r in main_rows
        if r.values.get("URL")
    }
    extra_by_url = {
        _normalize_url_for_match(r.values.get("URL")): r
        for r in extra_rows
        if r.values.get("URL")
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
        row_values = e.values
        url = _normalize_url_for_match(row_values.get("URL"))
        issues = str(row_values.get("Matched Issues") or "").lower()
        if url and any(tok in issues for tok in content_issue_tokens):
            manual_content_urls.add(url)

    if not manual_content_urls:
        scored_urls: list[tuple[float, str]] = []
        for e in extra_rows:
            row_values = e.values
            raw_url = _normalize_url_for_match(row_values.get("URL"))
            if not raw_url:
                continue
            try:
                score = float(row_values.get("SEO Health Score") or 0.0)
            except Exception:
                score = 0.0
            scored_urls.append((score, raw_url))
        scored_urls.sort(key=lambda item: item[0])
        for _score, url in scored_urls[:15]:
            manual_content_urls.add(url)

    g_l = content_hub_column_letter("Current Title")
    i_l = content_hub_column_letter("Current Meta Desc")
    k_l = content_hub_column_letter("H1")
    m_l = content_hub_column_letter("H2")
    o_l = content_hub_column_letter("H3")
    q_l = content_hub_column_letter("H4")
    s_l = content_hub_column_letter("H5")
    u_l = content_hub_column_letter("H6")
    w_l = content_hub_column_letter("On-Page Optimization Score")
    f_l = content_hub_column_letter("URL")

    rows: list[dict[str, Any]] = []
    for excel_row, url in enumerate(sorted(manual_content_urls), start=3):
        main_payload = main_by_url.get(url)
        extra_payload = extra_by_url.get(url)
        m = main_payload.values if main_payload else {}
        e = extra_payload.values if extra_payload else {}
        raw_url = ""
        if main_payload:
            raw_url = str(main_payload.values.get("URL") or "").strip()
        if not raw_url and extra_payload:
            raw_url = str(extra_payload.values.get("URL") or "").strip()
        if not raw_url:
            raw_url = str(url)
        post_id = e.get("WordPress Post ID")
        try:
            post_id = int(post_id) if post_id is not None else None
        except Exception:
            post_id = None
        elementor_link = None
        if post_id:
            parsed = urlparse(raw_url)
            if parsed.scheme and parsed.netloc:
                elementor_link = (
                    f"{parsed.scheme}://{parsed.netloc}/wp-admin/post.php?post={post_id}&action=elementor"
                )
        elementor_cell = ""
        if elementor_link:
            safe_url = str(elementor_link).replace('"', '""')
            elementor_cell = f'=HYPERLINK("{safe_url}","Open in Elementor")'
        target_keywords = str(
            e.get("Meta Keywords") or m.get("Meta Keywords") or ""
        ).strip()
        if not target_keywords:
            target_keywords = _fallback_keyword(
                url, str(e.get("Current H-Tag Structure") or m.get("H1 Content") or "")
            )

        h_by_level = _heading_levels_from_h_tag_structure(e.get("Current H-Tag Structure"))

        def _h_values(n: int) -> list[str]:
            items: list[str] = []
            from_main = _first_non_empty(
                m,
                f"H{n} Content",
                f"h{n}_content",
                f"h{n} content",
                f"h{n}",
            )
            if from_main:
                items.append(from_main)
            from_extra = _first_non_empty(
                e,
                f"H{n} Content",
                f"h{n}_content",
                f"h{n} content",
                f"h{n}",
            )
            if from_extra:
                items.append(from_extra)
            items.extend(h_by_level.get(n, []))
            return items

        def _h_joined(n: int) -> str:
            return _join_pipe(_h_values(n))

        h1_values = _h_values(1)
        h2_values = _h_values(2)
        h3_values = _h_values(3)
        h4_values = _h_values(4)
        h5_values = _h_values(5)
        h6_values = _h_values(6)

        title_health = (
            f'=IF({g_l}{excel_row}="","MISSING",'
            f'IF(AND(LEN({g_l}{excel_row})>=50,LEN({g_l}{excel_row})<=60),"OK 50-60 chars",'
            f'IF(LEN({g_l}{excel_row})<50,"SHORT: "&LEN({g_l}{excel_row}),"LONG: "&LEN({g_l}{excel_row}))))'
        )
        meta_health = (
            f'=IF({i_l}{excel_row}="","MISSING",'
            f'IF(AND(LEN({i_l}{excel_row})>=120,LEN({i_l}{excel_row})<=160),"OK 120-160 chars",'
            f'IF(LEN({i_l}{excel_row})<120,"SHORT: "&LEN({i_l}{excel_row}),"LONG: "&LEN({i_l}{excel_row}))))'
        )
        # Live linter formulas: driven by visible H-tag cells so edits recalculate instantly.
        h1_health = (
            f'=IF(TRIM({k_l}{excel_row})="","FIX: MULTIPLE/MISSING",'
            f'IF((LEN({k_l}{excel_row})-LEN(SUBSTITUTE({k_l}{excel_row},"|",""))+1)=1,'
            f'"OK","FIX: MULTIPLE/MISSING"))'
        )
        h2_health = f'=IF(TRIM({m_l}{excel_row})="","MISSING","OK")'
        h3_health = f'=IF(TRIM({o_l}{excel_row})="","MISSING","OK")'
        h4_health = f'=IF(TRIM({q_l}{excel_row})="","MISSING","OK")'
        h5_health = f'=IF(TRIM({s_l}{excel_row})="","MISSING","OK")'
        h6_health = f'=IF(TRIM({u_l}{excel_row})="","MISSING","OK")'
        on_page_score = _content_hub_on_page_score_from_health_formula(excel_row)
        action_formula = f'=IF({w_l}{excel_row}>=85,"Complete","Needs Copy")'
        open_main_formula = _content_hub_open_in_main_formula(f_l, excel_row)

        rows.append(
            {
                "SEO Score": _hub_score_value(e.get("SEO Score")),
                "Technical Health": _hub_score_value(e.get("Technical Health")),
                "Copy Score": _hub_score_value(e.get("Copy Score")),
                "Action Required": action_formula,
                "Status": "To Do",
                "Assigned Owner": "Copy Writer",
                "URL": _hyperlink_url_formula(raw_url),
                "Current Title": str(m.get("Title") or "").strip() or "MISSING TITLE",
                "Title Health": title_health,
                "Current Meta Desc": str(m.get("Meta Description") or "").strip()
                or "MISSING DESCRIPTION",
                "Meta Health": meta_health,
                "H1": _h_joined(1),
                "H1 Health": h1_health,
                "H2": _h_joined(2),
                "H2 Health": h2_health,
                "H3": _h_joined(3),
                "H3 Health": h3_health,
                "H4": _h_joined(4),
                "H4 Health": h4_health,
                "H5": _h_joined(5),
                "H5 Health": h5_health,
                "H6": _h_joined(6),
                "H6 Health": h6_health,
                "On-Page Optimization Score": on_page_score,
                "Elementor Builder Link": elementor_cell,
                "URL Slug Normalization": target_keywords,
                "Current OG-Image URL": _sanitize_excel_url(e.get("OG Image")),
                "OG Image Preview": "",
                "Open in Main": open_main_formula,
            }
        )
    return rows


def build_content_optimization_hub_rows(
    main_rows: list[MainRowPayload],
    extra_rows: list[ExtraRowPayload],
    fixplan_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Backward-compatible alias (US spelling) for :func:`build_content_optimisation_hub_rows`."""
    return build_content_optimisation_hub_rows(main_rows, extra_rows, fixplan_rows)
