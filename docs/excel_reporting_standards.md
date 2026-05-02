# Excel reporting standards

## Integrity first

Workbooks are end-user artifacts. Prefer conservative openpyxl operations: valid merges, freezes compatible with selection panes, and sanitized cell text so worksheet XML remains valid in common desktop clients.

## Sanitization

- **Strings:** Strip illegal XML control characters and non-printable content before write (`pipeline/export.py` helpers mirror the intent of `main.py` sanitization paths).
- **Numbers:** Replace non-finite floats with blank-safe values for export.
- **Dates:** Normalize timezone-aware and datetime columns to naive string forms where the export path expects strings.

## View state and “ghost” panes

- **`sanitize_sheet_view_selection`** enforces that active pane selections match actual split panes (`xSplit` / `ySplit`). Invalid combinations (e.g. `bottomRight` without both splits) are removed to prevent corrupted view state.
- **`apply_optimal_view_state`** applies governed freeze defaults and disables freeze/autofilter on very small non-core sheets to avoid fragile client layouts.

When clearing `freeze_panes`, also clear orphaned `sheetView` selections per the patterns in `reporters/sheets/toc.py` and `view_state.py`.

## Table of Contents

The TOC sheet lists each workbook tab with:

- A stable **section** name (sheet title),
- An **Open** hyperlink,
- A **descriptive** blurb (`toc_descriptions` dictionary pattern in `reporters/sheets/toc.py`).

New sheets must register a human-readable description there.

## Content hub — Action Required

Business logic for draft vs ready copy uses explicit literals:

- Ready path: **`Ready to Publish`**
- Blocked path: **`Needs Copy`**

Conditional formatting must highlight **`Needs Copy`** in **red** (see `reporters/sheets/conditional.py` for the `CellIsRule` pattern). Do not rename these literals without updating both formulas and format rules.

## Numeric conditional formats

Columns with numeric conditional formatting must not receive arbitrary string placeholders; use blank or numeric defaults when data is missing.

## Testing touchpoints

Excel behavior is covered in part by `test_excel_engine.py` and tests under `tests/`. Run pytest after changing view state, TOC, or conditional formatting.
