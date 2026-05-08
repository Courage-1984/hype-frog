from __future__ import annotations

import asyncio
import os
import sys
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd

from hype_frog.config import (
    DEFAULT_EFFORT_BY_SEVERITY,
    DEFAULT_OWNER_BY_SEVERITY,
    MAX_RETRIES,
    TIMEOUT_SECONDS,
)
from hype_frog.core import get_logger
from hype_frog.core.run_config import RunConfig
from hype_frog.orchestration.crawl_runner import execute_crawl
from hype_frog.orchestration.enrichment_flow import run_enrichment
from hype_frog.orchestration.run_setup import resolve_run_setup
from hype_frog.pipeline.enrich import value_or_default as _value_or_default_pipeline
from hype_frog.pipeline.export import sanitize_rows, to_excel_safe
from hype_frog.reporter import adjust_sheet_format, apply_tab_hyperlinks
from hype_frog.reporter.excel_engine import (
    apply_workbook_export_guardrails,
    build_content_optimisation_hub_rows,
    build_fixplan_rows,
    write_dict_rows_sheet,
)
from hype_frog.reporter.sheets.config import CONTENT_OPTIMISATION_HUB_SHEET
from hype_frog.reporter.summary_builder import (
    build_issue_inventory_rows,
    build_summary_rows,
)
from hype_frog.rules import (
    get_summary_rules,
    owner_for_issue,
    root_cause_and_fix,
    stable_issue_id,
    workflow_metrics_for_issue,
)
from hype_frog.utils import (
    normalize_text_hash,
    normalize_url_key,
)

logger = get_logger(__name__)


def _normalize_url_key(url: object) -> str:
    return normalize_url_key(url)


def _extract_subfolder(url: str) -> str:
    parsed = urlparse(str(url or ""))
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    return f"/{parts[0]}/" if parts else "/"


def _value_or_default(value: object, default: float = 0.0) -> float:
    return _value_or_default_pipeline(value, default)


