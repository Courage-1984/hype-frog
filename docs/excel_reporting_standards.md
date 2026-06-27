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

- A stable **section** name rendered as a `=HYPERLINK("#'Sheet'!A1","Sheet")` jump (column A),
- An **Open** hyperlink (column B),
- A **descriptive** blurb (column C).

Canonical descriptions live in `_TOC_FRIENDLY_DESCRIPTIONS` in
`src/hype_frog/reporter/engine_guardrails.py` (surfaced via `friendly_toc_description`).
`src/hype_frog/reporter/sheets/toc.py` seeds the blurb when each row is appended, and
`refresh_toc_descriptions_dynamic` rewrites column C from the same map at export time.

New sheets must register a human-readable description in
`_TOC_FRIENDLY_DESCRIPTIONS`; otherwise the row falls back to the generic
`Diagnostic metrics for <sheet>.` blurb. The dynamic refresh resolves the target
sheet from the HYPERLINK target (handling sheet names with spaces/apostrophes), so a
bare-name fallback only applies to legacy/plain rows.

### Landing tab and view state

- The workbook **opens on the Dashboard** (`apply_workbook_active_tab`, run last in
  `apply_workbook_export_guardrails`); the Table of Contents stays left-most at index 0.
- `apply_freeze_c2_data_sheets` is the **final freeze authority** for ordinary data
  sheets (normalised to `C2`). Sheets with bespoke layouts are exempt via
  `FREEZE_C2_EXEMPT_SHEETS` (TOC `A3`, Content Optimisation Hub, Executive Dashboard `A8`).
- The **Executive Dashboard** is not a navigation dead-end: it carries `BACK TO
  DASHBOARD` / `BACK TO CONTENTS` links (column N, on the frozen header rows).

### Tooltips and dropdowns

Header tooltips (Excel comments) are gated by **`HF_DISABLE_TOOLTIPS`** (the legacy
`HF_DISABLE_DATA_VALIDATION` still suppresses them for backward compatibility), while
status **dropdowns** remain gated by `HF_DISABLE_DATA_VALIDATION` only. Curated per-column
help bodies live in `_SHEET_CURATED_HEADER_HELP` (`reporter/sheets/validation.py`); semantic
Content Hub tooltips and merged-tab help are applied via `apply_curated_header_tooltips`
(delegated from `help_layer.py`). Schema-metadata tooltips remain in
`SCHEMA_METADATA_HEADER_TOOLTIP_BODIES`; Dashboard KPI blocks stay in `dashboard_config`.
A contract test keeps curated keys aligned with exported column headers.

### Advanced-sheet navigation

The Dashboard "Advanced Sheets" panel surfaces a **curated subset** of the advanced
tabs (relocated below the Owner Issue Summary at row 32+ to avoid column overlap); the
TOC's "Technical & Historical (Advanced)" section remains the complete index of every
advanced sheet (`ADVANCED_WORKBOOK_TAB_ORDER`). **Issue Register** is the canonical issue
backlog; legacy **IssueInventory** is hidden and excluded from the TOC.

### Formulas and display projection (Phase 3 polish)

- Cross-sheet joins use header-resolved ranges (`sheet_data_column_range`,
  `link_inventory_column_letter`, `content_hub_column_letter`) rather than hardcoded
  column letters.
- FixPlan **Hub Status (Content Hub)** INDEX/MATCHes Hub **Status** on Hub **URL**.
- Content Hub **SEO / Technical / Copy Score** columns live-link to Main via INDEX/MATCH.
- Main **Performance & CWV** columns remain in a collapsed/hidden group; Technical
  Diagnostics is the source of truth for PSI/CWV detail.
- British display headers (e.g. **On-Page Optimisation Score**) are applied at the reporter
  layer via `DISPLAY_HEADER_ALIASES`; pipeline row keys stay append-only.
- The **Dashboard** Owner Issue Summary (G24–K31), status/severity side panels (M7/M8), sprint
  roll-ups (M5/M6), and Top Issues block (G/H15+) use live `COUNTIF`/`SUMIF`/`INDEX`/`MATCH`
  against FixPlan header-resolved ranges so figures stay current when FixPlan rows change.
- **Link Inventory** table headers use the shared navy mock-table style (`STD_NAVY`) for visual
  parity with other inventory sheets.

## Content hub — freeze and slug column

