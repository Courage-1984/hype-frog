"""Post-crawl enrichment and scoring orchestration."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass

from hype_frog.core import get_logger
from hype_frog.crawler import (
    check_url_status_light_limited,
    create_session,
    fetch_gsc_page_metrics,
    fetch_psi_metrics_batch,
)
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult
from hype_frog.core.models import CrawlRowPayload, ExtraRowPayload, MainRowPayload
from hype_frog.pipeline.assemble import (
    assemble_enriched_row,
    build_inlinks_map,
    build_title_meta_segment_maps,
    enrich_extra_rows_with_composite_scores,
    main_by_url_map,
    row_with_canonical_and_internal_links,
    row_with_psi_gsc_harden,
    row_with_seo_health_enrichment,
)
from hype_frog.pipeline.enrich import (
    compute_internal_link_intelligence,
)
from hype_frog.rules import get_summary_rules
from hype_frog.utils import normalize_url_key

logger = get_logger(__name__)


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
    crawl_rows: list[CrawlRowPayload] = list(crawl_result.crawl_rows)
    main_rows = [row.main for row in crawl_rows]
    extra_rows = [row.extra for row in crawl_rows]
    sitemap_url_keys = {normalize_url_key(url) for url in crawl_result.sitemap_meta.keys()}
    async with create_session() as session:
        try:
            gsc_metrics = await asyncio.to_thread(
                fetch_gsc_page_metrics, crawl_result.target_input
            )
        except Exception as exc:
            logger.warning("GSC metrics unavailable due to runtime error: %s", exc)
            gsc_metrics = {}
        if gsc_metrics:
            logger.info(
                "Merged GSC metrics for last 30 days: %s URL records.",
                len(gsc_metrics),
            )
        else:
            logger.warning(
                "GSC metrics unavailable (missing credentials, property mismatch, or no data)."
            )

        if crawl_result.max_psi_urls == 0:
            psi_map: dict[str, dict[str, object]] = {}
            logger.info("PSI disabled for this run (max PSI URLs set to 0).")
        else:
            psi_map = await fetch_psi_metrics_batch(
                session,
                [
                    str(row.values.get("URL") or "")
                    for row in extra_rows
                    if row.values.get("URL")
                ],
                max_urls=crawl_result.max_psi_urls,
            )
            if crawl_result.max_psi_urls is not None:
                logger.info(
                    "PSI URL cap applied: processed up to %s URLs.",
                    crawl_result.max_psi_urls,
                )

        extra_work: list[ExtraRowPayload] = []
        for row in extra_rows:
            row_values = row.values
            url_key = str(row_values.get("Final URL") or row_values.get("URL") or "").strip()
            extra_work.append(
                row_with_psi_gsc_harden(
                    row,
                    url_key=url_key,
                    normalized_key=normalize_url_key(url_key),
                    psi_map=psi_map,
                    gsc_metrics=gsc_metrics,
                )
            )

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

    return EnrichmentResult(
        typed_main_rows=enriched_main_rows,
        typed_extra_rows=enriched_extra_rows,
        status_by_url=status_by_url,
        sitemap_url_keys=sitemap_url_keys,
    )