async def main(run: RunConfig | None = None) -> None:
    setup = resolve_run_setup(run)
    crawl_result = await execute_crawl(setup)
    output_filename = crawl_result.output_filename
    main_rows = crawl_result.main_rows
    extra_rows = crawl_result.extra_rows
    urls = crawl_result.crawl_urls
    sitemap_meta = crawl_result.sitemap_meta
    workers = crawl_result.workers
    request_delay = crawl_result.request_delay
    full_suite = crawl_result.full_suite
    previous_audit_path = crawl_result.previous_audit_path
    checkpoint_every = crawl_result.checkpoint_every
    high_value_slugs = setup.high_value_slugs
    enrichment_result = await run_enrichment(crawl_result)
    main_rows = enrichment_result.main_rows
    extra_rows = enrichment_result.extra_rows
    status_by_url = enrichment_result.status_by_url
    sitemap_url_keys = enrichment_result.sitemap_url_keys

    main_df = pd.DataFrame(main_rows)
    main_by_url = {
        str(r.get("URL") or "").strip(): r for r in main_rows if r.get("URL")
    }
    summary_rules = get_summary_rules()

    prev_issue_ids: set[str] = set()
    prev_counts: dict[str, int] = {}
    prev_fixed_issue_ids: set[str] = set()
    previous_issue_inventory_df = pd.DataFrame()
    previous_audit_exists = bool(previous_audit_path) and os.path.exists(
        previous_audit_path
    )
    if previous_audit_exists:
        try:
            prev_xls = pd.ExcelFile(previous_audit_path)
            if "IssueInventory" in prev_xls.sheet_names:
                previous_issue_inventory_df = pd.read_excel(
                    previous_audit_path, sheet_name="IssueInventory"
                )
                if "Stable Issue ID" in previous_issue_inventory_df.columns:
                    prev_issue_ids = {
                        str(v).strip()
                        for v in previous_issue_inventory_df["Stable Issue ID"]
                        .dropna()
                        .tolist()
                        if str(v).strip()
                    }
                    if "Status" in previous_issue_inventory_df.columns:
                        prev_fixed_issue_ids = {
                            str(row.get("Stable Issue ID")).strip()
                            for _, row in previous_issue_inventory_df.iterrows()
                            if str(row.get("Stable Issue ID", "")).strip()
                            and str(row.get("Status", "")).strip().lower()
                            in {"fixed", "done", "closed"}
                        }
                else:
                    logger.warning(
                        "Previous audit IssueInventory is missing 'Stable Issue ID'. "
                        "Delta compare will mark all current issues as New."
                    )
            else:
                logger.warning(
                    "Previous audit is missing 'IssueInventory'. "
                    "Delta compare will mark all current issues as New."
                )
            if "Summary" in prev_xls.sheet_names:
                prev_summary = pd.read_excel(
                    previous_audit_path, sheet_name="Summary"
                )
                for _, srow in prev_summary.iterrows():
                    if str(srow.get("Section", "")) == "Issue Counts":
                        prev_counts[str(srow.get("Issue", ""))] = int(
                            srow.get("Affected URL Count", 0) or 0
                        )
        except Exception as exc:
            logger.warning("Could not parse previous audit for compare: %s", exc)
            prev_issue_ids = set()
            prev_counts = {}
            prev_fixed_issue_ids = set()
            previous_issue_inventory_df = pd.DataFrame()
    elif previous_audit_path:
        logger.warning(
            "Previous audit file not found: %s. Delta compare will mark all current issues as New.",
            previous_audit_path,
        )

    main_rows = sanitize_rows(main_rows)
    extra_rows = sanitize_rows(extra_rows)
    writer = None
    try:
        writer = pd.ExcelWriter(output_filename, engine="openpyxl")
        main_cols = list(main_rows[0].keys()) if main_rows else []
        write_dict_rows_sheet(writer, "Main", main_cols, main_rows)
        adjust_sheet_format(writer, "Main")
        if full_suite:
            technical_cols = [
                "URL",
                "Content Cluster ID",
                "Extraction State",
                "Extraction Source",
                "Health Icon",
                "Severity Badge",
                "SEO Health Score",
                "SEO Score",
                "Technical Health",
                "Copy Score",
                "Action Needed",
                "Owner",
                "Sprint",
                "Status",
                "Status Code",
                "Final URL",
                "Protocol",
                "Redirect Chain Length",
                "Redirect Target",
                "Redirect Hops",
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
                "X-Robots-Tag",
                "Content-Security-Policy",
                "Meta Robots Raw",
                "Canonical URL",
                "Canonical Matches Final URL",
                "Canonical Type",
                "Canonical Absolute URL",
                "Canonical in Sitemap Match",
                "Hreflang Present",
                "Hreflang Count",
                "Hreflang Self Reference",
                "Hreflang Reciprocal Check",
                "Hreflang Canonical Consistency",
                "x-default Present",
                "Pagination rel=next",
                "Pagination rel=prev",
                "Last-Modified",
                "Published Date",
                "Modified Date",
                "Last Updated",
                "Change Frequency",
                "Priority",
                "Indexability Reason",
                "Schema Types Count",
                "Schema Types Found",
                "Internal Links Count",
                "Unique Internal Links Count",
                "External Links Count",
                "AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)",
                "llms.txt Present",
                "Desktop PSI Score",
                "Mobile PSI Score",
                "Mobile LCP (s)",
                "Mobile CLS",
                "Mobile TTFB (s)",
                "CWV LCP (s)",
                "CWV CLS",
                "CWV Data Source",
                "Field vs Lab",
                "GSC Clicks",
                "GSC Impressions",
                "GSC CTR",
                "GSC Avg Position",
                "Click Depth",
                "Internal Inlinks",
                "Orphan Pages",
                "Internal PageRank",
                "Regional Authority Score",
                "Regional Entity Hits",
                "Answer Block Detected (First 60 Words)",
                "AEO Extractability Score",
                "Critical Issues Count",
                "Warning Issues Count",
                "Observation Issues Count",
                "Inlinks Bucket",
                "Important But Underlinked",
                "SERP Title Truncation Risk",
                "SERP Meta Truncation Risk",
                "SERP Title Pixel Approx",
                "SERP Meta Pixel Approx",
                "Cannibalization Hint",
                "Stable Issue IDs",
                "URL Depth",
                "Param URL Flag",
            ]
            content_cols = [
                "URL",
                "H1 Count",
                "Missing H1 Flag",
                "Multiple H1 Flag",
                "Title Missing",
                "Meta Description Missing",
                "Word Count",
                "Word Count Band",
                "Sentence Count",
                "Body Text-to-HTML Ratio",
                "Readability (Rough Flesch)",
                "Thin Content Flag",
            ]
            links_cols = [
                "URL",
                "Internal Links Count",
                "Unique Internal Links Count",
                "External Links Count",
                "Nofollow Internal Links Count",
                "Nofollow External Links Count",
                "Generic Anchor Text Count",
                "Broken Internal Links Count",
                "Unresolved Internal Links Count",
                "Internal Link Statuses",
            ]
            media_cols = [
                "URL",
                "Image Count",
                "Images",
                "Images Missing Alt",
                "Image Alt Coverage (%)",
                "Image Extension Distribution",
                "Likely Large Image Count",
                "Image Filename Quality Issues",
                "Image On Canonical Domain (%)",
                "Mixed Content Detected",
            ]
            schema_cols = [
                "URL",
                "Schema Types Found",
                "Schema Types Count",
                "Schema Parse Errors",
                "OG Title",
                "OG Description",
                "OG Image",
                "Open Graph Complete",
                "Twitter Card Type",
            ]
            aeo_cols = [
                "URL",
                "AEO Badge",
                "AEO Readiness Score",
                "Why It Matters",
                "FAQ Section Count",
                "Question Heading Count",
                "QAPage/FAQ Schema Present",
                "Speakable Schema Present",
                "HowTo Signal",
                "Definition Signal",
                "List/Table Answer Signal",
                "Paragraphs 40-60 Words Count",
                "Answer Block Detected (First 60 Words)",
                "AEO Extractability Score",
                "Snippet Preview Mockup",
                "Title Missing",
                "Meta Description Missing",
            ]
            security_cols = [
                "URL",
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
            ]
            write_dict_rows_sheet(writer, "Technical", technical_cols, extra_rows)
            write_dict_rows_sheet(writer, "Content", content_cols, extra_rows)
            write_dict_rows_sheet(writer, "Links", links_cols, extra_rows)
            write_dict_rows_sheet(writer, "Media", media_cols, extra_rows)
            write_dict_rows_sheet(
                writer, "Schema & Metadata", schema_cols, extra_rows
            )
            aeo_rows = _build_aeo_rows(extra_rows)
            write_dict_rows_sheet(writer, "AEO", aeo_cols, aeo_rows)
            aioseo_rows = _build_aioseo_rows(
                extra_rows, main_by_url, DEFAULT_OWNER_BY_SEVERITY
            )
            aioseo_cols = [
                "URL",
                "WordPress Post ID",
                "Direct Edit Link",
                "AIOSEO Panel",
                "Severity",
                "Issue",
                "Current Value",
                "Recommended Target",
                "Why It Matters",
                "How to Fix in AIOSEO",
                "Reference Tab",
                "Reference Field",
                "Action Needed",
                "Owner",
                "Status",
                "Priority Score",
                "Est. Hours",
                "Stable Issue ID",
            ]
            write_dict_rows_sheet(writer, "AIOSEO", aioseo_cols, aioseo_rows)
            write_dict_rows_sheet(writer, "Security", security_cols, extra_rows)
            psi_rows = [
                {
                    "URL": r.get("URL"),
                    "Desktop Score": r.get("Desktop PSI Score", 0),
                    "Mobile Score": r.get("Mobile PSI Score", 0),
                    "Mobile LCP": r.get("Mobile LCP (s)", 0.0),
                    "Mobile CLS": r.get("Mobile CLS", 0.0),
                    "Mobile TTFB": r.get("Mobile TTFB (s)", 0.0),
                }
                for r in extra_rows
            ]
            to_excel_safe(
                pd.DataFrame(psi_rows), writer, "PSI Performance", index=False
            )
            indexability_cols = [
                "URL",
                "Status Code",
                "Status Class",
                "Final URL",
                "Indexability Reason",
                "Meta Robots Raw",
                "X-Robots-Tag",
                "Canonical URL",
                "Canonical Type",
                "Canonical Matches Final URL",
                "Canonical in Sitemap Match",
            ]
            write_dict_rows_sheet(
                writer, "Indexability", indexability_cols, extra_rows
            )
            redirects_rows = []
            for r in extra_rows:
                redirects_rows.append(
                    {
                        "URL": r.get("URL"),
                        "Status Code": r.get("Status Code"),
                        "Final URL": r.get("Final URL"),
                        "Redirect Chain Length": r.get("Redirect Chain Length"),
                        "Redirect Target": r.get("Redirect Target"),
                        "Redirect Hops": r.get("Redirect Hops"),
                        "HTTP->HTTPS Redirect": r.get("HTTP->HTTPS Redirect"),
                        "Redirect Loop Flag": (
                            isinstance(r.get("Redirect Hops"), str)
                            and _normalize_url_key(r.get("URL", ""))
                            == _normalize_url_key(r.get("Final URL", ""))
                            and int(r.get("Redirect Chain Length") or 0) > 0
                        ),
                    }
                )
            write_dict_rows_sheet(
                writer,
                "Redirects",
                [
                    "URL",
                    "Status Code",
                    "Final URL",
                    "Redirect Chain Length",
                    "Redirect Target",
                    "Redirect Hops",
                    "HTTP->HTTPS Redirect",
                    "Redirect Loop Flag",
                ],
                redirects_rows,
            )
            link_rows = []
            for row in extra_rows:
                for item in row.get("Link Details", []):
                    target_status = status_by_url.get(
                        _normalize_url_key(item.get("Target URL", ""))
                    )
                    crawlable = target_status is None or (
                        isinstance(target_status, int) and target_status < 400
                    )
                    link_rows.append(
                        {
                            **item,
                            "Target Status (if crawled)": target_status,
                            "Crawlable": crawlable,
                        }
                    )
            to_excel_safe(
                pd.DataFrame(link_rows), writer, "LinksDetail", index=False
            )
            title_groups: defaultdict[str, list[str]] = defaultdict(list)
            desc_groups: defaultdict[str, list[str]] = defaultdict(list)
            for row in main_rows:
                t_key = normalize_text_hash(row.get("Title"))
                d_key = normalize_text_hash(row.get("Meta Description"))
                if t_key:
                    title_groups[t_key].append(row.get("URL"))
                if d_key:
                    desc_groups[d_key].append(row.get("URL"))
            duplicate_rows = []
            for row in main_rows:
                t_key = normalize_text_hash(row.get("Title"))
                d_key = normalize_text_hash(row.get("Meta Description"))
                duplicate_rows.append(
                    {
                        "URL": row.get("URL"),
                        "Title Duplicate Count": (
                            len(title_groups.get(t_key, [])) if t_key else 0
                        ),
                        "Meta Description Duplicate Count": (
                            len(desc_groups.get(d_key, [])) if d_key else 0
                        ),
                        "Title Duplicate URLs": (
                            " | ".join(title_groups.get(t_key, []))
                            if t_key and len(title_groups.get(t_key, [])) > 1
                            else None
                        ),
                        "Meta Duplicate URLs": (
                            " | ".join(desc_groups.get(d_key, []))
                            if d_key and len(desc_groups.get(d_key, [])) > 1
                            else None
                        ),
                    }
                )
            to_excel_safe(
                pd.DataFrame(duplicate_rows), writer, "Duplicates", index=False
            )
            folder_groups: defaultdict[str, list[dict[str, object]]] = defaultdict(
                list
            )
            for row in extra_rows:
                folder_groups[
                    _extract_subfolder(
                        str(row.get("Final URL") or row.get("URL") or "")
                    )
                ].append(row)
            cluster_rows = []
            template_issue_counts: defaultdict[str, defaultdict[str, int]] = (
                defaultdict(lambda: defaultdict(int))
            )
            for folder, urls_in_group in sorted(
                folder_groups.items(), key=lambda x: len(x[1]), reverse=True
            ):
                if not urls_in_group:
                    continue
                url_count = len(urls_in_group)
                missing_h1_count = sum(
                    1 for r in urls_in_group if bool(r.get("Missing H1 Flag"))
                )
                missing_meta_count = sum(
                    1
                    for r in urls_in_group
                    if bool(r.get("Meta Description Missing"))
                )
                systemic_issue = None
                exact_action = None
                if (missing_h1_count / max(1, url_count)) >= 0.8:
                    systemic_issue = "Missing H1 is template-wide"
                    exact_action = "Update template to render exactly one descriptive H1 for each page based on page-specific title data."
                elif (missing_meta_count / max(1, url_count)) >= 0.8:
                    systemic_issue = "Missing meta description is template-wide"
                    exact_action = "Update template/meta generation logic to output a unique 120-160 character meta description per page."
                if systemic_issue:
                    cluster_rows.append(
                        {
                            "Subfolder": folder,
                            "URL Count": url_count,
                            "Systemic Issue": systemic_issue,
                            "Affected Ratio": round(
                                (
                                    max(missing_h1_count, missing_meta_count)
                                    / max(1, url_count)
                                )
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
            pattern_df = pd.DataFrame(cluster_rows)
            if pattern_df.empty:
                pattern_df = pd.DataFrame(
                    [
                        {
                            "Subfolder": "/",
                            "URL Count": 0,
                            "Systemic Issue": "No systemic template issues above 80%.",
                            "Affected Ratio": 0,
                            "Exact Action": "N/A",
                        }
                    ]
                )
            to_excel_safe(
                pattern_df,
                writer,
                "Pattern and Template Issues",
                index=False,
                startrow=1,
            )
            pattern_ws = writer.book["Pattern and Template Issues"]
            pattern_ws["A1"] = (
                "WHAT IS THIS? This tab detects structural flaws coded into your page templates. "
                "Fixing one template here can instantly fix hundreds of pages."
            )
            aeo_issue_names = {
                "Low AEO Readiness Score",
                "Missing FAQ/QA Schema",
                "No Question Headings",
                "No Answer-Friendly Structure",
                "No 40-60 Word Answer Paragraphs",
            }
            summary_rows = build_summary_rows(
                summary_rules,
                extra_rows,
                template_issue_counts,
                _value_or_default,
            )
            to_excel_safe(
                pd.DataFrame(summary_rows), writer, "Summary", index=False
            )
            issue_inventory_rows = build_issue_inventory_rows(
                summary_rules, extra_rows
            )
            issue_inventory_df = pd.DataFrame(issue_inventory_rows)
            to_excel_safe(issue_inventory_df, writer, "IssueInventory", index=False)
            fixplan_rows = build_fixplan_rows(
                summary_rules,
                extra_rows,
                aeo_issue_names,
                root_cause_and_fix,
                DEFAULT_EFFORT_BY_SEVERITY,
                DEFAULT_OWNER_BY_SEVERITY,
            )
            issue_actions = {
                "Missing meta description": "Write a 120-160 character meta description including the primary keyword and a clear CTA.",
                "Missing H1 heading": "Add one descriptive H1 that matches primary search intent and avoids duplication with template boilerplate.",
                "Thin content": "Expand the page to at least 300 words with unique intent-focused sections and direct answers.",
                "Canonical configuration issue": "Set canonical to the self-referencing preferred URL and remove conflicting canonical hints.",
            }
            for fix_row in fixplan_rows:
                issue_name = str(fix_row.get("Issue Type") or "")
                matched_rows = [
                    e
                    for e in extra_rows
                    if issue_name in str(e.get("Matched Issues") or "").split(" | ")
                ]
                total_clicks = sum(
                    _value_or_default(r.get("GSC Clicks"), 0.0)
                    for r in matched_rows
                )
                max_clicks = max(
                    (
                        _value_or_default(r.get("GSC Clicks"), 0.0)
                        for r in matched_rows
                    ),
                    default=0.0,
                )
                est_hours = _value_or_default(fix_row.get("Est. Hours"), 1.0)
                fix_type = (
                    "Technical"
                    if any(
                        t in issue_name.lower()
                        for t in ["canonical", "status", "redirect", "index"]
                    )
                    else "Content"
                )
                fix_row["Fix Type"] = fix_type
                fix_row["Estimated Traffic Impact"] = (
                    "High"
                    if max_clicks > 100
                    else "Medium" if max_clicks > 25 else "Low"
                )
                fix_row["Fix Effort"] = round(est_hours, 2)
                fix_row["ROI Score"] = round(total_clicks / max(est_hours, 1.0), 2)
                fix_row["Exact Action"] = issue_actions.get(
                    issue_name,
                    f"Resolve '{issue_name}' using {fix_type.lower()} best practices and validate in the related detail tab.",
                )
            fixplan_df = pd.DataFrame(
                sorted(
                    fixplan_rows,
                    key=lambda x: (-x["Affected Count"], x["Severity"]),
                )
            )
            to_excel_safe(fixplan_df, writer, "FixPlan", index=False)
            hub_base_rows = build_content_optimisation_hub_rows(
                main_rows, extra_rows, fixplan_rows
            )
            extra_by_url = {str(r.get("URL") or ""): r for r in extra_rows}
            content_hub_rows: list[dict[str, object]] = []
            for hub_row in hub_base_rows:
                metrics = extra_by_url.get(str(hub_row.get("URL") or ""), {})
                merged: dict[str, object] = {
                    **hub_row,
                    "SEO Score": metrics.get("SEO Score", 0.0),
                    "Technical Health": metrics.get("Technical Health", 0.0),
                }
                content_hub_rows.append(dict(merged))
            content_hub_cols = [
                "Action Required",
                "Status",
                "Assigned Owner",
                "URL",
                "Current SEO Score",
                "Projected SEO Score",
                "Elementor Builder Link",
                "Target Keywords",
                "Current Page Copy Snippet",
                "Current Title",
                "Proposed Title (50-60 Chars)",
                "Title Count",
                "Current Meta Desc",
                "Proposed Meta Desc (120-160 Chars)",
                "Desc Count",
                "Current H-Tag Structure",
                "Proposed H-Tag Fixes",
                "AEO Answer Block Draft",
                "FAQ/QA Draft",
                "Current OG-Image URL",
                "OG Image Preview",
                "Social Share Note",
                "SEO Score",
                "Technical Health",
                "Copy Score",
                "Open in Main",
            ]
            write_dict_rows_sheet(
                writer,
                CONTENT_OPTIMISATION_HUB_SHEET,
                content_hub_cols,
                content_hub_rows,
            )
            quick_reference_rows = [
                {
                    "Section": "[Meta Data Standards]",
                    "Item": "",
                    "Guideline": "",
                    "Why It Matters": "",
                },
                {
                    "Section": "",
                    "Item": "Meta Title",
                    "Guideline": "50-60 characters. Place primary keyword at the front. Avoid brand repetition unless there is space.",
                    "Why It Matters": "Improves clarity and reduces SERP truncation risk.",
                },
                {
                    "Section": "",
                    "Item": "Meta Description",
                    "Guideline": "120-160 characters. Must contain a clear Call-To-Action (CTA) and active verbs.",
                    "Why It Matters": "Supports stronger click-through and intent alignment.",
                },
                {
                    "Section": "",
                    "Item": "Target Keywords",
                    "Guideline": "1 Primary, 2 Secondary per page. Do not keyword stuff; focus on user intent.",
                    "Why It Matters": "Keeps copy focused on topical relevance over keyword density.",
                },
                {"Section": "", "Item": "", "Guideline": "", "Why It Matters": ""},
                {
                    "Section": "[On-Page Structure (H-Tags)]",
                    "Item": "",
                    "Guideline": "",
                    "Why It Matters": "",
                },
                {
                    "Section": "",
                    "Item": "H1 Tag",
                    "Guideline": "Exactly ONE per page. Must contain the primary topic/keyword. Think of it as the 'Book Title'.",
                    "Why It Matters": "Provides the clearest top-level topical signal.",
                },
                {
                    "Section": "",
                    "Item": "H2 Tags",
                    "Guideline": "Main sections. Use question formats (Who, What, How) to trigger Answer Engine extraction.",
                    "Why It Matters": "Improves structured scannability for users and LLMs.",
                },
                {
                    "Section": "",
                    "Item": "H3 Tags",
                    "Guideline": "Sub-sections under H2s. Use for lists, steps, or detailed breakdowns.",
                    "Why It Matters": "Strengthens hierarchy and supports extraction-ready formatting.",
                },
                {
                    "Section": "",
                    "Item": "H4-H6 Tags",
                    "Guideline": "Use sparingly. Only for granular formatting within complex H3 topics.",
                    "Why It Matters": "Avoids over-nesting while preserving semantic structure.",
                },
                {"Section": "", "Item": "", "Guideline": "", "Why It Matters": ""},
                {
                    "Section": "[AEO (Answer Engine Optimisation) & Content]",
                    "Item": "",
                    "Guideline": "",
                    "Why It Matters": "",
                },
                {
                    "Section": "",
                    "Item": "AEO Answer Blocks",
                    "Guideline": "40-60 words. Placed directly beneath an H2 question. Must be factual, objective, and devoid of marketing fluff (e.g., 'The best way to...').",
                    "Why It Matters": "Optimises direct extraction for answer engines and voice search.",
                },
                {
                    "Section": "",
                    "Item": "FAQ Schema",
                    "Guideline": "Minimum 2-3 questions per informational page. Answers must be direct and stand alone without needing the rest of the page for context.",
                    "Why It Matters": "Improves machine readability and rich-answer eligibility.",
                },
                {
                    "Section": "",
                    "Item": "Content Readability",
                    "Guideline": "Keep sentences under 20 words. Use bullet points for any list of 3 or more items.",
                    "Why It Matters": "Increases comprehension and snippet usability.",
                },
                {"Section": "", "Item": "", "Guideline": "", "Why It Matters": ""},
                {
                    "Section": "[Visual & Social Branding]",
                    "Item": "",
                    "Guideline": "",
                    "Why It Matters": "",
                },
                {
                    "Section": "",
                    "Item": "OG Image",
                    "Guideline": "1200 x 630 pixels. Keep text centered (safe zone) so it isn't cropped by mobile devices on LinkedIn/X.",
                    "Why It Matters": "Ensures consistent social card presentation.",
                },
                {
                    "Section": "",
                    "Item": "Social Share Note",
                    "Guideline": "Customize the message for the platform. LinkedIn = Professional insight. X (Twitter) = Quick hook. Facebook = Conversational.",
                    "Why It Matters": "Improves engagement by matching platform context.",
                },
            ]
            to_excel_safe(
                pd.DataFrame(quick_reference_rows),
                writer,
                "Quick Reference Guide",
                index=False,
            )
            priority_rows = []
            for row in extra_rows:
                risk_score = (
                    _value_or_default(row.get("Critical Issues Count"), 0.0) * 30
                    + _value_or_default(row.get("Warning Issues Count"), 0.0) * 10
                    + (100 - _value_or_default(row.get("SEO Health Score"), 100.0))
                )
                reasons = []
                if _value_or_default(row.get("Critical Issues Count"), 0.0) > 0:
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
                    else (
                        "Canonical Points Elsewhere"
                        if row.get("Canonical Type") == "cross-canonical"
                        else (
                            "Noindex Directive"
                            if "noindex"
                            in str(row.get("Indexability Reason", "")).lower()
                            else ""
                        )
                    )
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
                        "SEO Health Score": row.get("SEO Health Score"),
                        "Severity Badge": row.get("Severity Badge"),
                        "Critical Issues Count": row.get("Critical Issues Count"),
                        "Warning Issues Count": row.get("Warning Issues Count"),
                        "Indexability Reason": row.get("Indexability Reason"),
                        "Broken Internal Links Count": row.get(
                            "Broken Internal Links Count"
                        ),
                        "Canonical Type": row.get("Canonical Type"),
                        "GSC Impressions": row.get("GSC Impressions", 0.0),
                        "GSC CTR": row.get("GSC CTR", 0.0),
                        "Revenue Intent": revenue_intent,
                        "Why Prioritized": (
                            " | ".join(reasons) if reasons else "Monitor"
                        ),
                        "Action Needed": "Yes" if risk_score >= 30 else "No",
                        "Owner": owner_for_issue(
                            owner_seed_issue, str(row.get("Severity Badge") or "")
                        ),
                        "Sprint": "",
                        "Status": "Open",
                    }
                )
            priority_df = pd.DataFrame(
                sorted(
                    priority_rows,
                    key=lambda x: x["Business Risk Score"],
                    reverse=True,
                )
            )
            to_excel_safe(priority_df, writer, "Priority URLs", index=False)
            total_urls = len(extra_rows)
            # Pass rate from Technical (extra_rows) Severity Badge distribution only.
            pass_count = sum(
                1
                for r in extra_rows
                if str(r.get("Severity Badge") or "") == "Pass"
            )
            critical_count = sum(
                1
                for r in extra_rows
                if str(r.get("Severity Badge") or "") == "Critical"
            )
            warning_count = sum(
                1
                for r in extra_rows
                if str(r.get("Severity Badge") or "") == "Warning"
            )
            top_blockers = fixplan_df.head(10)[
                ["Issue Type", "Severity", "Affected Count"]
            ]
            seo_health_values: list[float] = []
            for r in extra_rows:
                raw_hs = r.get("SEO Health Score")
                if raw_hs is None or str(raw_hs).strip() == "":
                    continue
                try:
                    seo_health_values.append(float(raw_hs))
                except (TypeError, ValueError):
                    continue
            avg_seo_health_pct = (
                round(sum(seo_health_values) / len(seo_health_values), 2)
                if seo_health_values
                else 0.0
            )
            seo_pass_pct = round((pass_count / max(1, total_urls)) * 100.0, 2)
            to_do_share = (critical_count + warning_count) / max(1, total_urls)
            projected_health_pct = min(
                100.0,
                round(
                    avg_seo_health_pct
                    + max(0.0, 100.0 - avg_seo_health_pct) * to_do_share * 0.9,
                    2,
                ),
            )
            projected_pass_pct = min(
                100.0,
                round(
                    seo_pass_pct
                    + max(0.0, 100.0 - seo_pass_pct) * to_do_share * 0.85,
                    2,
                ),
            )
            # Keys must match labels consumed by style_dashboard (Metric/Value feeder row).
            dashboard_rows = [
                {"Metric": "URLs Crawled", "Value": total_urls},
                {"Metric": "SEO Pass Rate %", "Value": seo_pass_pct},
                {"Metric": "Health Score %", "Value": avg_seo_health_pct},
                {"Metric": "Critical URL Count", "Value": critical_count},
                {"Metric": "Warning URL Count", "Value": warning_count},
                {
                    "Metric": "Projected Health Score %",
                    "Value": projected_health_pct,
                },
                {"Metric": "Projected Pass Rate %", "Value": projected_pass_pct},
            ]
            to_excel_safe(
                pd.DataFrame(dashboard_rows), writer, "Dashboard", index=False
            )
            critical_issues_rows = [
                {
                    "Block": "Critical Issues",
                    "URL": r.get("URL"),
                    "Issue": r.get("Matched Issues"),
                }
                for r in extra_rows
                if _value_or_default(r.get("Critical Issues Count"), 0.0) > 0
            ][:10]
            quick_wins_rows = [
                {
                    "Block": "Quick Wins",
                    "URL": r.get("URL"),
                    "Issue": "Missing meta on high-impression page",
                }
                for r in extra_rows
                if bool(r.get("Meta Description Missing"))
                and _value_or_default(r.get("GSC Impressions"), 0.0) > 500
            ][:10]
            growth_rows = [
                {
                    "Block": "Growth Opportunities",
                    "URL": r.get("URL"),
                    "Issue": "Missing FAQ/QA schema or thin content on revenue URL",
                }
                for r in extra_rows
                if (
                    (
                        not bool(r.get("QAPage/FAQ Schema Present"))
                        or _value_or_default(r.get("Word Count"), 0.0) < 300
                    )
                    and any(
                        slug in str(r.get("URL") or "").lower()
                        for slug in high_value_slugs
                    )
                )
            ][:10]
            action_hub_df = pd.DataFrame(
                critical_issues_rows + quick_wins_rows + growth_rows
            )
            if not action_hub_df.empty:
                to_excel_safe(
                    action_hub_df, writer, "Dashboard", index=False, startrow=20
                )
            immediate_action_cols = [
                "URL",
                "Business Risk Score",
                "Why Prioritized",
                "Action Needed",
                "Owner",
                "Status",
            ]
            immediate_actions_df = (
                priority_df.reindex(columns=immediate_action_cols).head(5).copy()
            )
            immediate_actions_df.insert(
                0, "Rank", range(1, len(immediate_actions_df) + 1)
            )
            immediate_actions_startrow = len(dashboard_rows) + len(top_blockers) + 7
            to_excel_safe(
                pd.DataFrame(
                    [{"Immediate Actions": "Top 5 URLs by Business Risk Score"}]
                ),
                writer,
                "Dashboard",
                index=False,
                startrow=immediate_actions_startrow,
            )
            to_excel_safe(
                immediate_actions_df,
                writer,
                "Dashboard",
                index=False,
                startrow=immediate_actions_startrow + 2,
            )
            run_meta_rows = [
                {
                    "Key": "Run Timestamp",
                    "Value": datetime.now()
                    .astimezone()
                    .strftime("%Y-%m-%d %H:%M:%S"),
                },
                {"Key": "Total URLs", "Value": len(urls)},
                {"Key": "Mode", "Value": "Full Suite"},
                {"Key": "Workers", "Value": workers},
                {"Key": "Delay Seconds", "Value": request_delay},
                {"Key": "Retries", "Value": MAX_RETRIES},
                {"Key": "Timeout Seconds", "Value": TIMEOUT_SECONDS},
                {"Key": "Checkpoint Every", "Value": checkpoint_every},
                {
                    "Key": "Previous Audit Path",
                    "Value": previous_audit_path or "Not supplied",
                },
            ]
            to_excel_safe(
                pd.DataFrame(run_meta_rows), writer, "RunMetadata", index=False
            )
            current_issue_inventory_df = issue_inventory_df.copy()
            current_issue_ids = {
                str(v).strip()
                for v in current_issue_inventory_df.get(
                    "Stable Issue ID", pd.Series(dtype="object")
                )
                .dropna()
                .tolist()
                if str(v).strip()
            }
            new_issues = current_issue_ids - prev_issue_ids
            resolved_issues = prev_issue_ids - current_issue_ids
            unchanged_issues = current_issue_ids & prev_issue_ids
            delta_rows = [
                {"Metric": "New Issues", "Count": len(new_issues)},
                {"Metric": "Resolved Issues", "Count": len(resolved_issues)},
                {"Metric": "Unchanged Issues", "Count": len(unchanged_issues)},
            ]
            reopened_from_previously_fixed = len(
                current_issue_ids & prev_fixed_issue_ids
            )
            delta_rows.append(
                {
                    "Metric": "Previously Fixed But Reopened",
                    "Count": reopened_from_previously_fixed,
                }
            )
            for _, issue_name, _ in summary_rules:
                current_count = len(
                    [
                        r
                        for r in extra_rows
                        if issue_name
                        in str(r.get("Matched Issues") or "").split(" | ")
                    ]
                )
                delta_rows.append(
                    {
                        "Metric": f"Issue Delta: {issue_name}",
                        "Count": current_count
                        - int(prev_counts.get(issue_name, 0)),
                    }
                )
            to_excel_safe(
                pd.DataFrame(delta_rows),
                writer,
                "DeltaFromPreviousRun",
                index=False,
            )
            if (
                not previous_issue_inventory_df.empty
                and "Stable Issue ID" in previous_issue_inventory_df.columns
            ):
                previous_issue_inventory_df = previous_issue_inventory_df.copy()
                previous_issue_inventory_df["Stable Issue ID"] = (
                    previous_issue_inventory_df["Stable Issue ID"]
                    .astype(str)
                    .str.strip()
                )
                resolved_issues_df = previous_issue_inventory_df[
                    previous_issue_inventory_df["Stable Issue ID"].isin(
                        resolved_issues
                    )
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
            to_excel_safe(resolved_issues_df, writer, "ResolvedIssues", index=False)
            legend_rows = [
                {
                    "Section": "How To Use",
                    "Term": "Step 1: Start on Dashboard",
                    "Meaning": "Review pass rate, critical URL count, and Immediate Actions to understand overall risk first.",
                    "Values/Threshold": "5-minute executive scan",
                    "Related Tabs": "Dashboard, Priority URLs",
                },
                {
                    "Section": "How To Use",
                    "Term": "Step 2: Prioritize and Assign",
                    "Meaning": "Use Priority URLs and FixPlan to pick highest-impact items, assign owner, and set status/sprint.",
                    "Values/Threshold": "Work top-down by Business Risk Score",
                    "Related Tabs": "Priority URLs, FixPlan",
                },
                {
                    "Section": "How To Use",
                    "Term": "Step 3: Execute and Validate",
                    "Meaning": "Implement fixes, then verify by checking Technical/Indexability/AEO tabs and rerunning the audit.",
                    "Values/Threshold": "Close loop every sprint",
                    "Related Tabs": "Technical, Indexability, AEO, AIOSEO",
                },
                {
                    "Section": "Orientation",
                    "Term": "Where to Start",
                    "Meaning": "If you're short on time, work only Critical and Warning issues first, then return to Observation items.",
                    "Values/Threshold": "Critical > Warning > Observation",
                    "Related Tabs": "Summary, FixPlan, Technical",
                },
                {
                    "Section": "Orientation",
                    "Term": "How to Track Progress",
                    "Meaning": "Use Status and Owner columns as your project board; move from To Do -> In Progress -> Fixed.",
                    "Values/Threshold": "Update weekly",
                    "Related Tabs": "FixPlan, AIOSEO, Priority URLs",
                },
                {
                    "Section": "Severity",
                    "Term": "Critical",
                    "Meaning": "High-impact SEO blocker that should be fixed first.",
                    "Values/Threshold": "Immediate action",
                    "Related Tabs": "Summary, FixPlan, Technical",
                },
                {
                    "Section": "Severity",
                    "Term": "Warning",
                    "Meaning": "Out-of-best-practice issue likely affecting performance.",
                    "Values/Threshold": "Plan next sprint",
                    "Related Tabs": "Summary, FixPlan, Technical",
                },
                {
                    "Section": "Severity",
                    "Term": "Observation",
                    "Meaning": "Optimisation opportunity or context signal.",
                    "Values/Threshold": "Backlog/monitor",
                    "Related Tabs": "Summary, Technical",
                },
                {
                    "Section": "Scoring",
                    "Term": "SEO Health Score",
                    "Meaning": "Weighted technical SEO quality score per URL.",
                    "Values/Threshold": ">=90 green, 70-89 orange, <70 red",
                    "Related Tabs": "Technical, Priority URLs, Dashboard",
                },
                {
                    "Section": "Scoring",
                    "Term": "AEO Readiness Score",
                    "Meaning": "Answer Engine Optimisation readiness score per URL.",
                    "Values/Threshold": ">=80 strong, 60-79 good, 40-59 fair",
                    "Related Tabs": "AEO",
                },
                {
                    "Section": "Indexing",
                    "Term": "Indexability Reason",
                    "Meaning": "Primary reason URL may not be indexed.",
                    "Values/Threshold": "Noindex, non-200, canonical mismatch",
                    "Related Tabs": "Indexability, Technical",
                },
                {
                    "Section": "Links",
                    "Term": "Broken Internal Links Count",
                    "Meaning": "Internal links returning 4xx/5xx or equivalent failures.",
                    "Values/Threshold": ">0 flagged",
                    "Related Tabs": "Links, LinksDetail, Priority URLs",
                },
                {
                    "Section": "Content",
                    "Term": "Word Count Band",
                    "Meaning": "Body content depth class.",
                    "Values/Threshold": "Thin / OK / Strong",
                    "Related Tabs": "Content",
                },
                {
                    "Section": "AEO",
                    "Term": "Question Heading Count",
                    "Meaning": "Headings phrased as questions to match answer intent.",
                    "Values/Threshold": "Higher is generally better",
                    "Related Tabs": "AEO",
                },
                {
                    "Section": "AEO & Generative Search Terms",
                    "Term": "Answer Engine Optimisation",
                    "Meaning": "The practice of structuring content so AI answer engines can reliably extract and cite direct answers.",
                    "Values/Threshold": "Answer-first formatting",
                    "Related Tabs": f"AEO, {CONTENT_OPTIMISATION_HUB_SHEET}",
                },
                {
                    "Section": "AEO & Generative Search Terms",
                    "Term": "Featured Snippet",
                    "Meaning": "A concise answer block surfaced prominently in search results, often extracted from clear headings + short answer text.",
                    "Values/Threshold": "Direct question-answer format",
                    "Related Tabs": "AEO, Content",
                },
                {
                    "Section": "AEO & Generative Search Terms",
                    "Term": "FAQ Schema",
                    "Meaning": "Structured data that marks up common questions and answers to improve machine readability and eligibility for rich results.",
                    "Values/Threshold": "Valid JSON-LD",
                    "Related Tabs": "AEO, Schema & Metadata",
                },
                {
                    "Section": "AEO & Generative Search Terms",
                    "Term": "llms.txt",
                    "Meaning": "A guidance file for AI crawlers that can indicate allowed access and preferred content handling behavior.",
                    "Values/Threshold": "Present and reachable",
                    "Related Tabs": "Technical, Security",
                },
                {
                    "Section": "AEO & Generative Search Terms",
                    "Term": "Entity-Based Search",
                    "Meaning": "Search interpretation based on known entities (people, places, brands, topics) and their relationships, not only keywords.",
                    "Values/Threshold": "Clear entity context",
                    "Related Tabs": "AEO, Content",
                },
                {
                    "Section": "Color Key",
                    "Term": "Green",
                    "Meaning": "Pass / aligned with best practice or completed workflow item.",
                    "Values/Threshold": "Good",
                    "Related Tabs": "All",
                },
                {
                    "Section": "Color Key",
                    "Term": "Orange",
                    "Meaning": "Warning / in progress / medium-priority attention needed.",
                    "Values/Threshold": "Medium risk",
                    "Related Tabs": "All",
                },
                {
                    "Section": "Color Key",
                    "Term": "Red",
                    "Meaning": "Failure / high-priority issue or to-do critical task.",
                    "Values/Threshold": "High risk",
                    "Related Tabs": "All",
                },
                {
                    "Section": "Color Key",
                    "Term": "Purple",
                    "Meaning": "Informational edge-case or AEO category signal.",
                    "Values/Threshold": "Context",
                    "Related Tabs": "All",
                },
            ]
            to_excel_safe(
                pd.DataFrame(legend_rows), writer, "Glossary & Legend", index=False
            )
            crawl_inlinks_map: defaultdict[str, set[str]] = defaultdict(set)
            crawled_set_main = {
                _normalize_url_key(u) for u in main_df["URL"].dropna().tolist()
            }
            for row in extra_rows:
                source = _normalize_url_key(row.get("URL"))
                for target in row.get("Internal Links List", []):
                    target_norm = _normalize_url_key(target)
                    if target_norm in crawled_set_main:
                        crawl_inlinks_map[target_norm].add(source)
            graph_rows = [
                {
                    "URL": url_item,
                    "Inlinks Count": len(
                        inlinks := sorted(
                            list(
                                crawl_inlinks_map.get(
                                    _normalize_url_key(url_item), set()
                                )
                            )
                        )
                    ),
                    "Inlinks URLs": " | ".join(inlinks) if inlinks else None,
                    "Orphan Candidate": len(inlinks) == 0,
                    "Click Depth": next(
                        (
                            e.get("Click Depth")
                            for e in extra_rows
                            if _normalize_url_key(e.get("URL"))
                            == _normalize_url_key(url_item)
                        ),
                        None,
                    ),
                    "Internal PageRank": next(
                        (
                            e.get("Internal PageRank")
                            for e in extra_rows
                            if _normalize_url_key(e.get("URL"))
                            == _normalize_url_key(url_item)
                        ),
                        0.0,
                    ),
                }
                for url_item in main_df["URL"].dropna().tolist()
            ]
            to_excel_safe(
                pd.DataFrame(graph_rows), writer, "CrawlGraph", index=False
            )
            sitemap_rows = []
            if sitemap_meta:
                for sitemap_url, meta in sitemap_meta.items():
                    matched = next(
                        (
                            row
                            for row in extra_rows
                            if _normalize_url_key(row.get("URL", ""))
                            == _normalize_url_key(sitemap_url)
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
                                matched.get("Redirect Chain Length", 0) > 0
                                if matched
                                else None
                            ),
                            "In Sitemap but Canonicalized Elsewhere": (
                                matched.get("Canonical Type") == "cross-canonical"
                                if matched
                                else None
                            ),
                            "Missing <lastmod>": not bool(meta.get("lastmod")),
                            "Missing <changefreq>": not bool(
                                meta.get("changefreq")
                            ),
                            "Missing <priority>": not bool(meta.get("priority")),
                            "Sitemap <lastmod>": meta.get("lastmod"),
                            "Sitemap <changefreq>": meta.get("changefreq"),
                            "Sitemap <priority>": meta.get("priority"),
                            "Source Sitemap": meta.get("source_sitemap"),
                        }
                    )
            to_excel_safe(
                pd.DataFrame(sitemap_rows), writer, "SitemapQA", index=False
            )
            apply_tab_hyperlinks(writer)
            for sname in (
                "Dashboard",
                CONTENT_OPTIMISATION_HUB_SHEET,
                "Quick Reference Guide",
                "Summary",
                "FixPlan",
                "Content",
                "Main",
                "Priority URLs",
                "AIOSEO",
                "Technical",
                "PSI Performance",
                "AEO",
                "Indexability",
                "Redirects",
                "Security",
                "Schema & Metadata",
                "Links",
                "LinksDetail",
                "Media",
                "Duplicates",
                "Pattern and Template Issues",
                "CrawlGraph",
                "SitemapQA",
                "IssueInventory",
                "ResolvedIssues",
                "DeltaFromPreviousRun",
                "RunMetadata",
                "Glossary & Legend",
            ):
                adjust_sheet_format(writer, sname)
        apply_workbook_export_guardrails(writer.book)
        logger.info("Audit complete! Report saved to %s", output_filename)
    finally:
        if writer is not None:
            writer.close()


def _build_aeo_rows(extra_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in extra_rows:
        question_heading_count = int(row.get("Question Heading Count") or 0)
        faq_count = int(row.get("FAQ Section Count") or 0)
        answer_para_count = int(row.get("Paragraphs 40-60 Words Count") or 0)
        has_qa_schema = bool(row.get("QAPage/FAQ Schema Present"))
        has_speakable = bool(row.get("Speakable Schema Present"))
        has_howto = bool(row.get("HowTo Signal"))
        has_definition = bool(row.get("Definition Signal"))
        has_list_table = bool(row.get("List/Table Answer Signal"))
        title_missing = bool(row.get("Title Missing"))
        meta_missing = bool(row.get("Meta Description Missing"))
        aeo_score = int(row.get("AEO Readiness Score") or 0)

        why_notes: list[str] = []
        if answer_para_count == 0:
            why_notes.append(
                "Missing 30-60 word answer blocks reduces eligibility for featured snippets."
            )
        if question_heading_count == 0:
            why_notes.append(
                "Question-style headings help match conversational search and answer intent."
            )
        if not has_qa_schema:
            why_notes.append(
                "FAQ/QA schema improves machine understanding for rich answer surfaces."
            )
        if not has_speakable:
            why_notes.append(
                "Speakable markup can improve voice assistant readability of key answers."
            )
        if not has_howto and not has_definition and not has_list_table:
            why_notes.append(
                "Answer-friendly structure (how-to, definitions, lists/tables) helps extraction by answer engines."
            )
        if title_missing or meta_missing:
            why_notes.append(
                "Missing title/meta weakens topical context and lowers snippet confidence."
            )
        if not why_notes and aeo_score >= 80:
            why_notes.append(
                "Strong answer-engine foundations are present; maintain concise, direct answer blocks."
            )

        row_copy = dict(row)
        row_copy["Why It Matters"] = " ".join(why_notes)
        row_copy["Question Heading Count"] = question_heading_count
        row_copy["FAQ Section Count"] = faq_count
        row_copy["Paragraphs 40-60 Words Count"] = answer_para_count
        first_snippet = (
            (row.get("aeo_snippets") or [{}])[0] if row.get("aeo_snippets") else {}
        )
        heading = str(first_snippet.get("heading") or "").strip()
        snippet = str(first_snippet.get("snippet") or "").strip()
        row_copy["Snippet Preview Mockup"] = (
            f"{heading}\n{snippet}".strip() if heading or snippet else None
        )
        rows.append(row_copy)
    return rows


def _build_aioseo_rows(
    extra_rows: list[dict[str, object]],
    main_by_url: dict[str, dict[str, object]],
    default_owner_by_severity: dict[str, str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    severity_rank = {"Critical": 0, "Warning": 1, "Observation": 2}

    def _to_int(value: object, fallback: int = 0) -> int:
        try:
            return int(float(value)) if value is not None else fallback
        except Exception:
            return fallback

    def _to_float(value: object, fallback: float = 0.0) -> float:
        try:
            return float(value) if value is not None else fallback
        except Exception:
            return fallback

    def add_issue(
        *,
        url: str,
        issue: str,
        severity: str,
        panel: str,
        current_value: object,
        recommended_target: str,
        why_it_matters: str,
        how_to_fix: str,
        reference_tab: str,
        reference_field: str,
    ) -> None:
        workflow = workflow_metrics_for_issue(severity)
        rows.append(
            {
                "URL": url,
                "WordPress Post ID": current_post_id if current_post_id > 0 else None,
                "Direct Edit Link": current_direct_edit_link,
                "AIOSEO Panel": panel,
                "Severity": severity,
                "Issue": issue,
                "Current Value": current_value,
                "Recommended Target": recommended_target,
                "Why It Matters": why_it_matters,
                "How to Fix in AIOSEO": how_to_fix,
                "Reference Tab": reference_tab,
                "Reference Field": reference_field,
                "Action Needed": "Yes" if severity in {"Critical", "Warning"} else "No",
                "Owner": owner_for_issue(issue, severity),
                "Status": "Open",
                "Priority Score": workflow.get("Priority Score"),
                "Est. Hours": workflow.get("Est. Hours"),
                "Stable Issue ID": stable_issue_id(url, f"AIOSEO::{issue}"),
            }
        )

    for row in extra_rows:
        url = str(row.get("URL") or "").strip()
        if not url:
            continue
        post_id_raw = row.get("WordPress Post ID")
        current_post_id = _to_int(post_id_raw, 0)
        parsed_url = urlparse(url)
        site_root = (
            f"{parsed_url.scheme}://{parsed_url.netloc}"
            if parsed_url.scheme and parsed_url.netloc
            else ""
        )
        current_direct_edit_link = (
            f"{site_root}/wp-admin/post.php?post={current_post_id}&action=edit"
            if site_root and current_post_id > 0
            else None
        )
        main_row = main_by_url.get(url, {})
        title = str(main_row.get("Title") or "").strip()
        meta = str(main_row.get("Meta Description") or "").strip()
        title_len = len(title)
        meta_len = len(meta)

        status_code = _to_int(row.get("Status Code"))
        if status_code >= 400:
            add_issue(
                url=url,
                issue="Page returns non-200 response",
                severity="Critical",
                panel="Basic SEO",
                current_value=status_code,
                recommended_target="200",
                why_it_matters="Pages that error cannot perform in search and fail core page-level SEO checks.",
                how_to_fix="Update URL target, restore page, or set correct redirect. In AIOSEO, review canonical/robots only after the page returns 200.",
                reference_tab="Technical",
                reference_field="Status Code",
            )

        if "noindex" in str(row.get("Indexability Reason") or "").lower():
            add_issue(
                url=url,
                issue="Noindex directive on page",
                severity="Critical",
                panel="Advanced SEO",
                current_value=row.get("Indexability Reason"),
                recommended_target="Indexable",
                why_it_matters="Noindex prevents the page from being indexed.",
                how_to_fix="In AIOSEO page settings -> Advanced, remove noindex for pages intended to rank.",
                reference_tab="Indexability",
                reference_field="Indexability Reason",
            )

        canonical_type = str(row.get("Canonical Type") or "")
        if canonical_type in {"missing", "cross-canonical"}:
            add_issue(
                url=url,
                issue="Canonical configuration issue",
                severity=(
                    "Critical" if canonical_type == "cross-canonical" else "Warning"
                ),
                panel="Advanced SEO",
                current_value=canonical_type,
                recommended_target="self",
                why_it_matters="Incorrect canonicals can de-index or de-prioritise the intended URL.",
                how_to_fix="In AIOSEO -> Advanced -> Canonical URL, set canonical to the preferred final URL for this page.",
                reference_tab="Indexability",
                reference_field="Canonical Type",
            )

        if not title:
            add_issue(
                url=url,
                issue="Missing SEO title",
                severity="Warning",
                panel="Title",
                current_value="Missing",
                recommended_target="40-60 characters",
                why_it_matters="Titles are a core relevance and CTR signal.",
                how_to_fix="In AIOSEO snippet settings, add a unique SEO title with the primary topic near the beginning.",
                reference_tab="Main",
                reference_field="Title",
            )
        else:
            if title_len < 40:
                add_issue(
                    url=url,
                    issue="SEO title too short",
                    severity="Observation",
                    panel="Title",
                    current_value=title_len,
                    recommended_target="40-60 characters",
                    why_it_matters="Very short titles often under-describe page intent.",
                    how_to_fix="Expand title in AIOSEO snippet editor with clearer intent and value proposition.",
                    reference_tab="Main",
                    reference_field="Title",
                )
            elif title_len > 60:
                add_issue(
                    url=url,
                    issue="SEO title too long",
                    severity="Observation",
                    panel="Title",
                    current_value=title_len,
                    recommended_target="40-60 characters",
                    why_it_matters="Long titles are more likely to truncate in SERPs.",
                    how_to_fix="Shorten title in AIOSEO snippet editor and keep key terms in the first 55-60 characters.",
                    reference_tab="Main",
                    reference_field="Title",
                )

        if not meta:
            add_issue(
                url=url,
                issue="Missing meta description",
                severity="Warning",
                panel="Basic SEO",
                current_value="Missing",
                recommended_target="120-160 characters",
                why_it_matters="Missing descriptions reduce control over search snippet messaging.",
                how_to_fix="In AIOSEO snippet settings, add a concise, unique meta description aligned to page intent.",
                reference_tab="Main",
                reference_field="Meta Description",
            )
        else:
            if meta_len < 120:
                add_issue(
                    url=url,
                    issue="Meta description too short",
                    severity="Observation",
                    panel="Basic SEO",
                    current_value=meta_len,
                    recommended_target="120-160 characters",
                    why_it_matters="Short descriptions can under-communicate relevance and value.",
                    how_to_fix="Expand meta description in AIOSEO to include key value points and intent terms naturally.",
                    reference_tab="Main",
                    reference_field="Meta Description",
                )
            elif meta_len > 160:
                add_issue(
                    url=url,
                    issue="Meta description too long",
                    severity="Observation",
                    panel="Basic SEO",
                    current_value=meta_len,
                    recommended_target="120-160 characters",
                    why_it_matters="Long descriptions are often truncated and lose message clarity.",
                    how_to_fix="Trim meta description in AIOSEO and front-load essential context.",
                    reference_tab="Main",
                    reference_field="Meta Description",
                )

        if bool(row.get("Missing H1 Flag")):
            add_issue(
                url=url,
                issue="Missing H1 heading",
                severity="Warning",
                panel="Readability",
                current_value=row.get("H1 Count"),
                recommended_target="Exactly 1 descriptive H1",
                why_it_matters="A missing H1 weakens topical clarity for users and crawlers.",
                how_to_fix="Update page content to include a single descriptive H1 aligned to primary intent.",
                reference_tab="Content",
                reference_field="Missing H1 Flag",
            )
        if bool(row.get("Multiple H1 Flag")):
            add_issue(
                url=url,
                issue="Multiple H1 headings",
                severity="Observation",
                panel="Readability",
                current_value=row.get("H1 Count"),
                recommended_target="Exactly 1 H1",
                why_it_matters="Multiple H1s can reduce heading hierarchy clarity.",
                how_to_fix="Keep one primary H1, convert remaining top-level headings to H2/H3 where appropriate.",
                reference_tab="Content",
                reference_field="Multiple H1 Flag",
            )

        word_count = _to_int(row.get("Word Count"))
        if bool(row.get("Thin Content Flag")) or word_count < 300:
            add_issue(
                url=url,
                issue="Thin content",
                severity="Warning",
                panel="Readability",
                current_value=word_count,
                recommended_target=">=300 words (quality first)",
                why_it_matters="Low-content pages can struggle to satisfy intent and rank competitively.",
                how_to_fix="Expand page copy with useful, unique sections that answer key user questions.",
                reference_tab="Content",
                reference_field="Word Count",
            )

        readability = _to_float(row.get("Readability (Rough Flesch)"), -1)
        if readability >= 0 and readability < 50:
            add_issue(
                url=url,
                issue="Low readability score",
                severity="Observation",
                panel="Readability",
                current_value=readability,
                recommended_target=">=50",
                why_it_matters="Hard-to-read content lowers engagement and comprehension.",
                how_to_fix="Use shorter sentences/paragraphs, clearer transitions, and simpler phrasing in page content.",
                reference_tab="Content",
                reference_field="Readability (Rough Flesch)",
            )

        if _to_int(row.get("Internal Links Count")) == 0:
            add_issue(
                url=url,
                issue="No internal links found",
                severity="Observation",
                panel="Basic SEO",
                current_value=0,
                recommended_target=">=2 relevant internal links",
                why_it_matters="Internal links help discovery, topical signals, and authority flow.",
                how_to_fix="Add contextual internal links from and to related pages using descriptive anchor text.",
                reference_tab="Links",
                reference_field="Internal Links Count",
            )
        if _to_int(row.get("Broken Internal Links Count")) > 0:
            add_issue(
                url=url,
                issue="Broken internal links",
                severity="Critical",
                panel="Links",
                current_value=row.get("Broken Internal Links Count"),
                recommended_target="0",
                why_it_matters="Broken links waste crawl budget and degrade user experience.",
                how_to_fix="Replace dead links with live targets, or remove them in the page editor.",
                reference_tab="Links",
                reference_field="Broken Internal Links Count",
            )

        alt_coverage = _to_float(row.get("Image Alt Coverage (%)"), 100.0)
        if alt_coverage < 80:
            add_issue(
                url=url,
                issue="Low image alt coverage",
                severity="Warning",
                panel="Readability",
                current_value=alt_coverage,
                recommended_target=">=80%",
                why_it_matters="Missing alt text reduces accessibility and weakens image context signals.",
                how_to_fix="Add descriptive alt text to meaningful images in the page editor/media fields.",
                reference_tab="Media",
                reference_field="Image Alt Coverage (%)",
            )

        if _to_int(row.get("Schema Types Count")) == 0:
            add_issue(
                url=url,
                issue="No schema markup detected",
                severity="Warning",
                panel="Schema",
                current_value=0,
                recommended_target="At least one relevant schema type",
                why_it_matters="Schema improves understanding and rich result eligibility.",
                how_to_fix="In AIOSEO schema settings for the page, add the most relevant type (Article/FAQ/HowTo/Product, etc.).",
                reference_tab="Schema & Metadata",
                reference_field="Schema Types Count",
            )

        aeo_score = _to_int(row.get("AEO Readiness Score"), 100)
        if aeo_score < 60:
            add_issue(
                url=url,
                issue="Low AEO readiness score",
                severity="Warning",
                panel="Content",
                current_value=aeo_score,
                recommended_target=">=60",
                why_it_matters="Weak answer-style structure lowers AI/answer-engine retrieval potential.",
                how_to_fix="Add concise answer blocks, question-led subheadings, and clear structured sections.",
                reference_tab="AEO",
                reference_field="AEO Readiness Score",
            )
        if not bool(row.get("QAPage/FAQ Schema Present")):
            add_issue(
                url=url,
                issue="No FAQ/QA schema",
                severity="Observation",
                panel="Schema",
                current_value=False,
                recommended_target="True when page has Q&A intent",
                why_it_matters="Q&A schema can improve eligibility for answer-rich results.",
                how_to_fix="If content is Q&A style, add FAQPage/QAPage schema in AIOSEO and keep markup aligned with on-page content.",
                reference_tab="AEO",
                reference_field="QAPage/FAQ Schema Present",
            )
        if _to_int(row.get("Question Heading Count")) == 0:
            add_issue(
                url=url,
                issue="No question-style headings",
                severity="Observation",
                panel="Readability",
                current_value=0,
                recommended_target=">=1 where intent is informational",
                why_it_matters="Question headings better align with query phrasing and snippet extraction.",
                how_to_fix="Add at least one natural question heading (H2/H3) matching user intent.",
                reference_tab="AEO",
                reference_field="Question Heading Count",
            )
        if _to_int(row.get("Paragraphs 40-60 Words Count")) == 0:
            add_issue(
                url=url,
                issue="No concise answer paragraph (40-60 words)",
                severity="Observation",
                panel="Content",
                current_value=0,
                recommended_target=">=1 concise answer block",
                why_it_matters="Compact answer blocks improve direct-answer extraction chances.",
                how_to_fix="Add a direct 40-60 word answer immediately below key question headings.",
                reference_tab="AEO",
                reference_field="Paragraphs 40-60 Words Count",
            )

    rows.sort(
        key=lambda r: (
            severity_rank.get(str(r.get("Severity")), 9),
            -_to_int(r.get("Priority Score"), 0),
            str(r.get("AIOSEO Panel") or ""),
            str(r.get("URL") or ""),
            str(r.get("Issue") or ""),
        )
    )
    return rows


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
