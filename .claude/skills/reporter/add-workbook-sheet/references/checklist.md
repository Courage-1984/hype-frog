# New sheet checklist

1. **Constant** — string in `src/hype_frog/reporter/sheets/config.py`
2. **Tab order** — `VISIBLE_WORKBOOK_TAB_ORDER` or `ADVANCED_WORKBOOK_TAB_ORDER` in `sheets/workbook_layout.py`
3. **TOC** — `engine_guardrails._TOC_FRIENDLY_DESCRIPTIONS` (exact sheet name)
4. **Builder** — often `sheets/merged_builders.py` or a dedicated module; apply view-state guardrails
5. **Sanitize** — all string cells via existing I/O helpers
6. **Export wire** — `orchestration/export_workbook.py` / `export_registry.py` if a new export step
7. **Docs** — `docs/workbook_tabs.md` (+ `excel_reporting_standards.md` if integrity rules change)
8. **Tests** — `tests/reporter/` covering TOC sync / layout as appropriate

Hub Action Required literals (if touched): `Complete`, `Needs Copy`, `Needs Optimisation`.
