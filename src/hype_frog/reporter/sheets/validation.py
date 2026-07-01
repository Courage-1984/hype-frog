from __future__ import annotations

from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from hype_frog.reporter.sheets.config import (
    CONTENT_OPTIMISATION_HUB_SHEET,
    DISABLE_DATA_VALIDATION,
    DISABLE_TOOLTIPS,
    STATUS_OPTIONS,
    status_validation_list_formula,
)
from hype_frog.reporter.sheets.style_helpers import header_index

# Tooltips (cell comments) are suppressed by the dedicated tooltip flag, but the legacy
# data-validation flag is still honoured for backward compatibility. Dropdowns remain
# gated by ``DISABLE_DATA_VALIDATION`` only.
_DISABLE_TOOLTIP_COMMENTS: bool = DISABLE_TOOLTIPS or DISABLE_DATA_VALIDATION

HELP_DESCRIPTION_PREFIX: str = "Description:"
HELP_CALCULATION_PREFIX: str = "Calculation:"

_DEFAULT_COMMENT_WIDTH: float = 432.0
_DEFAULT_COMMENT_HEIGHT: float = 252.0


def format_help_layer(*, description: str, calculation: str) -> str:
    """Build a standardized two-part help string for Excel cell comments."""
    desc = (description or "").strip()
    calc = (calculation or "").strip()
    return (
        f"{HELP_DESCRIPTION_PREFIX} {desc}\n"
        f"{HELP_CALCULATION_PREFIX} {calc}"
    )


def apply_comment_dimensions(
    comment: Comment,
    *,
    width: float = _DEFAULT_COMMENT_WIDTH,
    height: float = _DEFAULT_COMMENT_HEIGHT,
) -> None:
    """Widen comment boxes so Description + Calculation text fits without manual resize."""
    comment.width = width
    comment.height = height


def _attach_header_comment(cell: object, text: str, author: str) -> None:
    comment = Comment(text, author)
    apply_comment_dimensions(comment)
    cell.comment = comment


# Curated bodies (Description + Calculation only; title line added in ``add_all_header_tooltips``).
_CONTENT_AI_READINESS_HELP: dict[str, str] = {
    "AEO Readiness Score": format_help_layer(
        description=(
            "0–100 score for how well the page supports answer-engine extraction "
            "(answer blocks, answer-focused schema, readability band, scannable structure, "
            "robots.txt AI-bot coverage)."
        ),
        calculation=(
            "Python ``compute_aeo_readiness_score`` sums capped sub-scores: "
            "min(30, 15 × Paragraphs 40-60 Words Count) + 25 if QAPage/FAQ OR HowTo OR "
            "Speakable schema + FK grade piecewise (up to 20) + 15 if List/Table Answer "
            "Signal + 10 × AEO Robots AI Bot Coverage ratio; result clamped to [0,100]. "
            "Non-scorable extraction states return a neutral 71 (Unmeasured badge)."
        ),
    ),
    "AEO Extractability Score": format_help_layer(
        description=(
            "How easily an LLM can map question-style headings to factual answer paragraphs "
            "on this URL (crawl-time label or numeric)."
        ),
        calculation=(
            "Export maps crawl labels to a 0–100 scale for reporting: High→85, Medium→55, "
            "Low→25; numeric inputs clamp to [0,100] (see ``_aeo_extractability_numeric`` in "
            "merged link-intelligence / Content-AI row builders)."
        ),
    ),
    "Answer Blocks": format_help_layer(
        description=(
            "Count of 40–60 word body paragraphs detected under question-oriented headings—"
            "the primary on-page pattern cited by answer engines."
        ),
        calculation=(
            "Equals ``Paragraphs 40-60 Words Count`` from the crawl/HTML pipeline, copied into "
            "the Content & AI ``Answer Blocks`` column at export (no Excel formula)."
        ),
    ),
    "Flesch-Kincaid Grade (Est.)": format_help_layer(
        description=(
            "Estimated U.S. school grade reading difficulty for visible body text; lower is "
            "easier. The AEO model treats grades 7–10 as the clarity sweet spot."
        ),
        calculation=(
            "Computed at crawl/enrichment from body text using the Flesch–Kincaid grade "
            "formula; surfaced here as a stored numeric estimate (not an Excel formula)."
        ),
    ),
    "Schema Types Count": format_help_layer(
        description=(
            "How many distinct structured-data types (for example JSON-LD @types) were "
            "detected for this URL."
        ),
        calculation=(
            "Integer count from the schema/metadata extraction stage; written to the row at "
            "export (no workbook formula)."
        ),
    ),
}

