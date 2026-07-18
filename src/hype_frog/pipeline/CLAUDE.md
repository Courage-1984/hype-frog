# pipeline/ — scoped context

Inherits root [`CLAUDE.md`](../../../CLAUDE.md).

**Source of truth:** [`.cursor/rules/crawler_engine.mdc`](../../../.cursor/rules/crawler_engine.mdc) — shared across `crawler/`, `extractors/`, `pipeline/`, `core/`, `orchestration/`.

Read it before editing this layer: enrichment glue, graph intelligence, scoring helpers, export-safe transforms. `print()` is prohibited here (root `CLAUDE.md` contract) — use `core/` logging. New signal sources must wire through `crawler/data_assembler.py`, not be merged ad hoc here.
