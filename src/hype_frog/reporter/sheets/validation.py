from __future__ import annotations

from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from hype_frog.reporter.sheets.config import DISABLE_DATA_VALIDATION
from hype_frog.reporter.sheets.style_helpers import header_index

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

_SHEET_CURATED_HEADER_HELP: dict[str, dict[str, str]] = {
    "Content & AI Readiness": _CONTENT_AI_READINESS_HELP,
    "Technical Diagnostics": _TECHNICAL_DIAGNOSTICS_HELP,
    "Link Intelligence": _LINK_INTELLIGENCE_HELP,
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


def add_all_header_tooltips(worksheet: Worksheet) -> None:
    """Attach generic header guidance as cell comments on row-one headers.

    Cell comments render above the grid and avoid freeze-pane clipping that affects
    Data Validation input messages.

    Args:
        worksheet: Worksheet where comments are added.
    """
    if DISABLE_DATA_VALIDATION:
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
        disable_data_validation=DISABLE_DATA_VALIDATION,
        header_index_fn=header_index,
    )


def apply_status_dropdown(worksheet: Worksheet, status_col: int) -> None:
    """Add controlled status dropdown validation for remediation fields.

    Args:
        worksheet: Worksheet to update.
        status_col: 1-based column index for the ``Status`` field.
    """
    if DISABLE_DATA_VALIDATION:
        return
    if status_col <= 0 or worksheet.max_row <= 1:
        return
    status_dv = DataValidation(
        type="list", formula1='"To Do,In Progress,Fixed"', allow_blank=True
    )
    worksheet.add_data_validation(status_dv)
    status_dv.add(
        f"{get_column_letter(status_col)}2:{get_column_letter(status_col)}{worksheet.max_row}"
    )


def apply_status_dropdown_to_inventory(worksheet: Worksheet) -> None:
    """Apply strict status dropdown validation using the sheet's Status column.

    Args:
        worksheet: Target worksheet (for example FixPlan or IssueInventory).
    """
    if DISABLE_DATA_VALIDATION:
        return
    if worksheet.max_row <= 1:
        return

    headers = header_index(worksheet)
    status_col = headers.get("Status")
    if status_col is None:
        return

    status_dv = DataValidation(
        type="list",
        formula1='"Open,In Progress,In Review,Done"',
        allow_blank=True,
    )
    status_dv.showErrorMessage = True
    status_dv.errorTitle = "Invalid Status"
    status_dv.error = "Select a value from the dropdown list."
    worksheet.add_data_validation(status_dv)
    status_dv.add(
        f"{get_column_letter(status_col)}2:{get_column_letter(status_col)}{worksheet.max_row}"
    )


__all__ = [
    "HELP_CALCULATION_PREFIX",
    "HELP_DESCRIPTION_PREFIX",
    "SCHEMA_METADATA_HEADER_TOOLTIP_BODIES",
    "apply_comment_dimensions",
    "apply_status_dropdown",
    "apply_status_dropdown_to_inventory",
    "add_all_header_tooltips",
    "add_header_tooltips",
    "curated_help_keys_by_sheet",
    "format_help_layer",
    "friendly_metric_label",
    "resolve_curated_help_body",
    "tooltip_for_header",
]
