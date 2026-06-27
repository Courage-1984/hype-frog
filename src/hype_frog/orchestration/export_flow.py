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
    resolve_project_relative_path,
)
from hype_frog.core import get_logger
from hype_frog.core.console import log_phase_banner
from hype_frog.core.models import SummaryMetricsPayload
from hype_frog.core.crawl_log import CRAWL_LOG_COLUMNS, crawl_log_sheet_rows
from hype_frog.crawler.robots_mapping import (
    ROBOTS_ANALYSIS_COLUMNS,
    build_robots_analysis_rows,
)
from hype_frog.analysis.link_equity import (
    ANCHOR_TEXT_AUDIT_COLUMNS,
    LINK_EQUITY_COLUMNS,
    build_anchor_text_audit_rows,
    build_link_equity_rows,
)
from hype_frog.analysis.snippet_opportunities import (
    SNIPPET_OPPORTUNITY_COLUMNS,
    build_snippet_opportunity_rows,
)
from hype_frog.analysis.third_party_scripts import (
    SCRIPT_INVENTORY_COLUMNS,
    build_script_inventory_rows,
)
from hype_frog.rules.playbook_entries import build_issue_playbook_rows
from hype_frog.pipeline.enrich import compute_internal_link_intelligence
from hype_frog.pipeline.image_inventory import (
    IMAGE_INVENTORY_COLUMNS,
    build_image_inventory_rows,
)
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult
from hype_frog.orchestration.enrichment_flow import EnrichmentResult
from hype_frog.analysis.delta_engine import (
    build_delta_workbook_output,
    delta_summary_path_for_workbook,
    load_run_snapshot,
    save_run_snapshot_json,
    snapshot_from_current_run,
)
from hype_frog.reporter.pdf_exporter import export_executive_summary_pdf
from hype_frog.orchestration.export_registry import (
    ExportRegistryConfig,
    build_crawlgraph_rows,
    build_cms_action_url_rows,
    build_duplicates_rows,
    build_pattern_rows,
    build_priority_rows,
    build_sitemapqa_rows,
    get_finalization_steps,
    get_merged_sheet_columns,
    get_sheet_sequence,
    get_standard_sheet_columns,
    CMS_ACTION_URLS_COLUMNS,
    CMS_ACTION_URLS_SHEET,
)
from hype_frog.orchestration.run_setup import RunSetup
from hype_frog.pipeline.export import sanitize_rows, to_excel_safe
from hype_frog.reporter import adjust_sheet_format, apply_tab_hyperlinks
from hype_frog.reporter.sheets.config import (
    AIOSEO_RECOMMENDATIONS_SHEET,
    ANCHOR_TEXT_AUDIT_SHEET,
    AUDIT_RUN_DETAILS_SHEET,
    CRAWL_LOG_SHEET,
    COMPETITOR_BENCHMARKS_SHEET,
    IMAGE_INVENTORY_SHEET,
    LINK_EQUITY_MAP_SHEET,
    REDIRECT_MAP_SHEET,
    ROBOTS_ANALYSIS_SHEET,
    SCRIPT_INVENTORY_SHEET,
    SNIPPET_OPPORTUNITIES_SHEET,
    COMPETITOR_BENCHMARKS_SHEET,
)
from hype_frog.reporter.sheets.executive_dashboard import write_executive_dashboard
from hype_frog.reporter.chart_compat import patch_xlsx_app_xml_for_excel_compatibility
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
    build_broken_link_impact_rows,
    build_content_ai_readiness_rows,
    build_issue_register_rows,
    build_link_intelligence_rows,
    build_link_inventory_rows,
    build_quick_wins_rows,
    build_redirect_map_rows,
    build_redirects_sheet_rows,
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

