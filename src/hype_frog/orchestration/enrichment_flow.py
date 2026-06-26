"""Post-crawl enrichment and scoring orchestration."""

from __future__ import annotations

import asyncio
import math
import time
from contextlib import contextmanager
from dataclasses import dataclass

from hype_frog.core import get_logger
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
from hype_frog.pipeline.content_duplicates import enrich_content_duplicate_signals
from hype_frog.pipeline.gsc_coverage import format_gsc_data_freshness
from hype_frog.pipeline.content_hub_metrics import backfill_extra_content_hub_metrics
from hype_frog.pipeline.enrich import (
    compute_internal_link_intelligence,
)
from hype_frog.rules import get_summary_rules
from hype_frog.core.url_normalization import normalize_url

logger = get_logger(__name__)


def _log_phase_banner(title: str) -> None:
    bar = "=" * 72
    logger.info("")
    logger.info(bar)
    logger.info(" %s", title)
    logger.info(bar)
    logger.info("")


@contextmanager
def _log_stage_timer(stage_name: str):
    started = time.perf_counter()
    logger.info(">> %s started", stage_name)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - started
        logger.info(">> %s completed in %.1fs", stage_name, elapsed)


def normalize_url_key(url: object, keep_query: bool = True) -> str:
    return normalize_url(url, keep_query=keep_query)


def _extra_status_is_200(status: object) -> bool:
    try:
        return int(float(status)) == 200
    except (TypeError, ValueError):
        return False


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
    inspection_fields: dict[str, str | None] | None,
) -> ExtraRowPayload:
    if not inspection_fields:
        return row
    merged = dict(row.values)
    merged.update(inspection_fields)
    return ExtraRowPayload.model_validate(merged)


@dataclass(frozen=True)
class EnrichmentResult:
    typed_main_rows: list[MainRowPayload]
    typed_extra_rows: list[ExtraRowPayload]
    status_by_url: dict[str, object]
    sitemap_url_keys: set[str]

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
    _log_phase_banner("ENRICHMENT: Starting post-crawl data pipeline")
    crawl_rows: list[CrawlRowPayload] = list(crawl_result.crawl_rows)
    main_rows = [row.main for row in crawl_rows]
    extra_rows = [row.extra for row in crawl_rows]
    sitemap_url_keys = {normalize_url_key(url) for url in crawl_result.sitemap_meta.keys()}
    async with create_session() as session:
        _log_phase_banner("ENRICHMENT PHASE 1/5: Load GSC analytics context")
        try:
            with _log_stage_timer("GSC analytics context load"):
                gsc_ctx = await asyncio.to_thread(
                    load_gsc_enrichment_context, crawl_result.target_input
                )
        except Exception as exc:
            logger.warning("GSC metrics unavailable due to runtime error: %s", exc)
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

        inspection_targets: list[str] = []
        for main_row, extra_row in zip(main_rows, extra_rows, strict=True):
            ev = extra_row.values
            url_key = str(ev.get("Final URL") or ev.get("URL") or "").strip()
            if not url_key:
                continue
            nk = normalize_url_key(url_key)
            if _url_passes_gsc_inspection_smart_gate(
                analytics_query_succeeded=gsc_ctx.analytics_query_succeeded,
                main_values=main_row.values,
                extra_values=ev,
                url_key=url_key,
                normalized_key=nk,
                gsc_metrics=gsc_metrics,
            ):
                inspection_targets.append(url_key)
        unique_inspection_urls = list(dict.fromkeys(inspection_targets))
        inspection_by_url: dict[str, dict[str, str | None]] = {}
        if (
            unique_inspection_urls
            and gsc_ctx.service is not None
            and gsc_ctx.site_url is not None
        ):
            _log_phase_banner(
                "ENRICHMENT PHASE 2/5: GSC URL Inspection batch"
            )
            logger.info(
                "GSC URL Inspection smart gate: %s of %s crawled URLs qualify for inspection API.",
                len(unique_inspection_urls),
                len(extra_rows),
            )
            try:
                with _log_stage_timer("GSC URL Inspection lookups"):
                    inspection_by_url = await asyncio.to_thread(
                        fetch_gsc_url_inspections_batch,
                        gsc_ctx.service,
                        gsc_ctx.site_url,
                        unique_inspection_urls,
                    )
            except Exception as exc:
                logger.warning("GSC URL Inspection batch failed: %s", exc)
                inspection_by_url = {}

        if crawl_result.max_psi_urls == 0:
            psi_map: dict[str, dict[str, object]] = {}
            logger.info("PSI disabled for this run (max PSI URLs set to 0).")
        else:
            _log_phase_banner("ENRICHMENT PHASE 3/5: PSI metric batch")
            with _log_stage_timer("PSI fetch"):
                psi_map = await fetch_psi_metrics_batch(
                    session,
                    [
                        str(
                            row.values.get("Final URL")
                            or row.values.get("URL")
                            or ""
                        ).strip()
                        for row in extra_rows
                        if row.values.get("Final URL") or row.values.get("URL")
                    ],
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
            extra_work.append(_merge_gsc_url_inspection_row(hardened, insp))

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
        _log_phase_banner("ENRICHMENT PHASE 4/5: Internal/external link status completion")
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
            logger.info("No unresolved internal-link targets; skipping lightweight status checks.")

        external_by_netloc: dict[str, int | None] | None = None
        if crawl_result.check_external_link_status:
            external_by_netloc = await sniff_external_domains_head(session, extra_work)
            logger.info(
                "External domain HEAD checks completed (%s unique hosts).",
                len(external_by_netloc),
            )
        else:
            logger.info("External domain HEAD checks disabled for this run.")

        annotate_link_details_with_status(
            extra_work,
            status_by_url=status_by_url,
            external_status_by_netloc=external_by_netloc,
            sniff_external=crawl_result.check_external_link_status,
            normalize_url_key_fn=normalize_url_key,
        )

    _log_phase_banner("ENRICHMENT PHASE 5/5: Scoring, intelligence, and row assembly")
    with _log_stage_timer(
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

        graph_metrics = compute_internal_link_intelligence(
            extra_work, crawl_result.source_label
        )
        title_map, meta_map, segment_by_url = build_title_meta_segment_maps(main_rows)
        summary_rules = get_summary_rules()
        main_by_url_pre = main_by_url_map(main_rows)
        inlinks_map = build_inlinks_map(extra_work)
        extra_work = enrich_content_duplicate_signals(
            main_rows,
            extra_work,
            inlinks_map=inlinks_map,
        )
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

    return EnrichmentResult(
        typed_main_rows=enriched_main_rows,
        typed_extra_rows=enriched_extra_rows,
        status_by_url=status_by_url,
        sitemap_url_keys=sitemap_url_keys,
    )
