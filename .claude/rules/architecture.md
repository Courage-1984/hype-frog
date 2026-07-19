---
paths:
  - src/hype_frog/**
---

# Architecture (path-scoped)

Dependency direction: **core/config → crawler/extractors → validators/analysis → pipeline/rules → reporter**. **orchestration** coordinates only.

## Boundaries
- `core/` — models, env accessors, logging, URL identity, discovery order
- `crawler/` — fetch, assemble, PSI/GSC (not parsing-only; not workbook)
- `extractors/` — parse-only; no workbook I/O
- `pipeline/` — enrichment glue, Main merge; no `print()`
- `rules/` — IssueRule + scoring + playbook
- `reporter/` — workbook/HTML/PDF; read-only rows
- `orchestration/` — BFS, enrichment phases, export sequence
- `checkpoint/` — resume; `snapshots/` — `--regen-report` replay
- `diagnostics/` — shipped CLI gates (not test helpers)
- `main.py` / `app_orchestrator.py` — no domain logic

## Always
- One-sentence vibe check before non-trivial logic
- Explicit type annotations on new/changed public APIs
- Row keys append-only; new fields additive in `core/models.py`
- LLM/PSI: short timeout (~5s), instant `Unknown`/degrade, no blocking retries
- Observability via `core` logging only

Detail: `docs/system_architecture.md`