# Sheets emitted only when optional enrichment data exists (e.g. --competitors).
_OPTIONAL_FORMAT_SHEETS: frozenset[str] = frozenset({COMPETITOR_BENCHMARKS_SHEET})


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
    sitemap_files_meta = crawl_result.sitemap_files_meta
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
    previous_snapshot = None
    previous_audit_exists = bool(previous_audit_path) and os.path.exists(previous_audit_path)
    if previous_audit_exists:
        previous_snapshot = load_run_snapshot(previous_audit_path)
        if previous_snapshot is not None:
            prev_issue_ids = set(previous_snapshot.issue_ids)
            prev_fixed_issue_ids = set(previous_snapshot.fixed_issue_ids)
            prev_counts = dict(previous_snapshot.issue_counts_by_name)
            logger.info(
                "Loaded previous run snapshot from %s (%s issues).",
                previous_audit_path,
                len(prev_issue_ids),
            )
        else:
            logger.warning(
                "Could not parse previous audit snapshot at %s; delta compare degraded.",
                previous_audit_path,
            )
    elif previous_audit_path:
        logger.warning(
            "Previous audit file not found: %s. Delta compare will mark all current issues as New.",
            previous_audit_path,
        )

    main_rows = sanitize_rows(main_rows)
    extra_rows = sanitize_rows(extra_rows)
    writer = None
    current_snapshot = None
    summary_rows: list[dict[str, Any]] = []
    fixplan_rows: list[dict[str, Any]] = []
    quick_wins_rows: list[dict[str, Any]] = []
    priority_rows: list[dict[str, Any]] = []
    broken_link_impact_rows: list[dict[str, Any]] = []
    run_timestamp: str = ""
    summary_metrics: SummaryMetricsPayload | None = None
    log_phase_banner("EXPORT: Building workbook")
    try:
        writer = pd.ExcelWriter(output_filename, engine="openpyxl")
        main_cols = list(main_rows[0].keys()) if main_rows else []
        logger.info("Writing Main sheet (%d rows)...", len(main_rows))
        write_dict_rows_sheet(writer, "Main", main_cols, typed_main_rows)
        adjust_sheet_format(writer, "Main")
        if full_suite:
            logger.info("Building full audit: %d URLs...", len(typed_extra_rows))
            sheet_columns = get_standard_sheet_columns()
            merged_columns = get_merged_sheet_columns()
            aioseo_rows = build_aioseo_rows_fn(extra_rows, main_by_url, DEFAULT_OWNER_BY_SEVERITY)
            write_dict_rows_sheet(
                writer,
                AIOSEO_RECOMMENDATIONS_SHEET,
                sheet_columns[AIOSEO_RECOMMENDATIONS_SHEET],
                aioseo_rows,
            )
            redirects_rows = build_redirects_sheet_rows(extra_rows)
            redirect_map_rows = build_redirect_map_rows(extra_rows)
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
            run_timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
            register_snapshot = snapshot_from_current_run(
                issue_inventory_df=issue_inventory_df,
                main_rows=main_rows,
                extra_rows=extra_rows,
                source_path=output_filename,
                run_date=run_timestamp,
                previous_snapshot=previous_snapshot,
            )
            technical_diagnostics_rows = build_technical_diagnostics_rows(
                extra_rows, main_rows=main_rows
            )
            content_ai_rows = build_content_ai_readiness_rows(
                extra_rows, main_rows=main_rows
            )
            issue_register_rows = build_issue_register_rows(
                summary_rows=summary_rows,
                issue_inventory_rows=issue_inventory_rows,
                issue_records=register_snapshot.issues,
                run_date=run_timestamp,
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
            logger.info("Writing summary and issue sheets...")
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
            cms_action_rows = build_cms_action_url_rows(
                crawl_result.excluded_cms_action_urls,
                extra_rows,
            )
            write_dict_rows_sheet(
                writer,
                CMS_ACTION_URLS_SHEET,
                CMS_ACTION_URLS_COLUMNS,
                cms_action_rows,
            )
            logger.info("Writing link and duplication analysis sheets...")
            link_inventory_rows = build_link_inventory_rows(extra_rows)
            write_dict_rows_sheet(
                writer,
                "Link Inventory",
                merged_columns["Link Inventory"],
                link_inventory_rows,
            )
            broken_link_impact_rows = build_broken_link_impact_rows(
                link_inventory_rows, extra_rows
            )
            write_dict_rows_sheet(
                writer,
                "Broken Link Impact",
                merged_columns["Broken Link Impact"],
                broken_link_impact_rows,
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
            _fixplan_top_blocker_cols = ("Issue Type", "Severity", "Affected Count")
            if fixplan_rows:
                fixplan_df = pd.DataFrame(
                    sorted(
                        fixplan_rows,
                        key=lambda item: (-item["Affected Count"], item["Severity"]),
                    )
                )
            else:
                fixplan_df = pd.DataFrame(columns=list(_fixplan_top_blocker_cols))
            to_excel_safe(fixplan_df, writer, "FixPlan", index=False)
            quick_wins_rows = build_quick_wins_rows(
                extra_rows, fixplan_rows, summary_rules
            )
            write_dict_rows_sheet(
                writer,
                "Quick Wins",
                merged_columns["Quick Wins"],
                quick_wins_rows,
            )
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
            top_blockers = fixplan_df.head(10).reindex(columns=list(_fixplan_top_blocker_cols))
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
            dashboard_quick_win_rows = [
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
            action_hub_df = pd.DataFrame(critical_issues_rows + dashboard_quick_win_rows + growth_rows)
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
            write_executive_dashboard(
                writer,
                summary_metrics=summary_metrics,
                typed_main_rows=typed_main_rows,
                typed_extra_rows=typed_extra_rows,
                priority_rows=priority_rows,
                fixplan_rows=fixplan_rows,
                hub_metrics_rows=hub_metrics_rows,
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
            playbook_rows.extend(
                [
                    {"Section": "", "Item": "", "Guideline": "", "Why It Matters": ""},
                    {
                        "Section": "[Issue Playbook]",
                        "Item": "",
                        "Guideline": "",
                        "Why It Matters": "",
                    },
                ]
            )
            for issue_row in build_issue_playbook_rows(summary_rules):
                playbook_rows.append(
                    {
                        "Section": issue_row["Section"],
                        "Item": issue_row["Issue"],
                        "Guideline": (
                            f"What: {issue_row['What It Is']}\n"
                            f"Fix: {issue_row['How To Fix']}\n"
                            f"Verify: {issue_row['How To Verify']}"
                        ),
                        "Why It Matters": (
                            f"{issue_row['Why It Matters']} "
                            f"(Severity: {issue_row['Severity']}; "
                            f"Owner: {issue_row['Owner']}; "
                            f"Time: {issue_row['Time To Fix']})"
                        ),
                    }
                )
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
            logger.debug("Crawl duration for Dashboard RunMetadata: %.1fs", crawl_duration_s)
            run_meta_rows = [
                {"Key": "Run Timestamp", "Value": run_timestamp},
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
                {
                    "Key": "OG Image Validation Performed",
                    "Value": int(1 if setup.check_og_images else 0),
                },
            ]
            to_excel_safe(
                pd.DataFrame(run_meta_rows), writer, AUDIT_RUN_DETAILS_SHEET, index=False
            )
            delta_rows, resolved_issues_df, current_snapshot = build_delta_workbook_output(
                issue_inventory_df=issue_inventory_df,
                main_rows=main_rows,
                extra_rows=extra_rows,
                typed_extra_rows=typed_extra_rows,
                summary_rules=summary_rules,
                previous_snapshot=previous_snapshot,
                baseline_report=previous_snapshot is None,
                output_path=output_filename,
                run_date=run_timestamp,
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
                sitemap_files_meta=sitemap_files_meta,
                extra_rows=extra_rows,
            )
            to_excel_safe(pd.DataFrame(sitemap_rows), writer, "SitemapQA", index=False)
            write_dict_rows_sheet(
                writer,
                "Redirects",
                sheet_columns["Redirects"],
                redirects_rows,
            )
            write_dict_rows_sheet(
                writer,
                REDIRECT_MAP_SHEET,
                merged_columns[REDIRECT_MAP_SHEET],
                redirect_map_rows,
            )
            robots_analysis_rows = build_robots_analysis_rows(
                robots_by_domain=crawl_result.robots_by_domain or {},
                extra_rows=extra_rows,
                sitemap_url_keys=enrichment.sitemap_url_keys,
            )
            write_dict_rows_sheet(
                writer,
                ROBOTS_ANALYSIS_SHEET,
                list(ROBOTS_ANALYSIS_COLUMNS),
                robots_analysis_rows,
            )
            write_dict_rows_sheet(
                writer,
                CRAWL_LOG_SHEET,
                list(CRAWL_LOG_COLUMNS),
                crawl_log_sheet_rows(enrichment.crawl_log_entries),
            )
            graph_metrics = compute_internal_link_intelligence(extra_rows, crawl_result.source_label)
            write_dict_rows_sheet(
                writer,
                LINK_EQUITY_MAP_SHEET,
                list(LINK_EQUITY_COLUMNS),
                build_link_equity_rows(extra_rows, graph_metrics),
            )
            write_dict_rows_sheet(
                writer,
                ANCHOR_TEXT_AUDIT_SHEET,
                list(ANCHOR_TEXT_AUDIT_COLUMNS),
                build_anchor_text_audit_rows(extra_rows),
            )
            write_dict_rows_sheet(
                writer,
                SNIPPET_OPPORTUNITIES_SHEET,
                list(SNIPPET_OPPORTUNITY_COLUMNS),
                build_snippet_opportunity_rows(extra_rows),
            )
            write_dict_rows_sheet(
                writer,
                SCRIPT_INVENTORY_SHEET,
                list(SCRIPT_INVENTORY_COLUMNS),
                build_script_inventory_rows(extra_rows),
            )
            write_dict_rows_sheet(
                writer,
                IMAGE_INVENTORY_SHEET,
                list(IMAGE_INVENTORY_COLUMNS),
                build_image_inventory_rows(
                    extra_rows,
                    enrichment.image_probe_by_url or {},
                ),
            )
            if enrichment.competitor_benchmark_rows is not None:
                write_dict_rows_sheet(
                    writer,
                    COMPETITOR_BENCHMARKS_SHEET,
                    list(enrichment.competitor_benchmark_columns or ("Metric", "Client Site")),
                    enrichment.competitor_benchmark_rows,
                )
        registry_config = ExportRegistryConfig(full_suite=full_suite)
        logger.info("Applying workbook formatting...")
        for final_step in get_finalization_steps():
            if final_step == "apply_tab_hyperlinks":
                apply_tab_hyperlinks(writer)
            elif final_step == "format_sheets":
                for sname in get_sheet_sequence(registry_config):
                    format_name = sname
                    if format_name in writer.sheets:
                        adjust_sheet_format(writer, format_name)
                    elif format_name in _OPTIONAL_FORMAT_SHEETS:
                        logger.debug(
                            "Optional sheet not present; skipping formatting: %s",
                            format_name,
                        )
                    else:
                        logger.warning(
                            "Skipping sheet formatting for missing sheet: %s", format_name
                        )
            elif final_step == "apply_workbook_export_guardrails":
                apply_workbook_export_guardrails(writer.book)
        logger.info("Audit complete! Report saved to %s", output_filename)
        try:
            if current_snapshot is not None:
                summary_path = delta_summary_path_for_workbook(output_filename)
                save_run_snapshot_json(summary_path, current_snapshot)
                logger.info("Delta summary saved to %s", summary_path)
        except Exception as exc:
            logger.warning("Could not save delta summary JSON: %s", exc)
    finally:
        if writer is not None:
            writer.close()

    patch_xlsx_app_xml_for_excel_compatibility(output_filename)

    export_pdf = os.getenv("HF_EXPORT_PDF", "").strip().lower() in {"1", "true", "yes"}
    export_html = os.getenv("HF_EXPORT_HTML", "").strip().lower() in {"1", "true", "yes"}
    if export_pdf or export_html:
        # Build the shared ReportContext ONCE so the PDF and HTML executive
        # reports always present identical figures (single source of truth).
        # Branding resolves HF_REPORT_* first, then HF_PDF_*, then a shared
        # default, keeping both deliverables visually consistent.
        from hype_frog.reporter.html_report_data import build_report_context
        from hype_frog.reporter.html_report_writer import _load_logo_base64

        shared_brand_colour = (
            os.getenv("HF_REPORT_BRAND_COLOUR", "").strip()
            or os.getenv("HF_PDF_BRAND_COLOUR", "").strip()
            or "#1e293b"
        )
        shared_prepared_by = (
            os.getenv("HF_REPORT_PREPARED_BY", "").strip()
            or os.getenv("HF_PDF_PREPARED_BY", "").strip()
        )
        shared_client_name = (
            os.getenv("HF_REPORT_CLIENT_NAME", "").strip()
            or os.getenv("HF_PDF_CLIENT_NAME", "").strip()
        )

        report_ctx = None
        try:
            report_ctx = build_report_context(
                main_rows=main_rows,
                extra_rows=extra_rows,
                fixplan_rows=fixplan_rows,
                priority_rows=priority_rows,
                summary_rows=summary_rows,
                broken_link_impact_rows=broken_link_impact_rows,
                quick_win_rows=quick_wins_rows,
                run_timestamp=run_timestamp,
                summary_metrics=summary_metrics,
                domain=crawl_result.source_label,
                prepared_by=shared_prepared_by,
                client_name=shared_client_name,
                logo_base64=_load_logo_base64(),
                brand_colour=shared_brand_colour,
                accent_colour=os.getenv("HF_REPORT_ACCENT_COLOUR", "#2563eb").strip() or "#2563eb",
            )
        except Exception as exc:
            logger.warning("Could not build executive report context (non-fatal): %s", exc)

        if export_pdf and report_ctx is not None:
            try:
                raw_logo = (
                    os.getenv("HF_PDF_LOGO_PATH", "").strip()
                    or os.getenv("HF_REPORT_LOGO_PATH", "").strip()
                )
                resolved_logo = (
                    str(resolve_project_relative_path(raw_logo)) if raw_logo else None
                )
                export_executive_summary_pdf(
                    workbook_path=output_filename,
                    ctx=report_ctx,
                    run_date="",
                    logo_path=resolved_logo,
                )
            except Exception as exc:
                logger.warning("Could not export executive summary PDF: %s", exc)

        if export_html and report_ctx is not None:
            try:
                from pathlib import Path as _Path
                from hype_frog.reporter.html_report_writer import write_html_report as _write_html

                _html_path = _Path(output_filename).with_suffix(".html")
                _write_html(report_ctx, _html_path)
            except Exception as exc:
                logger.warning("HTML report generation failed (non-fatal): %s", exc)

    return ExportSummary(
        output_filename=output_filename,
        main_rows_written=len(main_rows),
        extra_rows_written=len(extra_rows),
        full_suite=full_suite,
    )
