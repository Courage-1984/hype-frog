from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from hype_frog.analysis.delta_engine import (  # noqa: F401 — re-exported public API
    BASELINE_DELTA_NOTE,
    IssueRecord,
    RunSnapshot,
    build_delta_sheet_rows,
    build_delta_workbook_output,
    build_resolved_issues_dataframe,
    delta_summary_path_for_workbook,
    load_run_snapshot,
    save_run_snapshot_json,
    snapshot_from_current_run,
)
from hype_frog.core.models import ExtraRowPayload
from hype_frog.core.status_codes import is_success_status
from hype_frog.rules import IssueRule
from hype_frog.core.text_utils import normalize_text_hash
from hype_frog.core.url_normalization import normalize_url_key
from hype_frog.orchestration.crawl_runner import (
    ExcludedCmsActionUrl,
    cms_action_exclusion_keys,
)
from hype_frog.reporter.sheets.config import (
    AIOSEO_RECOMMENDATIONS_SHEET,
    ANCHOR_TEXT_AUDIT_SHEET,
    AUDIT_RUN_DETAILS_SHEET,
    CONTENT_HUB_METRICS_SHEET,
    CONTENT_OPTIMISATION_HUB_SHEET,
    CONTENT_PLANNER_SHEET,
    COMPETITOR_BENCHMARKS_SHEET,
    CRAWL_LOG_SHEET,
    IMAGE_INVENTORY_SHEET,
    LINK_EQUITY_MAP_SHEET,
    REDIRECT_MAP_SHEET,
    ROBOTS_ANALYSIS_SHEET,
    SCRIPT_INVENTORY_SHEET,
    SNIPPET_OPPORTUNITIES_SHEET,
)
from hype_frog.analysis.link_equity import ANCHOR_TEXT_AUDIT_COLUMNS, LINK_EQUITY_COLUMNS
from hype_frog.analysis.snippet_opportunities import SNIPPET_OPPORTUNITY_COLUMNS
from hype_frog.analysis.third_party_scripts import SCRIPT_INVENTORY_COLUMNS
from hype_frog.pipeline.image_inventory import IMAGE_INVENTORY_COLUMNS
from hype_frog.crawler.robots_mapping import ROBOTS_ANALYSIS_COLUMNS
from hype_frog.core.crawl_log import CRAWL_LOG_COLUMNS
from hype_frog.reporter.sheets.merged_builders import (
    BROKEN_LINK_IMPACT_COLUMNS,
    CONTENT_AI_READINESS_COLUMNS,
    ISSUE_REGISTER_COLUMNS,
    LINK_INTELLIGENCE_COLUMNS,
    LINK_INVENTORY_COLUMNS,
    QUICK_WINS_COLUMNS,
    REDIRECT_MAP_COLUMNS,
    TECHNICAL_DIAGNOSTICS_COLUMNS,
    TEMPLATE_DUPLICATION_RISKS_COLUMNS,
)

@dataclass(frozen=True)
class ExportRegistryConfig:
    full_suite: bool


STANDARD_SHEET_COLUMNS: dict[str, list[str]] = {
    "Schema & Metadata": [
        "URL", "Schema Types Found", "Schema Types Count", "Schema Parse Errors",
        "OG Title", "OG Description", "OG Type", "OG URL", "OG Image", "OG Image URL",
        "OG Image Width", "OG Image Height", "OG Image OK", "OG Completeness Score",
        "Open Graph Complete", "Twitter Card Type", "Twitter Title", "Twitter Description",
        "Twitter Image",
    ],
    AIOSEO_RECOMMENDATIONS_SHEET: [
        "URL", "WordPress Post ID", "Direct Edit Link", "AIOSEO Panel", "Severity",
        "Issue", "Current Value", "Recommended Target", "Why It Matters", "How to Fix in AIOSEO",
        "Reference Tab", "Reference Field", "Action Needed", "Owner", "Status",
        "Priority Score", "Est. Hours", "Stable Issue ID",
    ],
    "Redirects": [
        "URL",
        "Status Code",
        "Final URL",
        "Redirect Chain",
        "Redirect Chain Length",
        "Redirect Chain Hops",
        "Has 302 in Chain",
        "Has Mixed Redirect Types",
        "Redirect Target",
        "Redirect Hops",
        "HTTP->HTTPS Redirect",
        "Redirect Loop Flag",
        "Redirect SEO Risk",
    ],
    REDIRECT_MAP_SHEET: list(REDIRECT_MAP_COLUMNS),
    ROBOTS_ANALYSIS_SHEET: list(ROBOTS_ANALYSIS_COLUMNS),
    CRAWL_LOG_SHEET: list(CRAWL_LOG_COLUMNS),
}