The Content Optimisation Hub freezes through column **H** (``Assigned Owner`` plus
``URL Slug Normalization``) with ``freeze_panes = 'I3'`` (banner row 1, headers row 2,
data from row 3). ``URL`` and editorial columns scroll from column **I** onward.
The canonical freeze target is ``CONTENT_HUB_FREEZE_PANES`` in
``reporter/sheets/config.py``.

## Content hub — Action Required

The **Action Required** column is **formula-driven** in `engine_rows.py`:

```
=IF(<On-Page Optimization Score> >= 85, "Complete", "Needs Copy")
```

So the live literals are **`Complete`** (ready, score ≥ 85) and **`Needs Copy`** (blocked, score < 85). The full allowed set enforced by `engine_guardrails._ACTION_REQUIRED_ALLOWED` is **`Complete`**, **`Needs Copy`**, **`Needs Optimisation`**. `apply_action_required_guardrails` normalises legacy/free-text values to these (e.g. `Ready to Publish`, `completed` → `Complete`; `Needs Optimization` → `Needs Optimisation`; unknown text → `Needs Copy`) but **skips the `Content Optimisation Hub` sheet**, which relies on the conditional rules below.

Conditional formatting (`apply_content_hub_conditional_rules` in `src/hype_frog/reporter/sheets/conditional.py`) highlights **`Needs Copy`** in the canonical RAG **red** (`RAG_RED` fill, `RAG_RED_FONT` text), **`Needs Optimisation`** in RAG **amber**, and **`Complete`** / legacy `Ready to Publish` in RAG **green** — all drawn from the shared palette (see *Conditional formatting & colour palette* below). Guardrails normalise legacy US spellings to **`Needs Optimisation`** before export audit. The matching `engine_guardrails` direct fills (applied to non-Hub sheets) use the same RAG constants. Do not rename these literals without updating both the formula and the format rules.

A separate **Status** column (data-validation list `To Do, In Progress, Review, Completed`) tracks editorial workflow; Dashboard completion metrics count `Status == Completed`, not Action Required.

## Conditional formatting & colour palette

**Single source of truth.** Status colours are defined once in `reporter/sheets/config.py`
as the canonical **RAG palette** (`RAG_RED` / `RAG_AMBER` / `RAG_GREEN` with matching
`*_FONT` colours, plus `RAG_RED_SOFT` / `RAG_AMBER_SOFT`, `RAG_NEUTRAL`, `ZEBRA_BAND`) and a
single Office heatmap scale (`HEATMAP_LOW`/`MID`/`HIGH`) and `DATA_BAR_BLUE`. Prefer importing
these constants over inline hex literals. `dashboard_config` RAG names (`GOOD_COLOR`,
`WARN_COLOR`, `ALERT_COLOR`, `SOFT_ALERT_COLOR`, `SOFT_WARN_COLOR`) are thin aliases of the
canonical palette so the dashboards and the data sheets stay in lockstep.

**Kill switch.** `HF_DISABLE_CONDITIONAL_FORMATTING` disables every Excel conditional-formatting
**rule** (colour scales, data bars, `CellIs`/`Formula` rules). It is honoured defensively inside
each rule-adding helper — `apply_global_conditional_formatting`,
`apply_executive_priority_formatting`, `apply_main_sheet_heatmaps`,
`apply_dashboard_metric_conditional_rules`, the Content Hub passes, the PSI/merged passes, and
the OG Image Health rule — so the flag works regardless of caller. Static semantic cell fills
(zebra striping, KPI-card and section fills) are **layout**, not conditional formatting, and are
intentionally unaffected. See `.env.example` for the full toggle family.

**No double-CF on Main.** `apply_main_sheet_heatmaps` owns `Status Code`, `SEO Health Score`,
`AEO Readiness Score`, `Word Count (Body)`, and `Severity Badge` on the Main sheet. The global
pass receives `skip_headers` for these so two conflicting rules never stack on one range.

**Severity / status coverage.** The global pass colours both the rich `Severity Badge` column and
the plain `Severity` column (FixPlan/issue sheets), plus `Action Needed` (Yes/No), `Status`
(workflow), and numeric score bands — all via RAG constants.

**Tab colours.** Every ordered tab (except the TOC) carries a group tab colour in
`workbook_layout._SHEET_TAB_COLORS`; the advanced inventory/opportunity sheets (Link Equity Map,
Anchor Text Audit, Snippet Opportunities, Competitor Benchmarks, Script Inventory, Image
Inventory) use `TAB_COLOR_ADVANCED`.

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

