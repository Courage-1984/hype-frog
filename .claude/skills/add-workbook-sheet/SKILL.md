---
name: add-workbook-sheet
description: Add a new Excel workbook sheet with TOC sync and reporter guardrails for hype-frog.
disable-model-invocation: true
---

# Add workbook sheet workflow

## 3-way sheet name lock
1. `reporter/sheets/config.py` — string constant
2. `reporter/sheets/workbook_layout.py` — `VISIBLE_WORKBOOK_TAB_ORDER` or `ADVANCED_WORKBOOK_TAB_ORDER`
3. `reporter/engine_guardrails.py` — `_TOC_FRIENDLY_DESCRIPTIONS`

## Implementation
4. Builder in `reporter/sheets/merged_builders.py` or dedicated module
5. Sanitize strings; apply `sanitize_sheet_view_selection` / freeze guardrails
6. Wire `orchestration/export_workbook.py` if export sequencing changes

## Verify
```powershell
uv run pytest tests/reporter/ -q --tb=short
```

Full rules: `.cursor/rules/excel_engine.mdc` and `docs/excel_reporting_standards.md`.
