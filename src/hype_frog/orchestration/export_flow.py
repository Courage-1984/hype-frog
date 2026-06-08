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
from hype_frog.core.models import SummaryMetricsPayload
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult
from hype_frog.orchestration.enrichment_flow import EnrichmentResult
from hype_frog.orchestration.export_registry import (
    ExportRegistryConfig,
    build_crawlgraph_rows,
    build_delta_and_trend_rows,
    build_duplicates_rows,
    build_pattern_rows,
    build_priority_rows,
    build_sitemapqa_rows,
    get_finalization_steps,
    get_merged_sheet_columns,
    get_sheet_sequence,
    get_standard_sheet_columns,
)
from hype_frog.orchestration.run_setup import RunSetup
from hype_frog.pipeline.export import sanitize_rows, to_excel_safe
from hype_frog.reporter import adjust_sheet_format, apply_tab_hyperlinks
from hype_frog.reporter.sheets.config import (
    AIOSEO_RECOMMENDATIONS_SHEET,
    AUDIT_RUN_DETAILS_SHEET,
)
from hype_frog.reporter.engine_rows import (
    CONTENT_HUB_EXPORT_COLUMNS,
    CONTENT_HUB_METRICS_EXPORT_COLUMNS,
)
from hype_frog.reporter.excel_engine import (
    apply_workbook_export_guardrails,
    build_content_optimisation_hub_rows,
    build_fixplan_rows,
    write_dict_rows_sheet,
)
from hype_frog.reporter.engine_io import apply_link_intelligence_summary_broken_formulas
from hype_frog.reporter.sheets.config import (
    CONTENT_HUB_METRICS_SHEET,
    CONTENT_OPTIMISATION_HUB_SHEET,
)
from hype_frog.pipeline.link_inventory import unique_external_health_counts
from hype_frog.reporter.sheets.merged_builders import (
    build_content_ai_readiness_rows,
    build_issue_register_rows,
    build_link_intelligence_rows,
    build_link_inventory_rows,
    build_technical_diagnostics_rows,
    build_template_duplication_risks_rows,
)
from hype_frog.reporter.summary_builder import (
    build_issue_inventory_rows,
    build_summary_rows,
)
from hype_frog.rules import (
    get_summary_rules,
    owner_for_issue,
    root_cause_and_fix,
)
from hype_frog.core.url_normalization import normalize_url
from hype_frog.extractors.semantic_setup import probe_semantic_engine

logger = get_logger(__name__)


