from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

from hype_frog.crawler.redirect_chain import RedirectHopRecord, build_redirect_map_row
from hype_frog.config import get_quick_wins_max_effort_hours, get_quick_wins_max_results
from hype_frog.analysis.delta_engine import IssueRecord, days_between
from hype_frog.core import get_logger
from hype_frog.rules.playbook_entries import PlaybookEntry

logger = get_logger(__name__)

TECHNICAL_DIAGNOSTICS_LIGHTHOUSE_COLUMNS: tuple[str, ...] = (
    "CrUX Level",
    "Lab LCP (Mobile) (s)",
    "Lab TBT (Mobile) (ms)",
    "Lab FCP (Mobile) (s)",
    "Lab CLS (Mobile)",
    "Lab TTFB (Mobile) (ms)",
    "Lighthouse Accessibility (Mobile)",
    "Lighthouse Best Practices (Mobile)",
    "Lighthouse SEO Score (Mobile)",
    "Lab LCP (Desktop) (s)",
    "Lab TBT (Desktop) (ms)",
    "Lighthouse Performance (Desktop)",
    "Page Size (KB)",
    "DOM Size (nodes)",
    "JS Execution (ms)",
    "Network Request Count",
    "Origin CrUX LCP (s)",
    "Origin CrUX INP (ms)",
)

TECHNICAL_DIAGNOSTICS_COLUMNS: tuple[str, ...] = (
    "URL",  # A
    "Diagnostic Category",  # B
    "Status Code",  # C
    "Severity Badge",  # D
    "SEO Health Score",  # E
    "Pass Flag",  # F
    "Critical Issues Count",
    "Warning Issues Count",
    "Extraction State",
    "Extraction Source",
    "Indexability Reason",
    "Canonical Type",
    "Redirect Chain Length",
    "Redirect Loop Flag",
    "Strict-Transport-Security",
    "Content-Security-Policy",
    "X-Content-Type-Options",
    "Desktop PSI Score",
    "Mobile PSI Score",
    "Mobile LCP (s)",
    "Mobile CLS",
    "Mobile TTFB (s)",
    *TECHNICAL_DIAGNOSTICS_LIGHTHOUSE_COLUMNS,
    "Final URL",
    "Canonical URL",
    "Meta Robots Raw",
    "X-Robots-Tag",
    "GSC Index Status",
    "GSC Last Crawl",
    "GSC Coverage Category",
    "Discovered On URL",
    "Discovery Rank",
    "Reachable from Homepage",
    "Source Legacy Tab",
    # Sprint 5 — structural / security / i18n diagnostics migrated from
    # the Content Optimisation Hub. Appended at the END so existing
    # column-position contracts (notably the
    # ``_link_main_technical_health_to_diagnostics`` VLOOKUP into
    # ``'Technical Diagnostics'!$A:$E,5,FALSE`` for ``SEO Health Score``)
    # are preserved. ``Anchor Text Diversity`` is on ``Content Hub Metrics``
    # (not mirrored here).
    "Crawl Depth",
    "Security: HSTS",
    "Security: CSP",
    "Hreflang Signals",
    "Hreflang Declared Languages",
    "Hreflang Alternate URLs",
    "Hreflang Reciprocal Status",
    "Hreflang Code Valid",
)

CONTENT_AI_READINESS_COLUMNS: tuple[str, ...] = (
    "URL",  # A
    "Content Category",  # B
    "Word Count",
    "Readability (Rough Flesch)",
    "Flesch-Kincaid Grade (Est.)",
    "Thin Content Flag",
    "H1 Count",
    "Missing H1 Flag",
    "Meta Description Missing",
    "AEO Readiness Score",
    "AEO Badge",
    "Schema Types Count",  # K
    "Schema Types Found",
    "Schema Parse Errors",
    "Question Heading Count",
    "Answer Blocks",
    "FAQ Section Count",
    "Image Count",
    "Images Missing Alt",
    "Image Alt Coverage (%)",
    "AEO Extractability Score",
    "Title Missing",
    "Media Mixed Content Detected",
    "Source Legacy Tab",
)

ISSUE_REGISTER_COLUMNS: tuple[str, ...] = (
    "URL",  # A
    "Section",  # B
    "Issue",  # C
    "Severity",  # D
    "Affected URL Count",  # E
    "Reference Area",  # F
    "Stable Issue ID",  # G
    "Owner",  # H
    "Sprint",  # I
    "Status",  # J
    "Affected URLs Sample",  # K
    "Source Legacy Tab",  # L
    "Source Row ID",  # M
    "Date First Detected",  # N
    "Days Open",  # O
    "Assigned To",  # P
    "Client Notes",  # Q
)

LINK_INTELLIGENCE_COLUMNS: tuple[str, ...] = (
    "URL",  # A
    "Record Type",  # B
    "Target URL",
    "Anchor Text",
    "Target Status (if crawled)",
    "Crawlable",
    "Internal Links Count",
    "Broken Internal Links Count",  # H
    "Unresolved Internal Links Count",
    "External Links Count",
    "Inlinks Count",
    "Orphan Candidate",
    "Click Depth",
    "Internal PageRank",
    "Generic Anchor Text Count",
    "Nofollow Internal Links Count",
    "Nofollow External Links Count",
    "Internal Link Statuses",
    "Actionable Fixes",
    "Source Legacy Tab",
    "Broken Links (computed)",
)

