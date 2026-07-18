"""Re-fetch skipped HTTP-200 URLs with Playwright and re-assemble row payloads."""

from __future__ import annotations

import asyncio
from typing import Any

from hype_frog.core import get_logger
from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.core.skipped_row_contract import apply_skipped_row_contract
from hype_frog.core.status_codes import is_success_status
from hype_frog.crawler.data_assembler import finalize_row_state
from hype_frog.crawler.fetcher import _assemble_row_from_html_sync
from hype_frog.crawler.network_engine import PlaywrightSessionManager, fetch_rendered_with_diagnostics
from hype_frog.pipeline.content_hub_metrics import backfill_extra_content_hub_metrics
from hype_frog.rules.scoring import scorable_extraction_state

logger = get_logger(__name__)


async def _refetch_row_with_playwright(
    *,
    main_row: MainRowPayload,
    extra_row: ExtraRowPayload,
    render_wait_ms: int,
    selector_wait_ms: int,
    playwright_session_manager: PlaywrightSessionManager,
) -> bool:
    extra_values = extra_row.values
    main_values = main_row.values
    url = str(extra_values.get("URL") or main_values.get("URL") or "").strip()
    if not url:
        return False
    target = str(extra_values.get("Final URL") or url).strip() or url
    diagnostics = await fetch_rendered_with_diagnostics(
        target,
        render_wait_ms=render_wait_ms,
        selector_wait_ms=selector_wait_ms,
        session_manager=playwright_session_manager,
    )
    html = diagnostics.get("html")
    if not html:
        apply_skipped_row_contract(main_values, extra_values)
        return False

    response_headers = {
        str(k).lower(): str(v) for k, v in (diagnostics.get("response_headers") or {}).items()
    }
    depth = int(extra_values.get("Crawl Depth") or extra_values.get("URL Depth") or 0)
    await asyncio.to_thread(
        _assemble_row_from_html_sync,
        main_data=main_row,
        extra=extra_row,
        html=html,
        resolved_url=target,
        depth=depth,
        response_headers=response_headers,
    )
    extraction_source = str(diagnostics.get("extraction_source") or "rendered_browser")
    extraction_state = str(diagnostics.get("extraction_state") or "partial")
    main_values["Extraction Source"] = extraction_source
    extra_values["Extraction Source"] = extraction_source
    if extraction_source == "rendered_browser":
        extra_values["Extraction Source Fallback"] = False
    main_values["Extraction State"] = extraction_state
    extra_values["Extraction State"] = extraction_state
    extra_values["JS Dependent"] = bool(diagnostics.get("is_js_dependent"))
    extra_values["Raw Words"] = int(diagnostics.get("raw_word_count") or 0)
    extra_values["Rendered Words"] = int(diagnostics.get("rendered_word_count") or 0)
    extra_values["Field LCP (ms)"] = diagnostics.get("field_lcp_ms")
    extra_values["Field CLS"] = diagnostics.get("field_cls")
    extra_values.pop("skip_reason", None)
    finalize_row_state(main_row, extra_row)
    backfill_extra_content_hub_metrics(extra_values, main_values)
    return scorable_extraction_state(extraction_state)


async def refetch_skipped_render_urls(
    typed_main_rows: list[MainRowPayload],
    typed_extra_rows: list[ExtraRowPayload],
    *,
    render_wait_ms: int = 4000,
    selector_wait_ms: int = 3000,
) -> dict[str, Any]:
    """Attempt Playwright re-render for HTTP-200 rows left at skipped extraction."""
    extra_by_url = {
        str(row.values.get("URL") or "").strip(): row
        for row in typed_extra_rows
        if row.values.get("URL")
    }
    candidates: list[tuple[MainRowPayload, ExtraRowPayload]] = []
    for main_row in typed_main_rows:
        main_values = main_row.values
        url = str(main_values.get("URL") or "").strip()
        extra_row = extra_by_url.get(url)
        if not extra_row:
            continue
        extra_values = extra_row.values
        state = str(main_values.get("Extraction State") or extra_values.get("Extraction State") or "")
        if scorable_extraction_state(state):
            continue
        if not is_success_status(extra_values.get("Status Code")):
            apply_skipped_row_contract(main_values, extra_values)
            continue
        candidates.append((main_row, extra_row))

    if not candidates:
        return {"attempted": 0, "rescored": 0}

    rescored = 0
    async with PlaywrightSessionManager() as manager:
        for main_row, extra_row in candidates:
            try:
                if await _refetch_row_with_playwright(
                    main_row=main_row,
                    extra_row=extra_row,
                    render_wait_ms=render_wait_ms,
                    selector_wait_ms=selector_wait_ms,
                    playwright_session_manager=manager,
                ):
                    rescored += 1
            except Exception as exc:
                logger.warning(
                    "Skipped-row refetch failed for %s: %s",
                    extra_row.values.get("URL"),
                    exc,
                )
                apply_skipped_row_contract(main_row.values, extra_row.values)

    logger.info(
        "Skipped-row refetch: attempted %d URL(s), %d now scorable.",
        len(candidates),
        rescored,
    )
    return {"attempted": len(candidates), "rescored": rescored}


__all__ = ["refetch_skipped_render_urls"]
