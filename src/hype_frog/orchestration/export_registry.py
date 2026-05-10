from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from hype_frog.core.models import ExtraRowPayload
from hype_frog.core.text_utils import normalize_text_hash
from hype_frog.core.url_normalization import normalize_url
from hype_frog.reporter.sheets.merged_builders import (
    CONTENT_AI_READINESS_COLUMNS,
    ISSUE_REGISTER_COLUMNS,
    LINK_INTELLIGENCE_COLUMNS,
    LINK_INVENTORY_COLUMNS,
    TECHNICAL_DIAGNOSTICS_COLUMNS,
    TEMPLATE_DUPLICATION_RISKS_COLUMNS,
)


def normalize_url_key(url: object, keep_query: bool = True) -> str:
    return normalize_url(url, keep_query=keep_query)


@dataclass(frozen=True)
class ExportRegistryConfig:
    full_suite: bool


STANDARD_SHEET_COLUMNS: dict[str, list[str]] = {
    "Technical": [
        "URL", "Content Cluster ID", "Extraction State", "Extraction Source",
        "Health Icon", "Severity Badge", "SEO Health Score", "SEO Score",
        "Technical Health", "Copy Score", "Action Needed", "Owner", "Sprint",
        "Status", "Status Code", "Final URL", "Protocol", "Redirect Chain Length",
        "Redirect Target", "Redirect Hops", "HTTP->HTTPS Redirect", "Status Class",
        "TTFB (ms)", "Total Request Time (ms)", "Content-Type", "HTTP Version",
        "HTML Size (KB)", "Compression Enabled", "Cache-Control", "ETag",
        "X-Robots-Tag", "Content-Security-Policy", "Meta Robots Raw", "Canonical URL",
        "Canonical Matches Final URL", "Canonical Type", "Canonical Absolute URL",
        "Canonical in Sitemap Match", "Hreflang Present", "Hreflang Count",
        "Hreflang Self Reference", "Hreflang Reciprocal Check",
        "Hreflang Canonical Consistency", "x-default Present", "Pagination rel=next",
        "Pagination rel=prev", "Last-Modified", "Published Date", "Modified Date",
        "Last Updated", "Change Frequency", "Priority", "Indexability Reason",
        "Schema Types Count", "Schema Types Found", "Internal Links Count",
        "Unique Internal Links Count", "External Links Count",
        "AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)",
        "AEO Robots AI Bot Coverage",
        "llms.txt Present",
        "Desktop PSI Score", "Mobile PSI Score", "Mobile LCP (s)", "Mobile CLS",
        "Mobile TTFB (s)", "CWV LCP (s)", "CWV CLS", "CWV Data Source",
        "Field vs Lab", "GSC Clicks", "GSC Impressions", "GSC CTR",
        "GSC Avg Position", "Click Depth", "Internal Inlinks", "Orphan Pages",
        "Internal PageRank", "Regional Authority Score", "Regional Entity Hits",
        "Answer Block Detected (First 60 Words)", "AEO Extractability Score",
        "Critical Issues Count", "Warning Issues Count", "Observation Issues Count",
        "Inlinks Bucket", "Important But Underlinked", "SERP Title Truncation Risk",
        "SERP Meta Truncation Risk", "SERP Title Pixel Approx", "SERP Meta Pixel Approx",
        "Cannibalization Hint", "Stable Issue IDs", "URL Depth", "Param URL Flag",
    ],
    "Content": [
        "URL", "H1 Count", "Missing H1 Flag", "Multiple H1 Flag", "Title Missing",
        "Meta Description Missing", "Word Count", "Word Count Band", "Sentence Count",
        "Body Text-to-HTML Ratio", "Readability (Rough Flesch)", "Flesch-Kincaid Grade (Est.)",
        "Thin Content Flag",
    ],
    "Links": [
        "URL", "Internal Links Count", "Unique Internal Links Count", "External Links Count",
        "Nofollow Internal Links Count", "Nofollow External Links Count",
        "Generic Anchor Text Count", "Broken Internal Links Count",
        "Unresolved Internal Links Count", "Internal Link Statuses",
    ],
    "Media": [
        "URL", "Image Count", "Images", "Images Missing Alt", "Image Alt Coverage (%)",
        "Image Extension Distribution", "Likely Large Image Count", "Image Filename Quality Issues",
        "Image On Canonical Domain (%)", "Mixed Content Detected",
    ],
    "Schema & Metadata": [
        "URL", "Schema Types Found", "Schema Types Count", "Schema Parse Errors",
        "OG Title", "OG Description", "OG Image", "Open Graph Complete", "Twitter Card Type",
    ],
    "AEO": [
        "URL", "AEO Badge", "AEO Readiness Score", "Why It Matters", "FAQ Section Count",
        "Question Heading Count", "QAPage/FAQ Schema Present", "Speakable Schema Present",
        "HowTo Signal", "Definition Signal", "List/Table Answer Signal",
        "Paragraphs 40-60 Words Count", "Answer Block Detected (First 60 Words)",
        "AEO Extractability Score", "Snippet Preview Mockup", "Title Missing",
        "Meta Description Missing",
    ],
    "AIOSEO": [
        "URL", "WordPress Post ID", "Direct Edit Link", "AIOSEO Panel", "Severity",
        "Issue", "Current Value", "Recommended Target", "Why It Matters", "How to Fix in AIOSEO",
        "Reference Tab", "Reference Field", "Action Needed", "Owner", "Status",
        "Priority Score", "Est. Hours", "Stable Issue ID",
    ],
    "Security": [
        "URL", "Strict-Transport-Security", "Content-Security-Policy", "X-Content-Type-Options",
        "X-Frame-Options", "Referrer-Policy", "Permissions-Policy", "Robots.txt Accessible",
        "Sitemap in Robots.txt", "Robots.txt Crawl-Delay", "Robots.txt Disallow /",
    ],
    "Indexability": [
        "URL", "Status Code", "Status Class", "Final URL", "Indexability Reason",
        "Meta Robots Raw", "X-Robots-Tag", "Canonical URL", "Canonical Type",
        "Canonical Matches Final URL", "Canonical in Sitemap Match",
    ],
    "Redirects": [
        "URL", "Status Code", "Final URL", "Redirect Chain Length", "Redirect Target",
        "Redirect Hops", "HTTP->HTTPS Redirect", "Redirect Loop Flag",
    ],
}

