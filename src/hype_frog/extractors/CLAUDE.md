# extractors/ — scoped context

Inherits root [`CLAUDE.md`](../../../CLAUDE.md).

**Source of truth:** [`.cursor/rules/crawler_engine.mdc`](../../../.cursor/rules/crawler_engine.mdc) — shared across `crawler/`, `extractors/`, `pipeline/`, `core/`, `orchestration/`.

Read it before editing this layer: parsing-only, **no workbook I/O** — output feeds the `Extraction State`/`Extraction Source` contract that `crawler/` and `pipeline/` rely on. New extractor outcomes must map cleanly into `complete`/`partial`/`skipped` with an explicit reason where applicable.