def normalize_url_key(url: object, keep_query: bool = True) -> str:
    return normalize_url(url, keep_query=keep_query)


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

    typed_main_rows = list(enrichment.typed_main_rows)
    typed_extra_rows = list(enrichment.typed_extra_rows)
    main_rows = [row.values for row in typed_main_rows]
    extra_rows = [row.values for row in typed_extra_rows]
    status_by_url = dict(enrichment.status_by_url)

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
        write_dict_rows_sheet(writer, "Main", main_cols, typed_main_rows)
        adjust_sheet_format(writer, "Main")
        if full_suite:
            sheet_columns = get_standard_sheet_columns()
            merged_columns = get_merged_sheet_columns()
            aioseo_rows = build_aioseo_rows_fn(extra_rows, main_by_url, DEFAULT_OWNER_BY_SEVERITY)
            write_dict_rows_sheet(
                writer,
                AIOSEO_RECOMMENDATIONS_SHEET,
                sheet_columns[AIOSEO_RECOMMENDATIONS_SHEET],
                aioseo_rows,
            )
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
            link_rows = []
            for row in extra_rows:
                for item in row.get("Link Details", []):
                    raw_code = item.get("Status Code")
                    target_status = status_by_url.get(
                        normalize_url_key(item.get("Target URL", ""))
                    )
                    if raw_code is not None and raw_code != "":
                        target_status = raw_code
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
            duplicate_rows = build_duplicates_rows(main_rows, extra_rows)
            pattern_rows, template_issue_counts = build_pattern_rows(
                extra_rows,
                extract_subfolder_fn=extract_subfolder_fn,
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
                typed_extra_rows,
                template_issue_counts,
                value_or_default_fn,
                main_rows=typed_main_rows,
            )
            issue_inventory_rows = build_issue_inventory_rows(
                summary_rules,
                typed_extra_rows,
                main_rows=typed_main_rows,
            )
            issue_inventory_df = pd.DataFrame(issue_inventory_rows)
            technical_diagnostics_rows = build_technical_diagnostics_rows(
                extra_rows, main_rows=main_rows
            )
            content_ai_rows = build_content_ai_readiness_rows(
                extra_rows, main_rows=main_rows
            )
            issue_register_rows = build_issue_register_rows(
                summary_rows=summary_rows,
                issue_inventory_rows=issue_inventory_rows,
            )
            graph_rows = build_crawlgraph_rows(
                main_urls=[str(row.get("URL") or "") for row in main_rows if row.get("URL")],
                extra_rows=extra_rows,
            )
            link_intelligence_rows = build_link_intelligence_rows(
                extra_rows=extra_rows,
                link_detail_rows=link_rows,
                crawlgraph_rows=graph_rows,
                main_rows=main_rows,
            )
            summary_df = pd.DataFrame(summary_rows)
            to_excel_safe(summary_df, writer, "Summary", index=False)
            to_excel_safe(issue_inventory_df, writer, "IssueInventory", index=False)
            template_duplication_rows = build_template_duplication_risks_rows(
                duplicate_rows=duplicate_rows,
                pattern_rows=pattern_rows,
            )
            write_dict_rows_sheet(
                writer,
                "Issue Register",
                merged_columns["Issue Register"],
                issue_register_rows,
            )
            write_dict_rows_sheet(
                writer,
                "Technical Diagnostics",
                merged_columns["Technical Diagnostics"],
                technical_diagnostics_rows,
            )
            write_dict_rows_sheet(
                writer,
                "Content & AI Readiness",
                merged_columns["Content & AI Readiness"],
                content_ai_rows,
            )
            write_dict_rows_sheet(
                writer,
                "Link Intelligence",
                merged_columns["Link Intelligence"],
                link_intelligence_rows,
            )
            link_inventory_rows = build_link_inventory_rows(extra_rows)
            write_dict_rows_sheet(
                writer,
                "Link Inventory",
                merged_columns["Link Inventory"],
                link_inventory_rows,
            )
            ok_unique_ext, total_unique_ext = unique_external_health_counts(
                link_inventory_rows
            )

            apply_link_intelligence_summary_broken_formulas(writer.book)

            write_dict_rows_sheet(
                writer,
                "Template & Duplication Risks",
                merged_columns["Template & Duplication Risks"],
                template_duplication_rows,
            )
            fixplan_rows = build_fixplan_rows(
                summary_rules, typed_extra_rows, aeo_issue_names, root_cause_and_fix,
                DEFAULT_EFFORT_BY_SEVERITY, DEFAULT_OWNER_BY_SEVERITY,
            )
            fixplan_df = pd.DataFrame(sorted(fixplan_rows, key=lambda item: (-item["Affected Count"], item["Severity"])))
            to_excel_safe(fixplan_df, writer, "FixPlan", index=False)
            hub_base_rows, hub_metrics_rows = build_content_optimisation_hub_rows(
                typed_main_rows, typed_extra_rows, fixplan_rows
            )
            content_hub_cols = list(CONTENT_HUB_EXPORT_COLUMNS)
            write_dict_rows_sheet(
                writer, CONTENT_OPTIMISATION_HUB_SHEET, content_hub_cols, hub_base_rows
            )
            write_dict_rows_sheet(
                writer,
                CONTENT_HUB_METRICS_SHEET,
                list(CONTENT_HUB_METRICS_EXPORT_COLUMNS),
                hub_metrics_rows,
            )
            # Remaining dashboard/delta/report tabs preserved from prior flow
            priority_rows = build_priority_rows(
                extra_rows,
                high_value_slugs=high_value_slugs,
                value_or_default_fn=value_or_default_fn,
                owner_for_issue_fn=owner_for_issue,
            )
            priority_df = pd.DataFrame(priority_rows)
            to_excel_safe(priority_df, writer, "Priority URLs", index=False)
            total_urls = len(typed_extra_rows)
            pass_count = sum(
                1
                for row in typed_extra_rows
                if str(row.values.get("Severity Badge") or "") == "Pass"
            )
            critical_count = sum(
                1
                for row in typed_extra_rows
                if str(row.values.get("Severity Badge") or "") == "Critical"
            )
            warning_count = sum(
                1
                for row in typed_extra_rows
                if str(row.values.get("Severity Badge") or "") == "Warning"
            )
            top_blockers = fixplan_df.head(10)[["Issue Type", "Severity", "Affected Count"]]
            seo_health_values: list[float] = []
            for row in typed_extra_rows:
                raw_hs = row.values.get("SEO Health Score")
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
            summary_metrics = SummaryMetricsPayload(
                urls_crawled=total_urls,
                seo_pass_rate_pct=seo_pass_pct,
                health_score_pct=avg_seo_health_pct,
                critical_url_count=critical_count,
                warning_url_count=warning_count,
                projected_health_score_pct=projected_health_pct,
                projected_pass_rate_pct=projected_pass_pct,
            )
            dashboard_rows = [
                {"Metric": "URLs Crawled", "Value": summary_metrics.urls_crawled},
                {"Metric": "SEO Pass Rate %", "Value": summary_metrics.seo_pass_rate_pct},
                {"Metric": "Health Score %", "Value": summary_metrics.health_score_pct},
                {"Metric": "Critical URL Count", "Value": summary_metrics.critical_url_count},
                {"Metric": "Warning URL Count", "Value": summary_metrics.warning_url_count},
                {
                    "Metric": "Projected Health Score %",
                    "Value": summary_metrics.projected_health_score_pct,
                },
                {
                    "Metric": "Projected Pass Rate %",
                    "Value": summary_metrics.projected_pass_rate_pct,
                },
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
                {
                    "Section": "[2025 AEO STRATEGY & STANDARDS]",
                    "Item": "",
                    "Guideline": "",
                    "Why It Matters": "",
                },
                {
                    "Section": "",
                    "Item": "The 'Nugget' Rule",
                    "Guideline": (
                        "The direct answer to a query must be located within the first 100 words "
                        "of the relevant section."
                    ),
                    "Why It Matters": "Answer engines surface the earliest concise fact block; burying the answer loses extraction priority.",
                },
                {
                    "Section": "",
                    "Item": "Objective Fact-Density",
                    "Guideline": (
                        "Avoid subjective adjectives ('award-winning', 'best'). LLMs prioritize "
                        "objective nouns and verified data points."
                    ),
                    "Why It Matters": "Verifiable, concrete phrasing is easier to quote and less likely to be filtered as promotional noise.",
                },
                {
                    "Section": "",
                    "Item": "Inverted Pyramid Structure",
                    "Guideline": (
                        "Question Heading > Concise 50-word Answer > Supporting Data/List > "
                        "Detailed Context."
                    ),
                    "Why It Matters": "Mirrors how models chunk content: lead with the extractable answer, then evidence, then depth.",
                },
                {
                    "Section": "",
                    "Item": "Schema as an API",
                    "Guideline": (
                        "View Schema not just for Google snippets, but as a direct data-feed for "
                        "AI Answer Engines."
                    ),
                    "Why It Matters": "Structured types (FAQ, HowTo, Speakable) become machine-addressable facts when kept in sync with visible copy.",
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
            playbook_rows = list(quick_reference_rows)
            semantic_probe = probe_semantic_engine()
            crawl_semantic_modes = {
                str(row.values.get("Semantic Analysis Mode") or "").strip()
                for row in typed_extra_rows
                if str(row.values.get("Semantic Analysis Mode") or "").strip()
            }
            gsc_freshness = next(
                (
                    str(row.values.get("GSC Data Freshness") or "").strip()
                    for row in typed_extra_rows
                    if str(row.values.get("GSC Data Freshness") or "").strip()
                ),
                "",
            )
            gsc_matched_urls = sum(
                1
                for row in typed_extra_rows
                if str(row.values.get("GSC Coverage Note") or "").startswith("Matched in GSC")
            )
            gsc_unmatched_urls = sum(
                1
                for row in typed_extra_rows
                if "No Search Analytics row matched" in str(row.values.get("GSC Coverage Note") or "")
            )
            gsc_low_volume_urls = sum(
                1
                for row in typed_extra_rows
                if "low impressions" in str(row.values.get("GSC Coverage Note") or "").lower()
            )
            crawl_duration_s = round(crawl_result.crawl_duration_seconds, 1)
            rendered_source_count = sum(
                1 for row in typed_extra_rows if row.values.get("Extraction Source") == "rendered_browser"
            )
            raw_source_count = sum(
                1 for row in typed_extra_rows if row.values.get("Extraction Source") == "raw_http"
            )
            render_fallback_count = sum(
                1 for row in typed_extra_rows if row.values.get("Extraction Source Fallback")
            )
            logger.info("Crawl duration for Dashboard RunMetadata: %.1fs", crawl_duration_s)
            run_meta_rows = [
                {"Key": "Run Timestamp", "Value": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")},
                {"Key": "Total URLs", "Value": len(urls)},
                {"Key": "Duration (s)", "Value": crawl_duration_s},
                {"Key": "Crawl Mode", "Value": setup.crawl_mode},
                {
                    "Key": "Extraction Source Rendered Count",
                    "Value": rendered_source_count,
                },
                {"Key": "Extraction Source Raw HTTP Count", "Value": raw_source_count},
                {"Key": "Extraction Source Fallback Count", "Value": render_fallback_count},
                {"Key": "GSC Data Freshness", "Value": gsc_freshness or "Not available"},
                {
                    "Key": "GSC Coverage Note",
                    "Value": (
                        f"{gsc_matched_urls} URL(s) matched Search Analytics; "
                        f"{gsc_unmatched_urls} unmatched; "
                        f"{gsc_low_volume_urls} low-impression (CTR directional only)"
                        if gsc_freshness
                        else "GSC Search Analytics not loaded for this run"
                    ),
                },
                {"Key": "Mode", "Value": "Full Suite"},
                {
                    "Key": "Semantic Engine (install probe)",
                    "Value": semantic_probe.message,
                },
                {
                    "Key": "Semantic Analysis Modes (crawl)",
                    "Value": ", ".join(sorted(crawl_semantic_modes)) or "N/A",
                },
                {"Key": "Workers", "Value": workers},
                {"Key": "Delay Seconds", "Value": request_delay},
                {"Key": "Retries", "Value": MAX_RETRIES},
                {"Key": "Timeout Seconds", "Value": TIMEOUT_SECONDS},
                {"Key": "Checkpoint Every", "Value": checkpoint_every},
                {"Key": "Previous Audit Path", "Value": previous_audit_path or "Not supplied"},
                {
                    "Key": "External Link Unique Denominator",
                    "Value": int(total_unique_ext),
                },
                {"Key": "External Link Unique 200 OK", "Value": int(ok_unique_ext)},
                {
                    "Key": "External Sniff Performed",
                    "Value": int(1 if setup.check_external_link_status else 0),
                },
            ]
            to_excel_safe(
                pd.DataFrame(run_meta_rows), writer, AUDIT_RUN_DETAILS_SHEET, index=False
            )
            delta_rows, resolved_issues_df = build_delta_and_trend_rows(
                issue_inventory_df=issue_inventory_df,
                typed_extra_rows=typed_extra_rows,
                summary_rules=summary_rules,
                prev_issue_ids=prev_issue_ids,
                prev_fixed_issue_ids=prev_fixed_issue_ids,
                prev_counts=prev_counts,
                previous_issue_inventory_df=previous_issue_inventory_df,
                baseline_report=not previous_audit_exists,
            )
            to_excel_safe(pd.DataFrame(delta_rows), writer, "DeltaFromPreviousRun", index=False)
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
            playbook_rows.extend(
                [
                    {
                        "Section": "",
                        "Item": "",
                        "Guideline": "",
                        "Why It Matters": "",
                    },
                    {
                        "Section": "[Glossary & Legend]",
                        "Item": "",
                        "Guideline": "",
                        "Why It Matters": "",
                    },
                ]
            )
            for row in legend_rows:
                playbook_rows.append(
                    {
                        "Section": row.get("Section", ""),
                        "Item": row.get("Term", ""),
                        "Guideline": row.get("Values/Threshold", ""),
                        "Why It Matters": row.get("Meaning", ""),
                    }
                )
            to_excel_safe(pd.DataFrame(playbook_rows), writer, "Playbook", index=False)
            sitemap_rows = build_sitemapqa_rows(
                sitemap_meta=sitemap_meta,
                extra_rows=extra_rows,
            )
            to_excel_safe(pd.DataFrame(sitemap_rows), writer, "SitemapQA", index=False)
        registry_config = ExportRegistryConfig(full_suite=full_suite)
        for final_step in get_finalization_steps():
            if final_step == "apply_tab_hyperlinks":
                apply_tab_hyperlinks(writer)
            elif final_step == "format_sheets":
                for sname in get_sheet_sequence(registry_config):
                    format_name = sname
                    if format_name in writer.sheets:
                        adjust_sheet_format(writer, format_name)
                    else:
                        logger.warning(
                            "Skipping sheet formatting for missing sheet: %s", format_name
                        )
            elif final_step == "apply_workbook_export_guardrails":
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
