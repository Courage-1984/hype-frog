"""Reconstruct orchestration payloads from persisted crawl replay snapshots."""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any
from urllib.parse import urlparse

from hype_frog.analysis.delta_models import utc_now_iso
from hype_frog.core.crawl_log import CrawlLogEntry
from hype_frog.core.models import CrawlRowPayload, ExtraRowPayload, MainRowPayload
from hype_frog.crawler.robots_mapping import build_robot_parser
from hype_frog.pipeline.export import sanitize_rows
from hype_frog.orchestration.crawl_runner import CrawlExecutionResult
from hype_frog.orchestration.crawl_runner_frontier import ExcludedCmsActionUrl
from hype_frog.orchestration.enrichment_flow import EnrichmentResult
from hype_frog.orchestration.run_setup import RunSetup
from hype_frog.snapshots.models import CrawlReplaySnapshot


class ReplaySnapshotError(RuntimeError):
    """Raised when a replay snapshot cannot be loaded or applied."""


def resolve_snapshot_domain(target_input: str) -> str:
    """Normalise a crawl target or sitemap URL to a registrable domain key."""
    text = str(target_input or "").strip()
    if not text:
        return "unknown"
    if text.lower().endswith(".xml"):
        parsed = urlparse(text)
        host = (parsed.netloc or "").lower()
    else:
        parsed = urlparse(text if "://" in text else f"https://{text}")
        host = (parsed.netloc or text).lower()
    return host.removeprefix("www.").strip("/") or "unknown"


def _excluded_cms_to_dict(item: ExcludedCmsActionUrl) -> dict[str, Any]:
    return {
        "url": item.url,
        "excluded_query_params": list(item.excluded_query_params),
        "discovered_on_url": item.discovered_on_url,
        "exclusion_reason": item.exclusion_reason,
    }


def _excluded_cms_from_dict(raw: dict[str, Any]) -> ExcludedCmsActionUrl:
    params = raw.get("excluded_query_params") or []
    return ExcludedCmsActionUrl(
        url=str(raw.get("url") or "").strip(),
        excluded_query_params=tuple(str(p) for p in params),
        discovered_on_url=str(raw.get("discovered_on_url") or "").strip(),
        exclusion_reason=str(
            raw.get("exclusion_reason")
            or "CMS / WooCommerce action parameter — not crawled as a distinct page"
        ),
    )


def _crawl_log_entries_to_json(entries: list[Any] | None) -> list[dict[str, str]]:
    if not entries:
        return []
    serialised: list[dict[str, str]] = []
    for entry in entries:
        if isinstance(entry, CrawlLogEntry):
            serialised.append(
                {
                    "timestamp": entry.timestamp,
                    "url": entry.url,
                    "phase": entry.phase,
                    "error_type": entry.error_type,
                    "error_detail": entry.error_detail,
                    "recovery_action": entry.recovery_action,
                }
            )
        elif isinstance(entry, dict):
            serialised.append(
                {
                    "timestamp": str(entry.get("timestamp") or ""),
                    "url": str(entry.get("url") or ""),
                    "phase": str(entry.get("phase") or ""),
                    "error_type": str(entry.get("error_type") or ""),
                    "error_detail": str(entry.get("error_detail") or ""),
                    "recovery_action": str(entry.get("recovery_action") or ""),
                }
            )
    return serialised


