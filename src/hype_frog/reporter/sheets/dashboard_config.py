from __future__ import annotations

from hype_frog.reporter.sheets.config import (
    RAG_AMBER,
    RAG_AMBER_SOFT,
    RAG_GREEN,
    RAG_RED,
    RAG_RED_SOFT,
)
from hype_frog.reporter.sheets.validation import format_help_layer

LIGHT_HEADER_COLOR = "E5E7EB"
TABLE_HEADER_COLOR = "ADD8E6"
VALUE_BLOCK_COLOR = "DCE3EA"
PANEL_BG_COLOR = "F5F7FA"
# RAG fills resolve to the canonical palette in sheets/config.py (single source of truth).
GOOD_COLOR = RAG_GREEN
WARN_COLOR = RAG_AMBER
ALERT_COLOR = RAG_RED
SOFT_ALERT_COLOR = RAG_RED_SOFT
SOFT_WARN_COLOR = RAG_AMBER_SOFT

DASHBOARD_COLUMN_WIDTHS: dict[str, int] = {
    "A": 35,
    "B": 15,
    "C": 5,
    "D": 30,
    "E": 15,
    "F": 5,
    "G": 25,
    "H": 25,
    "I": 30,
    "J": 30,
    "K": 30,
}

STATUS_ROW_STYLE: list[tuple[str, str]] = [
    ("200 OK", GOOD_COLOR),
    ("3xx Redirects", SOFT_WARN_COLOR),
    ("4xx Errors", SOFT_ALERT_COLOR),
    ("5xx Errors", SOFT_ALERT_COLOR),
    ("Other", SOFT_WARN_COLOR),
]

SEVERITY_ROW_STYLE: list[tuple[str, str]] = [
    ("Critical", SOFT_ALERT_COLOR),
    ("Warning", SOFT_WARN_COLOR),
    ("Medium", SOFT_WARN_COLOR),
    ("Low", GOOD_COLOR),
]

QUICK_LINKS: list[tuple[str, str]] = [
    ("Issue Summary", "#Summary!A1"),
    ("Fix Plan", "#FixPlan!A1"),
    ("Main URL Data", "#Main!A1"),
    ("Technical Diagnostics", "#'Technical Diagnostics'!A1"),
    ("Indexability", "#'Technical Diagnostics'!A1"),
    ("AEO Opportunities", "#'Content & AI Readiness'!A1"),
    ("AIOSEO Recommendations", "#'AIOSEO Recommendations'!A1"),
]

