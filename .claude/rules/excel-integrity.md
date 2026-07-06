---
paths:
  - src/hype_frog/reporter/**
---

# Reporter / Excel integrity

Source of truth: `.cursor/rules/excel_engine.mdc` and `docs/excel_reporting_standards.md`.

## Non-negotiable
- Never mutate upstream row dicts in reporter.
- Sanitize all string cells (control chars, formula-injection prefixes).
- 3-way sheet name lock: `sheets/config.py` + `engine_guardrails._TOC_FRIENDLY_DESCRIPTIONS` + `sheets/workbook_layout.py`.

## Content Optimisation Hub Action Required
Literals: `Complete`, `Needs Copy`, `Needs Optimisation` (British spelling).
Computed in `pipeline/action_required.py::determine_action_required()` at export time.

## New sheet checklist
1. Constant in `sheets/config.py`
2. Tab order in `workbook_layout.py`
3. TOC description in `engine_guardrails.py`
4. View-state guardrails + sanitization in builder
5. `uv run pytest tests/reporter/`
