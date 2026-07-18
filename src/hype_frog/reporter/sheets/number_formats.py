from __future__ import annotations

from datetime import datetime

from dateutil import parser as date_parser
from openpyxl.worksheet.worksheet import Worksheet

from hype_frog.reporter.sheets.config import CONTENT_OPTIMISATION_HUB_SHEET
from hype_frog.reporter.sheets.layout import resolve_content_hub_header_row


def _parsed_date_or_original(value: object) -> object:
    """Return ``value`` parsed to a ``datetime`` when possible, else unchanged.

    Date-like fields arrive from extraction as raw strings in whatever format
    the source gave (ISO 8601 with an offset from schema/meta tags, RFC 2822
    from the HTTP ``Last-Modified`` header, plain ``YYYY-MM-DD`` from a
    sitemap). Excel only honours ``number_format`` on numeric/date-typed
    cells — a string cell displays its literal text regardless of format — so
    without this conversion the format below is silently a no-op and the
    different source formats read inconsistently side by side. Parsing here
    (not in the extractor) keeps the extractor's raw-string contract intact
    (see ``tests/extractors/test_freshness.py``) — this only changes what the
    *worksheet cell* holds, never the underlying pipeline row.
    """
    if not isinstance(value, str) or not value.strip():
        return value
    try:
        parsed = date_parser.parse(value)
    except (ValueError, OverflowError, TypeError):
        return value
    # openpyxl/Excel datetimes are naive local values; a tz-aware datetime
    # would serialize incorrectly, so drop the offset after parsing it.
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return parsed


def apply_south_african_formats(worksheet: Worksheet, *, header_row: int = 1) -> None:
    """Apply South African locale number/date formats based on header semantics.

    Args:
        worksheet: Worksheet whose data rows should be locale-formatted.
        header_row: 1-based row holding column headers. Most data sheets carry
            a row-1 "Return to Executive Briefing" banner, so real headers live
            on row 2 (see ``sheet_data_header_row``) — reading the wrong row
            silently matches nothing and this whole function becomes a no-op.
            Ignored for the Content Optimisation Hub, whose header row is
            resolved self-correctingly (see ``resolve_content_hub_header_row``)
            because it physically moves from row 1 to row 2 partway through
            ``adjust_sheet_format``, independently of the caller's banner state.
    """
    if worksheet.title == CONTENT_OPTIMISATION_HUB_SHEET:
        header_row = resolve_content_hub_header_row(worksheet)
    # Columns whose cells hold FRACTIONS (0–1): Excel's `%` code multiplies the
    # displayed value by 100, so only true fractions belong here.
    percent_headers: set[str] = {
        "Pass Rate (%)",
        "SEO Pass Rate %",
        "Error Rate % (4xx/5xx)",
        "Crawl Success Rate % (2xx)",
        "Critical URL Rate %",
        "Warning URL Rate %",
        "Pass Rate",
        "GSC CTR",
    }
    # Columns whose cells already hold PERCENT-POINTS (0–100). These need a
    # literal "%" suffix — a real percent code would display them 100x too big
    # (the "Entity Density 5758%" regression).
    literal_percent_headers: set[str] = {
        "Entity Density (%)",
        "Image Alt Coverage (%)",
        "Image On Canonical Domain (%)",
        "Content Similarity %",
        "Generic Inbound Anchor %",
        "Keyword Density (%)",
    }
    integer_headers: set[str] = {
        "URLs Crawled",
        "Value",
        "Critical URL Count",
        "Warning URL Count",
        "Pass URLs",
        "Critical URLs",
        "Warning URLs",
        "Top Issue Affected URLs",
        "Affected Count",
        "Priority Score",
        "Est. Sprint Points",
        "Potential Traffic Lift",
        "Page Size (KB)",
        "DOM Size",
        "Citation Candidate Count",
        "Desktop PSI Score",
        "Mobile PSI Score",
        "Lighthouse Performance (Mobile)",
        "Lighthouse Accessibility (Mobile)",
        "Lighthouse Best Practices (Mobile)",
        "Lighthouse SEO Score (Mobile)",
    }
    decimal_headers: set[str] = {
        "SEO Health Score",
        "AEO Readiness Score",
        "Flesch-Kincaid Grade (Est.)",
        "AEO Robots AI Bot Coverage",
        "TTFB (ms)",
        "Total Request Time (ms)",
        "Avg TTFB (ms)",
        "CWV LCP (s)",
        "CWV CLS",
        "CWV INP (ms)",
        "CWV FCP (ms)",
        "CWV TTFB (ms)",
        "Origin CrUX LCP (s)",
        "Origin CrUX CLS",
        "Origin CrUX INP (ms)",
        "Mobile LCP (s)",
        "Mobile CLS",
        "Mobile TTFB (s)",
        "Lab LCP (Mobile) (s)",
        "Lab CLS (Mobile)",
        "Lab TBT (Mobile) (ms)",
        "Semantic AEO Score",
        "AEO Visibility Gain",
        "ROI Score",
    }
    explicit_date_headers: set[str] = {
        "GSC Last Crawl Date",
        "Schema Published Date",
        "Schema Modified Date",
        "HTTP Last-Modified",
        "Sitemap <lastmod>",
        "Published Date",
        "Last Modified Date",
    }

    for col_idx, cell in enumerate(worksheet[header_row], start=1):
        header = str(cell.value or "").strip()
        rng_start = header_row + 1
        rng_end = worksheet.max_row
        if rng_end < rng_start:
            continue
        if header in percent_headers:
            fmt = "[$-en-ZA]0.00%"
        elif header in literal_percent_headers or "%" in header:
            # Percent-point columns (0–100): literal % suffix, no x100.
            fmt = '[$-en-ZA]0.00"%"'
        elif header in decimal_headers:
            fmt = "[$-en-ZA]#,##0.00"
        elif header in integer_headers:
            fmt = "[$-en-ZA]#,##0"
        elif header in explicit_date_headers:
            fmt = "[$-en-ZA]dd/mm/yyyy hh:mm:ss"
        else:
            continue
        is_date = header in explicit_date_headers
        for row_idx in range(rng_start, rng_end + 1):
            data_cell = worksheet.cell(row=row_idx, column=col_idx)
            if is_date:
                data_cell.value = _parsed_date_or_original(data_cell.value)
                if not isinstance(data_cell.value, datetime):
                    continue
            data_cell.number_format = fmt


__all__ = ["apply_south_african_formats"]