CMS_ACTION_URLS_SHEET = "CMS Action URLs"
CMS_ACTION_URLS_COLUMNS: list[str] = [
    "URL",
    "Excluded Query Parameters",
    "Exclusion Reason",
    "Discovered On URL",
    "Review Note",
]

_FULL_SUITE_FORMAT_SHEETS: list[str] = [
    "Executive Briefing",
    "Summary",
    "Priority URLs",
    "FixPlan",
    "Quick Wins",
    CONTENT_OPTIMISATION_HUB_SHEET,
    CONTENT_PLANNER_SHEET,
    CONTENT_HUB_METRICS_SHEET,
    "Main",
    AIOSEO_RECOMMENDATIONS_SHEET,
    "Link Inventory",
    "Broken Link Impact",
    "SitemapQA",
    "Template & Duplication Risks",
    "Playbook",
    "Issue Register",
    "Technical Diagnostics",
    "Content & AI Readiness",
    "Link Intelligence",
    CMS_ACTION_URLS_SHEET,
    "Redirects",
    REDIRECT_MAP_SHEET,
    ROBOTS_ANALYSIS_SHEET,
    CRAWL_LOG_SHEET,
    LINK_EQUITY_MAP_SHEET,
    ANCHOR_TEXT_AUDIT_SHEET,
    SNIPPET_OPPORTUNITIES_SHEET,
    SCRIPT_INVENTORY_SHEET,
    IMAGE_INVENTORY_SHEET,
    COMPETITOR_BENCHMARKS_SHEET,
    "ResolvedIssues",
    "DeltaFromPreviousRun",
    AUDIT_RUN_DETAILS_SHEET,
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
        "Quick Wins": list(QUICK_WINS_COLUMNS),
        "Broken Link Impact": list(BROKEN_LINK_IMPACT_COLUMNS),
        "Template & Duplication Risks": list(TEMPLATE_DUPLICATION_RISKS_COLUMNS),
        REDIRECT_MAP_SHEET: list(REDIRECT_MAP_COLUMNS),
        ROBOTS_ANALYSIS_SHEET: list(ROBOTS_ANALYSIS_COLUMNS),
        CRAWL_LOG_SHEET: list(CRAWL_LOG_COLUMNS),
        LINK_EQUITY_MAP_SHEET: list(LINK_EQUITY_COLUMNS),
        ANCHOR_TEXT_AUDIT_SHEET: list(ANCHOR_TEXT_AUDIT_COLUMNS),
        SNIPPET_OPPORTUNITIES_SHEET: list(SNIPPET_OPPORTUNITY_COLUMNS),
        SCRIPT_INVENTORY_SHEET: list(SCRIPT_INVENTORY_COLUMNS),
        IMAGE_INVENTORY_SHEET: list(IMAGE_INVENTORY_COLUMNS),
    }


def get_finalization_steps() -> tuple[str, ...]:
    return ("apply_tab_hyperlinks", "format_sheets", "apply_workbook_export_guardrails")


def build_cms_action_url_rows(
    crawl_exclusions: tuple[ExcludedCmsActionUrl, ...],
    extra_rows: list[dict[str, Any]],
) -> list[dict[str, object]]:
    """Merge crawl-time CMS exclusions with internal links seen on crawled pages."""
    registry: dict[str, ExcludedCmsActionUrl] = {
        item.url: item for item in crawl_exclusions
    }
    for row in extra_rows:
        parent_url = str(row.get("URL") or "").strip()
        links = row.get("Internal Links List Full") or []
        if not isinstance(links, list):
            continue
        for link in links:
            normalized = normalize_url_key(link)
            if not normalized or normalized in registry:
                continue
            keys = cms_action_exclusion_keys(normalized)
            if not keys:
                continue
            registry[normalized] = ExcludedCmsActionUrl(
                url=normalized,
                excluded_query_params=tuple(sorted(keys)),
                discovered_on_url=parent_url or "Internal link",
            )
    rows: list[dict[str, object]] = []
    for item in sorted(registry.values(), key=lambda entry: entry.url):
        rows.append(
            {
                "URL": item.url,
                "Excluded Query Parameters": ", ".join(item.excluded_query_params),
                "Exclusion Reason": item.exclusion_reason,
                "Discovered On URL": item.discovered_on_url,
                "Review Note": (
                    "Listed for audit visibility only; not crawled as a standalone page. "
                    "Confirm cart/checkout handlers and canonical targets in WooCommerce or CMS settings."
                ),
            }
        )
    return rows