_TECHNICAL_DIAGNOSTICS_HELP: dict[str, str] = {
    "SEO Health Score": format_help_layer(
        description=(
            "Composite 0–100 technical SEO quality for this URL from matched audit rules."
        ),
        calculation=(
            "Python ``score_url_health``: start at 100, subtract 25×Critical issue count, "
            "10×Warning count, and min(10, 3×Observation count); clamp to ≥0. Unmeasured when "
            "Extraction State is not scorable."
        ),
    ),
    "Desktop PSI Score": format_help_layer(
        description="Lab PageSpeed Insights performance score (0–100) for the desktop run.",
        calculation=(
            "Passed through from PSI crawl telemetry for the resolved URL; persisted on the "
            "Technical Diagnostics row (not recalculated in Excel)."
        ),
    ),
    "Mobile PSI Score": format_help_layer(
        description="Lab PageSpeed Insights performance score (0–100) for the mobile run.",
        calculation=(
            "Passed through from PSI crawl telemetry for the resolved URL; persisted on the "
            "Technical Diagnostics row (not recalculated in Excel)."
        ),
    ),
    "GSC Index Status": format_help_layer(
        description=(
            "Search Console URL Inspection-style verdict for whether Google treats this URL as "
            "indexed or blocked (verbatim crawl field)."
        ),
        calculation=(
            "Copied from ``GSC Inspection Verdict`` on the underlying extra row when Technical "
            "Diagnostics rows are merged (string pass-through, not an Excel formula)."
        ),
    ),
}

_LINK_INTELLIGENCE_HELP: dict[str, str] = {
    "Internal PageRank": format_help_layer(
        description=(
            "Directed-graph authority proxy: higher means more internal PageRank-style flow "
            "from other crawled pages."
        ),
        calculation=(
            "``networkx.pagerank`` on the internal-link DiGraph (α=0.85, max_iter=100); values "
            "rounded to 6 decimals in ``compute_internal_link_intelligence``."
        ),
    ),
    "Orphan Candidate": format_help_layer(
        description=(
            "Whether this URL behaves like an orphan in the internal graph—hard for crawlers "
            "to discover via internal paths."
        ),
        calculation=(
            "Summary rows: boolean ``Orphan Pages`` from the graph (in-degree 0 on crawled "
            "nodes). Graph rows: boolean ``Orphan Candidate`` from CrawlGraph export. "
            "Detail rows force FALSE because anchors are not graph nodes."
        ),
    ),
}

_FIXPLAN_HELP: dict[str, str] = {
    "Priority Score": format_help_layer(
        description="Remediation ranking (higher = fix sooner) blending severity and reach.",
        calculation=(
            "Computed in the pipeline from issue severity, affected-URL count, and business "
            "risk; persisted on the FixPlan row (not recalculated in Excel)."
        ),
    ),
    "Affected Link Instances": format_help_layer(
        description="Count of broken plus unresolved internal link instances for this issue/URL.",
        calculation="Sum of broken + unresolved internal links per URL from link analysis.",
    ),
    "Est. Sprint Points": format_help_layer(
        description="Relative delivery effort for this fix expressed in sprint points.",
        calculation="Mapped from the estimated hours band during FixPlan assembly.",
    ),
    "Aging/Priority": format_help_layer(
        description="Recommended sprint bucket for the fix.",
        calculation=(
            'One of "Immediate (Current Sprint)", "Next Sprint", or "Backlog", derived from '
            "Priority Score thresholds."
        ),
    ),
    "Action Needed": format_help_layer(
        description="Whether this row still requires work (Yes) or is clear (No).",
        calculation="Yes/No flag set during FixPlan assembly from the resolution state.",
    ),
}

_QUICK_WINS_HELP: dict[str, str] = {
    "Effort (hrs)": format_help_layer(
        description="Estimated hands-on hours to complete this quick win.",
        calculation="Estimated during Quick Wins assembly from the issue's fix profile.",
    ),
    "Business Risk Score": format_help_layer(
        description="Relative business exposure of leaving this issue unresolved (higher = worse).",
        calculation="Blends severity with traffic/visibility signals in the pipeline.",
    ),
    "GSC Clicks (30d)": format_help_layer(
        description="Search Console clicks for this URL over the trailing 30 days.",
        calculation="Pass-through from GSC performance data; blank when GSC is unavailable.",
    ),
    "Revenue Risk": format_help_layer(
        description="Qualitative revenue exposure flag for the affected page.",
        calculation="Derived from page intent and traffic during Quick Wins assembly.",
    ),
}