DASHBOARD_KPI_ROW_COMMENTS: dict[str, str] = {
    "A5": format_help_layer(
        description=(
            "Blended executive SEO score as a percentage: prefers ``SEO Score`` on Main, "
            "otherwise ``SEO Health Score``."
        ),
        calculation=(
            "Excel ``B5`` divides the header-resolved ``AVERAGE`` of Main "
            "``SEO Score`` (fallback ``SEO Health Score``) by 100 using ``INDEX``/``MATCH`` on "
            "Main row 1 so the KPI survives column reorders."
        ),
    ),
    "A6": format_help_layer(
        description="Site-wide technical health proxy from the Technical Diagnostics sheet.",
        calculation=(
            "Excel ``B6``: ``AVERAGE`` of ``SEO Health Score`` on Technical Diagnostics using "
            "``INDEX``/``MATCH`` on row 1, divided by 100 for display as a percentage."
        ),
    ),
    "A7": format_help_layer(
        description="Average lab PageSpeed Insights score across mobile and desktop fetches.",
        calculation=(
            "Excel ``B7``: mean of Technical Diagnostics ``Mobile PSI Score`` and "
            "``Desktop PSI Score`` columns resolved via ``INDEX``/``MATCH`` on row 1, then "
            "divided by 100 for display as a percentage."
        ),
    ),
    "A18": format_help_layer(
        description="Count of inventory URLs that carry valid JSON-LD during the crawl.",
        calculation=(
            "Excel ``B18`` uses ``COUNTIF`` over an ``OFFSET``/``MATCH`` range on Main row 1 "
            "so ``Has Valid JSON-LD`` stays correct when Main columns are reordered."
        ),
    ),
    "A20": format_help_layer(
        description=(
            "Total broken internal link instances (anchor-level) on Link Inventory "
            "where the target returned HTTP 4xx/5xx."
        ),
        calculation=(
            "Excel ``B20``: ``SUMPRODUCT`` over Link Inventory columns "
            "``Link Type`` = Internal and ``Status Code`` in 400–599. "
            "Matches FixPlan instance totals and Business Impact narrative."
        ),
    ),
    "A19": format_help_layer(
        description=(
            "Headroom for AI-search improvements: high values mean extractability or blended SEO "
            "still has gap versus a fully optimised profile."
        ),
        calculation=(
            "Excel ``B19``: ``MAX(0, IF(avg_AEO_extractability>0, (100-avg)/100, 1-IFERROR(B5,0)))`` "
            "where ``avg_AEO_extractability`` is ``AVERAGE`` of ``AEO Extractability Score`` on "
            "``Content & AI Readiness`` via header ``MATCH`` (falls back to SEO headroom from ``B5`` "
            "when extractability averages are zero)."
        ),
    ),
    "A21": format_help_layer(
        description="Total generic anchor-text occurrences summed across Link Intelligence summaries.",
        calculation=(
            "Excel ``B21``: ``SUMIFS('Link Intelligence'!O:O,'Link Intelligence'!B:B,\"Summary\")`` "
            "aggregates the per-URL ``Generic Anchor Text Count`` for Summary rows."
        ),
    ),
    "A22": format_help_layer(
        description="Share of unique external targets that returned HTTP 200 when probed.",
        calculation=(
            "Excel ``B22`` references Audit Run Details keys for external sniff coverage (see "
            "``_EXCEL_EXTERNAL_LINK_HEALTH_PCT`` in ``dashboard.py``); blank when sniff skipped."
        ),
    ),
}

