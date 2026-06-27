# Wave 2 Pydantic Status (Completed)

## Status

- Wave 2 modular + typed migration is complete in active runtime paths.
- The chain-of-trust now lives in `src/hype_frog/core/models.py`.
- This document is retained as historical context, not an active implementation plan.

## Historical migration map (for reference)

### Crawler layer

1. `src/hype_frog/crawler/data_assembler.py`
   - `init_rows()` now validates into typed payloads (`MainRowPayload` / `ExtraRowPayload`).
   - `assemble_from_html()` and `finalize_row_state()` operate on typed payload objects.
2. `src/hype_frog/crawler/fetcher.py`
   - `fetch_and_parse()` runs typed assembly flow and returns crawl payloads through typed boundaries.

### Reporter layer

1. `src/hype_frog/reporter/engine_io.py`
   - I/O helpers accept typed payloads and map to sheet-write forms safely.
2. `src/hype_frog/reporter/engine_rows.py` and `src/hype_frog/reporter/summary_builder.py`
   - Reporting row assembly consumes typed payload contracts.
3. `src/hype_frog/reporter/excel_engine.py`
   - Facade remains API-stable while delegating to modular engine helpers.

## Ongoing maintenance guardrails

- Keep new payload/state fields additive and backward-tolerant.
- Validate cross-layer row contracts in `core/models.py` before consumption.
- Preserve reporter workbook guardrails while extending typed row usage.
