"""Post-crawl enrichment and scoring orchestration."""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from typing import Any

from hype_frog.core import get_logger
from hype_frog.core.console import log_phase_banner, log_stage_timer
from hype_frog.core.discovery_order import order_main_and_extra_rows
from hype_frog.crawler import (
    check_url_status_light_limited,
    create_session,
    fetch_psi_metrics_batch,
)
from hype_frog.crawler.gsc_engine import (
    GSCEnrichmentContext,
    fetch_gsc_url_inspections_batch,
    load_gsc_enrichment_context,
)
from hype_frog.analysis.canonical_chain import enrich_extra_rows_canonical_chains
from hype_frog.analysis.competitor_benchmarks import benchmark_competitor_domains
from hype_frog.analysis.hreflang_audit import enrich_hreflang_reciprocity
from hype_frog.analysis.link_equity import enrich_link_equity_fields
from hype_frog.analysis.snippet_opportunities import enrich_snippet_opportunity_fields
from hype_frog.analysis.third_party_scripts import enrich_third_party_script_fields
from hype_frog.analysis.topical_authority import enrich_topical_authority_fields
from hype_frog.core.crawl_log import CrawlLogCollector
from hype_frog.crawler.robots_mapping import enrich_extra_rows_robots_mapping
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult
from hype_frog.core.models import CrawlRowPayload, ExtraRowPayload, MainRowPayload
from hype_frog.pipeline.assemble import (
    assemble_enriched_row,
    build_inlinks_map,
    build_title_meta_segment_maps,
    enrich_extra_rows_with_composite_scores,
    main_by_url_map,
    row_with_aeo_readiness_fields,
    row_with_canonical_and_internal_links,
    row_with_psi_gsc_harden,
    row_with_seo_health_enrichment,
)
from hype_frog.pipeline.link_inventory import (
    annotate_link_details_with_status,
    sniff_external_domains_head,
)
from hype_frog.pipeline.image_inventory import enrich_content_image_inventory
from hype_frog.pipeline.og_image_validation import enrich_og_image_validation
from hype_frog.analysis.content_similarity import enrich_content_similarity
from hype_frog.pipeline.gsc_coverage import format_gsc_data_freshness
from hype_frog.pipeline.gsc_inspection import (
    apply_gsc_inspection_fields,
    inspection_url_candidates_from_rows,
    select_gsc_inspection_urls,
)
from hype_frog.pipeline.content_hub_metrics import backfill_extra_content_hub_metrics
from hype_frog.pipeline.enrich import (
    compute_internal_link_intelligence,
)
from hype_frog.rules import get_summary_rules
from hype_frog.core.status_codes import is_success_status
from hype_frog.core.url_normalization import normalize_url
from hype_frog.pipeline.content_duplicates import enrich_content_duplicate_signals

logger = get_logger(__name__)

_PSI_SKIP_EXTENSIONS: frozenset[str] = frozenset({
    "png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "bmp", "tiff",
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "mp3", "mp4", "avi", "mov", "wav",
    "zip", "tar", "gz", "rar", "css", "js",
})


def _is_psi_eligible_url(url: str) -> bool:
    """Return False for non-HTML resource URLs that PSI cannot audit."""
    clean = url.split("?")[0].split("#")[0].lower()
    dot_idx = clean.rfind(".")
    slash_idx = clean.rfind("/")
    if dot_idx > slash_idx:
        return clean[dot_idx + 1:] not in _PSI_SKIP_EXTENSIONS
    return True


def normalize_url_key(url: object, keep_query: bool = True) -> str:
    return normalize_url(url, keep_query=keep_query)


def _extra_status_is_200(status: object) -> bool:
    return is_success_status(status)


def _url_passes_gsc_inspection_smart_gate(
    *,
    analytics_query_succeeded: bool,
    main_values: dict[str, object],
    extra_values: dict[str, object],
    url_key: str,
    normalized_key: str,
    gsc_metrics: dict[str, dict[str, float]],
) -> bool:
    """True when URL Inspection should run (indexable + 200 + zero GSC impressions / unknown in bulk)."""
    if not analytics_query_succeeded:
        return False
    if not _extra_status_is_200(extra_values.get("Status Code")):
        return False
    if str(main_values.get("Indexability") or "").strip() != "Indexable":
        return False
    gsc_row = (
        gsc_metrics.get(url_key)
        or gsc_metrics.get(normalized_key)
        or gsc_metrics.get(normalize_url_key(url_key))
    )
    if gsc_row is None:
        return True
    try:
        impressions = float(gsc_row.get("GSC Impressions") or 0.0)
    except (TypeError, ValueError):
        impressions = 0.0
    return impressions <= 0.0