_FULL_SUITE_FORMAT_SHEETS: list[str] = [
    "Dashboard",
    "FixPlan",
    "Priority URLs",
    "Content Optimisation Hub",
    "Issue Register",
    "Technical Diagnostics",
    "Content & AI Readiness",
    "Link Intelligence",
    "Link Inventory",
    "Template & Duplication Risks",
    "Playbook",
    # Deep-audit tail (far right)
    "AIOSEO",
    "SitemapQA",
    "ResolvedIssues",
    "DeltaFromPreviousRun",
    "RunMetadata",
    "Main",
]

_BASE_SHEETS: list[str] = ["Main"]


def get_sheet_sequence(config: ExportRegistryConfig) -> list[str]:
    if not config.full_suite:
        return list(_BASE_SHEETS)
    return list(_FULL_SUITE_FORMAT_SHEETS)


def get_standard_sheet_columns() -> dict[str, list[str]]:
    return {name: list(columns) for name, columns in STANDARD_SHEET_COLUMNS.items()}


def get_merged_sheet_columns() -> dict[str, list[str]]:
    return {
        "Issue Register": list(ISSUE_REGISTER_COLUMNS),
        "Technical Diagnostics": list(TECHNICAL_DIAGNOSTICS_COLUMNS),
        "Content & AI Readiness": list(CONTENT_AI_READINESS_COLUMNS),
        "Link Intelligence": list(LINK_INTELLIGENCE_COLUMNS),
        "Link Inventory": list(LINK_INVENTORY_COLUMNS),
        "Template & Duplication Risks": list(TEMPLATE_DUPLICATION_RISKS_COLUMNS),
    }


def get_finalization_steps() -> tuple[str, ...]:
    return ("apply_tab_hyperlinks", "format_sheets", "apply_workbook_export_guardrails")