_BROKEN_LINK_IMPACT_HELP: dict[str, str] = {
    "Inbound Link Count": format_help_layer(
        description="How many internal links point at this broken destination.",
        calculation="Count of internal link edges resolving to this broken target URL.",
    ),
    "Source Page Clicks Total": format_help_layer(
        description="Combined GSC clicks of the pages that link to this broken URL.",
        calculation="Sum of trailing-30-day GSC clicks across the linking source pages.",
    ),
    "Recommended Action": format_help_layer(
        description="Suggested remediation for the broken destination.",
        calculation="Heuristic from status code and link context (fix, redirect, or remove).",
    ),
}

_LINK_INVENTORY_HELP: dict[str, str] = {
    "Generic Anchor": format_help_layer(
        description='Whether the anchor text is non-descriptive (e.g. "click here", "read more").',
        calculation="Boolean flag from anchor-text analysis on the outbound link.",
    ),
    "Rel Attribute": format_help_layer(
        description="The link's rel value (e.g. nofollow, sponsored, ugc) or blank.",
        calculation="Captured verbatim from the anchor element during extraction.",
    ),
    "Link Type": format_help_layer(
        description="Internal vs external classification for the link edge.",
        calculation="Derived from comparing the target host with the crawl domain.",
    ),
}

_SITEMAPQA_HELP: dict[str, str] = {
    "Found via Crawl": format_help_layer(
        description="Whether the URL was discovered by crawling internal links.",
        calculation="Boolean membership check against the crawl frontier.",
    ),
    "Found via Sitemap": format_help_layer(
        description="Whether the URL appears in an XML sitemap.",
        calculation="Boolean membership check against parsed sitemap entries.",
    ),
    "In Sitemap but Non-200": format_help_layer(
        description="Sitemap URL that did not return HTTP 200 (wastes crawl budget).",
        calculation="True when a sitemap URL's resolved status code is not 200.",
    ),
    "Crawled but Missing from Sitemap": format_help_layer(
        description="Indexable crawled URL absent from any sitemap (discoverability gap).",
        calculation="True when a crawled 200 URL is not present in sitemap entries.",
    ),
    "Lastmod vs HTTP Match": format_help_layer(
        description="Whether the sitemap <lastmod> agrees with the HTTP Last-Modified header.",
        calculation="Date comparison (day precision) between sitemap lastmod and HTTP header.",
    ),
}

_CONTENT_HUB_SEMANTIC_HELP: dict[str, str] = {
    "Entity Density (%)": format_help_layer(
        description=(
            "The percentage of page content identified as named entities (people, orgs, places)."
        ),
        calculation="(Named entities / total words) × 100 from semantic extraction.",
    ),
    "Top Entities": format_help_layer(
        description="The most frequent named entities on the page (semantic relevance signal).",
        calculation="Ranked entity list from the semantic analyser for this URL.",
    ),
    "Citation Candidate Count": format_help_layer(
        description="Count of 40–60 word snippets suitable for answer-engine citation.",
        calculation="Snippets starting with answer triggers (e.g. 'is', 'means') from semantic pass.",
    ),
    "Semantic AEO Score": format_help_layer(
        description="Weighted 0–100 score from entity density and citation readiness.",
        calculation="Composite semantic/AEO score from the crawl enrichment pass.",
    ),
}

_SHEET_CURATED_HEADER_HELP: dict[str, dict[str, str]] = {
    "Content & AI Readiness": _CONTENT_AI_READINESS_HELP,
    "Technical Diagnostics": _TECHNICAL_DIAGNOSTICS_HELP,
    "Link Intelligence": _LINK_INTELLIGENCE_HELP,
    CONTENT_OPTIMISATION_HUB_SHEET: _CONTENT_HUB_SEMANTIC_HELP,
    "FixPlan": _FIXPLAN_HELP,
    "Quick Wins": _QUICK_WINS_HELP,
    "Broken Link Impact": _BROKEN_LINK_IMPACT_HELP,
    "Link Inventory": _LINK_INVENTORY_HELP,
    "SitemapQA": _SITEMAPQA_HELP,
}

