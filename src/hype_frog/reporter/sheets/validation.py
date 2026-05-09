from __future__ import annotations

from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from hype_frog.reporter.sheets.config import DISABLE_DATA_VALIDATION
from hype_frog.reporter.sheets.schema import add_schema_header_tooltips
from hype_frog.reporter.sheets.style_helpers import header_index


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
    """Generate contextual tooltip guidance for a header.

    Args:
        header: Raw worksheet header.

    Returns:
        Tooltip text shown by Excel input messages.
    """
    h = (header or "").strip()
    lower = h.lower()
    if not h:
        return "Column descriptor for this worksheet section."
    if "url" in lower:
        return f"{friendly_metric_label(h)}. Use this URL to inspect the page directly or jump to related tabs."
    if "status code" in lower:
        return "HTTP response code returned for this page/resource. Fix: Resolve 4xx/5xx errors and reduce unnecessary redirects."
    if "status class" in lower:
        return "Grouped HTTP class (2xx/3xx/4xx/5xx). Use this to quickly triage crawl health and error concentration."
    if "health score" in lower:
        return "Composite SEO quality score for this URL. Higher is better. Guide: 90+ strong, 70-89 needs tuning, below 70 high priority."
    if "pass rate" in lower:
        return "Share of URLs marked as pass across the crawl. Use together with Error Rate and critical issue counts for decisions."
    if "severity" in lower:
        return "Issue impact level. Fix: Resolve Critical first, then Warning, then improvement opportunities."
    if "priority score" in lower:
        return "Execution priority score combining impact and effort. Fix: Start from highest scores."
    if "affected count" in lower:
        return "How many URLs are impacted by this issue. Larger counts usually indicate template-level or systemic problems."
    if "ttfb" in lower:
        return "Time to First Byte: server responsiveness signal. Fix: optimise backend performance, caching, and CDN usage."
    if "load time" in lower or "request time" in lower:
        return "Page/request speed metric. Fix: optimise assets, server response time, and blocking resources."
    if "indexability" in lower or "canonical" in lower:
        return "Indexing/canonicalization signal. Fix: ensure indexable pages use correct canonicals and non-conflicting directives."
    if "meta robots" in lower or "x-robots" in lower:
        return "Robots directives that influence indexation. Fix: remove unintended noindex/nofollow values on important pages."
    if "word count" in lower or "readability" in lower:
        return "Content quality depth metric. Fix: expand thin content and improve clarity for search intent."
    if "link" in lower or "anchor" in lower:
        return "Link quality and crawl-path metric. Fix: repair broken links and improve internal linking relevance."
    if "open in main" in lower or "technical view" in lower or "view details" in lower:
        return "Navigation helper. Click to jump directly to the related record in another tab."
    if "schema" in lower or "json-ld" in lower:
        return "Structured data signal. Fix: add valid schema types and correct parsing/validation errors."
    if "owner" in lower or "sprint" in lower or "status" == lower:
        return "Workflow management field for planning and tracking remediation progress."
    if "section" in lower or "reference tab" in lower:
        return "Summary grouping/navigation field. Use with hyperlinks to jump into detailed tabs."
    return f"{friendly_metric_label(h)}. Review this metric to identify risk, then use linked tabs for details and remediation."


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
    for header, col_idx in headers.items():
        cell = worksheet.cell(row=1, column=col_idx)
        title = friendly_metric_label(header)[:32] or "Column"
        body = tooltip_for_header(header)
        text = f"{title}\n\n{body}" if title else body
        cell.comment = Comment(text, author)


def add_header_tooltips(worksheet: Worksheet) -> None:
    """Attach specialized schema-focused header tooltips.

    Args:
        worksheet: Worksheet where schema prompts are added.
    """
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
    "friendly_metric_label",
    "tooltip_for_header",
    "add_all_header_tooltips",
    "add_header_tooltips",
    "apply_status_dropdown",
    "apply_status_dropdown_to_inventory",
]