DASHBOARD_TOOLTIPS: dict[str, str] = {
    "C5": format_help_layer(
        description="Total URLs audited in this workbook run.",
        calculation="Integer from ``SummaryMetricsPayload.urls_crawled`` / Summary feed (not a tab formula).",
    ),
    "C6": format_help_layer(
        description="Executive Overall Health % shown beside the crawl summary strip.",
        calculation=(
            "Python ``compute_dashboard_metrics``: prefers ``summary_metrics.health_score_pct`` "
            "when >0; else mean(Main ``SEO Health Score`` across Technical/Main pairing); else "
            "pass-rate %. Mirrors the narrative feed, not cell ``B5``."
        ),
    ),
    "C7": format_help_layer(
        description="Share of URLs classified as SEO pass for the crawl window.",
        calculation="``(pass_urls / crawl_denominator) * 100`` in ``compute_dashboard_metrics`` (``dashboard_logic``).",
    ),
    "C8": format_help_layer(
        description="Count of URLs with zero Critical and zero Warning issues.",
        calculation="Incremented per Technical row when Critical Issues Count and Warning Issues Count are both zero.",
    ),
    "C9": format_help_layer(
        description="URLs whose Technical severity badge equals Critical.",
        calculation="Counts Technical rows where ``Severity Badge`` normalises to ``critical``.",
    ),
    "C10": format_help_layer(
        description="URLs flagged Warning (or legacy Needs Work) on Technical Diagnostics.",
        calculation="COUNTIFS on Technical ``Severity Badge`` for ``Warning`` plus ``Needs Work`` tokens.",
    ),
    "C11": format_help_layer(
        description="HTTP client/server error share of the crawl.",
        calculation="``(4xx URLs + 5xx URLs) / crawl_denominator`` using status buckets from Technical rows.",
    ),
    "C12": format_help_layer(
        description="Share of URLs returning a 2xx status.",
        calculation="``200 OK`` bucket count ÷ ``crawl_denominator`` in ``compute_dashboard_metrics``.",
    ),
    "C13": format_help_layer(
        description="Critical URLs as a percentage of the crawl set.",
        calculation="``(critical_urls / crawl_denominator) * 100`` from dashboard logic.",
    ),
    "C14": format_help_layer(
        description="Warning-class URLs as a percentage of the crawl set.",
        calculation="``(warning_urls / crawl_denominator) * 100`` from dashboard logic.",
    ),
    "C15": format_help_layer(
        description="Illustrative health ceiling if open FixPlan items were cleared.",
        calculation="``min(100, overall_health + (100-overall_health)*0.6)`` (``projected_health_pct``).",
    ),
    "C16": format_help_layer(
        description="Illustrative pass-rate ceiling if critical/warning backlog were reduced.",
        calculation=(
            "``min(100, pass_rate_pct + ((critical_urls + warning_urls*0.75)/denom)*100)`` "
            "(``projected_pass_rate_pct``)."
        ),
    ),
    "C17": format_help_layer(
        description="Fraction of Content Optimisation Hub rows marked Done.",
        calculation="``COUNTIF(Status range,\"Done\") / COUNTA(Status range)`` (see ``dashboard.py`` range constants).",
    ),
    "O5": format_help_layer(
        description="Most widespread FixPlan issue by affected URL count.",
        calculation="Max-scan over FixPlan rows comparing ``Affected Count`` in ``compute_dashboard_metrics``.",
    ),
    "O6": format_help_layer(
        description="URL coverage for the top blocker issue.",
        calculation="``Affected Count`` value on the FixPlan row that won the max in ``top_issue_name``.",
    ),
    "O7": format_help_layer(
        description="Combined volume of 4xx and 5xx responses.",
        calculation="Sum of ``4xx Errors`` and ``5xx Errors`` buckets from Technical status codes.",
    ),
    "O8": format_help_layer(
        description="Mean TTFB across Technical rows that reported a numeric value.",
        calculation="Arithmetic mean of ``TTFB (ms)`` values collected while iterating Technical extras.",
    ),
    "H15": format_help_layer(
        description="Affected URLs for the highest priority FixPlan row after sorting.",
        calculation="First entry in sorted ``top_issue_rows`` by affected count (ties broken by source row).",
    ),
    "H16": format_help_layer(
        description="Affected URLs for the second FixPlan priority slot.",
        calculation="Second entry in ``top_issue_rows`` (same ordering as ``H15``).",
    ),
    "H17": format_help_layer(
        description="Affected URLs for the third FixPlan priority slot.",
        calculation="Third entry in ``top_issue_rows``.",
    ),
    "H18": format_help_layer(
        description="Affected URLs for the fourth FixPlan priority slot.",
        calculation="Fourth entry in ``top_issue_rows``.",
    ),
    "H19": format_help_layer(
        description="Affected URLs for the fifth FixPlan priority slot.",
        calculation="Fifth entry in ``top_issue_rows`` (list truncated to five rows).",
    ),
    "G23": format_help_layer(
        description="Owner seed used for FixPlan accountability rollups.",
        calculation="Distinct ``Owner`` values from FixPlan rows grouped into the owner summary table.",
    ),
    "H23": format_help_layer(
        description="How many FixPlan issue rows map to this owner.",
        calculation="Count of FixPlan rows whose ``Owner`` column matches the grouped owner label.",
    ),
    "I23": format_help_layer(
        description="Total affected URLs summed across that owner's FixPlan rows.",
        calculation="Sum of ``Affected Count`` for rows owned by this owner.",
    ),
    "J23": format_help_layer(
        description="Number of Critical-severity FixPlan rows for this owner.",
        calculation="Count where owner matches and severity normalises to ``critical``.",
    ),
    "K23": format_help_layer(
        description="Number of Warning/High/Medium FixPlan rows for this owner.",
        calculation="Count where owner matches and severity maps to non-critical elevated classes.",
    ),
}

