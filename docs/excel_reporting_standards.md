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

## Workbook tab layout

Canonical tab order and default visibility: `reporter/sheets/workbook_layout.py` (`VISIBLE_WORKBOOK_TAB_ORDER`, `ADVANCED_WORKBOOK_TAB_ORDER`). TOC descriptions: `engine_guardrails.friendly_toc_description`.

### Merged diagnostic sheets

| Sheet | Builder | Purpose |
|-------|---------|---------|
| Technical Diagnostics | `merged_builders.build_technical_diagnostics_rows` | Technical, indexability, redirect, security, PSI/CrUX, GSC columns |
| Content & AI Readiness | `merged_builders.build_content_ai_readiness_rows` | Content, schema, AEO, media signals |
| Issue Register | `merged_builders.build_issue_register_rows` | Unified issue list with history fields |
| Link Inventory | `merged_builders.build_link_inventory_rows` | Internal links with status |
| Broken Link Impact | `merged_builders.build_broken_link_impact_rows` | Broken internal link instances |
| Quick Wins | `merged_builders.build_quick_wins_rows` | Actionable low-effort fixes |

### Inventory and opportunity sheets

**Script Inventory**, **Image Inventory**, **Snippet Opportunities**, **Link Equity Map**, **Anchor Text Audit**, **Redirect Map**, **Robots.txt Analysis**, **Crawl Log**, **Competitor Benchmarks** (optional), **CMS Action URLs**, **Template & Duplication Risks**, **Playbook**.

## Link Inventory deduplication

`build_link_inventory_rows` deduplicates rows on **`(Source URL, Target URL, Anchor Text)`** before write so repeated anchor edges from multi-page discovery do not inflate the sheet.

## Duplicate column prevention

`reporter/sheets/style_helpers.header_exists_in_worksheet` prevents inserting a second **BACK TO DASHBOARD** navigation column (`navigation.py`).

## IssueInventory and Issue Register scope branching

`summary_builder.py` treats `IssueRule.scope` values:

- **`url`** — per-URL rows in IssueInventory.
- **`site`** / **`server`** — one aggregate row with URL label `(site-wide)` or `(server config)` and **`Affected URL Count`**.

Issue Register mirrors reference areas with dynamic `INDIRECT` hyperlinks to the target diagnostic sheet.

## FixPlan columns

`engine_rows.build_fixplan_rows` emits **`Affected Link Instances`** (sum of broken + unresolved internal links per URL) alongside existing workflow columns.

## Main sheet conditional formatting

`conditional.apply_main_sheet_heatmaps` (skipped when `HF_DISABLE_CONDITIONAL_FORMATTING=1`):

- **Colour scale (0–100):** `SEO Health Score`, PSI scores, Lighthouse category scores, `AEO Readiness Score`.
- **Inverted colour scale:** `Lab LCP (Mobile) (s)` (green = fast).
- **Cell rule:** `Status Code` ≥ 400 highlighted red.

Main **Technical Health** column receives a post-format `VLOOKUP` into Technical Diagnostics `SEO Health Score` (`tables_impl._link_main_technical_health_to_diagnostics`).

## Content hub — Action Required (formula literals)

The Hub **Action Required** column uses formula literals **`Complete`** / **`Needs Copy`** (score threshold 85) in `engine_rows.py`. Conditional formatting in `conditional.py` highlights **`Needs Copy`** in red. Dashboard completion metrics count Hub **Status** = `Completed` (separate workflow column).
