Checklist for adding a new workbook sheet:

1. Add string constant to `src/hype_frog/reporter/sheets/config.py`
2. Add to `VISIBLE_WORKBOOK_TAB_ORDER` or `ADVANCED_WORKBOOK_TAB_ORDER` in `sheets/workbook_layout.py`
3. Register TOC description in `engine_guardrails._TOC_FRIENDLY_DESCRIPTIONS`
4. Implement builder (often `sheets/merged_builders.py` or dedicated module)
5. Apply view-state guardrails and string sanitization
6. Wire into `orchestration/export_workbook.py` if new export step needed

Verify: `uv run pytest tests/reporter/ -q --tb=short`

See `.cursor/rules/excel_engine.mdc` for full invariants.
