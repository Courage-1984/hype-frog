# Excel reporting standards

## Reporter module ownership

Excel reporting no longer relies on a single monolithic engine file. Responsibility is intentionally split across:

- `src/hype_frog/reporter/engine_guardrails.py` — invariant enforcement (Action Required normalization, TOC refresh, freeze policy, tooltip governance).
- `src/hype_frog/reporter/engine_formatting.py` — visual formatting and conditional format application.
- `src/hype_frog/reporter/engine_io.py` — workbook-safe I/O, sanitization helpers, and row writing bridges.
- `src/hype_frog/reporter/engine_rows.py` — report-row assembly and domain-specific row shaping.

`src/hype_frog/reporter/excel_engine.py` remains a compatibility facade/re-export layer, not a monolithic behaviour owner.

## Integrity first

Workbooks are end-user artifacts. Prefer conservative openpyxl operations: valid merges, freezes compatible with selection panes, and sanitized cell text so worksheet XML remains valid in common desktop clients.

## Sanitization

- **Strings:** Strip illegal XML control characters and non-printable content before write (`pipeline/export.py` and `reporter/engine_io.py` sanitization paths must stay aligned).
- **Numbers:** Replace non-finite floats with blank-safe values for export.
- **Dates:** Normalize timezone-aware and datetime columns to naive string forms where the export path expects strings.

## View state and “ghost” panes

- **`sanitize_sheet_view_selection`** enforces that active pane selections match actual split panes (`xSplit` / `ySplit`). Invalid combinations (for example `bottomRight` without both splits) are removed to prevent corrupted view state.
- **`apply_optimal_view_state`** applies governed freeze defaults and disables freeze/autofilter on very small non-core sheets to avoid fragile client layouts.

When clearing `freeze_panes`, also clear orphaned `sheetView` selections per the shared view-state helper patterns.

These invariants remain absolute after modularization:

- **Ghost pane safety:** pane selections must always match actual split panes.
- **Nuclear view-state guardrails:** tiny non-core sheets must not retain risky freeze/autofilter combinations.
- **String sanitization:** all written strings must remain workbook-safe and injection-safe.

## Table of Contents

The TOC sheet lists each workbook tab with:

- A stable **section** name (sheet title),
- An **Open** hyperlink,
- A **descriptive** blurb (`toc_descriptions` dictionary pattern in `src/hype_frog/reporter/sheets/toc.py`).

New sheets must register a human-readable description there.

## Content hub — freeze and slug column

The Content Optimisation Hub freezes through column **H** (``Assigned Owner`` plus
``URL Slug Normalization``) with ``freeze_panes = 'I3'`` (banner row 1, headers row 2,
data from row 3). ``URL`` and editorial columns scroll from column **I** onward.
The canonical freeze target is ``CONTENT_HUB_FREEZE_PANES`` in
``reporter/sheets/config.py``.

## Content hub — Action Required

Business logic for draft vs ready copy uses explicit literals:

- Ready path: **`Ready to Publish`**
- Blocked path: **`Needs Copy`**

Conditional formatting must highlight **`Needs Copy`** in **red** (see `src/hype_frog/reporter/sheets/conditional.py` for the `CellIsRule` pattern). Do not rename these literals without updating both formulas and format rules.

## Numeric conditional formats

Columns with numeric conditional formatting must not receive arbitrary string placeholders; use blank or numeric defaults when data is missing.

## Testing touchpoints

Excel behavior is covered in part by `test_excel_engine.py` and tests under `tests/`. Run pytest after changing view state, TOC, or conditional formatting.