def _merge_gsc_url_inspection_row(
    row: ExtraRowPayload,
    inspection_fields: dict[str, object] | None,
) -> ExtraRowPayload:
    if not inspection_fields:
        return row
    merged = dict(row.values)
    apply_gsc_inspection_fields(merged, inspection_fields)  # type: ignore[arg-type]
    return ExtraRowPayload.model_validate(merged)


@dataclass(frozen=True)
class EnrichmentResult:
    typed_main_rows: list[MainRowPayload]
    typed_extra_rows: list[ExtraRowPayload]
    status_by_url: dict[str, object]
    sitemap_url_keys: set[str]
    crawl_log_entries: list[Any] | None = None
    image_probe_by_url: dict[str, dict[str, Any]] | None = None
    competitor_benchmark_rows: list[dict[str, Any]] | None = None
    competitor_benchmark_columns: tuple[str, ...] | None = None
    graph_metrics: dict[str, dict[str, object]] | None = None

    @property
    def main_rows(self) -> list[dict[str, object]]:
        return [dict(row.values) for row in self.typed_main_rows]

    @property
    def extra_rows(self) -> list[dict[str, object]]:
        return [dict(row.values) for row in self.typed_extra_rows]


def _apply_seo_health_export_defaults(extra_rows: list[ExtraRowPayload]) -> None:
    for row in extra_rows:
        row_values = row.values
        badge = str(row_values.get("Severity Badge") or "").strip()
        raw = row_values.get("SEO Health Score")
        if isinstance(raw, float) and math.isnan(raw):
            raw = None
        if badge == "Unmeasured" or raw is None or str(raw).strip() == "":
            row_values["SEO Health Score"] = 0.0
        else:
            try:
                row_values["SEO Health Score"] = float(raw)
            except (TypeError, ValueError):
                row_values["SEO Health Score"] = 0.0
        raw_seo = row_values.get("SEO Score")
        if isinstance(raw_seo, float) and math.isnan(raw_seo):
            raw_seo = None
        if raw_seo is None or str(raw_seo).strip() == "":
            row_values["SEO Score"] = 0.0
        else:
            try:
                row_values["SEO Score"] = float(raw_seo)
            except (TypeError, ValueError):
                row_values["SEO Score"] = 0.0


def _sync_main_rows_seo_fields_from_extra(
    main_rows: list[MainRowPayload],
    extra_rows: list[ExtraRowPayload],
) -> None:
    extra_by_url = {
        str(row.values.get("URL") or "").strip(): row
        for row in extra_rows
        if row.values.get("URL")
    }
    for row in main_rows:
        row_values = row.values
        url = str(row_values.get("URL") or "").strip()
        extra = extra_by_url.get(url)
        if not extra:
            continue
        extra_values = extra.values
        row_values["SEO Health Score"] = extra_values.get("SEO Health Score")
        row_values["SEO Score"] = extra_values.get("SEO Score")
        row_values["Severity Badge"] = extra_values.get("Severity Badge")
        row_values["Action Needed"] = extra_values.get("Action Needed")