# Strict seven-column client export (no sparse ``Column_N`` headers); rows built in
# ``build_link_inventory_rows`` and written via ``write_dict_rows_sheet``.
LINK_INVENTORY_COLUMNS: tuple[str, ...] = (
    "Source URL",
    "Target URL",
    "Anchor Text",
    "Rel Attribute",
    "Link Type",
    "Status Code",
    "Generic Anchor",
)

TEMPLATE_DUPLICATION_RISKS_COLUMNS: tuple[str, ...] = (
    "URL",
    "Risk Category",
    "Subfolder / Template Group",
    "Issue",
    "Affected Ratio",
    "Affected URL Count",
    "Example URLs",
    "Exact Action",
    "Severity",
    "Source Legacy Tab",
)


def _to_int(value: object, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _aeo_extractability_numeric(value: object) -> float:
    """Map crawl labels or numerics to a 0–100 extractability scale for reporting."""
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        v = float(value)
        return max(0.0, min(100.0, v))
    s = str(value or "").strip().lower()
    if s == "high":
        return 85.0
    if s == "medium":
        return 55.0
    if s == "low":
        return 25.0
    try:
        return max(0.0, min(100.0, float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _joined(values: list[str]) -> str:
    unique = [item for item in dict.fromkeys(values) if item]
    return " | ".join(unique) if unique else ""


def _to_str(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _export_number(value: object) -> float | int | str:
    """Blank cell when a metric was not measured (avoid fake zeros in merged tabs)."""
    if value is None or str(value).strip() == "":
        return ""
    if isinstance(value, bool):
        return ""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return ""
    if numeric != numeric:
        return ""
    if numeric == int(numeric):
        return int(numeric)
    return numeric


def _technical_diagnostics_lighthouse_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    """Project PSI / Lighthouse / CrUX columns onto Technical Diagnostics rows."""
    out: dict[str, Any] = {}
    for key in TECHNICAL_DIAGNOSTICS_LIGHTHOUSE_COLUMNS:
        raw = row.get(key)
        if key == "CrUX Level":
            out[key] = _to_str(raw) if raw not in (None, "") else ""
        elif key in {"DOM Size (nodes)", "Network Request Count"}:
            out[key] = _export_number(raw)
        else:
            out[key] = _export_number(raw)
    return out


def _pair_main_extra_rows(
    main_rows: list[dict[str, Any]] | None,
    extra_rows: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Align Main and Extra dicts by URL for merged worksheet builders."""
    extra_by_url = {
        str(row.get("URL") or "").strip(): row for row in extra_rows if row.get("URL")
    }
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for main in main_rows or []:
        url = str(main.get("URL") or "").strip()
        if not url:
            continue
        pairs.append((main, extra_by_url.get(url, {})))
        seen.add(url)
    for extra in extra_rows:
        url = str(extra.get("URL") or "").strip()
        if url and url not in seen:
            pairs.append(({}, extra))
    if not pairs and extra_rows:
        for extra in extra_rows:
            pairs.append(({}, extra))
    return pairs


def _merged_export_row(
    main: Mapping[str, Any],
    extra: Mapping[str, Any],
) -> dict[str, Any]:
    """Combine Main + Extra with sensible fallbacks for merged diagnostic tabs."""
    m = dict(main or {})
    e = dict(extra or {})
    row: dict[str, Any] = {**m, **e}
    row["URL"] = str(e.get("URL") or m.get("URL") or "").strip()

    title = str(m.get("Title") or e.get("OG Title") or "").strip()
    meta = str(m.get("Meta Description") or e.get("OG Description") or "").strip()
    row["Title Missing"] = not bool(title)
    row["Meta Description Missing"] = not bool(meta)

    word_count = _to_int(e.get("Word Count"), 0)
    if word_count <= 0:
        word_count = _to_int(m.get("Word Count (Body)"), 0)
    row["Word Count"] = word_count

    h1_count = _to_int(e.get("H1 Count"), 0)
    if h1_count <= 0 and str(m.get("H1 Content") or e.get("Primary H1 Content") or "").strip():
        h1_count = 1
    row["H1 Count"] = h1_count
    row["Missing H1 Flag"] = h1_count <= 0

    for field in (
        "Desktop PSI Score",
        "Mobile PSI Score",
        "Mobile LCP (s)",
        "Mobile CLS",
        "Mobile TTFB (s)",
        "CWV LCP (s)",
        "CWV CLS",
        "CWV INP (ms)",
        "PSI Data Status",
        *TECHNICAL_DIAGNOSTICS_LIGHTHOUSE_COLUMNS,
        "SEO Health Score",
        "Severity Badge",
        "Status Code",
        "Final URL",
        "Discovery Rank",
        "Reachable from Homepage",
    ):
        if (e.get(field) in (None, "") and m.get(field) not in (None, "")):
            row[field] = m.get(field)

    return row


def build_technical_diagnostics_rows(
    extra_rows: list[dict[str, Any]],
    *,
    main_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build merged rows for the 'Technical Diagnostics' worksheet."""
    rows: list[dict[str, Any]] = []
    for _main, extra in _pair_main_extra_rows(main_rows, extra_rows):
        row = _merged_export_row(_main, extra)
        status_code = _to_int(row.get("Status Code"), 0)
        severity = str(row.get("Severity Badge") or "")
        categories: list[str] = ["Technical"]
        sources: list[str] = ["Technical"]

        if any(
            row.get(key) not in (None, "", False)
            for key in (
                "Indexability Reason",
                "Canonical Type",
                "Canonical URL",
                "Meta Robots Raw",
                "X-Robots-Tag",
            )
        ):
            categories.append("Indexability")
            sources.append("Indexability")
        if _to_int(row.get("Redirect Chain Length"), 0) > 0:
            categories.append("Redirect")
            sources.append("Redirects")
        if any(
            row.get(key) not in (None, "", False)
            for key in (
                "Strict-Transport-Security",
                "Content-Security-Policy",
                "X-Content-Type-Options",
                "Security: HSTS",
                "Security: CSP",
            )
        ):
            categories.append("Security")
            sources.append("Security")
        psi_status = str(row.get("PSI Data Status") or "").strip().lower()
        if psi_status not in {"", "not measured", "unavailable"} and any(
            row.get(key) not in (None, "", False)
            for key in (
                "Desktop PSI Score",
                "Mobile PSI Score",
                "Mobile LCP (s)",
                "CrUX Level",
                "Lab LCP (Mobile) (s)",
                "Lighthouse Performance (Mobile)",
            )
        ):
            categories.append("Performance")
            sources.append("PSI Performance")
        if any(
            row.get(key) not in (None, "", False, 0, 0.0)
            for key in (
                "GSC Inspection Verdict",
                "GSC Inspection Coverage State",
                "GSC Inspection Last Crawl",
                "GSC Clicks",
                "GSC Impressions",
                "GSC Coverage Note",
            )
        ):
            categories.append("Search Console")
            sources.append("Search Console")

        pass_flag = "Pass" if severity == "Pass" else "Non-Pass"

        rows.append(
            {
                "URL": row.get("URL"),
                "Diagnostic Category": _joined(categories),
                "Status Code": status_code,
                "Severity Badge": severity,
                "SEO Health Score": _export_number(row.get("SEO Health Score")),
                "Pass Flag": pass_flag,
                "Critical Issues Count": _to_int(row.get("Critical Issues Count"), 0),
                "Warning Issues Count": _to_int(row.get("Warning Issues Count"), 0),
                "Extraction State": row.get("Extraction State"),
                "Extraction Source": row.get("Extraction Source"),
                "Indexability Reason": row.get("Indexability Reason"),
                "Canonical Type": row.get("Canonical Type"),
                "Redirect Chain Length": _to_int(row.get("Redirect Chain Length"), 0),
                "Redirect Loop Flag": _to_bool(row.get("Redirect Loop Flag")),
                "Strict-Transport-Security": row.get("Strict-Transport-Security"),
                "Content-Security-Policy": row.get("Content-Security-Policy"),
                "X-Content-Type-Options": row.get("X-Content-Type-Options"),
                "Desktop PSI Score": _export_number(row.get("Desktop PSI Score")),
                "Mobile PSI Score": _export_number(row.get("Mobile PSI Score")),
                "Mobile LCP (s)": _export_number(row.get("Mobile LCP (s)")),
                "Mobile CLS": _export_number(row.get("Mobile CLS")),
                "Mobile TTFB (s)": _export_number(row.get("Mobile TTFB (s)")),
                **_technical_diagnostics_lighthouse_fields(row),
                "Final URL": row.get("Final URL"),
                "Canonical URL": row.get("Canonical URL"),
                "Meta Robots Raw": row.get("Meta Robots Raw"),
                "X-Robots-Tag": row.get("X-Robots-Tag"),
                "GSC Index Status": _to_str(
                    row.get("GSC Index Status") or row.get("GSC Inspection Verdict")
                ),
                "GSC Last Crawl": _to_str(
                    row.get("GSC Last Crawl Date") or row.get("GSC Inspection Last Crawl")
                ),
                "GSC Coverage Category": _to_str(
                    row.get("GSC Coverage Reason") or row.get("GSC Inspection Coverage State")
                ),
                "Discovered On URL": _to_str(row.get("Discovered On URL")),
                "Discovery Rank": row.get("Discovery Rank"),
                "Reachable from Homepage": _to_bool(row.get("Reachable from Homepage")),
                "Source Legacy Tab": _joined(sources),
                "Crawl Depth": _to_int(row.get("Crawl Depth"), 0),
                "Security: HSTS": _to_bool(row.get("Security: HSTS")),
                "Security: CSP": _to_bool(row.get("Security: CSP")),
                "Hreflang Signals": _to_str(row.get("Hreflang Signals")),
                "Hreflang Declared Languages": _to_str(row.get("Hreflang Declared Languages")),
                "Hreflang Alternate URLs": _to_str(row.get("Hreflang Alternate URLs")),
                "Hreflang Reciprocal Status": _to_str(row.get("Hreflang Reciprocal Status")),
                "Hreflang Code Valid": _to_bool(row.get("Hreflang Code Valid")),
            }
        )
    return rows


def build_content_ai_readiness_rows(
    extra_rows: list[dict[str, Any]],
    *,
    main_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build merged rows for the 'Content & AI Readiness' worksheet.

    ``AEO Readiness Score`` is produced upstream by
    ``hype_frog.pipeline.assemble.compute_aeo_readiness_score`` (weighted 0–100 model).
    """
    rows: list[dict[str, Any]] = []
    for main, extra in _pair_main_extra_rows(main_rows, extra_rows):
        row = _merged_export_row(main, extra)
        categories: list[str] = ["Content"]
        sources: list[str] = ["Content"]
        if any(
            row.get(key) not in (None, "", False, 0, 0.0)
            for key in (
                "AEO Readiness Score",
                "Question Heading Count",
                "FAQ Section Count",
                "AEO Extractability Score",
                "QAPage/FAQ Schema Present",
                "Speakable Schema Present",
            )
        ):
            categories.append("AEO")
            sources.append("AEO")
        if any(
            row.get(key) not in (None, "", False, 0)
            for key in ("Schema Types Count", "Schema Types Found", "Schema Parse Errors")
        ) or _to_bool(row.get("Has Valid JSON-LD")):
            categories.append("Schema")
            sources.append("Schema & Metadata")
        if any(
            row.get(key) not in (None, "", False, 0)
            for key in ("Image Count", "Images Missing Alt", "Image Alt Coverage (%)")
        ):
            categories.append("Media")
            sources.append("Media")

        readability = row.get("Readability (Rough Flesch)")
        alt_coverage = row.get("Image Alt Coverage (%)")
        rows.append(
            {
                "URL": row.get("URL"),
                "Content Category": _joined(categories),
                "Word Count": _to_int(row.get("Word Count"), 0),
                "Readability (Rough Flesch)": _export_number(readability),
                "Flesch-Kincaid Grade (Est.)": row.get("Flesch-Kincaid Grade (Est.)"),
                "Thin Content Flag": _to_bool(row.get("Thin Content Flag")),
                "H1 Count": _to_int(row.get("H1 Count"), 0),
                "Missing H1 Flag": _to_bool(row.get("Missing H1 Flag")),
                "Meta Description Missing": _to_bool(row.get("Meta Description Missing")),
                "AEO Readiness Score": _export_number(row.get("AEO Readiness Score")),
                "AEO Badge": row.get("AEO Badge"),
                "Schema Types Count": _to_int(row.get("Schema Types Count"), 0),
                "Schema Types Found": row.get("Schema Types Found"),
                "Schema Parse Errors": _to_int(row.get("Schema Parse Errors"), 0),
                "Question Heading Count": _to_int(row.get("Question Heading Count"), 0),
                "Answer Blocks": _to_int(row.get("Paragraphs 40-60 Words Count"), 0),
                "FAQ Section Count": _to_int(row.get("FAQ Section Count"), 0),
                "Image Count": _to_int(row.get("Image Count"), 0),
                "Images Missing Alt": _to_int(row.get("Images Missing Alt"), 0),
                "Image Alt Coverage (%)": _export_number(alt_coverage),
                "AEO Extractability Score": _aeo_extractability_numeric(
                    row.get("AEO Extractability Score")
                ),
                "Title Missing": _to_bool(row.get("Title Missing")),
                "Media Mixed Content Detected": _to_bool(row.get("Mixed Content Detected")),
                "Source Legacy Tab": _joined(sources),
            }
        )
    return rows


def _issue_register_history_fields(
    *,
    stable_issue_id: str,
    issue_records: dict[str, IssueRecord] | None,
    run_date: str | None,
) -> dict[str, Any]:
    record = (issue_records or {}).get(stable_issue_id)
    first_seen = record.first_seen if record and record.first_seen else (run_date or "")
    days_open = days_between(first_seen, run_date) if first_seen and run_date else ""
    return {
        "Date First Detected": first_seen,
        "Days Open": days_open if days_open is not None else "",
        "Assigned To": "",
        "Client Notes": "",
    }


def build_issue_register_rows(
    *,
    summary_rows: list[dict[str, Any]],
    issue_inventory_rows: list[dict[str, Any]],
    issue_records: dict[str, IssueRecord] | None = None,
    run_date: str | None = None,
) -> list[dict[str, Any]]:
    """Build merged rows for the 'Issue Register' worksheet."""
    rows: list[dict[str, Any]] = []

    for idx, row in enumerate(summary_rows, start=2):
        section = _to_str(row.get("Section")) or "Issue Counts"
        issue_name = _to_str(row.get("Issue"))
        if not issue_name:
            continue
        ref = _to_str(row.get("Reference Tab") or row.get("Reference Area"))
        raw_count = row.get("Affected URL Count")
        if raw_count is None:
            continue
        affected_count = _to_int(raw_count, 0)
        if affected_count <= 0:
            continue
        history = _issue_register_history_fields(
            stable_issue_id="",
            issue_records=issue_records,
            run_date=run_date,
        )
        rows.append(
            {
                "URL": "",
                "Section": section,
                "Issue": issue_name,
                "Severity": _to_str(row.get("Severity")),
                "Affected URL Count": affected_count,
                "Reference Area": ref,
                "Stable Issue ID": "",
                "Owner": "",
                "Sprint": "",
                "Status": "Open",
                "Affected URLs Sample": _to_str(row.get("Affected URLs (sample)")),
                "Source Legacy Tab": "Summary (site-wide — no single URL; sort by URL to separate from per-URL issues)",
                "Source Row ID": idx,
                **history,
            }
        )

    for idx, row in enumerate(issue_inventory_rows, start=2):
        stable_id = _to_str(row.get("Stable Issue ID"))
        history = _issue_register_history_fields(
            stable_issue_id=stable_id,
            issue_records=issue_records,
            run_date=run_date,
        )
        rows.append(
            {
                "URL": _to_str(row.get("URL")),
                "Section": "Issue Inventory",
                "Issue": _to_str(row.get("Issue")),
                "Severity": _to_str(row.get("Severity")),
                "Affected URL Count": 1,
                "Reference Area": _to_str(row.get("Reference Tab")),
                "Stable Issue ID": stable_id,
                "Owner": _to_str(row.get("Owner")),
                "Sprint": _to_str(row.get("Sprint")),
                "Status": _to_str(row.get("Status")) or "To Do",
                "Affected URLs Sample": _to_str(row.get("URL")),
                "Source Legacy Tab": "IssueInventory",
                "Source Row ID": idx,
                **history,
            }
        )

    if not rows:
        history = _issue_register_history_fields(
            stable_issue_id="",
            issue_records=issue_records,
            run_date=run_date,
        )
        rows.append(
            {
                "URL": "",
                "Section": "Issue Counts",
                "Issue": "No open issues detected in this crawl",
                "Severity": "Observation",
                "Affected URL Count": 0,
                "Reference Area": "Technical Diagnostics",
                "Stable Issue ID": "",
                "Owner": "",
                "Sprint": "",
                "Status": "Open",
                "Affected URLs Sample": "All crawled URLs passed configured issue rules.",
                "Source Legacy Tab": "Summary",
                "Source Row ID": 2,
                **history,
            }
        )
    return rows


def build_link_intelligence_rows(
    *,
    extra_rows: list[dict[str, Any]],
    link_detail_rows: list[dict[str, Any]],
    crawlgraph_rows: list[dict[str, Any]],
    main_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build merged rows for the 'Link Intelligence' worksheet."""
    rows: list[dict[str, Any]] = []
    graph_by_url = {
        _to_str(row.get("URL")): row for row in crawlgraph_rows if row.get("URL")
    }

    for main, extra in _pair_main_extra_rows(main_rows, extra_rows):
        row = _merged_export_row(main, extra)
        url = _to_str(row.get("URL"))
        graph = graph_by_url.get(url, {})
        inlinks_urls = _to_str(graph.get("Inlinks URLs"))
        link_statuses = _to_str(row.get("Internal Link Statuses"))
        if inlinks_urls and not link_statuses:
            link_statuses = inlinks_urls
        broken_ct = _to_int(row.get("Broken Internal Links Count"), 0)
        inlinks_count = _to_int(
            row.get("Internal Inlinks") or graph.get("Inlinks Count"),
            0,
        )
        rows.append(
            {
                "URL": url,
                "Record Type": "Summary",
                "Target URL": "",
                "Anchor Text": "",
                "Target Status (if crawled)": "",
                "Crawlable": "",
                "Internal Links Count": _to_int(row.get("Internal Links Count"), 0),
                "Broken Internal Links Count": broken_ct,
                "Unresolved Internal Links Count": _to_int(
                    row.get("Unresolved Internal Links Count"), 0
                ),
                "External Links Count": _to_int(row.get("External Links Count"), 0),
                "Inlinks Count": inlinks_count,
                "Orphan Candidate": _to_bool(
                    row.get("Orphan Pages") or graph.get("Orphan Candidate")
                ),
                "Click Depth": _to_int(
                    row.get("Click Depth") or graph.get("Click Depth"),
                    0,
                ),
                "Internal PageRank": _to_float(
                    row.get("Internal PageRank") or graph.get("Internal PageRank"),
                    0.0,
                ),
                "Generic Anchor Text Count": _to_int(
                    row.get("Generic Anchor Text Count"), 0
                ),
                "Nofollow Internal Links Count": _to_int(
                    row.get("Nofollow Internal Links Count"), 0
                ),
                "Nofollow External Links Count": _to_int(
                    row.get("Nofollow External Links Count"), 0
                ),
                "Internal Link Statuses": link_statuses,
                "Actionable Fixes": (
                    f"Fix {broken_ct} broken links (See Link Inventory tab for details)."
                    if broken_ct > 0
                    else ""
                ),
                "Source Legacy Tab": "Links",
                "Broken Links (computed)": broken_ct,
            }
        )

    for row in link_detail_rows:
        rows.append(
            {
                "URL": _to_str(row.get("Source URL") or row.get("URL")),
                "Record Type": "Detail",
                "Target URL": _to_str(row.get("Target URL")),
                "Anchor Text": _to_str(row.get("Anchor Text")),
                "Target Status (if crawled)": _to_int(
                    row.get("Target Status (if crawled)"), 0
                ),
                "Crawlable": _to_bool(row.get("Crawlable")),
                "Internal Links Count": 0,
                "Broken Internal Links Count": 0,
                "Unresolved Internal Links Count": 0,
                "External Links Count": 0,
                "Inlinks Count": 0,
                "Orphan Candidate": False,
                "Click Depth": 0,
                "Internal PageRank": 0.0,
                "Generic Anchor Text Count": 0,
                "Nofollow Internal Links Count": 0,
                "Nofollow External Links Count": 0,
                "Internal Link Statuses": "",
                "Actionable Fixes": "",
                "Source Legacy Tab": "LinksDetail",
            }
        )

    return rows


def build_link_inventory_rows(extra_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten per-anchor rows for the Link Inventory worksheet."""
    from hype_frog.pipeline.link_inventory_stream import build_link_inventory_rows_list

    return build_link_inventory_rows_list(extra_rows)


def build_template_duplication_risks_rows(
    *,
    duplicate_rows: list[dict[str, Any]],
    pattern_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build merged rows for the 'Template & Duplication Risks' worksheet."""
    rows: list[dict[str, Any]] = []

    for row in duplicate_rows:
        title_count = _to_int(row.get("Title Duplicate Count"), 0)
        meta_count = _to_int(row.get("Meta Description Duplicate Count"), 0)
        if title_count > 1:
            rows.append(
                {
                    "URL": _to_str(row.get("URL")),
                    "Risk Category": "Duplicate Title",
                    "Subfolder / Template Group": "",
                    "Issue": "Title duplicated across URLs",
                    "Affected Ratio": 0.0,
                    "Affected URL Count": title_count,
                    "Example URLs": _to_str(row.get("Title Duplicate URLs")),
                    "Exact Action": "Rewrite duplicated page titles to be unique per URL.",
                    "Severity": "Warning",
                    "Source Legacy Tab": "Duplicates",
                }
            )
        if meta_count > 1:
            rows.append(
                {
                    "URL": _to_str(row.get("URL")),
                    "Risk Category": "Duplicate Meta",
                    "Subfolder / Template Group": "",
                    "Issue": "Meta description duplicated across URLs",
                    "Affected Ratio": 0.0,
                    "Affected URL Count": meta_count,
                    "Example URLs": _to_str(row.get("Meta Duplicate URLs")),
                    "Exact Action": (
                        "Rewrite duplicated meta descriptions to reflect each page intent."
                    ),
                    "Severity": "Observation",
                    "Source Legacy Tab": "Duplicates",
                }
            )
        if _to_bool(row.get("Probable Duplicate Flag")):
            duplicate_of = _to_str(row.get("Duplicate Of URL"))
            # Fall back to the best-match candidate when duplicate_of is blank
            # (e.g. this page won the rank comparison against its own cluster
            # match, so it's flagged as probable-duplicate with a populated
            # similarity score but no confirmed "points to" target).
            best_match_url = _to_str(row.get("Best Match URL"))
            example_url = duplicate_of or best_match_url
            similarity = row.get("Content Similarity %")
            similarity_note = (
                f" ({float(similarity):.0f}% content similarity)"
                if similarity is not None and str(similarity).strip() != ""
                else ""
            )
            if duplicate_of:
                exact_action = (
                    "Consolidate to one canonical URL: remove or noindex the draft/copy page, "
                    "301 redirect to the primary page, and deduplicate repetitive H2/H3 blocks."
                )
            elif best_match_url:
                exact_action = (
                    f"Review against best-match candidate ({best_match_url}): confirm which "
                    "page is canonical, then remove/noindex the non-canonical copy and "
                    "deduplicate repetitive H2/H3 blocks."
                )
            else:
                exact_action = (
                    "Review for duplicate/near-duplicate content; no specific counterpart "
                    "URL was identified above the similarity threshold."
                )
            rows.append(
                {
                    "URL": _to_str(row.get("URL")),
                    "Risk Category": "Duplicate Content",
                    "Subfolder / Template Group": "",
                    "Issue": (
                        "Probable draft or near-duplicate page"
                        + similarity_note
                        + (f" of {example_url}" if example_url else "")
                    ),
                    "Affected Ratio": 0.0,
                    "Affected URL Count": _to_int(row.get("Heading Structure Cluster Size"), 1),
                    "Example URLs": example_url or "",
                    "Exact Action": exact_action,
                    "Severity": "Warning",
                    "Source Legacy Tab": "Duplicates",
                }
            )

    for row in pattern_rows:
        rows.append(
            {
                "URL": "",
                "Risk Category": "Template Pattern",
                "Subfolder / Template Group": _to_str(row.get("Subfolder")),
                "Issue": _to_str(row.get("Systemic Issue")),
                "Affected Ratio": _to_float(row.get("Affected Ratio"), 0.0),
                "Affected URL Count": _to_int(row.get("URL Count"), 0),
                "Example URLs": "",
                "Exact Action": _to_str(row.get("Exact Action")),
                "Severity": "Warning",
                "Source Legacy Tab": "Pattern and Template Issues",
            }
        )

    if not rows:
        rows.append(
            {
                "URL": "",
                "Risk Category": "Template Pattern",
                "Subfolder / Template Group": "/",
                "Issue": "No template or duplication risks identified.",
                "Affected Ratio": 0.0,
                "Affected URL Count": 0,
                "Example URLs": "",
                "Exact Action": "N/A",
                "Severity": "Observation",
                "Source Legacy Tab": "Pattern and Template Issues",
            }
        )

    return rows


QUICK_WINS_COLUMNS: tuple[str, ...] = (
    # Identity — what and where.
    "URL",
    "Issue",
    "Severity",
    # Why it's a quick win — the numbers that justify prioritising this row.
    "Priority Score",
    "Business Risk Score",
    "GSC Clicks (30d)",
    "Effort (hrs)",
    # What to do — the narrative columns, kept together to reduce row-height variance.
    "What It Is",
    "Why It Matters",
    "Recommended Fix",
    "How To Verify",
    # Ownership / planning.
    "Owner",
    "Sprint",
    "Revenue Risk",
    # Navigation.
    "Jump to FixPlan",
    "Jump to Playbook",
)

BROKEN_LINK_IMPACT_COLUMNS: tuple[str, ...] = (
    "Priority Score",
    "Broken URL",
    "Status Code",
    "Inbound Link Count",
    "Source Page Clicks Total",
    "Source Pages (first 5)",
    "Anchor Texts Used",
    "Recommended Action",
)


def build_quick_wins_rows(
    extra_rows: list[dict[str, Any]],
    fixplan_rows: list[dict[str, Any]],
    summary_rules: list[Any],
    playbook_index: dict[str, PlaybookEntry] | None = None,
    risk_score_by_url: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build Quick Wins tab: top high-impact low-effort URL+issue combinations."""
    fp_index: dict[str, dict[str, Any]] = {}
    for fp_row in fixplan_rows:
        name = str(fp_row.get("Issue Type") or "")
        fp_index[name] = fp_row

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for rule in summary_rules:
        rule_name = rule.name if hasattr(rule, "name") else str(rule[1])
        fp = fp_index.get(rule_name)
        if not fp:
            continue
        hours_raw = fp.get("Est. Hours", 99)
        try:
            hours = float(hours_raw)
        except (TypeError, ValueError):
            hours = 99.0
        if hours > get_quick_wins_max_effort_hours():
            continue

        rule_fn = rule.fn if hasattr(rule, "fn") else rule[2]
        severity = rule.severity if hasattr(rule, "severity") else rule[0]
        for row in extra_rows:
            url = str(row.get("URL") or "")
            try:
                if not rule_fn(row):
                    continue
            except Exception as exc:
                logger.debug(
                    "Issue rule %s skipped for URL %s: %s",
                    rule_name,
                    url,
                    exc,
                )
                continue
            if (url, rule_name) in seen:
                continue
            seen.add((url, rule_name))

            clicks = float(row.get("GSC Clicks") or 0)
            # "Business Risk Score" is never set on the raw extra_rows dict
            # itself (only computed separately for Priority URLs) — look it
            # up by URL from that same computation instead of silently
            # reading 0 for every row.
            risk_raw = (
                (risk_score_by_url or {}).get(url) if risk_score_by_url else None
            )
            risk = float(risk_raw or 0)
            if clicks == 0 and risk <= 0:
                continue

            _sev_weights = {"Critical": 100, "Warning": 50, "Observation": 10}
            sev_weight = _sev_weights.get(str(severity or ""), 10)
            composite = (
                (sev_weight * (1.0 / max(hours, 0.5)))
                + (clicks / 10.0)
                + (risk / 100.0)
            )
            rows.append(
                {
                    "Priority Score": round(composite, 1),
                    "URL": url,
                    "Issue": rule_name,
                    "Severity": severity,
                    "Effort (hrs)": hours,
                    "Owner": fp.get("Owner", ""),
                    "GSC Clicks (30d)": int(clicks),
                    "Business Risk Score": risk,
                    "What It Is": (
                        playbook_index[rule_name].what_it_is
                        if playbook_index and rule_name in playbook_index
                        else ""
                    ),
                    "Why It Matters": (
                        playbook_index[rule_name].why_it_matters
                        if playbook_index and rule_name in playbook_index
                        else ""
                    ),
                    "How To Verify": (
                        playbook_index[rule_name].how_to_verify
                        if playbook_index and rule_name in playbook_index
                        else ""
                    ),
                    "Recommended Fix": fp.get("Recommended Fix", ""),
                    "Sprint": fp.get("Aging/Priority", ""),
                    "Revenue Risk": fp.get("Revenue Risk", ""),
                    "Jump to FixPlan": (
                        "=IFERROR(HYPERLINK(\"#'FixPlan'!A\"&MATCH(\""
                        + str(rule_name).replace('"', '""')
                        + "\",'FixPlan'!A:A,0),\"Open in FixPlan\"),"
                        "HYPERLINK(\"#'FixPlan'!A1\",\"Open in FixPlan\"))"
                    ),
                    "Jump to Playbook": (
                        "=IFERROR(HYPERLINK(\"#'Playbook'!A\"&MATCH(\""
                        + str(rule_name).replace('"', '""')
                        + "\",'Playbook'!B:B,0),\"Open in Playbook\"),"
                        "HYPERLINK(\"#'Playbook'!A1\",\"Open in Playbook\"))"
                    ),
                    # Sort-only field, stripped by the QUICK_WINS_COLUMNS filter below —
                    # not shown as a visible column.
                    "Discovery Rank": _to_int(row.get("Discovery Rank"), 10**9),
                }
            )

    rows.sort(
        key=lambda item: (-item["Priority Score"], item.get("Discovery Rank", 10**9))
    )
    capped = rows[: get_quick_wins_max_results()]
    return [{col: row.get(col) for col in QUICK_WINS_COLUMNS} for row in capped]


def build_broken_link_impact_rows(
    link_inventory_rows: list[dict[str, Any]] | Iterable[dict[str, Any]],
    extra_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rank broken internal destinations by inbound link volume and source traffic."""
    from collections import defaultdict

    url_index: dict[str, dict[str, Any]] = {
        str(row.get("URL") or ""): row for row in extra_rows
    }
    broken_targets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "source_urls": [],
            "source_clicks_total": 0.0,
            "anchor_texts": [],
            "status_code": None,
        }
    )

    for link in link_inventory_rows:
        target = str(link.get("Target URL") or "")
        status = link.get("Status Code")
        link_type = str(link.get("Link Type") or "")

        if link_type.lower() != "internal":
            continue
        try:
            status_code = int(status)
            if status_code < 400:
                continue
        except (TypeError, ValueError):
            if str(status).lower() not in ("timeout", "error"):
                continue
            status_code = str(status)

        source = str(link.get("Source URL") or "")
        anchor = str(link.get("Anchor Text") or "")
        source_row = url_index.get(source, {})
        source_clicks = float(source_row.get("GSC Clicks") or 0)

        entry = broken_targets[target]
        entry["status_code"] = status_code
        if source not in entry["source_urls"]:
            entry["source_urls"].append(source)
            entry["source_clicks_total"] += source_clicks
        if anchor and anchor not in entry["anchor_texts"]:
            entry["anchor_texts"].append(anchor)

    output_rows: list[dict[str, Any]] = []
    for target_url, data in broken_targets.items():
        inbound_count = len(data["source_urls"])
        clicks = data["source_clicks_total"]
        priority = clicks + (inbound_count * 10)
        status_code = data["status_code"]
        if isinstance(status_code, int) and status_code == 404:
            action = "Restore page OR set up 301 redirect to nearest equivalent"
        elif isinstance(status_code, str):
            action = "Investigate — page is timing out"
        else:
            action = f"Investigate {status_code} response"

        target_rank_raw = url_index.get(target_url, {}).get("Discovery Rank")
        output_rows.append(
            {
                "Priority Score": round(priority, 0),
                "Broken URL": target_url,
                "Status Code": status_code,
                "Inbound Link Count": inbound_count,
                "Source Page Clicks Total": int(clicks),
                "Source Pages (first 5)": " | ".join(data["source_urls"][:5]),
                "Anchor Texts Used": " | ".join(data["anchor_texts"][:5]),
                "Recommended Action": action,
                # Sort-only field, stripped by the BROKEN_LINK_IMPACT_COLUMNS filter
                # below — not shown as a visible column.
                "Discovery Rank": _to_int(target_rank_raw, 10**9),
            }
        )

    output_rows.sort(
        key=lambda item: (-item["Priority Score"], item["Discovery Rank"])
    )
    return [{col: row.get(col) for col in BROKEN_LINK_IMPACT_COLUMNS} for row in output_rows]


REDIRECT_MAP_COLUMNS: tuple[str, ...] = (
    "Source URL",
    "Hop 1 URL",
    "Hop 1 Status",
    "Hop 2 URL",
    "Hop 2 Status",
    "Hop 3 URL",
    "Hop 3 Status",
    "Final URL",
    "Chain Length",
    "Has 302",
    "SEO Risk",
    "Redirect Chain",
)


def _hop_records_from_extra_row(row: dict[str, Any]) -> list[RedirectHopRecord]:
    raw = row.get("Redirect Chain Hops")
    if not raw:
        return []
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    records: list[RedirectHopRecord] = []
    for item in parsed:
        if not isinstance(item, dict) or item.get("url") is None:
            continue
        try:
            records.append(
                RedirectHopRecord(url=str(item["url"]), status=int(item["status"]))
            )
        except (TypeError, ValueError):
            continue
    return records


def build_redirects_sheet_rows(extra_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build rows for the legacy Redirects worksheet."""
    return [
        {
            "URL": row.get("URL"),
            "Status Code": row.get("Status Code"),
            "Final URL": row.get("Final URL"),
            "Redirect Chain": row.get("Redirect Chain"),
            "Redirect Chain Length": row.get("Redirect Chain Length"),
            "Redirect Chain Hops": row.get("Redirect Chain Hops"),
            "Has 302 in Chain": row.get("Has 302 in Chain"),
            "Has Mixed Redirect Types": row.get("Has Mixed Redirect Types"),
            "Redirect Target": row.get("Redirect Target"),
            "Redirect Hops": row.get("Redirect Hops"),
            "HTTP->HTTPS Redirect": row.get("HTTP->HTTPS Redirect"),
            "Redirect Loop Flag": row.get("Redirect Loop Flag"),
            "Redirect SEO Risk": row.get("Redirect SEO Risk"),
        }
        for row in extra_rows
    ]


def build_redirect_map_rows(extra_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per source URL that returned a redirect chain."""
    rows: list[dict[str, Any]] = []
    for row in extra_rows:
        if int(row.get("Redirect Chain Length") or 0) <= 0:
            continue
        hop_records = _hop_records_from_extra_row(row)
        map_row = build_redirect_map_row(
            source_url=str(row.get("URL") or ""),
            hop_records=hop_records,
            final_url=row.get("Final URL"),
            fields=row,
        )
        rows.append({col: map_row.get(col) for col in REDIRECT_MAP_COLUMNS})
    return rows


__all__ = [
    "TECHNICAL_DIAGNOSTICS_COLUMNS",
    "TECHNICAL_DIAGNOSTICS_LIGHTHOUSE_COLUMNS",
    "CONTENT_AI_READINESS_COLUMNS",
    "ISSUE_REGISTER_COLUMNS",
    "LINK_INTELLIGENCE_COLUMNS",
    "LINK_INVENTORY_COLUMNS",
    "TEMPLATE_DUPLICATION_RISKS_COLUMNS",
    "QUICK_WINS_COLUMNS",
    "BROKEN_LINK_IMPACT_COLUMNS",
    "REDIRECT_MAP_COLUMNS",
    "build_technical_diagnostics_rows",
    "build_content_ai_readiness_rows",
    "build_issue_register_rows",
    "build_link_intelligence_rows",
    "build_link_inventory_rows",
    "build_template_duplication_risks_rows",
    "build_quick_wins_rows",
    "build_broken_link_impact_rows",
    "build_redirects_sheet_rows",
    "build_redirect_map_rows",
]

