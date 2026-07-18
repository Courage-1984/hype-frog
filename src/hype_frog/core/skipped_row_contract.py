"""Row contract for non-scorable (skipped) crawl rows — blank content fields, never fake zeros."""

from __future__ import annotations

from typing import Any, MutableMapping

from hype_frog.core.models import EXTRA_ROW_DEFAULTS, MAIN_ROW_DEFAULTS
from hype_frog.rules.scoring import scorable_extraction_state

# Transport, enrichment, discovery, workflow, and composite scores stay populated when
# extraction is skipped; HTML-derived content metrics must be blank (None), not 0/False.
_UNMEASURED_PRESERVE_KEYS: frozenset[str] = frozenset(
    {
        "URL",
        "Extraction State",
        "Extraction Source",
        "Extraction Source Fallback",
        "skip_reason",
        "Status Code",
        "Load Time (s)",
        "Final URL",
        "Protocol",
        "Redirect Chain Length",
        "Redirect Target",
        "Redirect Hops",
        "Redirect Chain",
        "Redirect Chain Hops",
        "Has 302 in Chain",
        "Has Mixed Redirect Types",
        "Redirect Loop Flag",
        "Redirect SEO Risk",
        "Canonical Chain Depth",
        "Canonical Chain Final",
        "Canonical Chain",
        "Canonical Loop Detected",
        "Canonical Points to Redirect",
        "Canonical Points to Non-200",
        "HTTP->HTTPS Redirect",
        "Status Class",
        "TTFB (ms)",
        "Total Request Time (ms)",
        "Content-Type",
        "HTTP Version",
        "HTML Size (KB)",
        "Compression Enabled",
        "Cache-Control",
        "ETag",
        "Last-Modified",
        "X-Robots-Tag",
        "Strict-Transport-Security",
        "Content-Security-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Robots.txt Accessible",
        "Sitemap in Robots.txt",
        "Robots.txt Crawl-Delay",
        "Robots.txt Disallow /",
        "Robots.txt: Googlebot",
        "Robots.txt: Bingbot",
        "Robots.txt: GPTBot",
        "Robots.txt: ClaudeBot",
        "Robots.txt: PerplexityBot",
        "Crawl-Delay Applies",
        "AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)",
        "llms.txt Present",
        "AEO Robots AI Bot Coverage",
        "JS Dependent",
        "Raw Words",
        "Rendered Words",
        "Field LCP (ms)",
        "Field CLS",
        "Param URL Flag",
        "URL Depth",
        "Crawl Depth",
        "Change Frequency",
        "Priority",
        "Last Updated",
        "Sitemap Image Count",
        "Sitemap First Image",
        "GSC Clicks",
        "GSC Impressions",
        "GSC CTR",
        "GSC Avg Position",
        "GSC Data Freshness",
        "GSC Coverage Note",
        "GSC Inspection Coverage",
        "GSC Inspection Verdict",
        "GSC Inspection Coverage State",
        "GSC Inspection Google Canonical",
        "GSC Inspection Crawl State",
        "GSC Inspection Robots State",
        "GSC Inspection Last Crawl",
        "GSC Index Status",
        "GSC Last Crawl Date",
        "GSC Mobile Usability",
        "GSC Rich Result Status",
        "GSC Coverage Reason",
        "Days Since Last Crawl",
        "Click Depth",
        "Orphan Pages",
        "Reachable from Homepage",
        "Internal PageRank",
        "Internal Inlinks",
        "Found via Sitemap",
        "Found via Crawl",
        "Discovery Source",
        "Discovered On URL",
        "Discovery Rank",
        "SEO Health Score",
        "Severity Badge",
        "Health Icon",
        "Critical Issues Count",
        "Warning Issues Count",
        "Observation Issues Count",
        "Matched Issues",
        "AEO Readiness Score",
        "AEO Badge",
        "Technical Health",
        "Copy Score",
        "SEO Score",
        "Action Needed",
        "PSI Data Status",
        "Desktop PSI Score",
        "Mobile PSI Score",
        "Mobile LCP (s)",
        "Mobile CLS",
        "Mobile TTFB (s)",
        "CWV LCP (s)",
        "CWV CLS",
        "CWV INP (ms)",
        "CWV FCP (ms)",
        "CWV TTFB (ms)",
        "CrUX Level",
        "CrUX LCP Category",
        "CrUX CLS Category",
        "CrUX INP Category",
        "Origin CrUX LCP (s)",
        "Origin CrUX CLS",
        "Origin CrUX INP (ms)",
        "Field vs Lab",
        "CWV Data Source",
        "Owner",
        "Sprint",
        "Status",
        "Stable Issue IDs",
        "WordPress Post ID",
        "Search Intent",
        "Search Intent Source",
        "Content Cluster ID",
        "Indexability",
        "Indexability Reason",
        "Internal Links List Full",
        "Internal Links List",
        "Link Details",
        "Nav Footer Link Details",
        "aeo_snippets",
    }
)

UNMEASURED_CONTENT_FIELD_KEYS: frozenset[str] = frozenset(
    key
    for key in set(MAIN_ROW_DEFAULTS) | set(EXTRA_ROW_DEFAULTS)
    if key not in _UNMEASURED_PRESERVE_KEYS
)


def apply_skipped_row_contract(
    main_values: MutableMapping[str, Any],
    extra_values: MutableMapping[str, Any],
) -> None:
    """Null out HTML-derived content fields when extraction did not run."""
    state = main_values.get("Extraction State") or extra_values.get("Extraction State")
    if scorable_extraction_state(state):
        return
    for mapping in (main_values, extra_values):
        for key in UNMEASURED_CONTENT_FIELD_KEYS:
            if key in mapping:
                mapping[key] = None


__all__ = [
    "UNMEASURED_CONTENT_FIELD_KEYS",
    "apply_skipped_row_contract",
]
