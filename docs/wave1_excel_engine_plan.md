# Wave 1 plan: split `excel_engine.py`

This plan documents how to decompose `src/hype_frog/reporter/excel_engine.py` while preserving workbook integrity guarantees required by reporter guardrails.

## Current logical blocks in `excel_engine.py`

1. **Legacy formatting and conditional formatting**
   - Functions like `apply_fixplan_workflow_formatting`, `ensure_auto_filter`, `ensure_freeze_header`, `apply_global_conditional_formatting`.
   - Handles coloring, databar/scales, and legacy header-driven formatting.

2. **Row writing + sanitization utilities**
   - `_safe_sheet_name`, `_sanitize_excel_value`, `_sanitize_excel_url`, `_normalize_url_for_match`.
   - `write_dict_rows_sheet`, `write_cached_sheet_chunked`, `load_cached_rows`, `build_core_dataframes`.

3. **Report row assemblers**
   - `build_fixplan_rows`, `write_snippet_candidates_chunked`, `build_content_optimisation_hub_rows`.
   - Includes fallback keyword heuristics and action-required row preparation.

4. **Strict workbook guardrails**
   - TOC descriptions and metadata maps.
   - `apply_action_required_guardrails`, `refresh_toc_descriptions_dynamic`, `apply_freeze_c2_data_sheets`, `apply_workbook_export_guardrails`.

5. **Facade wrappers**
   - `adjust_sheet_format`, `apply_tab_hyperlinks` that delegate into `reporter/sheets/*`.

## Proposed split (4 modules)

### 1) `src/hype_frog/reporter/engine_io.py`
- Owns pure workbook IO + sheet writing and low-level safe value/sheet-name helpers:
  - `_safe_sheet_name`, `_sanitize_excel_value`, `_sanitize_excel_url`, `_normalize_url_for_match`
  - `write_dict_rows_sheet`, `write_cached_sheet_chunked`, `load_cached_rows`, `build_core_dataframes`
- Goal: isolate write-path safety and data serialization.

### 2) `src/hype_frog/reporter/engine_formatting.py`
- Owns visual formatting/conditional rules:
  - `apply_fixplan_workflow_formatting`, `ensure_auto_filter`, `ensure_freeze_header`, `apply_global_conditional_formatting`
- Goal: keep style rules and sheet-level formatting separate from row assembly logic.

### 3) `src/hype_frog/reporter/engine_rows.py`
- Owns row-building/domain transforms:
  - `build_fixplan_rows`, `write_snippet_candidates_chunked`, `build_content_optimisation_hub_rows`
- Goal: isolate business calculations and row shape assembly from openpyxl mechanics.

### 4) `src/hype_frog/reporter/engine_guardrails.py`
- Owns invariant enforcement:
  - TOC description maps
  - `friendly_toc_description`, `apply_header_tooltips`, `apply_action_required_guardrails`
  - `refresh_toc_descriptions_dynamic`, `apply_freeze_c2_data_sheets`, `apply_workbook_export_guardrails`
- Goal: make safety-critical behavior explicit and centralized.

## Guardrail preservation requirements (non-negotiable)

The split must preserve these invariants exactly:

1. **Nuclear view-state guardrails**
   - For small non-core sheets, disable freeze panes and autofilter behavior as currently implemented.
   - When freeze panes are removed, clear orphaned sheet selections.

2. **Ghost pane selection guards**
   - Keep pane/selection consistency logic intact (no invalid pane selections relative to split state).
   - Preserve existing safe patterns used by TOC and sheet view-state utilities.

3. **Action Required literal and formatting contract**
   - Continue enforcing `Needs Copy` red conditional behavior.
   - Never emit inconsistent action literals for the Content Optimisation Hub flow.

4. **TOC parity**
   - TOC naming and descriptive blurbs must continue matching actual sheet names.
   - Dynamic TOC refresh must remain part of workbook guardrail pass.

5. **Sanitization**
   - Continue stripping illegal/non-printable characters before writing.
   - Preserve numeric-safe handling in conditional-format-sensitive columns.

## Incremental execution plan (safe rollout)

1. **Phase A: move code without behavior changes**
   - Create new modules and copy functions verbatim.
   - Keep `excel_engine.py` re-exporting existing APIs to avoid call-site churn.

2. **Phase B: switch internal imports**
   - Point `excel_engine.py` wrappers at new module homes.
   - Maintain old symbol names and `__all__` compatibility.

3. **Phase C: tighten tests**
   - Add/extend tests for:
     - expected sheet set and TOC descriptions
     - action-required formatting/state
     - freeze/view-state behavior on small sheets
     - ghost-pane selection safety

4. **Phase D: optional cleanup**
   - Remove duplicate legacy scaffolding once parity tests are stable.

## Success criteria

- `uv run hype-frog --quick-test` completes with no missing-sheet format warnings.
- Workbook includes full expected sheet set with TOC parity.
- Guardrail functions still run in the same export order and produce identical outcomes for:
  - view state
  - Action Required formatting
  - TOC descriptions
  - freeze behavior.