- **Colour scale (0–100):** `SEO Health Score`, `Mobile PSI Score`, `Desktop PSI Score`, the Lighthouse category scores (Performance / Accessibility / Best Practices / SEO, Mobile), and `AEO Readiness Score`.
- **Inverted colour scale:** `Lab LCP (Mobile) (s)` (green = fast).
- **0/5/10 colour scale:** `E-E-A-T Signal Score`.
- **Data bar:** `Word Count (Body)` (0–2000).
- **Cell rules (`CellIsRule`):** `Status Code` ≥ 400 highlighted red, plus fills on `Schema Error Count`, `Click Depth`, `Page Size (KB)`, `Severity Badge`, `Content Age (days)`, `Meta Desc Length`, and thin-content flags.

Main **Technical Health** column receives a post-format `VLOOKUP` into Technical Diagnostics `SEO Health Score` (`tables_impl._link_main_technical_health_to_diagnostics`).

## HTML executive report

The reporter layer also produces a parallel HTML executive report via `html_report_data.py`, `html_report_renderer.py`, and `html_report_writer.py`. This report reads the same enriched data as the xlsx but produces a self-contained HTML file for stakeholder distribution (triggered by `HF_EXPORT_HTML=1`).

The HTML report follows the same data-integrity principles as the xlsx:
- It reads pipeline data as **read-only** — it must not mutate upstream row dicts.
- Cell values are sanitised via `html.escape` before insertion into the template.
- No tool-internal naming appears in the rendered output (white-label).

New data points added to the xlsx output should be reflected in `html_report_data.py` → `ReportContext` where relevant to the executive summary.

### Single source of truth for executive deliverables

Both the HTML report **and** the PDF executive summary (`pdf_exporter.py`, triggered by `HF_EXPORT_PDF=1`) are presentation-only consumers of the **same** `ReportContext` built once by `build_report_context`. `orchestration/export_flow.py` constructs the context a single time and feeds both renderers, so the two deliverables always show identical figures.

Invariants:
- **Do not re-aggregate** pipeline rows inside `pdf_exporter.py`; read from `ReportContext` only. (The legacy `_aggregate_kpis` / `_top_issues` helpers were removed.)
- **Effort is reported in hours** everywhere (the `Sprint & resource plan` uses `ReportContext.sprint_plan` hours, not T-shirt sizes).
- **Severity headline counts are page counts** (`critical_url_count` / `warning_url_count`), matching the HTML severity bar and KPI cards.
- The PDF audit date comes from the crawl `run_timestamp` (via `ReportContext.crawl_date`), not `datetime.now()`.
- Branding (`brand_colour`, `prepared_by`, `client_name`) resolves once in `export_flow`, preferring `HF_REPORT_*` then `HF_PDF_*`, then a shared default (`#1e293b`).
- `ReportContext.quick_wins` is an additive projection of the Quick Wins sheet rows (`name`, `effort_hours`, `owner`).

Presentation conventions shared by both deliverables:
- **Two severity views, clearly distinguished.** The "Pages by Worst Severity" tally counts each page once by its highest-severity issue (with a visible page total); "Top Issues by Impact" counts pages affected by each individual issue (a page may appear under several). Captions in the HTML report make the distinction explicit.
- **Feature parity.** Both the HTML report and the PDF surface the same shared facts: KPIs, Mobile PSI, projected SEO health, Search Console summary, top issues, quick wins, and the sprint/resource plan.
- **RAG is never colour-only.** Status is also conveyed textually (PDF status words + legend; HTML severity counts/totals and numeric cell values) for accessibility and greyscale printing.

Regression guards (`tests/reporter/test_executive_report_parity.py`) lock these invariants in: both deliverables build from a single `ReportContext` (top-issue counts cannot diverge), quick-win effort is always numeric, the severity tally reconciles to the page total, and the PDF audit date comes from the crawl timestamp. The `--full-smoke-test` fixtures (`diagnostics/full_smoke_fixtures.py`) are deterministically enriched to produce a *representative* audit (varied SEO health, AEO readiness, a realistic severity mix, and a populated HTTP status table) rather than an all-missing baseline, so the smoke artefacts exercise the real scoring and reporting paths.

## Content hub — freeze panes

The Hub freezes through column **H** with `freeze_panes = CONTENT_HUB_FREEZE_PANES` (**`"I3"`**, defined in `reporter/sheets/config.py`): banner row 1, headers row 2, data from row 3. `URL` and editorial columns scroll from column **I** onward. Applied via `set_freeze_panes_safe` inside `apply_content_hub_conditional_rules`. (Action Required literals: see the *Content hub — Action Required* section above.)