async def run_enrichment(crawl_result: CrawlExecutionResult) -> EnrichmentResult:
    log_phase_banner("ENRICHMENT: Starting post-crawl data pipeline")
    image_probe_by_url: dict[str, dict[str, Any]] | None = None
    graph_metrics: dict[str, dict[str, object]] = {}
    crawl_log = CrawlLogCollector()
    if crawl_result.crawl_log_entries is not None:
        crawl_log.entries.extend(crawl_result.crawl_log_entries)
    crawl_rows: list[CrawlRowPayload] = list(crawl_result.crawl_rows)
    main_rows = [row.main for row in crawl_rows]
    extra_rows = [row.extra for row in crawl_rows]
    sitemap_url_keys = {normalize_url_key(url) for url in crawl_result.sitemap_meta.keys()}
    async with create_session() as session:
        log_phase_banner("ENRICHMENT PHASE 1/5: Load GSC analytics context")
        try:
            with log_stage_timer("GSC analytics context load"):
                gsc_ctx = await asyncio.to_thread(
                    load_gsc_enrichment_context, crawl_result.target_input
                )
        except Exception as exc:
            logger.error("GSC metrics unavailable due to runtime error: %s", exc)
            gsc_ctx = GSCEnrichmentContext({}, False, None, None)
        gsc_metrics = gsc_ctx.page_metrics
        gsc_data_freshness = format_gsc_data_freshness(
            gsc_ctx.period_start,
            gsc_ctx.period_end,
        )
        if gsc_ctx.analytics_query_succeeded and gsc_metrics:
            logger.info(
                "GSC bulk Search Analytics (30d, page dimension): %s lookup keys materialized.",
                len(gsc_metrics),
            )
        elif gsc_ctx.analytics_query_succeeded:
            logger.info("GSC bulk Search Analytics returned zero rows for this property (last 30 days).")
        else:
            logger.warning(
                "GSC metrics unavailable (missing credentials, property mismatch, or query error)."
            )

        inspection_targets = inspection_url_candidates_from_rows(
            main_rows,
            extra_rows,
            analytics_query_succeeded=gsc_ctx.analytics_query_succeeded,
            gsc_metrics=gsc_metrics,
            gate_fn=_url_passes_gsc_inspection_smart_gate,
        )
        inspection_mode = crawl_result.gsc_url_inspection or ""
        unique_inspection_urls = select_gsc_inspection_urls(
            inspection_targets,
            mode=inspection_mode,
        )
        inspection_by_url: dict[str, dict[str, object]] = {}
        if (
            inspection_mode
            and unique_inspection_urls
            and gsc_ctx.service is not None
            and gsc_ctx.site_url is not None
        ):
            log_phase_banner(
                "ENRICHMENT PHASE 2/5: GSC URL Inspection batch"
            )
            logger.info(
                "GSC URL Inspection (%s): %s of %s crawled URLs selected.",
                inspection_mode,
                len(unique_inspection_urls),
                len(extra_rows),
            )
            try:
                with log_stage_timer("GSC URL Inspection lookups"):
                    inspection_by_url = await asyncio.to_thread(
                        fetch_gsc_url_inspections_batch,
                        gsc_ctx.service,
                        gsc_ctx.site_url,
                        unique_inspection_urls,
                    )
            except Exception as exc:
                logger.error("GSC URL Inspection batch failed: %s", exc)
                inspection_by_url = {}
                crawl_log.record(
                    url=crawl_result.target_input,
                    phase="GSC",
                    error_type="URL Inspection Batch Failed",
                    error_detail=str(exc),
                    recovery_action="Inspection columns left blank for this run.",
                )
        elif inspection_mode:
            logger.info(
                "GSC URL Inspection enabled (%s) but no URLs qualified or GSC API unavailable.",
                inspection_mode,
            )
        else:
            logger.info("ENRICHMENT PHASE 2/5: GSC URL Inspection — skipped (not configured for this run).")

        if crawl_result.max_psi_urls == 0:
            psi_map: dict[str, dict[str, object]] = {}
            logger.info("PSI disabled for this run (max PSI URLs set to 0).")
        else:
            log_phase_banner("ENRICHMENT PHASE 3/5: PSI metric batch")
            with log_stage_timer("PSI fetch"):
                _raw_psi_urls = [
                    str(row.values.get("Final URL") or row.values.get("URL") or "").strip()
                    for row in extra_rows
                    if row.values.get("Final URL") or row.values.get("URL")
                ]
                _psi_urls = [u for u in _raw_psi_urls if _is_psi_eligible_url(u)]
                _psi_skipped = len(_raw_psi_urls) - len(_psi_urls)
                if _psi_skipped > 0:
                    logger.info("PSI: skipped %d non-HTML URL(s) (images/media/assets).", _psi_skipped)
                psi_map = await fetch_psi_metrics_batch(
                    session,
                    _psi_urls,
                    max_urls=crawl_result.max_psi_urls,
                )
            if crawl_result.max_psi_urls is not None:
                logger.info(
                    "PSI URL cap applied: processed up to %s URLs.",
                    crawl_result.max_psi_urls,
                )

        extra_work: list[ExtraRowPayload] = []
        for main_row, row in zip(main_rows, extra_rows, strict=True):
            row_values = row.values
            url_key = str(row_values.get("Final URL") or row_values.get("URL") or "").strip()
            normalized_key = normalize_url_key(url_key)
            hardened = row_with_psi_gsc_harden(
                row,
                url_key=url_key,
                normalized_key=normalized_key,
                psi_map=psi_map,
                gsc_metrics=gsc_metrics,
                gsc_analytics_succeeded=gsc_ctx.analytics_query_succeeded,
                gsc_data_freshness=gsc_data_freshness,
            )
            insp = inspection_by_url.get(url_key) or inspection_by_url.get(normalized_key)
            merged_row = _merge_gsc_url_inspection_row(hardened, insp)
            if crawl_log is not None and insp:
                coverage = str(merged_row.values.get("GSC Inspection Coverage") or "")
                if coverage == "Error":
                    crawl_log.record(
                        url=url_key,
                        phase="GSC",
                        error_type="URL Inspection Error",
                        error_detail=str(
                            merged_row.values.get("GSC Coverage Reason")
                            or "Inspection API error"
                        ),
                        recovery_action="Skipped inspection fields for this URL.",
                    )
            extra_work.append(merged_row)

        status_by_url: dict[str, object] = {}
        for row in extra_work:
            row_values = row.values
            if row_values.get("Final URL"):
                status_by_url[normalize_url_key(row_values["Final URL"])] = row_values.get("Status Code")
            if row_values.get("URL"):
                status_by_url[normalize_url_key(row_values["URL"])] = row_values.get("Status Code")

        unresolved_targets = set()
        for row in extra_work:
            for target in row.values.get("Internal Links List Full", []):
                if normalize_url_key(target) not in status_by_url:
                    unresolved_targets.add(target)
        log_phase_banner("ENRICHMENT PHASE 4/5: Internal/external link status completion")
        if unresolved_targets:
            logger.info(
                "Running lightweight status checks for %s internal links not in crawl set...",
                len(unresolved_targets),
            )
            link_check_semaphore = asyncio.Semaphore(min(20, max(5, crawl_result.workers * 3)))
            checked_statuses = await asyncio.gather(
                *[
                    check_url_status_light_limited(session, target, link_check_semaphore)
                    for target in unresolved_targets
                ]
            )
            for target, status in zip(unresolved_targets, checked_statuses):
                status_by_url[normalize_url_key(target)] = status
        else:
            logger.debug("No unresolved internal-link targets; skipping lightweight status checks.")

        external_by_netloc: dict[str, int | None] | None = None
        if crawl_result.check_external_link_status:
            external_by_netloc = await sniff_external_domains_head(session, extra_work)
            logger.info(
                "External domain HEAD checks completed (%s unique hosts).",
                len(external_by_netloc),
            )
        else:
            logger.debug("External domain HEAD checks disabled for this run.")

        if crawl_result.check_og_images:
            log_phase_banner("ENRICHMENT: OG image status and dimension checks")
            await enrich_og_image_validation(
                session,
                extra_work,
                workers=crawl_result.workers,
            )
            logger.info("OG image validation completed for pages with og:image set.")
        else:
            logger.debug("OG image validation disabled for this run.")

        if crawl_result.check_content_images:
            log_phase_banner("ENRICHMENT: Content image status and size checks")
            image_probe_by_url = await enrich_content_image_inventory(
                session,
                extra_work,
                workers=crawl_result.workers,
            )
            logger.info(
                "Content image validation completed (%s unique URLs probed).",
                len(image_probe_by_url or {}),
            )
        else:
            logger.debug("Content image validation disabled for this run.")

        annotate_link_details_with_status(
            extra_work,
            status_by_url=status_by_url,
            external_status_by_netloc=external_by_netloc,
            sniff_external=crawl_result.check_external_link_status,
            normalize_url_key_fn=normalize_url_key,
        )
        enrich_extra_rows_canonical_chains(
            [row.values for row in extra_work],
            status_by_url=status_by_url,
        )
        enrich_extra_rows_robots_mapping(
            [row.values for row in extra_work],
            robots_by_domain=crawl_result.robots_by_domain or {},
        )
        for extra_row in extra_work:
            psi_status = str(extra_row.values.get("PSI Data Status") or "").strip().lower()
            if psi_status in {"not available", "error", "failed"}:
                url_key = str(
                    extra_row.values.get("Final URL") or extra_row.values.get("URL") or ""
                ).strip()
                crawl_log.record(
                    url=url_key,
                    phase="PSI",
                    error_type="PSI Unavailable",
                    error_detail=psi_status or "not measured",
                    recovery_action="PSI columns left blank for this URL.",
                )

    log_phase_banner("ENRICHMENT PHASE 5/5: Scoring, intelligence, and row assembly")
    with log_stage_timer(
        "Scoring + link graph + SEO health merge (no network; scales with URL count)"
    ):
        crawled_finals = {
            normalize_url_key(row.values.get("Final URL"))
            for row in extra_work
            if row.values.get("Final URL")
        }
        extra_work = [
            row_with_canonical_and_internal_links(
                row,
                crawled_finals=crawled_finals,
                status_by_url=status_by_url,
            )
            for row in extra_work
        ]

        graph_metrics = compute_internal_link_intelligence(extra_work)
        title_map, meta_map, segment_by_url = build_title_meta_segment_maps(main_rows)
        summary_rules = get_summary_rules()
        main_by_url_pre = main_by_url_map(main_rows)
        inlinks_map = build_inlinks_map(extra_work)
        extra_work = enrich_content_duplicate_signals(
            main_rows,
            extra_work,
            inlinks_map=inlinks_map,
        )
        titles_by_url = {
            str(row.values.get("URL") or "").strip(): row.values.get("Title")
            for row in main_rows
            if row.values.get("URL")
        }
        for extra_row in extra_work:
            url_key = str(extra_row.values.get("URL") or "").strip()
            main_match = main_by_url_pre.get(url_key)
            if main_match is not None:
                extra_row.values["Word Count (Body)"] = main_match.values.get(
                    "Word Count (Body)"
                )
        enrich_content_similarity(extra_work, titles_by_url=titles_by_url)
        enrich_topical_authority_fields(extra_work)
        enrich_hreflang_reciprocity(extra_work)
        enrich_third_party_script_fields(extra_work)
        enrich_link_equity_fields(extra_work, graph_metrics)
        extra_work = [row_with_aeo_readiness_fields(row) for row in extra_work]
        extra_work = [
            row_with_seo_health_enrichment(
                row,
                summary_rules=summary_rules,
                sitemap_url_keys=sitemap_url_keys,
                graph_metrics=graph_metrics,
                inlinks_map=inlinks_map,
                title_map=title_map,
                meta_map=meta_map,
                segment_by_url=segment_by_url,
                main_by_url=main_by_url_pre,
            )
            for row in extra_work
        ]
        enriched_extra_rows = enrich_extra_rows_with_composite_scores(
            extra_work, main_by_url=main_by_url_pre
        )
        enrich_snippet_opportunity_fields(enriched_extra_rows)
        enriched_extra_rows = [
            ExtraRowPayload.model_validate(row.values) for row in enriched_extra_rows
        ]
        _apply_seo_health_export_defaults(enriched_extra_rows)

        extra_by_url: dict[str, ExtraRowPayload] = {
            str(row.values.get("URL") or "").strip(): row
            for row in enriched_extra_rows
            if row.values.get("URL")
        }
        enriched_main_rows = [
            assemble_enriched_row(
                row,
                extra_by_url.get(
                    str(row.values.get("URL") or "").strip(),
                    ExtraRowPayload.model_validate({}),
                ),
                sitemap_url_keys=sitemap_url_keys,
            )
            for row in main_rows
        ]
        _sync_main_rows_seo_fields_from_extra(enriched_main_rows, enriched_extra_rows)
        enriched_main_rows, enriched_extra_rows = order_main_and_extra_rows(
            enriched_main_rows,
            enriched_extra_rows,
            crawl_result.crawl_urls,
        )
        for main_row, extra_row in zip(
            enriched_main_rows, enriched_extra_rows, strict=False
        ):
            backfill_extra_content_hub_metrics(extra_row.values, main_row.values)

        if gsc_ctx.analytics_query_succeeded:
            matched = sum(
                1
                for row in enriched_extra_rows
                if str(row.values.get("GSC Coverage Note") or "").startswith("Matched in GSC")
            )
            logger.info(
                "GSC coverage: %s/%s crawled URLs matched Search Analytics; freshness=%s; API rows=%s.",
                matched,
                len(enriched_extra_rows),
                gsc_data_freshness or "unknown",
                gsc_ctx.analytics_row_count,
            )

    competitor_rows: list[dict[str, Any]] | None = None
    competitor_columns: tuple[str, ...] | None = None
    competitor_domains = list(crawl_result.competitor_domains or ())
    if competitor_domains:
        with log_stage_timer("Competitor benchmark sampling"):
            competitor_rows, competitor_columns = await benchmark_competitor_domains(
                client_label=crawl_result.source_label,
                main_rows=[row.values for row in enriched_main_rows],
                extra_rows=[row.values for row in enriched_extra_rows],
                competitor_domains=competitor_domains,
            )

    return EnrichmentResult(
        typed_main_rows=enriched_main_rows,
        typed_extra_rows=enriched_extra_rows,
        status_by_url=status_by_url,
        sitemap_url_keys=sitemap_url_keys,
        crawl_log_entries=crawl_log.entries,
        image_probe_by_url=image_probe_by_url,
        competitor_benchmark_rows=competitor_rows,
        competitor_benchmark_columns=competitor_columns,
        graph_metrics=graph_metrics,
    )
