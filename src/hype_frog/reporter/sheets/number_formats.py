from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet


def apply_south_african_formats(worksheet: Worksheet) -> None:
    """Apply South African locale number/date formats based on header semantics.

    Args:
        worksheet: Worksheet whose data rows should be locale-formatted.
    """
    percent_headers: set[str] = {
        "Pass Rate (%)",
        "SEO Pass Rate %",
        "Error Rate % (4xx/5xx)",
        "Crawl Success Rate % (2xx)",
        "Critical URL Rate %",
        "Warning URL Rate %",
        "Pass Rate",
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
    }
    decimal_headers: set[str] = {
        "SEO Health Score",
        "AEO Readiness Score",
        "Flesch-Kincaid Grade (Est.)",
        "AEO Robots AI Bot Coverage",
        "TTFB (ms)",
        "Total Request Time (ms)",
        "Avg TTFB (ms)",
    }
    date_like_tokens: tuple[str, ...] = ("date", "timestamp", "lastmod", "updated")

    for col_idx, cell in enumerate(worksheet[1], start=1):
        header = str(cell.value or "").strip()
        rng_start = 2
        rng_end = worksheet.max_row
        if rng_end < rng_start:
            continue
        if header in percent_headers or "%" in header:
            fmt = "[$-en-ZA]0.00%"
        elif header in decimal_headers:
            fmt = "[$-en-ZA]#,##0.00"
        elif header in integer_headers:
            fmt = "[$-en-ZA]#,##0"
        elif any(token in header.lower() for token in date_like_tokens):
            fmt = "[$-en-ZA]dd/mm/yyyy hh:mm:ss"
        else:
            continue
        for row_idx in range(rng_start, rng_end + 1):
            worksheet.cell(row=row_idx, column=col_idx).number_format = fmt


__all__ = ["apply_south_african_formats"]