def build_duplicates_rows(main_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    title_groups: defaultdict[str, list[str]] = defaultdict(list)
    desc_groups: defaultdict[str, list[str]] = defaultdict(list)
    for row in main_rows:
        title_key = normalize_text_hash(row.get("Title"))
        desc_key = normalize_text_hash(row.get("Meta Description"))
        if title_key:
            title_groups[title_key].append(str(row.get("URL") or ""))
        if desc_key:
            desc_groups[desc_key].append(str(row.get("URL") or ""))

    duplicate_rows: list[dict[str, Any]] = []
    for row in main_rows:
        title_key = normalize_text_hash(row.get("Title"))
        desc_key = normalize_text_hash(row.get("Meta Description"))
        title_urls = title_groups.get(title_key, []) if title_key else []
        desc_urls = desc_groups.get(desc_key, []) if desc_key else []
        duplicate_rows.append(
            {
                "URL": row.get("URL"),
                "Title Duplicate Count": len(title_urls),
                "Meta Description Duplicate Count": len(desc_urls),
                "Title Duplicate URLs": " | ".join(title_urls)
                if len(title_urls) > 1
                else None,
                "Meta Duplicate URLs": " | ".join(desc_urls)
                if len(desc_urls) > 1
                else None,
            }
        )
    return duplicate_rows


def build_pattern_rows(
    extra_rows: list[dict[str, Any]],
    *,
    extract_subfolder_fn: Callable[[str], str],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    folder_groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in extra_rows:
        folder = extract_subfolder_fn(str(row.get("Final URL") or row.get("URL") or ""))
        folder_groups[folder].append(row)

    cluster_rows: list[dict[str, Any]] = []
    template_issue_counts: defaultdict[str, defaultdict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for folder, urls_in_group in sorted(
        folder_groups.items(), key=lambda item: len(item[1]), reverse=True
    ):
        if not urls_in_group:
            continue
        url_count = len(urls_in_group)
        missing_h1_count = sum(1 for row in urls_in_group if bool(row.get("Missing H1 Flag")))
        missing_meta_count = sum(
            1 for row in urls_in_group if bool(row.get("Meta Description Missing"))
        )

        systemic_issue: str | None = None
        exact_action: str | None = None
        if (missing_h1_count / max(1, url_count)) >= 0.8:
            systemic_issue = "Missing H1 is template-wide"
            exact_action = (
                "Update template to render exactly one descriptive H1 for each page based on "
                "page-specific title data."
            )
        elif (missing_meta_count / max(1, url_count)) >= 0.8:
            systemic_issue = "Missing meta description is template-wide"
            exact_action = (
                "Update template/meta generation logic to output a unique 120-160 character "
                "meta description per page."
            )
        if systemic_issue:
            cluster_rows.append(
                {
                    "Subfolder": folder,
                    "URL Count": url_count,
                    "Systemic Issue": systemic_issue,
                    "Affected Ratio": round(
                        (max(missing_h1_count, missing_meta_count) / max(1, url_count))
                        * 100,
                        2,
                    ),
                    "Exact Action": exact_action,
                }
            )
        for row in urls_in_group:
            for issue in str(row.get("Matched Issues") or "").split(" | "):
                if issue:
                    template_issue_counts[folder][issue] += 1

    if not cluster_rows:
        cluster_rows = [
            {
                "Subfolder": "/",
                "URL Count": 0,
                "Systemic Issue": "No systemic template issues above 80%.",
                "Affected Ratio": 0,
                "Exact Action": "N/A",
            }
        ]
    return cluster_rows, {
        folder: dict(issue_counts) for folder, issue_counts in template_issue_counts.items()
    }


def build_priority_rows(
    extra_rows: list[dict[str, Any]],
    *,
    high_value_slugs: list[str],
    value_or_default_fn: Callable[[object, float], float],
    owner_for_issue_fn: Callable[[str, str], str],
) -> list[dict[str, Any]]:
    priority_rows: list[dict[str, Any]] = []
    for row in extra_rows:
        risk_score = (
            value_or_default_fn(row.get("Critical Issues Count"), 0.0) * 30
            + value_or_default_fn(row.get("Warning Issues Count"), 0.0) * 10
            + (100 - value_or_default_fn(row.get("SEO Health Score"), 100.0))
        )
        reasons: list[str] = []
        if value_or_default_fn(row.get("Critical Issues Count"), 0.0) > 0:
            reasons.append("Has critical issues")
        if (row.get("Broken Internal Links Count") or 0) > 0:
            reasons.append("Broken internal links")
        if row.get("Canonical Type") == "cross-canonical":
            reasons.append("Cross canonical")
        if "noindex" in str(row.get("Indexability Reason", "")).lower():
            reasons.append("Noindex")
        owner_seed_issue = (
            "Broken Internal Links"
            if (row.get("Broken Internal Links Count") or 0) > 0
            else "Canonical Points Elsewhere"
            if row.get("Canonical Type") == "cross-canonical"
            else "Noindex Directive"
            if "noindex" in str(row.get("Indexability Reason", "")).lower()
            else ""
        )
        url_value = str(row.get("URL") or "")
        revenue_intent = (
            "High"
            if any(slug in url_value.lower() for slug in high_value_slugs)
            else "Standard"
        )
        priority_rows.append(
            {
                "URL": row.get("URL"),
                "Business Risk Score": int(risk_score),
                "SEO Health Score": round(
                    value_or_default_fn(row.get("SEO Health Score"), 0.0), 2
                ),
                "Severity Badge": row.get("Severity Badge"),
                "Critical Issues Count": row.get("Critical Issues Count"),
                "Warning Issues Count": row.get("Warning Issues Count"),
                "Indexability Reason": row.get("Indexability Reason"),
                "Broken Internal Links Count": row.get("Broken Internal Links Count"),
                "Canonical Type": row.get("Canonical Type"),
                "GSC Impressions": row.get("GSC Impressions", 0.0),
                "GSC CTR": round(value_or_default_fn(row.get("GSC CTR"), 0.0), 4),
                "Revenue Intent": revenue_intent,
                "Why Prioritized": " | ".join(reasons) if reasons else "Monitor",
                "Action Needed": "Yes" if risk_score >= 30 else "No",
                "Owner": owner_for_issue_fn(
                    owner_seed_issue, str(row.get("Severity Badge") or "")
                ),
                "Sprint": "",
                "Status": "Open",
            }
        )
    return sorted(
        priority_rows, key=lambda item: item["Business Risk Score"], reverse=True
    )


def build_delta_and_trend_rows(
    *,
    issue_inventory_df: pd.DataFrame,
    typed_extra_rows: list[ExtraRowPayload],
    summary_rules: list[tuple[str, str, str]],
    prev_issue_ids: set[str],
    prev_fixed_issue_ids: set[str],
    prev_counts: dict[str, int],
    previous_issue_inventory_df: pd.DataFrame,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    current_issue_ids = {
        str(value).strip()
        for value in issue_inventory_df.get("Stable Issue ID", pd.Series(dtype="object"))
        .dropna()
        .tolist()
        if str(value).strip()
    }
    resolved_issues = prev_issue_ids - current_issue_ids
    delta_rows: list[dict[str, Any]] = [
        {"Metric": "New Issues", "Count": len(current_issue_ids - prev_issue_ids)},
        {"Metric": "Resolved Issues", "Count": len(resolved_issues)},
        {"Metric": "Unchanged Issues", "Count": len(current_issue_ids & prev_issue_ids)},
        {
            "Metric": "Previously Fixed But Reopened",
            "Count": len(current_issue_ids & prev_fixed_issue_ids),
        },
    ]
    for _, issue_name, _ in summary_rules:
        current_count = len(
            [
                row
                for row in typed_extra_rows
                if issue_name in str(row.values.get("Matched Issues") or "").split(" | ")
            ]
        )
        delta_rows.append(
            {
                "Metric": f"Issue Delta: {issue_name}",
                "Count": current_count - int(prev_counts.get(issue_name, 0)),
            }
        )

    if (
        not previous_issue_inventory_df.empty
        and "Stable Issue ID" in previous_issue_inventory_df.columns
    ):
        resolved_issues_df = previous_issue_inventory_df.copy()
        resolved_issues_df["Stable Issue ID"] = (
            resolved_issues_df["Stable Issue ID"].astype(str).str.strip()
        )
        resolved_issues_df = resolved_issues_df[
            resolved_issues_df["Stable Issue ID"].isin(resolved_issues)
        ].copy()
    else:
        resolved_issues_df = pd.DataFrame(columns=["Stable Issue ID"])
    if resolved_issues_df.empty:
        resolved_issues_df = pd.DataFrame(
            [
                {
                    "Stable Issue ID": "",
                    "Issue": "No resolved issues identified for this comparison run.",
                    "URL": "",
                }
            ]
        )
    return delta_rows, resolved_issues_df


def build_schema_and_snippets_rows(
    *,
    extra_rows: list[dict[str, Any]],
    build_aeo_rows_fn: Callable[[list[dict[str, object]]], list[dict[str, object]]],
) -> dict[str, list[dict[str, Any]]]:
    psi_rows = [
        {
            "URL": row.get("URL"),
            "Desktop Score": row.get("Desktop PSI Score", 0),
            "Mobile Score": row.get("Mobile PSI Score", 0),
            "Mobile LCP": row.get("Mobile LCP (s)", 0.0),
            "Mobile CLS": row.get("Mobile CLS", 0.0),
            "Mobile TTFB": row.get("Mobile TTFB (s)", 0.0),
        }
        for row in extra_rows
    ]
    aeo_rows = build_aeo_rows_fn(extra_rows)
    return {
        "AEO": aeo_rows,
        "PSI Performance": psi_rows,
    }


def build_crawlgraph_rows(
    *,
    main_urls: list[str],
    extra_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    crawl_inlinks_map: defaultdict[str, set[str]] = defaultdict(set)
    crawled_set_main = {normalize_url_key(url) for url in main_urls if url}
    for row in extra_rows:
        source = normalize_url_key(row.get("URL"))
        for target in row.get("Internal Links List", []):
            target_norm = normalize_url_key(target)
            if target_norm in crawled_set_main:
                crawl_inlinks_map[target_norm].add(source)
    return [
        {
            "URL": url_item,
            "Inlinks Count": len(
                inlinks := sorted(list(crawl_inlinks_map.get(normalize_url_key(url_item), set())))
            ),
            "Inlinks URLs": " | ".join(inlinks) if inlinks else None,
            "Orphan Candidate": len(inlinks) == 0,
            "Click Depth": next(
                (
                    row.get("Click Depth")
                    for row in extra_rows
                    if normalize_url_key(row.get("URL")) == normalize_url_key(url_item)
                ),
                None,
            ),
            "Internal PageRank": round(
                float(
                    next(
                        (
                            row.get("Internal PageRank")
                            for row in extra_rows
                            if normalize_url_key(row.get("URL"))
                            == normalize_url_key(url_item)
                        ),
                        0.0,
                    )
                    or 0.0
                ),
                6,
            ),
        }
        for url_item in main_urls
    ]


def build_sitemapqa_rows(
    *,
    sitemap_meta: dict[str, dict[str, Any]],
    extra_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sitemap_rows: list[dict[str, Any]] = []
    if not sitemap_meta:
        return [
            {
                "Sitemap URL": "No Sitemap data available for this run.",
                "Final URL": "",
                "Status Code": "",
                "Found via Crawl": "",
                "Found via Sitemap": "",
                "Discovery Source": "",
                "In Sitemap but Non-200": "",
                "Sitemap URL Redirects": "",
                "In Sitemap but Canonicalized Elsewhere": "",
                "Missing <lastmod>": "",
                "Missing <changefreq>": "",
                "Missing <priority>": "",
                "Sitemap <lastmod>": "",
                "Sitemap <changefreq>": "",
                "Sitemap <priority>": "",
                "Source Sitemap": "",
            }
        ]
    for sitemap_url, meta in sitemap_meta.items():
        matched = next(
            (
                row
                for row in extra_rows
                if normalize_url_key(row.get("URL", "")) == normalize_url_key(sitemap_url)
            ),
            None,
        )
        final_url = matched.get("Final URL") if matched else None
        status_code = matched.get("Status Code") if matched else None
        sitemap_rows.append(
            {
                "Sitemap URL": sitemap_url,
                "Final URL": final_url,
                "Status Code": status_code,
                "Found via Crawl": bool(matched),
                "Found via Sitemap": True,
                "Discovery Source": "Both" if matched else "Sitemap",
                "In Sitemap but Non-200": status_code != 200,
                "Sitemap URL Redirects": (
                    matched.get("Redirect Chain Length", 0) > 0 if matched else None
                ),
                "In Sitemap but Canonicalized Elsewhere": (
                    matched.get("Canonical Type") == "cross-canonical" if matched else None
                ),
                "Missing <lastmod>": not bool(meta.get("lastmod")),
                "Missing <changefreq>": not bool(meta.get("changefreq")),
                "Missing <priority>": not bool(meta.get("priority")),
                "Sitemap <lastmod>": meta.get("lastmod"),
                "Sitemap <changefreq>": meta.get("changefreq"),
                "Sitemap <priority>": meta.get("priority"),
                "Source Sitemap": meta.get("source_sitemap"),
            }
        )
    return sitemap_rows


__all__ = [
    "ExportRegistryConfig",
    "get_finalization_steps",
    "get_sheet_sequence",
    "get_standard_sheet_columns",
    "get_merged_sheet_columns",
    "build_delta_and_trend_rows",
    "build_duplicates_rows",
    "build_pattern_rows",
    "build_priority_rows",
    "build_schema_and_snippets_rows",
    "build_crawlgraph_rows",
    "build_sitemapqa_rows",
]

