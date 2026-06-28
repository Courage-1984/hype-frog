# reporter/ — scoped Claude Code context

Inherits root `CLAUDE.md`. Additional invariants for this layer only.

## Highest-priority rules

- **Never mutate upstream row dicts** (`main_data` / pipeline dicts) inside reporter. Treat all incoming data as read-only.
- **Workbook integrity over convenience.** Prefer defensive openpyxl patterns (`set_freeze_panes_safe`, `sanitize_sheet_view_selection`) over direct attribute writes.
- **String sanitization is mandatory** on every cell write — strip non-printable/control characters and formula-injection prefixes (`=`, `+`, `-`, `@`). The enforcement paths in `engine_io.py` and `pipeline/export.py` must stay aligned.

## Sheet name synchronization (3-way lock)

Sheet names are held in three places that must always stay in sync:

1. `sheets/config.py` — string constants (e.g. `CONTENT_HUB_METRICS_SHEET`)
2. `engine_guardrails.py` — `_TOC_FRIENDLY_DESCRIPTIONS` dict (TOC blurb + hyperlink target)
3. `sheets/workbook_layout.py` — `VISIBLE_WORKBOOK_TAB_ORDER` / `ADVANCED_WORKBOOK_TAB_ORDER`

Renaming a sheet requires updating all three. Missing any one breaks TOC hyperlinks or hides tabs incorrectly.

## RAG palette — single source of truth

All status colours import from `sheets/config.py` (`RAG_RED`, `RAG_AMBER`, `RAG_GREEN`, `*_FONT` variants, `RAG_RED_SOFT`, `RAG_AMBER_SOFT`, `RAG_NEUTRAL`, `ZEBRA_BAND`). Never use inline hex literals. Mocha overrides apply at module import time when `HF_EXCEL_THEME=mocha`.

## Module ownership (who writes what)

| Module | Role |
|--------|------|
| `engine_guardrails.py` | TOC refresh, Action Required normalisation, freeze policy, tooltips — runs last |
| `engine_formatting.py` | Conditional formatting application |
| `engine_io.py` | Workbook-safe I/O and sanitization |
| `engine_rows.py` | Report-row assembly and domain shaping |
| `excel_engine.py` | Compatibility facade only — not a behaviour owner |
| `narrative_engine.py` | Natural-language copy — read-only consumer, no workbook writes |
| `summary_builder.py` | Cross-sheet aggregation — no workbook writes |
| `workbook_audit.py` | Post-write audit pass — read-only, must not modify cells |

## Action Required literals (Content Optimisation Hub)

Allowed set: `Complete`, `Needs Copy`, `Needs Optimisation` (British spelling).
Formula in `engine_rows.py`: `=IF(<On-Page Optimization Score> >= 85, "Complete", "Needs Copy")`.
`apply_action_required_guardrails` normalises legacy values but **skips the Hub sheet** (conditional rules handle it there). Do not rename these literals without updating both the formula and `sheets/conditional.py`.

## Ghost pane safety

When clearing `freeze_panes`, also clear orphaned `sheetView` selections. Use `sanitize_sheet_view_selection` and `apply_optimal_view_state` — do not bypass them with direct `worksheet.freeze_panes =` assignments on data sheets.

## Adding a new sheet checklist

1. Add string constant to `sheets/config.py`
2. Add to `VISIBLE_WORKBOOK_TAB_ORDER` or `ADVANCED_WORKBOOK_TAB_ORDER` in `sheets/workbook_layout.py`
3. Register a TOC description in `engine_guardrails._TOC_FRIENDLY_DESCRIPTIONS`
4. Apply view-state guardrails and string sanitization in the builder
5. Run `uv run pytest tests/reporter/` to catch TOC/tab alignment regressions