SCHEMA_METADATA_HEADER_TOOLTIP_BODIES: dict[str, str] = {
    "TTFB (ms)": format_help_layer(
        description="Time to First Byte in milliseconds: server/network responsiveness.",
        calculation=(
            "Measured during the HTTP fetch for this URL and stored on the row (not derived "
            "in Excel)."
        ),
    ),
    "AEO Readiness Score": _CONTENT_AI_READINESS_HELP["AEO Readiness Score"],
    "Indexability Reason": format_help_layer(
        description="Primary explanation when a URL is treated as non-indexable or risky.",
        calculation=(
            "Rule- and signal-driven text from the indexability pipeline (canonical, robots, "
            "status); exported as a string field."
        ),
    ),
    "Status Code": format_help_layer(
        description="Final HTTP status observed for this URL during the crawl.",
        calculation=(
            "Integer from the HTTP client response stored on the crawl row; Technical sheets "
            "reference that stored value."
        ),
    ),
    "SEO Health Score": _TECHNICAL_DIAGNOSTICS_HELP["SEO Health Score"],
    "Priority Score": format_help_layer(
        description="Relative urgency for FixPlan-style remediation rows.",
        calculation=(
            "``workflow_metrics_for_issue``: severity base (Critical=100, Warning=65, "
            "Observation=35, default=25) plus sprint points from effort band "
            "(S=2, M=5, L=8, default=2)."
        ),
    ),
    "Severity": format_help_layer(
        description="Impact tier for the issue attached to this row.",
        calculation=(
            "Categorical label from rules (Critical / Warning / Observation / etc.); "
            "drives SEO Health Score penalties when aggregated per URL."
        ),
    ),
    "Word Count": format_help_layer(
        description="Approximate visible body word count used for thin-content signals.",
        calculation=(
            "Tokenised word count from extracted main content at crawl time; stored numeric "
            "on the row."
        ),
    ),
    "Canonical Type": format_help_layer(
        description="How the declared canonical relates to the crawled URL.",
        calculation=(
            "Classifier output (self / cross-canonical / missing) from canonical tag "
            "analysis; string field on the export row."
        ),
    ),
    "Redirect Chain Length": format_help_layer(
        description="Count of hops before the crawler reached the final URL.",
        calculation=(
            "Integer from redirect tracing during fetch; stored on the row (lower is better)."
        ),
    ),
}


def curated_help_keys_by_sheet() -> dict[str, frozenset[str]]:
    """Canonical header keys that have curated help (for contract tests vs layout tuples)."""
    return {name: frozenset(body.keys()) for name, body in _SHEET_CURATED_HEADER_HELP.items()}


def resolve_curated_help_body(sheet_title: str, header: str) -> str | None:
    """Return curated help text when this sheet/header pair is in the registry.

    Matching is case-sensitive on the stored header text (Excel headers are stable literals).
    Content & AI also maps any header starting with ``Flesch-Kincaid Grade`` to the FK help.
    """
    sheet = (sheet_title or "").strip()
    h = (header or "").strip()
    mapping = _SHEET_CURATED_HEADER_HELP.get(sheet)
    if not mapping:
        return None
    if h in mapping:
        return mapping[h]
    if sheet == "Content & AI Readiness" and h.startswith("Flesch-Kincaid Grade"):
        return mapping.get("Flesch-Kincaid Grade (Est.)")
    return None


def friendly_metric_label(header: str) -> str:
    """Return a user-facing metric label used in validation prompt titles.

    Args:
        header: Raw worksheet header text.

    Returns:
        Cleaned and presentation-friendly label text.
    """
    return (
        header.replace("_", " ")
        .replace("URL", "URL")
        .replace("SEO", "SEO")
        .replace("AEO", "AEO")
        .strip()
    )


