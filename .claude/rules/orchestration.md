---
paths:
  - src/hype_frog/orchestration/**
---

# Orchestration coordination

Source of truth: `.cursor/rules/orchestration.mdc` and `docs/system_architecture.md`.

## Boundaries
Coordinates crawl, enrichment, export — no business logic. Calls `crawler/`, `analysis/`, `pipeline/`, `reporter/`.

## Export sequencing (export_flow.py)
1. xlsx first (must succeed)
2. HTML if `HF_EXPORT_HTML=1` (non-fatal)
3. PDF if `HF_EXPORT_PDF=1` (non-fatal)

## BFS
Respect `max_pages`/`max_depth`; log at INFO when budget exhausted.

## No print()
Use `core/` logging only.
