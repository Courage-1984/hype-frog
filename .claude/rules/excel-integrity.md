---
paths:
  - src/hype_frog/reporter/**
---

# Reporter / Excel integrity

## Non-negotiable
- Never mutate upstream row dicts — read-only consumers
- Sanitize all string cells (control chars; formula-injection prefixes `=+-@`)
- **3-way sheet name lock:** `sheets/config.py` + `workbook_layout.py` tab order + `engine_guardrails._TOC_FRIENDLY_DESCRIPTIONS`
- Ghost/nuclear view-state guardrails on freezes and small sheets
- Numeric CF columns: blank/`None` when unmeasured — never non-numeric strings

## Content Optimisation Hub — Action Required
Literals only: `Complete`, `Needs Copy`, `Needs Optimisation` (British spelling).
Computed in `pipeline/action_required.py::determine_action_required()`; CF in `sheets/conditional.py`. Do not rename without updating all three + header tooltip.

## Module split
- `engine_guardrails.py` — invariants, TOC, freezes, tooltips
- `engine_formatting.py` / `engine_io.py` / `engine_rows.py` — format, I/O, row shaping
- `excel_engine.py` — facade only
- `sheets/merged_builders.py` — merged diagnostic tabs
- `workbook_audit.py` — post-write audit (read-only on workbook)

## New sheet
Use skill `.claude/skills/reporter/add-workbook-sheet/`. Verify: `uv run pytest tests/reporter/`

Detail: `docs/excel_reporting_standards.md`, `docs/workbook_tabs.md`
