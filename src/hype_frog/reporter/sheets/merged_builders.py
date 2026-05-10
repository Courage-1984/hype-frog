from __future__ import annotations

from typing import Any

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
    "Final URL",
    "Canonical URL",
    "Meta Robots Raw",
    "X-Robots-Tag",
    "GSC Index Status",
    "GSC Last Crawl",
    "GSC Coverage Category",
    "Source Legacy Tab",
    # Sprint 5 — structural / security / i18n diagnostics migrated from
    # the Content Optimisation Hub. Appended at the END so existing
    # column-position contracts (notably the
    # ``_link_main_technical_health_to_diagnostics`` VLOOKUP into
    # ``'Technical Diagnostics'!$A:$E,5,FALSE`` for ``SEO Health Score``)
    # are preserved. ``Anchor Text Diversity`` deliberately stays on the
    # Hub per the brief and is not mirrored here.
    "Crawl Depth",
    "Security: HSTS",
    "Security: CSP",
    "Hreflang Signals",
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


def build_technical_diagnostics_rows(
    extra_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build merged rows for the 'Technical Diagnostics' worksheet."""
    rows: list[dict[str, Any]] = []
    for row in extra_rows:
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
            )
        ):
            categories.append("Security")
            sources.append("Security")
        if any(
            row.get(key) not in (None, "", False)
            for key in ("Desktop PSI Score", "Mobile PSI Score", "Mobile LCP (s)")
        ):
            categories.append("Performance")
            sources.append("PSI Performance")
        if any(
            row.get(key) not in (None, "", False)
            for key in (
                "GSC Inspection Verdict",
                "GSC Inspection Coverage State",
                "GSC Inspection Last Crawl",
                "GSC Clicks",
                "GSC Impressions",
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
                "SEO Health Score": _to_float(row.get("SEO Health Score"), 0.0),
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
                "Desktop PSI Score": _to_float(row.get("Desktop PSI Score"), 0.0),
                "Mobile PSI Score": _to_float(row.get("Mobile PSI Score"), 0.0),
                "Mobile LCP (s)": _to_float(row.get("Mobile LCP (s)"), 0.0),
                "Mobile CLS": _to_float(row.get("Mobile CLS"), 0.0),
                "Mobile TTFB (s)": _to_float(row.get("Mobile TTFB (s)"), 0.0),
                "Final URL": row.get("Final URL"),
                "Canonical URL": row.get("Canonical URL"),
                "Meta Robots Raw": row.get("Meta Robots Raw"),
                "X-Robots-Tag": row.get("X-Robots-Tag"),
                "GSC Index Status": _to_str(row.get("GSC Inspection Verdict")),
                "GSC Last Crawl": _to_str(row.get("GSC Inspection Last Crawl")),
                "GSC Coverage Category": _to_str(row.get("GSC Inspection Coverage State")),
                "Source Legacy Tab": _joined(sources),
                # Sprint 5 — migrated from the Content Optimisation Hub.
                # ``Crawl Depth`` is the BFS hop distance from the seed
                # (currently always ``0`` until a spider entrypoint
                # passes a real value); the security columns are boolean
                # digests of the raw response headers above; the
                # hreflang string is purely on-page extraction.
                "Crawl Depth": _to_int(row.get("Crawl Depth"), 0),
                "Security: HSTS": _to_bool(row.get("Security: HSTS")),
                "Security: CSP": _to_bool(row.get("Security: CSP")),
                "Hreflang Signals": _to_str(row.get("Hreflang Signals")),
            }
        )
    return rows


def build_content_ai_readiness_rows(
    extra_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build merged rows for the 'Content & AI Readiness' worksheet.

    ``AEO Readiness Score`` is produced upstream by
    ``hype_frog.pipeline.assemble.compute_aeo_readiness_score`` (weighted 0–100 model).
    """
    rows: list[dict[str, Any]] = []
    for row in extra_rows:
        categories: list[str] = ["Content"]
        sources: list[str] = ["Content"]
        if any(
            row.get(key) not in (None, "", False)
            for key in (
                "AEO Readiness Score",
                "Question Heading Count",
                "FAQ Section Count",
                "AEO Extractability Score",
            )
        ):
            categories.append("AEO")
            sources.append("AEO")
        if any(
            row.get(key) not in (None, "", False)
            for key in ("Schema Types Count", "Schema Types Found", "Schema Parse Errors")
        ):
            categories.append("Schema")
            sources.append("Schema & Metadata")
        if any(
            row.get(key) not in (None, "", False)
            for key in ("Image Count", "Images Missing Alt", "Image Alt Coverage (%)")
        ):
            categories.append("Media")
            sources.append("Media")

        rows.append(
            {
                "URL": row.get("URL"),
                "Content Category": _joined(categories),
                "Word Count": _to_int(row.get("Word Count"), 0),
                "Readability (Rough Flesch)": _to_float(
                    row.get("Readability (Rough Flesch)"), 0.0
                ),
                "Flesch-Kincaid Grade (Est.)": row.get("Flesch-Kincaid Grade (Est.)"),
                "Thin Content Flag": _to_bool(row.get("Thin Content Flag")),
                "H1 Count": _to_int(row.get("H1 Count"), 0),
                "Missing H1 Flag": _to_bool(row.get("Missing H1 Flag")),
                "Meta Description Missing": _to_bool(row.get("Meta Description Missing")),
                "AEO Readiness Score": _to_float(row.get("AEO Readiness Score"), 0.0),
                "AEO Badge": row.get("AEO Badge"),
                "Schema Types Count": _to_int(row.get("Schema Types Count"), 0),
                "Schema Types Found": row.get("Schema Types Found"),
                "Schema Parse Errors": _to_int(row.get("Schema Parse Errors"), 0),
                "Question Heading Count": _to_int(row.get("Question Heading Count"), 0),
                "Answer Blocks": _to_int(row.get("Paragraphs 40-60 Words Count"), 0),
                "FAQ Section Count": _to_int(row.get("FAQ Section Count"), 0),
                "Image Count": _to_int(row.get("Image Count"), 0),
                "Images Missing Alt": _to_int(row.get("Images Missing Alt"), 0),
                "Image Alt Coverage (%)": _to_float(
                    row.get("Image Alt Coverage (%)"), 0.0
                ),
                "AEO Extractability Score": _aeo_extractability_numeric(
                    row.get("AEO Extractability Score")
                ),
                "Title Missing": _to_bool(row.get("Title Missing")),
                "Media Mixed Content Detected": _to_bool(row.get("Mixed Content Detected")),
                "Source Legacy Tab": _joined(sources),
            }
        )
    return rows


def build_issue_register_rows(
    *,
    summary_rows: list[dict[str, Any]],
    issue_inventory_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build merged rows for the 'Issue Register' worksheet."""
    rows: list[dict[str, Any]] = []

    for idx, row in enumerate(summary_rows, start=2):
        section = _to_str(row.get("Section")) or "Issue Counts"
        issue_name = _to_str(row.get("Issue"))
        ref = _to_str(row.get("Reference Tab"))
        rows.append(
            {
                "URL": "",
                "Section": section,
                "Issue": issue_name,
                "Severity": _to_str(row.get("Severity")),
                "Affected URL Count": _to_int(row.get("Affected URL Count"), 0),
                "Reference Area": ref,
                "Stable Issue ID": "",
                "Owner": "",
                "Sprint": "",
                "Status": "Open",
                "Affected URLs Sample": _to_str(row.get("Affected URLs (sample)")),
                "Source Legacy Tab": "Summary",
                "Source Row ID": idx,
            }
        )

    for idx, row in enumerate(issue_inventory_rows, start=2):
        rows.append(
            {
                "URL": _to_str(row.get("URL")),
                "Section": "Issue Inventory",
                "Issue": _to_str(row.get("Issue")),
                "Severity": _to_str(row.get("Severity")),
                "Affected URL Count": 1,
                "Reference Area": _to_str(row.get("Reference Tab")),
                "Stable Issue ID": _to_str(row.get("Stable Issue ID")),
                "Owner": _to_str(row.get("Owner")),
                "Sprint": _to_str(row.get("Sprint")),
                "Status": _to_str(row.get("Status")) or "Open",
                "Affected URLs Sample": _to_str(row.get("URL")),
                "Source Legacy Tab": "IssueInventory",
                "Source Row ID": idx,
            }
        )
    return rows


def build_link_intelligence_rows(
    *,
    extra_rows: list[dict[str, Any]],
    link_detail_rows: list[dict[str, Any]],
    crawlgraph_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build merged rows for the 'Link Intelligence' worksheet."""
    rows: list[dict[str, Any]] = []

    for row in extra_rows:
        broken_ct = _to_int(row.get("Broken Internal Links Count"), 0)
        rows.append(
            {
                "URL": _to_str(row.get("URL")),
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
                "Inlinks Count": _to_int(row.get("Internal Inlinks"), 0),
                "Orphan Candidate": _to_bool(row.get("Orphan Pages")),
                "Click Depth": _to_int(row.get("Click Depth"), 0),
                "Internal PageRank": _to_float(row.get("Internal PageRank"), 0.0),
                "Generic Anchor Text Count": _to_int(
                    row.get("Generic Anchor Text Count"), 0
                ),
                "Nofollow Internal Links Count": _to_int(
                    row.get("Nofollow Internal Links Count"), 0
                ),
                "Nofollow External Links Count": _to_int(
                    row.get("Nofollow External Links Count"), 0
                ),
                "Internal Link Statuses": _to_str(row.get("Internal Link Statuses")),
                "Actionable Fixes": (
                    f"Fix {broken_ct} broken links (See Link Inventory tab for details)."
                    if broken_ct > 0
                    else ""
                ),
                "Source Legacy Tab": "Links",
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

    for row in crawlgraph_rows:
        rows.append(
            {
                "URL": _to_str(row.get("URL")),
                "Record Type": "Graph",
                "Target URL": "",
                "Anchor Text": "",
                "Target Status (if crawled)": "",
                "Crawlable": "",
                "Internal Links Count": 0,
                "Broken Internal Links Count": 0,
                "Unresolved Internal Links Count": 0,
                "External Links Count": 0,
                "Inlinks Count": _to_int(row.get("Inlinks Count"), 0),
                "Orphan Candidate": _to_bool(row.get("Orphan Candidate")),
                "Click Depth": _to_int(row.get("Click Depth"), 0),
                "Internal PageRank": _to_float(row.get("Internal PageRank"), 0.0),
                "Generic Anchor Text Count": 0,
                "Nofollow Internal Links Count": 0,
                "Nofollow External Links Count": 0,
                "Internal Link Statuses": _to_str(row.get("Inlinks URLs")),
                "Actionable Fixes": "",
                "Source Legacy Tab": "CrawlGraph",
            }
        )

    return rows


def build_link_inventory_rows(extra_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten per-anchor rows for the Link Inventory worksheet."""
    rows: list[dict[str, Any]] = []
    for row in extra_rows:
        source = _to_str(row.get("URL"))
        for item in row.get("Link Details") or []:
            code_raw = item.get("Status Code")
            code_out: int | str = ""
            if isinstance(code_raw, int):
                code_out = code_raw
            elif code_raw is not None and str(code_raw).strip() != "":
                try:
                    code_out = int(float(code_raw))
                except (TypeError, ValueError):
                    code_out = ""
            gen = item.get("Generic Anchor")
            row_dict: dict[str, Any] = {
                "Source URL": source,
                "Target URL": _to_str(item.get("Target URL")),
                "Anchor Text": _to_str(item.get("Anchor Text")),
                "Rel Attribute": _to_str(item.get("Rel Attribute") or item.get("Rel")),
                "Link Type": _to_str(item.get("Link Type")),
                "Status Code": code_out,
                "Generic Anchor": (
                    "TRUE"
                    if gen is True
                    else "FALSE"
                    if gen is False
                    else ""
                ),
            }
            rows.append({col: row_dict[col] for col in LINK_INVENTORY_COLUMNS})
    return rows


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


__all__ = [
    "TECHNICAL_DIAGNOSTICS_COLUMNS",
    "CONTENT_AI_READINESS_COLUMNS",
    "ISSUE_REGISTER_COLUMNS",
    "LINK_INTELLIGENCE_COLUMNS",
    "LINK_INVENTORY_COLUMNS",
    "TEMPLATE_DUPLICATION_RISKS_COLUMNS",
    "build_technical_diagnostics_rows",
    "build_content_ai_readiness_rows",
    "build_issue_register_rows",
    "build_link_intelligence_rows",
    "build_link_inventory_rows",
    "build_template_duplication_risks_rows",
]