def build_duplicates_rows(
    main_rows: list[dict[str, Any]],
    extra_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    title_groups: defaultdict[str, list[str]] = defaultdict(list)
    desc_groups: defaultdict[str, list[str]] = defaultdict(list)
    for row in main_rows:
        title_key = normalize_text_hash(row.get("Title"))
        desc_key = normalize_text_hash(row.get("Meta Description"))
        if title_key:
            title_groups[title_key].append(str(row.get("URL") or ""))
        if desc_key:
            desc_groups[desc_key].append(str(row.get("URL") or ""))

    extra_by_url: dict[str, dict[str, Any]] = {}
    if extra_rows:
        for row in extra_rows:
            url = str(row.get("URL") or "").strip()
            if url:
                extra_by_url[url] = row
    duplicate_rows: list[dict[str, Any]] = []
    for row in main_rows:
        url = str(row.get("URL") or "")
        title_key = normalize_text_hash(row.get("Title"))
        desc_key = normalize_text_hash(row.get("Meta Description"))
        title_urls = title_groups.get(title_key, []) if title_key else []
        desc_urls = desc_groups.get(desc_key, []) if desc_key else []
        extra = extra_by_url.get(url, {})
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
                "Draft Page Flag": extra.get("Draft Page Flag"),
                "Probable Duplicate Flag": extra.get("Probable Duplicate Flag"),
                "Duplicate Of URL": extra.get("Duplicate Of URL"),
                "Content Similarity %": extra.get("Content Similarity %"),
                "Heading Structure Cluster Size": extra.get("Heading Structure Cluster Size"),
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
        badge = str(row.get("Severity Badge") or "").strip()
        seo_raw = row.get("SEO Health Score")
        health_penalty = 0.0
        if (
            badge != "Unmeasured"
            and seo_raw is not None
            and str(seo_raw).strip() != ""
        ):
            health_penalty = 100 - value_or_default_fn(seo_raw, 100.0)
        risk_score = (
            value_or_default_fn(row.get("Critical Issues Count"), 0.0) * 30
            + value_or_default_fn(row.get("Warning Issues Count"), 0.0) * 10
            + health_penalty
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
        seo_display = row.get("SEO Health Score")
        if badge == "Unmeasured" or seo_display is None or str(seo_display).strip() == "":
            seo_health_out: float | None = None
        else:
            seo_health_out = round(value_or_default_fn(seo_display, 0.0), 2)
        try:
            _discovery_rank = int(float(row.get("Discovery Rank")))
        except (TypeError, ValueError):
            _discovery_rank = 10**9
        priority_rows.append(
            {
                "URL": row.get("URL"),
                "Business Risk Score": int(risk_score),
                # Sort-only field, popped before return — not a visible column.
                "Discovery Rank": _discovery_rank,
                "SEO Health Score": seo_health_out,
                "Severity Badge": row.get("Severity Badge"),
                "Critical Issues Count": row.get("Critical Issues Count"),
                "Warning Issues Count": row.get("Warning Issues Count"),
                "Indexability Reason": row.get("Indexability Reason"),
                "Broken Internal Links Count": row.get("Broken Internal Links Count"),
                "Canonical Type": row.get("Canonical Type"),
                "GSC Impressions": row.get("GSC Impressions", 0.0),
                "GSC CTR": round(value_or_default_fn(row.get("GSC CTR"), 0.0), 4),
                "GSC Data Freshness": row.get("GSC Data Freshness"),
                "GSC Coverage Note": row.get("GSC Coverage Note"),
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
    priority_rows.sort(
        key=lambda item: (-item["Business Risk Score"], item["Discovery Rank"])
    )
    for item in priority_rows:
        item.pop("Discovery Rank", None)
    return priority_rows


def build_delta_and_trend_rows(
    *,
    issue_inventory_df: pd.DataFrame,
    typed_extra_rows: list[ExtraRowPayload],
    summary_rules: list[IssueRule],
    prev_issue_ids: set[str],
    prev_fixed_issue_ids: set[str],
    prev_counts: dict[str, int],
    previous_issue_inventory_df: pd.DataFrame,
    baseline_report: bool = False,
    previous_snapshot: RunSnapshot | None = None,
    main_rows: list[dict[str, Any]] | None = None,
    extra_rows: list[dict[str, Any]] | None = None,
    output_path: str = "",
    run_date: str | None = None,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    if previous_snapshot is not None or (main_rows is not None and extra_rows is not None):
        delta_rows, resolved_df, _snapshot = build_delta_workbook_output(
            issue_inventory_df=issue_inventory_df,
            main_rows=main_rows or [],
            extra_rows=extra_rows or [],
            summary_rules=summary_rules,
            previous_snapshot=previous_snapshot,
            baseline_report=baseline_report,
            output_path=output_path,
            run_date=run_date,
        )
        return delta_rows, resolved_df

    current_snapshot = snapshot_from_current_run(
        issue_inventory_df=issue_inventory_df,
        main_rows=[],
        extra_rows=[row.values for row in typed_extra_rows],
        source_path=output_path,
        run_date=run_date,
    )
    if baseline_report:
        return (
            build_delta_sheet_rows(
                current=current_snapshot,
                previous=None,
                baseline_report=True,
                summary_rules=summary_rules,
            ),
            build_resolved_issues_dataframe(
                current=current_snapshot,
                previous=None,
                baseline_report=True,
            ),
        )

    previous = RunSnapshot(
        run_date=run_date or "",
        source_path="legacy-compare",
        issues={},
        issue_counts_by_name=dict(prev_counts),
        fixed_issue_ids=set(prev_fixed_issue_ids),
    )
    if (
        not previous_issue_inventory_df.empty
        and "Stable Issue ID" in previous_issue_inventory_df.columns
    ):
        for _, row in previous_issue_inventory_df.iterrows():
            stable_id = str(row.get("Stable Issue ID") or "").strip()
            if not stable_id:
                continue
            previous.issues[stable_id] = IssueRecord(
                stable_issue_id=stable_id,
                url=str(row.get("URL") or "").strip(),
                issue=str(row.get("Issue") or "").strip(),
                severity=str(row.get("Severity") or "").strip(),
                last_seen=previous.run_date or None,
            )
    for stable_id in prev_issue_ids:
        previous.issues.setdefault(
            stable_id,
            IssueRecord(
                stable_issue_id=stable_id,
                url="",
                issue="",
                severity="",
                last_seen=previous.run_date or None,
            ),
        )

    return (
        build_delta_sheet_rows(
            current=current_snapshot,
            previous=previous,
            baseline_report=False,
            summary_rules=summary_rules,
        ),
        build_resolved_issues_dataframe(
            current=current_snapshot,
            previous=previous,
            baseline_report=False,
        ),
    )


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
    sitemap_files_meta: dict[str, dict[str, Any]] | None = None,
    extra_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sitemap_rows: list[dict[str, Any]] = []
    empty_row = {
        "Record Type": "",
        "Sitemap URL": "No Sitemap data available for this run.",
        "Final URL": "",
        "Status Code": "",
        "Found via Crawl": "",
        "Found via Sitemap": "",
        "Discovery Source": "",
        "In Sitemap but Non-200": "",
        "Sitemap URL Redirects": "",
        "Redirect Type": "",
        "In Sitemap but Canonicalized Elsewhere": "",
        "Missing <lastmod>": "",
        "Missing <changefreq>": "",
        "Missing <priority>": "",
        "Sitemap <lastmod>": "",
        "Sitemap <changefreq>": "",
        "Sitemap <priority>": "",
        "Sitemap Image Count": "",
        "Sitemap First Image": "",
        "Source Sitemap": "",
        "Sitemap Kind": "",
        "Sitemap URL Count": "",
        "Sitemap Size (KB)": "",
        "Lastmod vs HTTP Match": "",
        "Canonical vs Sitemap Match": "",
        "Crawled but Missing from Sitemap": "",
    }
    if not sitemap_meta and not sitemap_files_meta:
        return [empty_row]

    def _normalize_date(value: object) -> str:
        text = str(value or "").strip()
        return text[:10] if text else ""

    def _lastmod_match(sitemap_lastmod: object, http_lastmod: object) -> str:
        sitemap_day = _normalize_date(sitemap_lastmod)
        http_day = _normalize_date(http_lastmod)
        if not sitemap_day or not http_day:
            return "Unknown"
        return "Match" if sitemap_day == http_day else "Mismatch"

    def _canonical_match(sitemap_url: str, matched: dict[str, Any] | None) -> str:
        if not matched:
            return "Unknown"
        canonical = str(matched.get("Canonical URL") or matched.get("URL") or "").strip()
        if not canonical:
            return "Unknown"
        return (
            "Match"
            if normalize_url_key(canonical) == normalize_url_key(sitemap_url)
            else "Mismatch"
        )

    sitemap_url_keys = {normalize_url_key(url) for url in sitemap_meta.keys()}

    for file_url, file_meta in (sitemap_files_meta or {}).items():
        size_kb = round(float(file_meta.get("size_bytes") or 0) / 1024.0, 1)
        sitemap_rows.append(
            {
                "Record Type": "Sitemap File",
                "Sitemap URL": file_url,
                "Final URL": "",
                "Status Code": "",
                "Found via Crawl": "",
                "Found via Sitemap": True,
                "Discovery Source": "Sitemap",
                "In Sitemap but Non-200": "",
                "Sitemap URL Redirects": "",
                "Redirect Type": "",
                "In Sitemap but Canonicalized Elsewhere": "",
                "Missing <lastmod>": "",
                "Missing <changefreq>": "",
                "Missing <priority>": "",
                "Sitemap <lastmod>": "",
                "Sitemap <changefreq>": "",
                "Sitemap <priority>": "",
                "Sitemap Image Count": "",
                "Sitemap First Image": "",
                "Source Sitemap": file_url,
                "Sitemap Kind": file_meta.get("kind"),
                "Sitemap URL Count": file_meta.get("url_count"),
                "Sitemap Size (KB)": size_kb,
                "Lastmod vs HTTP Match": "",
                "Canonical vs Sitemap Match": "",
                "Crawled but Missing from Sitemap": "",
            }
        )

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
                "Record Type": "Sitemap URL",
                "Sitemap URL": sitemap_url,
                "Final URL": final_url,
                "Status Code": status_code,
                "Found via Crawl": bool(matched),
                "Found via Sitemap": True,
                "Discovery Source": "Both" if matched else "Sitemap",
                "In Sitemap but Non-200": not is_success_status(status_code),
                "Sitemap URL Redirects": (
                    matched.get("Redirect Chain Length", 0) > 0 if matched else None
                ),
                "Redirect Type": matched.get("Redirect SEO Risk") if matched else None,
                "In Sitemap but Canonicalized Elsewhere": (
                    matched.get("Canonical Type") == "cross-canonical" if matched else None
                ),
                "Missing <lastmod>": not bool(meta.get("lastmod")),
                "Missing <changefreq>": not bool(meta.get("changefreq")),
                "Missing <priority>": not bool(meta.get("priority")),
                "Sitemap <lastmod>": meta.get("lastmod"),
                "Sitemap <changefreq>": meta.get("changefreq"),
                "Sitemap <priority>": meta.get("priority"),
                "Sitemap Image Count": meta.get("image_count", 0),
                "Sitemap First Image": meta.get("first_image_url"),
                "Source Sitemap": meta.get("source_sitemap"),
                "Sitemap Kind": meta.get("sitemap_kind"),
                "Sitemap URL Count": "",
                "Sitemap Size (KB)": "",
                "Lastmod vs HTTP Match": _lastmod_match(
                    meta.get("lastmod"),
                    matched.get("HTTP Last-Modified") if matched else None,
                ),
                "Canonical vs Sitemap Match": _canonical_match(sitemap_url, matched),
                "Crawled but Missing from Sitemap": False,
            }
        )

    for row in extra_rows:
        url = str(row.get("URL") or "").strip()
        if not url:
            continue
        if normalize_url_key(url) in sitemap_url_keys:
            continue
        if not is_success_status(row.get("Status Code")):
            continue
        sitemap_rows.append(
            {
                "Record Type": "Crawled URL",
                "Sitemap URL": url,
                "Final URL": row.get("Final URL"),
                "Status Code": row.get("Status Code"),
                "Found via Crawl": True,
                "Found via Sitemap": False,
                "Discovery Source": "Crawl",
                "In Sitemap but Non-200": False,
                "Sitemap URL Redirects": row.get("Redirect Chain Length", 0) > 0,
                "Redirect Type": row.get("Redirect SEO Risk"),
                "In Sitemap but Canonicalized Elsewhere": (
                    row.get("Canonical Type") == "cross-canonical"
                ),
                "Missing <lastmod>": "",
                "Missing <changefreq>": "",
                "Missing <priority>": "",
                "Sitemap <lastmod>": "",
                "Sitemap <changefreq>": "",
                "Sitemap <priority>": "",
                "Sitemap Image Count": "",
                "Sitemap First Image": "",
                "Source Sitemap": "",
                "Sitemap Kind": "",
                "Sitemap URL Count": "",
                "Sitemap Size (KB)": "",
                "Lastmod vs HTTP Match": "",
                "Canonical vs Sitemap Match": "",
                "Crawled but Missing from Sitemap": True,
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