def _crawl_log_entries_from_json(raw: list[Any] | None) -> list[CrawlLogEntry] | None:
    if not raw:
        return None
    entries: list[CrawlLogEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        entries.append(
            CrawlLogEntry(
                timestamp=str(item.get("timestamp") or ""),
                url=str(item.get("url") or ""),
                phase=str(item.get("phase") or ""),
                error_type=str(item.get("error_type") or ""),
                error_detail=str(item.get("error_detail") or ""),
                recovery_action=str(item.get("recovery_action") or ""),
            )
        )
    return entries


def _robots_by_domain_to_json(
    robots_by_domain: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if not robots_by_domain:
        return {}
    serialised: dict[str, dict[str, Any]] = {}
    for domain, entry in robots_by_domain.items():
        if not isinstance(entry, dict):
            continue
        serialised[domain] = {k: v for k, v in entry.items() if k != "parser"}
    return serialised


def _robots_by_domain_from_json(
    raw: dict[str, Any] | None,
) -> dict[str, dict[str, Any]] | None:
    if not raw:
        return None
    restored: dict[str, dict[str, Any]] = {}
    for domain, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        item = dict(entry)
        robots_text = item.get("robots_text")
        if item.get("robots_accessible") and robots_text:
            item["parser"] = build_robot_parser(str(robots_text))
        else:
            item["parser"] = None
        restored[domain] = item
    return restored


def _serialize_setup_context(setup: RunSetup) -> dict[str, Any]:
    return {
        "target_input": setup.target_input,
        "high_value_slugs": list(setup.high_value_slugs),
        "previous_audit_path_preset": setup.previous_audit_path_preset,
        "competitor_domains": list(setup.competitor_domains),
        "export_pdf": setup.export_pdf,
        "check_og_images": setup.check_og_images,
        "check_content_images": setup.check_content_images,
        "gsc_url_inspection": setup.gsc_url_inspection,
        "max_memory_mb": setup.max_memory_mb,
        "streaming": setup.streaming,
        "full_suite_preset": setup.full_suite_preset,
    }


def _serialize_crawl_context(
    crawl_result: CrawlExecutionResult,
) -> dict[str, Any]:
    return {
        "target_input": crawl_result.target_input,
        "crawl_urls": list(crawl_result.crawl_urls),
        "sitemap_meta": crawl_result.sitemap_meta,
        "sitemap_files_meta": crawl_result.sitemap_files_meta,
        "source_label": crawl_result.source_label,
        "workers": crawl_result.workers,
        "request_delay": crawl_result.request_delay,
        "full_suite": crawl_result.full_suite,
        "previous_audit_path": crawl_result.previous_audit_path,
        "checkpoint_every": crawl_result.checkpoint_every,
        "check_external_link_status": crawl_result.check_external_link_status,
        "check_og_images": crawl_result.check_og_images,
        "check_content_images": crawl_result.check_content_images,
        "excluded_cms_action_urls": [
            _excluded_cms_to_dict(item) for item in crawl_result.excluded_cms_action_urls
        ],
        "crawl_log_entries": _crawl_log_entries_to_json(crawl_result.crawl_log_entries),
        "robots_by_domain": _robots_by_domain_to_json(crawl_result.robots_by_domain),
        "competitor_domains": list(crawl_result.competitor_domains),
        "gsc_url_inspection": crawl_result.gsc_url_inspection,
        "max_memory_mb": crawl_result.max_memory_mb,
        "streaming": crawl_result.streaming,
        "crawl_duration_seconds": crawl_result.crawl_duration_seconds,
        "crawl_completed": crawl_result.crawl_completed,
        "max_psi_urls": crawl_result.max_psi_urls,
        "output_filename": crawl_result.output_filename,
    }


def _serialize_enrichment_context(enrichment: EnrichmentResult) -> dict[str, Any]:
    return {
        "status_by_url": dict(enrichment.status_by_url),
        "sitemap_url_keys": sorted(enrichment.sitemap_url_keys),
        "image_probe_by_url": enrichment.image_probe_by_url,
        "competitor_benchmark_rows": enrichment.competitor_benchmark_rows,
        "competitor_benchmark_columns": (
            list(enrichment.competitor_benchmark_columns)
            if enrichment.competitor_benchmark_columns
            else None
        ),
        "graph_metrics": enrichment.graph_metrics,
        "crawl_log_entries": _crawl_log_entries_to_json(enrichment.crawl_log_entries),
    }


def build_crawl_replay_snapshot(
    setup: RunSetup,
    crawl_result: CrawlExecutionResult,
    enrichment: EnrichmentResult,
    *,
    snapshot_id: str | None = None,
    run_timestamp: str | None = None,
) -> CrawlReplaySnapshot:
    """Build a replay snapshot from post-enrichment orchestration state."""
    domain = resolve_snapshot_domain(crawl_result.target_input)
    main_rows = sanitize_rows([dict(row.values) for row in enrichment.typed_main_rows])
    extra_rows = sanitize_rows([dict(row.values) for row in enrichment.typed_extra_rows])
    return CrawlReplaySnapshot(
        snapshot_id=snapshot_id or str(uuid.uuid4()),
        domain=domain,
        run_timestamp=run_timestamp or utc_now_iso(),
        source_output_path=crawl_result.output_filename,
        main_rows=main_rows,
        extra_rows=extra_rows,
        crawl_context=_serialize_crawl_context(crawl_result),
        enrichment_context=_serialize_enrichment_context(enrichment),
        setup_context=_serialize_setup_context(setup),
    )


def _rows_to_crawl_rows(
    main_rows: list[dict[str, Any]],
    extra_rows: list[dict[str, Any]],
) -> list[CrawlRowPayload]:
    extra_by_url = {
        str(row.get("URL") or "").strip(): row for row in extra_rows if row.get("URL")
    }
    crawl_rows: list[CrawlRowPayload] = []
    for main in main_rows:
        url = str(main.get("URL") or "").strip()
        extra = extra_by_url.get(url, {})
        crawl_rows.append(
            CrawlRowPayload(
                main=MainRowPayload.model_validate(main),
                extra=ExtraRowPayload.model_validate(extra),
            )
        )
    return crawl_rows


def replay_from_snapshot(
    snapshot: CrawlReplaySnapshot,
    setup: RunSetup,
    *,
    output_filename: str,
) -> tuple[CrawlExecutionResult, EnrichmentResult]:
    """Reconstruct crawl and enrichment results for export-only replay."""
    crawl_ctx = snapshot.crawl_context
    enrich_ctx = snapshot.enrichment_context

    excluded_raw = crawl_ctx.get("excluded_cms_action_urls") or []
    excluded: tuple[ExcludedCmsActionUrl, ...] = tuple(
        _excluded_cms_from_dict(item)
        for item in excluded_raw
        if isinstance(item, dict)
    )

    typed_main_rows = [MainRowPayload.model_validate(row) for row in snapshot.main_rows]
    typed_extra_rows = [ExtraRowPayload.model_validate(row) for row in snapshot.extra_rows]
    crawl_rows = _rows_to_crawl_rows(snapshot.main_rows, snapshot.extra_rows)

    crawl_result = CrawlExecutionResult(
        output_filename=output_filename,
        crawl_rows=crawl_rows,
        target_input=str(crawl_ctx.get("target_input") or setup.target_input),
        max_psi_urls=crawl_ctx.get("max_psi_urls"),
        crawl_urls=list(crawl_ctx.get("crawl_urls") or []),
        sitemap_meta=dict(crawl_ctx.get("sitemap_meta") or {}),
        sitemap_files_meta=dict(crawl_ctx.get("sitemap_files_meta") or {}),
        source_label=str(crawl_ctx.get("source_label") or snapshot.domain),
        workers=int(crawl_ctx.get("workers") or 0),
        request_delay=float(crawl_ctx.get("request_delay") or 0.0),
        full_suite=bool(crawl_ctx.get("full_suite", True)),
        previous_audit_path=str(
            setup.previous_audit_path_preset
            or crawl_ctx.get("previous_audit_path")
            or ""
        ),
        checkpoint_every=int(crawl_ctx.get("checkpoint_every") or 0),
        crawl_completed=bool(crawl_ctx.get("crawl_completed", True)),
        check_external_link_status=bool(crawl_ctx.get("check_external_link_status", True)),
        check_og_images=bool(crawl_ctx.get("check_og_images", False)),
        check_content_images=bool(crawl_ctx.get("check_content_images", False)),
        crawl_duration_seconds=float(crawl_ctx.get("crawl_duration_seconds") or 0.0),
        excluded_cms_action_urls=excluded,
        gsc_url_inspection=crawl_ctx.get("gsc_url_inspection"),
        max_memory_mb=crawl_ctx.get("max_memory_mb"),
        streaming=bool(crawl_ctx.get("streaming", False)),
        crawl_log_entries=_crawl_log_entries_from_json(crawl_ctx.get("crawl_log_entries")),
        robots_by_domain=_robots_by_domain_from_json(crawl_ctx.get("robots_by_domain")),
        competitor_domains=tuple(crawl_ctx.get("competitor_domains") or ()),
    )

    sitemap_keys_raw = enrich_ctx.get("sitemap_url_keys") or []
    benchmark_columns = enrich_ctx.get("competitor_benchmark_columns")
    enrichment_result = EnrichmentResult(
        typed_main_rows=typed_main_rows,
        typed_extra_rows=typed_extra_rows,
        status_by_url=dict(enrich_ctx.get("status_by_url") or {}),
        sitemap_url_keys=set(str(key) for key in sitemap_keys_raw),
        crawl_log_entries=_crawl_log_entries_from_json(enrich_ctx.get("crawl_log_entries")),
        image_probe_by_url=enrich_ctx.get("image_probe_by_url"),
        competitor_benchmark_rows=enrich_ctx.get("competitor_benchmark_rows"),
        competitor_benchmark_columns=(
            tuple(benchmark_columns) if benchmark_columns else None
        ),
        graph_metrics=enrich_ctx.get("graph_metrics"),
    )
    return crawl_result, enrichment_result


def assert_snapshot_domain_matches(
    snapshot: CrawlReplaySnapshot,
    target_input: str,
) -> None:
    expected = resolve_snapshot_domain(target_input)
    if snapshot.domain != expected:
        raise ReplaySnapshotError(
            f"Snapshot domain {snapshot.domain!r} does not match target {expected!r}."
        )


def merge_setup_from_snapshot(setup: RunSetup, snapshot: CrawlReplaySnapshot) -> RunSetup:
    """Overlay export-relevant setup fields stored in the snapshot."""
    ctx = snapshot.setup_context
    return replace(
        setup,
        high_value_slugs=list(
            ctx.get("high_value_slugs") or setup.high_value_slugs
        ),
        competitor_domains=tuple(
            ctx.get("competitor_domains") or setup.competitor_domains
        ),
        export_pdf=bool(ctx.get("export_pdf", setup.export_pdf)),
    )
