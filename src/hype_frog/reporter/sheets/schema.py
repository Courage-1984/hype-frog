from __future__ import annotations

from collections.abc import Callable

from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet


def add_schema_header_tooltips(
    worksheet: Worksheet,
    *,
    disable_data_validation: bool,
    header_index_fn: Callable[[Worksheet], dict[str, int]],
) -> None:
    if disable_data_validation:
        return
    author = "hype-frog"
    tooltip_messages = {
        "TTFB (ms)": "Time to First Byte. Measures server responsiveness. Fix: Optimise server-side code or use a CDN.",
        "AEO Readiness Score": "Composite Answer Engine Optimisation quality score. Fix: Add concise answer sections, FAQ schema, and clear question headings.",
        "Indexability Reason": "Primary reason this URL may not be indexed. Fix: Resolve noindex directives, non-200 responses, and canonical mismatches.",
        "Status Code": "HTTP status returned for the URL. Fix: Resolve 4xx/5xx errors and remove unnecessary redirect chains.",
        "SEO Health Score": "Weighted technical SEO quality score for this URL. Fix: Prioritize critical issues and improve warnings in FixPlan.",
        "Priority Score": "Issue priority score for execution order. Fix: Start with the highest values to reduce risk fastest.",
        "Severity": "Impact level of the issue. Fix: Resolve Critical first, then Warning, then Observation opportunities.",
        "Word Count": "Approximate body word count depth. Fix: Expand thin pages with original, search-intent-aligned content.",
        "Canonical Type": "Canonical relationship classification. Fix: Use self-canonical on indexable pages; avoid unintended cross-canonicals.",
        "Redirect Chain Length": "Number of redirect hops before final destination. Fix: Reduce to a single hop where possible.",
    }
    headers = header_index_fn(worksheet)
    for header, message in tooltip_messages.items():
        col_idx = headers.get(header)
        if not col_idx:
            continue
        cell = worksheet.cell(row=1, column=col_idx)
        text = f"{header}\n\n{message}"
        cell.comment = Comment(text, author)
