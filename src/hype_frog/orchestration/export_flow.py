"""Historical comparison and workbook export orchestration."""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import pandas as pd

from hype_frog.config import (
    DEFAULT_EFFORT_BY_SEVERITY,
    DEFAULT_OWNER_BY_SEVERITY,
    MAX_RETRIES,
    TIMEOUT_SECONDS,
)
from hype_frog.core import get_logger
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult
from hype_frog.orchestration.enrichment_flow import EnrichmentResult
from hype_frog.orchestration.run_setup import RunSetup
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
)
from hype_frog.utils import normalize_text_hash, normalize_url_key

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExportSummary:
    output_filename: str
    main_rows_written: int
    extra_rows_written: int
    full_suite: bool


def execute_export(
    setup: RunSetup,
    crawl_result: CrawlExecutionResult,
    enrichment: EnrichmentResult,
    *,
    value_or_default_fn: Callable[[object, float], float],
    extract_subfolder_fn: Callable[[str], str],
    build_aeo_rows_fn: Callable[[list[dict[str, object]]], list[dict[str, object]]],
    build_aioseo_rows_fn: Callable[
        [list[dict[str, object]], dict[str, dict[str, object]], dict[str, str]],
        list[dict[str, object]],
    ],
) -> ExportSummary:
    output_filename = crawl_result.output_filename
    urls = crawl_result.crawl_urls
    sitemap_meta = crawl_result.sitemap_meta
    workers = crawl_result.workers
    request_delay = crawl_result.request_delay
    full_suite = crawl_result.full_suite
    previous_audit_path = crawl_result.previous_audit_path
    checkpoint_every = crawl_result.checkpoint_every
    high_value_slugs = setup.high_value_slugs

    main_rows = list(enrichment.main_rows)
    extra_rows = list(enrichment.extra_rows)
    status_by_url = dict(enrichment.status_by_url)

    main_df = pd.DataFrame(main_rows)
    main_by_url = {
        str(row.get("URL") or "").strip(): row for row in main_rows if row.get("URL")
    }
    summary_rules = get_summary_rules()

    prev_issue_ids: set[str] = set()
    prev_counts: dict[str, int] = {}
    prev_fixed_issue_ids: set[str] = set()
    previous_issue_inventory_df = pd.DataFrame()
    previous_audit_exists = bool(previous_audit_path) and os.path.exists(previous_audit_path)
    if previous_audit_exists:
        try:
            prev_xls = pd.ExcelFile(previous_audit_path)
            if "IssueInventory" in prev_xls.sheet_names:
                previous_issue_inventory_df = pd.read_excel(
                    previous_audit_path, sheet_name="IssueInventory"
                )
                if "Stable Issue ID" in previous_issue_inventory_df.columns:
                    prev_issue_ids = {
                        str(value).strip()
                        for value in previous_issue_inventory_df["Stable Issue ID"]
                        .dropna()
                        .tolist()
                        if str(value).strip()
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
                prev_summary = pd.read_excel(previous_audit_path, sheet_name="Summary")
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
                "AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)", "llms.txt Present",
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
            ]
            content_cols = [
                "URL", "H1 Count", "Missing H1 Flag", "Multiple H1 Flag", "Title Missing",
                "Meta Description Missing", "Word Count", "Word Count Band", "Sentence Count",
                "Body Text-to-HTML Ratio", "Readability (Rough Flesch)", "Thin Content Flag",
            ]
            links_cols = [
                "URL", "Internal Links Count", "Unique Internal Links Count", "External Links Count",
                "Nofollow Internal Links Count", "Nofollow External Links Count",
                "Generic Anchor Text Count", "Broken Internal Links Count",
                "Unresolved Internal Links Count", "Internal Link Statuses",
            ]
            media_cols = [
                "URL", "Image Count", "Images", "Images Missing Alt", "Image Alt Coverage (%)",
                "Image Extension Distribution", "Likely Large Image Count", "Image Filename Quality Issues",
                "Image On Canonical Domain (%)", "Mixed Content Detected",
            ]
            schema_cols = [
                "URL", "Schema Types Found", "Schema Types Count", "Schema Parse Errors",
                "OG Title", "OG Description", "OG Image", "Open Graph Complete", "Twitter Card Type",
            ]
            aeo_cols = [
                "URL", "AEO Badge", "AEO Readiness Score", "Why It Matters", "FAQ Section Count",
                "Question Heading Count", "QAPage/FAQ Schema Present", "Speakable Schema Present",
                "HowTo Signal", "Definition Signal", "List/Table Answer Signal",
                "Paragraphs 40-60 Words Count", "Answer Block Detected (First 60 Words)",
                "AEO Extractability Score", "Snippet Preview Mockup", "Title Missing",
                "Meta Description Missing",
            ]
            security_cols = [
                "URL", "Strict-Transport-Security", "Content-Security-Policy", "X-Content-Type-Options",
                "X-Frame-Options", "Referrer-Policy", "Permissions-Policy", "Robots.txt Accessible",
                "Sitemap in Robots.txt", "Robots.txt Crawl-Delay", "Robots.txt Disallow /",
            ]
            write_dict_rows_sheet(writer, "Technical", technical_cols, extra_rows)
            write_dict_rows_sheet(writer, "Content", content_cols, extra_rows)
            write_dict_rows_sheet(writer, "Links", links_cols, extra_rows)
            write_dict_rows_sheet(writer, "Media", media_cols, extra_rows)
            write_dict_rows_sheet(writer, "Schema & Metadata", schema_cols, extra_rows)
            aeo_rows = build_aeo_rows_fn(extra_rows)
            write_dict_rows_sheet(writer, "AEO", aeo_cols, aeo_rows)
            aioseo_rows = build_aioseo_rows_fn(extra_rows, main_by_url, DEFAULT_OWNER_BY_SEVERITY)
            aioseo_cols = [
                "URL", "WordPress Post ID", "Direct Edit Link", "AIOSEO Panel", "Severity",
                "Issue", "Current Value", "Recommended Target", "Why It Matters", "How to Fix in AIOSEO",
                "Reference Tab", "Reference Field", "Action Needed", "Owner", "Status",
                "Priority Score", "Est. Hours", "Stable Issue ID",
            ]
            write_dict_rows_sheet(writer, "AIOSEO", aioseo_cols, aioseo_rows)
            write_dict_rows_sheet(writer, "Security", security_cols, extra_rows)
            psi_rows = [{
                "URL": row.get("URL"),
                "Desktop Score": row.get("Desktop PSI Score", 0),
                "Mobile Score": row.get("Mobile PSI Score", 0),
                "Mobile LCP": row.get("Mobile LCP (s)", 0.0),
                "Mobile CLS": row.get("Mobile CLS", 0.0),
                "Mobile TTFB": row.get("Mobile TTFB (s)", 0.0),
            } for row in extra_rows]
            to_excel_safe(pd.DataFrame(psi_rows), writer, "PSI Performance", index=False)
            indexability_cols = [
                "URL", "Status Code", "Status Class", "Final URL", "Indexability Reason",
                "Meta Robots Raw", "X-Robots-Tag", "Canonical URL", "Canonical Type",
                "Canonical Matches Final URL", "Canonical in Sitemap Match",
            ]
            write_dict_rows_sheet(writer, "Indexability", indexability_cols, extra_rows)
            redirects_rows = []
            for row in extra_rows:
                redirects_rows.append({
                    "URL": row.get("URL"),
                    "Status Code": row.get("Status Code"),
                    "Final URL": row.get("Final URL"),
                    "Redirect Chain Length": row.get("Redirect Chain Length"),
                    "Redirect Target": row.get("Redirect Target"),
                    "Redirect Hops": row.get("Redirect Hops"),
                    "HTTP->HTTPS Redirect": row.get("HTTP->HTTPS Redirect"),
                    "Redirect Loop Flag": (
                        isinstance(row.get("Redirect Hops"), str)
                        and normalize_url_key(row.get("URL", "")) == normalize_url_key(row.get("Final URL", ""))
                        and int(row.get("Redirect Chain Length") or 0) > 0
                    ),
                })
            write_dict_rows_sheet(
                writer, "Redirects",
                ["URL", "Status Code", "Final URL", "Redirect Chain Length", "Redirect Target", "Redirect Hops", "HTTP->HTTPS Redirect", "Redirect Loop Flag"],
                redirects_rows,
            )
            link_rows = []
            for row in extra_rows:
                for item in row.get("Link Details", []):
                    target_status = status_by_url.get(normalize_url_key(item.get("Target URL", "")))
                    crawlable = target_status is None or (isinstance(target_status, int) and target_status < 400)
                    link_rows.append({**item, "Target Status (if crawled)": target_status, "Crawlable": crawlable})
            to_excel_safe(pd.DataFrame(link_rows), writer, "LinksDetail", index=False)
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
                duplicate_rows.append({
                    "URL": row.get("URL"),
                    "Title Duplicate Count": len(title_groups.get(t_key, [])) if t_key else 0,
                    "Meta Description Duplicate Count": len(desc_groups.get(d_key, [])) if d_key else 0,
                    "Title Duplicate URLs": " | ".join(title_groups.get(t_key, [])) if t_key and len(title_groups.get(t_key, [])) > 1 else None,
                    "Meta Duplicate URLs": " | ".join(desc_groups.get(d_key, [])) if d_key and len(desc_groups.get(d_key, [])) > 1 else None,
                })
            to_excel_safe(pd.DataFrame(duplicate_rows), writer, "Duplicates", index=False)
            folder_groups: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
            for row in extra_rows:
                folder_groups[extract_subfolder_fn(str(row.get("Final URL") or row.get("URL") or ""))].append(row)
            cluster_rows = []
            template_issue_counts: defaultdict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
            for folder, urls_in_group in sorted(folder_groups.items(), key=lambda item: len(item[1]), reverse=True):
                if not urls_in_group:
                    continue
                url_count = len(urls_in_group)
                missing_h1_count = sum(1 for row in urls_in_group if bool(row.get("Missing H1 Flag")))
                missing_meta_count = sum(1 for row in urls_in_group if bool(row.get("Meta Description Missing")))
                systemic_issue = None
                exact_action = None
                if (missing_h1_count / max(1, url_count)) >= 0.8:
                    systemic_issue = "Missing H1 is template-wide"
                    exact_action = "Update template to render exactly one descriptive H1 for each page based on page-specific title data."
                elif (missing_meta_count / max(1, url_count)) >= 0.8:
                    systemic_issue = "Missing meta description is template-wide"
                    exact_action = "Update template/meta generation logic to output a unique 120-160 character meta description per page."
                if systemic_issue:
                    cluster_rows.append({
                        "Subfolder": folder,
                        "URL Count": url_count,
                        "Systemic Issue": systemic_issue,
                        "Affected Ratio": round((max(missing_h1_count, missing_meta_count) / max(1, url_count)) * 100, 2),
                        "Exact Action": exact_action,
                    })
                for row in urls_in_group:
                    for issue in str(row.get("Matched Issues") or "").split(" | "):
                        if issue:
                            template_issue_counts[folder][issue] += 1
            pattern_df = pd.DataFrame(cluster_rows)
            if pattern_df.empty:
                pattern_df = pd.DataFrame([{
                    "Subfolder": "/", "URL Count": 0,
                    "Systemic Issue": "No systemic template issues above 80%.",
                    "Affected Ratio": 0, "Exact Action": "N/A",
                }])
            to_excel_safe(pd.DataFrame(pattern_df), writer, "Pattern and Template Issues", index=False, startrow=1)
            writer.book["Pattern and Template Issues"]["A1"] = (
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
            summary_rows = build_summary_rows(summary_rules, extra_rows, template_issue_counts, value_or_default_fn)
            to_excel_safe(pd.DataFrame(summary_rows), writer, "Summary", index=False)
            issue_inventory_rows = build_issue_inventory_rows(summary_rules, extra_rows)
            issue_inventory_df = pd.DataFrame(issue_inventory_rows)
            to_excel_safe(issue_inventory_df, writer, "IssueInventory", index=False)
            fixplan_rows = build_fixplan_rows(
                summary_rules, extra_rows, aeo_issue_names, root_cause_and_fix,
                DEFAULT_EFFORT_BY_SEVERITY, DEFAULT_OWNER_BY_SEVERITY,
            )
            fixplan_df = pd.DataFrame(sorted(fixplan_rows, key=lambda item: (-item["Affected Count"], item["Severity"])))
            to_excel_safe(fixplan_df, writer, "FixPlan", index=False)
            hub_base_rows = build_content_optimisation_hub_rows(main_rows, extra_rows, fixplan_rows)
            extra_by_url = {str(row.get("URL") or ""): row for row in extra_rows}
            content_hub_rows: list[dict[str, object]] = []
            for hub_row in hub_base_rows:
                metrics = extra_by_url.get(str(hub_row.get("URL") or ""), {})
                content_hub_rows.append({**hub_row, "SEO Score": metrics.get("SEO Score", 0.0), "Technical Health": metrics.get("Technical Health", 0.0)})
            content_hub_cols = [
                "Action Required", "Status", "Assigned Owner", "URL", "Current SEO Score", "Projected SEO Score",
                "Elementor Builder Link", "Target Keywords", "Current Page Copy Snippet", "Current Title",
                "Proposed Title (50-60 Chars)", "Title Count", "Current Meta Desc",
                "Proposed Meta Desc (120-160 Chars)", "Desc Count", "Current H-Tag Structure",
                "Proposed H-Tag Fixes", "AEO Answer Block Draft", "FAQ/QA Draft", "Current OG-Image URL",
                "OG Image Preview", "Social Share Note", "SEO Score", "Technical Health", "Copy Score", "Open in Main",
            ]
            write_dict_rows_sheet(writer, CONTENT_OPTIMISATION_HUB_SHEET, content_hub_cols, content_hub_rows)
            # Remaining dashboard/delta/report tabs preserved from prior flow
            priority_rows = []
            for row in extra_rows:
                risk_score = (
                    value_or_default_fn(row.get("Critical Issues Count"), 0.0) * 30
                    + value_or_default_fn(row.get("Warning Issues Count"), 0.0) * 10
                    + (100 - value_or_default_fn(row.get("SEO Health Score"), 100.0))
                )
                reasons = []
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
                    else "Canonical Points Elsewhere" if row.get("Canonical Type") == "cross-canonical"
                    else "Noindex Directive" if "noindex" in str(row.get("Indexability Reason", "")).lower()
                    else ""
                )
                url_value = str(row.get("URL") or "")
                revenue_intent = "High" if any(slug in url_value.lower() for slug in high_value_slugs) else "Standard"
                priority_rows.append({
                    "URL": row.get("URL"),
                    "Business Risk Score": int(risk_score),
                    "SEO Health Score": row.get("SEO Health Score"),
                    "Severity Badge": row.get("Severity Badge"),
                    "Critical Issues Count": row.get("Critical Issues Count"),
                    "Warning Issues Count": row.get("Warning Issues Count"),
                    "Indexability Reason": row.get("Indexability Reason"),
                    "Broken Internal Links Count": row.get("Broken Internal Links Count"),
                    "Canonical Type": row.get("Canonical Type"),
                    "GSC Impressions": row.get("GSC Impressions", 0.0),
                    "GSC CTR": row.get("GSC CTR", 0.0),
                    "Revenue Intent": revenue_intent,
                    "Why Prioritized": " | ".join(reasons) if reasons else "Monitor",
                    "Action Needed": "Yes" if risk_score >= 30 else "No",
                    "Owner": owner_for_issue(owner_seed_issue, str(row.get("Severity Badge") or "")),
                    "Sprint": "",
                    "Status": "Open",
                })
            priority_df = pd.DataFrame(sorted(priority_rows, key=lambda item: item["Business Risk Score"], reverse=True))
            to_excel_safe(priority_df, writer, "Priority URLs", index=False)
            total_urls = len(extra_rows)
            pass_count = sum(
                1
                for row in extra_rows
                if str(row.get("Severity Badge") or "") == "Pass"
            )
            critical_count = sum(
                1
                for row in extra_rows
                if str(row.get("Severity Badge") or "") == "Critical"
            )
            warning_count = sum(
                1
                for row in extra_rows
                if str(row.get("Severity Badge") or "") == "Warning"
            )
            top_blockers = fixplan_df.head(10)[["Issue Type", "Severity", "Affected Count"]]
            seo_health_values: list[float] = []
            for row in extra_rows:
                raw_hs = row.get("SEO Health Score")
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
            dashboard_rows = [
                {"Metric": "URLs Crawled", "Value": total_urls},
                {"Metric": "SEO Pass Rate %", "Value": seo_pass_pct},
                {"Metric": "Health Score %", "Value": avg_seo_health_pct},
                {"Metric": "Critical URL Count", "Value": critical_count},
                {"Metric": "Warning URL Count", "Value": warning_count},
                {"Metric": "Projected Health Score %", "Value": projected_health_pct},
                {"Metric": "Projected Pass Rate %", "Value": projected_pass_pct},
            ]
            to_excel_safe(pd.DataFrame(dashboard_rows), writer, "Dashboard", index=False)
            critical_issues_rows = [
                {"Block": "Critical Issues", "URL": row.get("URL"), "Issue": row.get("Matched Issues")}
                for row in extra_rows
                if value_or_default_fn(row.get("Critical Issues Count"), 0.0) > 0
            ][:10]
            quick_wins_rows = [
                {"Block": "Quick Wins", "URL": row.get("URL"), "Issue": "Missing meta on high-impression page"}
                for row in extra_rows
                if bool(row.get("Meta Description Missing"))
                and value_or_default_fn(row.get("GSC Impressions"), 0.0) > 500
            ][:10]
            growth_rows = [
                {"Block": "Growth Opportunities", "URL": row.get("URL"), "Issue": "Missing FAQ/QA schema or thin content on revenue URL"}
                for row in extra_rows
                if (
                    (
                        not bool(row.get("QAPage/FAQ Schema Present"))
                        or value_or_default_fn(row.get("Word Count"), 0.0) < 300
                    )
                    and any(slug in str(row.get("URL") or "").lower() for slug in high_value_slugs)
                )
            ][:10]
            action_hub_df = pd.DataFrame(critical_issues_rows + quick_wins_rows + growth_rows)
            if not action_hub_df.empty:
                to_excel_safe(action_hub_df, writer, "Dashboard", index=False, startrow=20)
            immediate_action_cols = ["URL", "Business Risk Score", "Why Prioritized", "Action Needed", "Owner", "Status"]
            immediate_actions_df = priority_df.reindex(columns=immediate_action_cols).head(5).copy()
            immediate_actions_df.insert(0, "Rank", range(1, len(immediate_actions_df) + 1))
            immediate_actions_startrow = len(dashboard_rows) + len(top_blockers) + 7
            to_excel_safe(
                pd.DataFrame([{"Immediate Actions": "Top 5 URLs by Business Risk Score"}]),
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
            quick_reference_rows = [
                {"Section": "[Meta Data Standards]", "Item": "", "Guideline": "", "Why It Matters": ""},
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
                {"Section": "[On-Page Structure (H-Tags)]", "Item": "", "Guideline": "", "Why It Matters": ""},
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
                {"Section": "[AEO (Answer Engine Optimisation) & Content]", "Item": "", "Guideline": "", "Why It Matters": ""},
                {
                    "Section": "",
                    "Item": "AEO Answer Blocks",
                    "Guideline": "40-60 words. Placed directly beneath an H2 question. Must be factual, objective, and devoid of marketing fluff.",
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
                {"Section": "[Visual & Social Branding]", "Item": "", "Guideline": "", "Why It Matters": ""},
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
            to_excel_safe(pd.DataFrame(quick_reference_rows), writer, "Quick Reference Guide", index=False)
            run_meta_rows = [
                {"Key": "Run Timestamp", "Value": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")},
                {"Key": "Total URLs", "Value": len(urls)},
                {"Key": "Mode", "Value": "Full Suite"},
                {"Key": "Workers", "Value": workers},
                {"Key": "Delay Seconds", "Value": request_delay},
                {"Key": "Retries", "Value": MAX_RETRIES},
                {"Key": "Timeout Seconds", "Value": TIMEOUT_SECONDS},
                {"Key": "Checkpoint Every", "Value": checkpoint_every},
                {"Key": "Previous Audit Path", "Value": previous_audit_path or "Not supplied"},
            ]
            to_excel_safe(pd.DataFrame(run_meta_rows), writer, "RunMetadata", index=False)
            current_issue_ids = {
                str(value).strip()
                for value in issue_inventory_df.get("Stable Issue ID", pd.Series(dtype="object")).dropna().tolist()
                if str(value).strip()
            }
            resolved_issues = prev_issue_ids - current_issue_ids
            delta_rows = [
                {"Metric": "New Issues", "Count": len(current_issue_ids - prev_issue_ids)},
                {"Metric": "Resolved Issues", "Count": len(resolved_issues)},
                {"Metric": "Unchanged Issues", "Count": len(current_issue_ids & prev_issue_ids)},
                {"Metric": "Previously Fixed But Reopened", "Count": len(current_issue_ids & prev_fixed_issue_ids)},
            ]
            for _, issue_name, _ in summary_rules:
                current_count = len([row for row in extra_rows if issue_name in str(row.get("Matched Issues") or "").split(" | ")])
                delta_rows.append({"Metric": f"Issue Delta: {issue_name}", "Count": current_count - int(prev_counts.get(issue_name, 0))})
            to_excel_safe(pd.DataFrame(delta_rows), writer, "DeltaFromPreviousRun", index=False)
            if (
                not previous_issue_inventory_df.empty
                and "Stable Issue ID" in previous_issue_inventory_df.columns
            ):
                previous_issue_inventory_df = previous_issue_inventory_df.copy()
                previous_issue_inventory_df["Stable Issue ID"] = (
                    previous_issue_inventory_df["Stable Issue ID"].astype(str).str.strip()
                )
                resolved_issues_df = previous_issue_inventory_df[
                    previous_issue_inventory_df["Stable Issue ID"].isin(resolved_issues)
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
                {"Section": "How To Use", "Term": "Step 1: Start on Dashboard", "Meaning": "Review pass rate, critical URL count, and Immediate Actions to understand overall risk first.", "Values/Threshold": "5-minute executive scan", "Related Tabs": "Dashboard, Priority URLs"},
                {"Section": "How To Use", "Term": "Step 2: Prioritize and Assign", "Meaning": "Use Priority URLs and FixPlan to pick highest-impact items, assign owner, and set status/sprint.", "Values/Threshold": "Work top-down by Business Risk Score", "Related Tabs": "Priority URLs, FixPlan"},
                {"Section": "How To Use", "Term": "Step 3: Execute and Validate", "Meaning": "Implement fixes, then verify by checking Technical/Indexability/AEO tabs and rerunning the audit.", "Values/Threshold": "Close loop every sprint", "Related Tabs": "Technical, Indexability, AEO, AIOSEO"},
                {"Section": "Orientation", "Term": "Where to Start", "Meaning": "If you're short on time, work only Critical and Warning issues first, then return to Observation items.", "Values/Threshold": "Critical > Warning > Observation", "Related Tabs": "Summary, FixPlan, Technical"},
                {"Section": "Color Key", "Term": "Green", "Meaning": "Pass / aligned with best practice or completed workflow item.", "Values/Threshold": "Good", "Related Tabs": "All"},
                {"Section": "Color Key", "Term": "Orange", "Meaning": "Warning / in progress / medium-priority attention needed.", "Values/Threshold": "Medium risk", "Related Tabs": "All"},
                {"Section": "Color Key", "Term": "Red", "Meaning": "Failure / high-priority issue or to-do critical task.", "Values/Threshold": "High risk", "Related Tabs": "All"},
            ]
            to_excel_safe(pd.DataFrame(legend_rows), writer, "Glossary & Legend", index=False)
            crawl_inlinks_map: defaultdict[str, set[str]] = defaultdict(set)
            crawled_set_main = {normalize_url_key(url) for url in main_df["URL"].dropna().tolist()}
            for row in extra_rows:
                source = normalize_url_key(row.get("URL"))
                for target in row.get("Internal Links List", []):
                    target_norm = normalize_url_key(target)
                    if target_norm in crawled_set_main:
                        crawl_inlinks_map[target_norm].add(source)
            graph_rows = [
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
                    "Internal PageRank": next(
                        (
                            row.get("Internal PageRank")
                            for row in extra_rows
                            if normalize_url_key(row.get("URL")) == normalize_url_key(url_item)
                        ),
                        0.0,
                    ),
                }
                for url_item in main_df["URL"].dropna().tolist()
            ]
            to_excel_safe(pd.DataFrame(graph_rows), writer, "CrawlGraph", index=False)
            sitemap_rows = []
            if sitemap_meta:
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
            to_excel_safe(pd.DataFrame(sitemap_rows), writer, "SitemapQA", index=False)
            apply_tab_hyperlinks(writer)
            for sname in (
                "Dashboard", CONTENT_OPTIMISATION_HUB_SHEET, "Quick Reference Guide", "Summary", "FixPlan",
                "Content", "Main", "Priority URLs", "AIOSEO", "Technical", "PSI Performance", "AEO",
                "Indexability", "Redirects", "Security", "Schema & Metadata", "Links", "LinksDetail",
                "Media", "Duplicates", "Pattern and Template Issues", "CrawlGraph", "SitemapQA",
                "IssueInventory", "ResolvedIssues", "DeltaFromPreviousRun", "RunMetadata", "Glossary & Legend",
            ):
                if sname in writer.sheets:
                    adjust_sheet_format(writer, sname)
                else:
                    logger.warning(
                        "Skipping sheet formatting for missing sheet: %s", sname
                    )
        apply_workbook_export_guardrails(writer.book)
        logger.info("Audit complete! Report saved to %s", output_filename)
    finally:
        if writer is not None:
            writer.close()

    return ExportSummary(
        output_filename=output_filename,
        main_rows_written=len(main_rows),
        extra_rows_written=len(extra_rows),
        full_suite=full_suite,
    )