def tooltip_for_header(header: str) -> str:
    """Generate contextual tooltip guidance for a header (Description + Calculation)."""
    h = (header or "").strip()
    lower = h.lower()
    label = friendly_metric_label(h)
    if not h:
        return format_help_layer(
            description="Placeholder for an unnamed column in this section.",
            calculation="No formula: bind a header text in row 1 so metrics stay traceable.",
        )
    if "url" in lower:
        return format_help_layer(
            description=f"{label} identifies the audited page for drill-down and hyperlinks.",
            calculation="String URL from the crawl/export row; workbook hyperlinks wrap this value where enabled.",
        )
    if "status code" in lower:
        return format_help_layer(
            description="HTTP response code returned for this page or resource.",
            calculation="Integer status from the crawler HTTP layer; compare to Technical Diagnostics for evidence.",
        )
    if "status class" in lower:
        return format_help_layer(
            description="Bucketed HTTP class (2xx/3xx/4xx/5xx) for fast volume triage.",
            calculation="Derived categorisation from the numeric Status Code field in the pipeline or pivot logic.",
        )
    if "health score" in lower:
        return format_help_layer(
            description="Composite SEO quality score for this URL (higher is better).",
            calculation=(
                "When labelled ``SEO Health Score``, matches ``score_url_health`` "
                "(100 − 25×Critical − 10×Warning − min(10,3×Observation), floored at 0). "
                "Other *Health* columns may use different pipeline blends—see sheet context."
            ),
        )
    if "pass rate" in lower:
        return format_help_layer(
            description="Share of URLs classified as pass for this slice of the crawl.",
            calculation="Pass URL count ÷ crawl denominator (see Dashboard / Summary formulas for the active definition).",
        )
    if "severity" in lower:
        return format_help_layer(
            description="Issue impact level used to prioritise remediation.",
            calculation="Categorical rule output; when aggregated per URL it feeds SEO Health Score deductions.",
        )
    if "priority score" in lower:
        return format_help_layer(
            description="Relative execution priority combining severity and effort.",
            calculation="``SEVERITY_PRIORITY_BASE[severity] + EFFORT_TO_SPRINT_POINTS[effort]`` (see ``workflow_metrics_for_issue``).",
        )
    if "affected count" in lower:
        return format_help_layer(
            description="How many URLs are impacted by this issue row.",
            calculation="Integer rollup from FixPlan / inventory builders counting matching URLs for the issue.",
        )
    if "ttfb" in lower:
        return format_help_layer(
            description="Time to First Byte: server responsiveness signal.",
            calculation="Milliseconds from the first response byte timestamp in the HTTP fetch metrics.",
        )
    if "load time" in lower or "request time" in lower:
        return format_help_layer(
            description="Elapsed time for the page or request path being measured.",
            calculation="Stopwatch-style timing from the crawler session, stored as a numeric field on the row.",
        )
    if "indexability" in lower or "canonical" in lower:
        return format_help_layer(
            description="Indexing and canonical consistency signal for this URL.",
            calculation="Classifier + directive parser outputs (canonical URL, robots, status) merged into the export row.",
        )
    if "meta robots" in lower or "x-robots" in lower:
        return format_help_layer(
            description="Robots directives that influence crawling and indexing.",
            calculation="Parsed header/tag text from the crawl stored verbatim or normalised on the row.",
        )
    if "word count" in lower or "readability" in lower:
        return format_help_layer(
            description="Content depth / readability signal for editorial quality.",
            calculation="Word / readability metrics computed from extracted visible text at crawl time.",
        )
    if "link" in lower or "anchor" in lower:
        return format_help_layer(
            description="Link graph or anchor-quality signal for crawl equity and clarity.",
            calculation="Aggregated from per-URL link extraction (counts, flags, targets) in the pipeline export.",
        )
    if "open in main" in lower or "technical view" in lower or "view details" in lower:
        return format_help_layer(
            description="Navigation helper to jump to the related record on another tab.",
            calculation="Workbook ``HYPERLINK`` or equivalent jump wiring resolved at export time.",
        )
    if "schema" in lower or "json-ld" in lower:
        return format_help_layer(
            description="Structured-data coverage or validation signal.",
            calculation="JSON-LD / microdata parsers populate typed fields (counts, errors) on the crawl row.",
        )
    if "owner" in lower or "sprint" in lower or lower == "status":
        return format_help_layer(
            description="Workflow field for ownership, cadence, or row state.",
            calculation="Editorial / process value (dropdowns may apply); does not change crawl scores until republished.",
        )
    if "section" in lower or "reference tab" in lower:
        return format_help_layer(
            description="Summary grouping or pointer toward a deeper tab.",
            calculation="String label from Summary / inventory builders for navigation context.",
        )
    return format_help_layer(
        description=f"{label}: auxiliary diagnostic field for this worksheet.",
        calculation="See Glossary & Legend and the crawl export schema for the precise field definition.",
    )


