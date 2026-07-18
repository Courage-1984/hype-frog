# crawler/ — scoped context

Inherits root [`CLAUDE.md`](../../../CLAUDE.md).

**Source of truth:** [`.cursor/rules/crawler_engine.mdc`](../../../.cursor/rules/crawler_engine.mdc) — shared across `crawler/`, `extractors/`, `pipeline/`, `core/`, `orchestration/`.

Read it before editing this layer: Playwright `async_api` only, dual-mode fetch (fast HTTP / accurate rendered with graceful fallback), the `Extraction State` (`complete`/`partial`/`skipped`) and `Extraction Source` contract, bounded retries with exponential backoff, and the `data_assembler.py` module-function ownership of raw+rendered row merging.
