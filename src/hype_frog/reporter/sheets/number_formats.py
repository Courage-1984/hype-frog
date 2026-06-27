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
        "Entity Density (%)",
        "Image Alt Coverage (%)",
        "GSC CTR",
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
    }

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
        elif header in explicit_date_headers:
            fmt = "[$-en-ZA]dd/mm/yyyy hh:mm:ss"
        else:
            continue
        for row_idx in range(rng_start, rng_end + 1):
            worksheet.cell(row=row_idx, column=col_idx).number_format = fmt


__all__ = ["apply_south_african_formats"]