def apply_curated_header_tooltips(
    worksheet: Worksheet,
    sheet_title: str,
    *,
    header_row: int = 1,
    only_headers: frozenset[str] | None = None,
) -> None:
    """Attach curated help comments for ``sheet_title`` (single registry entry point)."""
    if _DISABLE_TOOLTIP_COMMENTS:
        return
    author = "hype-frog"
    for col_idx in range(1, worksheet.max_column + 1):
        cell = worksheet.cell(row=header_row, column=col_idx)
        header = str(cell.value or "").strip()
        if not header or (only_headers is not None and header not in only_headers):
            continue
        body = resolve_curated_help_body(sheet_title, header)
        if body is None:
            continue
        title = friendly_metric_label(header)[:32] or "Column"
        _attach_header_comment(cell, f"{title}\n\n{body}", author)


def add_all_header_tooltips(worksheet: Worksheet) -> None:
    """Attach generic header guidance as cell comments on row-one headers.

    Cell comments render above the grid and avoid freeze-pane clipping that affects
    Data Validation input messages.

    Args:
        worksheet: Worksheet where comments are added.
    """
    if _DISABLE_TOOLTIP_COMMENTS:
        return
    headers = header_index(worksheet)
    author = "hype-frog"
    sheet_title = worksheet.title or ""
    for header, col_idx in headers.items():
        cell = worksheet.cell(row=1, column=col_idx)
        title = friendly_metric_label(header)[:32] or "Column"
        curated = resolve_curated_help_body(sheet_title, header)
        body = curated if curated is not None else tooltip_for_header(header)
        text = f"{title}\n\n{body}" if title else body
        _attach_header_comment(cell, text, author)


def add_header_tooltips(worksheet: Worksheet) -> None:
    """Attach specialized schema-focused header tooltips.

    Args:
        worksheet: Worksheet where schema prompts are added.
    """
    # Lazy import avoids import cycle: ``schema`` consumes ``SCHEMA_METADATA_HEADER_TOOLTIP_BODIES``.
    from hype_frog.reporter.sheets.schema import add_schema_header_tooltips

    add_schema_header_tooltips(
        worksheet,
        disable_data_validation=_DISABLE_TOOLTIP_COMMENTS,
        header_index_fn=header_index,
    )


def apply_workflow_status_dropdown(
    worksheet: Worksheet,
    status_col: int,
    *,
    header_row: int = 1,
) -> None:
    """Apply unified workflow status list to a ``Status`` column.

    Permitted values: ``STATUS_OPTIONS`` (To Do, In Progress, In Review, Done).
    """
    if DISABLE_DATA_VALIDATION:
        return
    if status_col <= 0 or worksheet.max_row <= header_row:
        return
    data_start = header_row + 1
    status_dv = DataValidation(
        type="list",
        formula1=status_validation_list_formula(),
        allow_blank=True,
    )
    status_dv.showErrorMessage = True
    status_dv.errorTitle = "Invalid Status"
    status_dv.error = "Select a value from the dropdown list."
    worksheet.add_data_validation(status_dv)
    status_dv.add(
        f"{get_column_letter(status_col)}{data_start}:"
        f"{get_column_letter(status_col)}{worksheet.max_row}"
    )


def apply_status_dropdown(worksheet: Worksheet, status_col: int, *, header_row: int = 1) -> None:
    """Add controlled status dropdown validation for remediation fields."""
    apply_workflow_status_dropdown(worksheet, status_col, header_row=header_row)


def apply_status_dropdown_to_inventory(
    worksheet: Worksheet, *, header_row: int = 1
) -> None:
    """Apply strict status dropdown validation using the sheet's Status column."""
    if DISABLE_DATA_VALIDATION:
        return
    if worksheet.max_row <= header_row:
        return

    headers = header_index(worksheet, header_row)
    status_col = headers.get("Status")
    if status_col is None:
        return

    apply_workflow_status_dropdown(worksheet, status_col, header_row=header_row)


__all__ = [
    "HELP_CALCULATION_PREFIX",
    "HELP_DESCRIPTION_PREFIX",
    "SCHEMA_METADATA_HEADER_TOOLTIP_BODIES",
    "apply_comment_dimensions",
    "apply_workflow_status_dropdown",
    "apply_status_dropdown",
    "apply_status_dropdown_to_inventory",
    "STATUS_OPTIONS",
    "add_all_header_tooltips",
    "add_header_tooltips",
    "curated_help_keys_by_sheet",
    "format_help_layer",
    "friendly_metric_label",
    "resolve_curated_help_body",
    "tooltip_for_header",
]
