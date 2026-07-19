---
paths:
  - src/hype_frog/orchestration/**
---

# Orchestration

Coordinates crawl, enrichment, export — **no domain logic** (no extraction, scoring formulas, or cell formatting).

## Modules
- BFS: `crawl_runner.py` → `crawl_runner_bfs.py` / `_frontier.py` / `_interactive.py`
- Enrichment: `enrichment_flow.py` (GSC → optional URL Inspection → PSI → probes → scoring/graph/issues)
- Export: `export_flow.py` → `export_workbook.py` / `export_registry.py` / `export_row_builders.py` / `export_executive_reports.py`

## Export order
1. xlsx must succeed
2. HTML if `HF_EXPORT_HTML=1` (non-fatal)
3. PDF if `HF_EXPORT_PDF=1` (non-fatal)

## Invariants
- Respect `max_pages` / `max_depth`; log INFO when budget exhausted
- **No `print()`** — `core` logging only
- CMS action exclusions: extend `config_defaults.EXCLUDED_CMS_ACTION_QUERY_PARAMS`, not hard-coded frontier lists
- Sheet assembly selects/wires; reporter formats/writes/guards

Detail: `docs/system_architecture.md`
