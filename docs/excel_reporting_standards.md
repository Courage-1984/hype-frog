# Excel reporting standards

## Reporter module ownership

Excel reporting no longer relies on a single monolithic engine file. Responsibility is intentionally split across:

- `src/hype_frog/reporter/engine_guardrails.py` — invariant enforcement (Action Required normalization, TOC refresh, freeze policy, tooltip governance).
- `src/hype_frog/reporter/engine_formatting.py` — visual formatting and conditional format application.
- `src/hype_frog/reporter/engine_io.py` — workbook-safe I/O, sanitization helpers, and row writing bridges.
- `src/hype_frog/reporter/engine_rows.py` — report-row assembly and domain-specific row shaping.

`src/hype_frog/reporter/excel_engine.py` remains a compatibility facade/re-export layer, not a monolithic behaviour owner.

### Orchestration-layer workbook builders

Full workbook assembly and delta integration are coordinated from the orchestration layer (not the reporter layer) via:

- `src/hype_frog/orchestration/export_workbook.py` — `build_standard_sheets()` drives all 20+ tab builders (Main, Summary, Priority, FixPlan, Quick Wins, Content Optimisation Hub, Link Equity Map, Anchor Text Audit, Script Inventory, Image Inventory, Crawl Log, DeltaFromPreviousRun, etc.) and integrates `snapshot_from_current_run()` / `build_delta_workbook_output()` from the analysis layer.
- `src/hype_frog/orchestration/export_row_builders.py` — Sheet-specific row builders: `build_aeo_rows()`, `build_aioseo_rows()`, pattern rows, template risk rows.
- `src/hype_frog/orchestration/export_workbook_constants.py` — `PLAYBOOK_LEGEND_ROWS` and `PLAYBOOK_QUICK_REFERENCE_ROWS` constant tables.

These modules call into `reporter/` for formatting and write operations but own the sheet-assembly logic and data-selection decisions.

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

- The workbook **opens on Executive Briefing** (`apply_workbook_active_tab`, run last in
  `apply_workbook_export_guardrails`); the Table of Contents stays left-most at index 0.
- `apply_freeze_c2_data_sheets` is the **final freeze authority** for ordinary data
  sheets (normalised to `C3` — return strip row 1 + header row 2 above the data grid).
  Sheets with bespoke layouts are exempt via
  `FREEZE_C2_EXEMPT_SHEETS` (TOC `A3`, Content Optimisation Hub, Content Planner `E2`,
  Executive Briefing `A10` — pins the title/KPI/insights band above the
  non-overlapping chart grid; the four chart bands are spaced ~19 rows apart with
  the triage matrix and chart source tables stacked well below them).
- The legacy **Dashboard** tab is no longer exported; **Executive Briefing** is the sole executive landing tab.

### Tooltips and dropdowns

Header tooltips (Excel comments) are gated by **`HF_DISABLE_TOOLTIPS`** (the legacy
`HF_DISABLE_DATA_VALIDATION` still suppresses them for backward compatibility), while
status **dropdowns** remain gated by `HF_DISABLE_DATA_VALIDATION` only. Curated per-column
help bodies live in `_SHEET_CURATED_HEADER_HELP` (`reporter/sheets/validation.py`); semantic
Content Hub tooltips and merged-tab help are applied via `apply_curated_header_tooltips`
(delegated from `help_layer.py`). Schema-metadata tooltips remain in
`SCHEMA_METADATA_HEADER_TOOLTIP_BODIES`; Executive Briefing KPI blocks use `dashboard_config` and `executive_dashboard.py`.
A contract test keeps curated keys aligned with exported column headers.

### Advanced-sheet navigation

The Executive Briefing "Advanced Sheets" panel surfaces a **curated subset** of the advanced
tabs (relocated below the Owner Issue Summary at row 32+ to avoid column overlap); the
TOC's "Technical & Historical (Advanced)" section remains the complete index of every
advanced sheet (`ADVANCED_WORKBOOK_TAB_ORDER`). **Issue Register** is the canonical issue
backlog (Summary roll-ups plus per-URL rows); the legacy **IssueInventory** tab is no longer exported.

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
- **Executive Briefing** Owner Issue Summary, status/severity side panels, sprint
  roll-ups, and Top Issues blocks use live `COUNTIF`/`SUMIF`/`INDEX`/`MATCH`
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

A separate **Status** column (data-validation list `To Do, In Progress, Review, Completed`) tracks editorial workflow, distinct from Action Required.

## Conditional formatting & colour palette

**Single source of truth.** Status colours are defined once in `reporter/sheets/config.py`
as the canonical **RAG palette** (`RAG_RED` / `RAG_AMBER` / `RAG_GREEN` with matching
`*_FONT` colours, plus `RAG_RED_SOFT` / `RAG_AMBER_SOFT`, `RAG_NEUTRAL`, `ZEBRA_BAND`) and a
single Office heatmap scale (`HEATMAP_LOW`/`MID`/`HIGH`) and `DATA_BAR_BLUE`. Table headers use
`THEME_HEADER_BG` (`#222A35`) and `THEME_HEADER_TEXT` (`#FFFFFF`) with left-aligned text /
right-aligned numeric headers. Tab colours follow persona grouping in `workbook_layout.py`
— six genuinely distinct hues so the tab bar reads at a glance (Management `#2C3E50`, Content
`#27AE60`, Technical `#2980B9` including AIOSEO, Inventory `#E67E22`, Advanced `#8E44AD`,
Historical `#95A5A6` — grey reserved for archival tabs only). Prefer importing these constants over
inline hex literals. `dashboard_config` RAG names (`GOOD_COLOR`,
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

### Catppuccin Mocha theme (`HF_EXCEL_THEME=mocha`)

Hype Frog ships an optional **Catppuccin Mocha** palette — a dark, frog-pond-inspired take on the [official Catppuccin Mocha](https://github.com/catppuccin/catppuccin#mocha) accent set. The canonical implementation lives in `src/hype_frog/reporter/mocha_theme.py`; Excel constants are applied at import time in `reporter/sheets/config.py` when `HF_EXCEL_THEME=mocha`.

**Enable for workbooks** (add to `.env` before the crawl/export process starts — palette is resolved at module import):

```env
HF_EXCEL_THEME=mocha
```

**Default vs mocha — brand constants**

| Constant | Default | Mocha |
|----------|---------|-------|
| `THEME_HEADER_BG` / `STD_NAVY` | `222A35` | `1E1E2E` (base) |
| `THEME_HEADER_TEXT` / `STD_WHITE` | `FFFFFF` | `CDD6F4` (text) |
| `STD_BLUE` | `2F6FA3` | `74C7EC` (sapphire) |
| `STD_FROG_GREEN` | `92D050` | `A6E3A1` (Catppuccin green) |

**RAG fills (default theme, Phase 1 refurbishment)** — muted pastels with dark text:

| Constant | Hex | Role |
|----------|-----|------|
| `RAG_RED` / `RAG_RED_FONT` | `FCE8E6` / `A51D24` | Critical / fail |
| `RAG_AMBER` / `RAG_AMBER_FONT` | `FEF3D6` / `8F6B00` | Warning |
| `RAG_GREEN` / `RAG_GREEN_FONT` | `E6F4EA` / `137333` | Pass / good |
| `RAG_RED_SOFT` / `RAG_AMBER_SOFT` | `FFF0F0` / `FFFAED` | Softer severity striping |
| `RAG_NEUTRAL` | `45475A` | N/A / to-do |
| `ZEBRA_BAND` | `313244` | Alternating rows |

**Heatmaps (mocha):** `HEATMAP_LOW`=`F38BA8`, `HEATMAP_MID`=`F9E2AF`, `HEATMAP_HIGH`=`A6E3A1`, `DATA_BAR_BLUE`=`74C7EC`.

**Signature hype-frog green** under mocha is `#a6e3a1` (Catppuccin green), replacing the legacy Excel lime `#92D050`.

**Programmatic access:**

```python
from hype_frog.reporter.mocha_theme import MOCHA, SEMANTIC, excel_palette_overrides

print(SEMANTIC.frog_green)  # #a6e3a1
print(MOCHA.base)             # #1e1e2e
```

Regression guards: `tests/reporter/test_mocha_theme.py`.

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

## Return navigation (Phase 3)

Standard data sheets insert a row-1 strip: **`← Return to Executive Briefing`**
(blue italic hyperlink to `Executive Briefing`!A1). The legacy trailing **BACK TO DASHBOARD**
column is removed. The banner merge spans the sheet's **real columns only** (capped at
column H); it must **not** force a minimum width, otherwise narrow sheets (e.g. the empty
3-column FixPlan) gain a phantom `Column_N` header via `normalize_table_headers`. Content
Optimisation Hub embeds the same return link in its row-1 banner.

## Duplicate column prevention

`navigation.add_return_to_briefing_strip` is idempotent (skips when row 1 already
carries the return label) and deletes a trailing legacy **BACK TO DASHBOARD** column
when present before inserting the strip.

## Column widths, wrap policy, and empty states

- **`layout.apply_column_widths` resolves the true header row** via
  `sheet_data_header_row(worksheet.title)` (data sheets carry a row-1 banner, so
  headers live on row 2) and **always assigns a concrete width** — the previous
  routine computed a max length but never wrote `column_dimensions[...].width`.
- **Per-header width contract:** `URL_LIKE_HEADERS` (URL, Final URL, Canonical URL,
  Direct Edit Link, …) get a fixed single-line width (`45`); `PROSE_HEADERS`
  (Affected URLs, How to Fix in AIOSEO, Why It Matters, Recommended Fix, …) get a
  generous wrapped width (`55`); everything else auto-fits from non-formula content
  clamped to `[10, 42]` (capped below the un-clamped auto-fit so ordinary columns
  don't force horizontal scrolling at the `SHEET_ZOOM_OVERRIDES` levels below on a
  laptop-sized display). Formula strings never drive auto-fit.
- **Wrap policy:** URL / hyperlink / short-scalar cells stay **single-line**
  (`wrap_text=False`); only prose columns wrap. `conditional.apply_wrapped_row_heights`
  inflates row heights **only** for prose columns and skips URL-type columns so URLs
  never stack into tall thin strips. Header rows get a min height (`30`) so wrapped
  two-line labels are never clipped.
- **AIOSEO `Direct Edit Link`** renders as a clean blue hyperlink (no dark button
  fill) — a dark fill combined with the blue link font re-applied by
  `apply_editor_url_column_hyperlinks` previously produced unreadable dark-on-dark.
- **Empty-state messaging:** FixPlan and Quick Wins with no data rows show a single
  merged, muted italic **"No items to report for this run."** message under the
  headers instead of a bare grid (`tables_impl._write_empty_state_message`).
- **Content Hub Metrics headers stay intact:** the former write-time `A2:…2` merge
  clobbered the metrics header/first-data row (B–K); it has been removed so all
  metric headers and data survive the formatting pass.

## Quick Wins / FixPlan — linked issue descriptions and Playbook jump links

Both **Quick Wins** and **FixPlan** carry a **"What It Is"** column (the rule's
short root-cause/description text) and a **"Jump to Playbook"** HYPERLINK/MATCH
formula column, both sourced from a single `build_playbook_entry_index(summary_rules)`
call (`rules/playbook_entries.py`) built once in `export_workbook.py` and passed
into both `engine_rows.build_fixplan_rows()` and `merged_builders.build_quick_wins_rows()`
— avoids recomputing the per-rule entry twice. The **"Playbook"** worksheet itself is
flattened to 4 columns (`Section, Item, Guideline, Why It Matters`) where `Item`
(column B) holds the rule name — `"Playbook"` is intentionally absent from
`_PREFERRED_COLUMN_ORDERS`, so column B stays stable and is safe to `MATCH()` against.

**Column-position contract:** `_PREFERRED_COLUMN_ORDERS["FixPlan"]` (`layout.py`) must
keep `"Issue Type"` at index 0, since both Quick Wins' `"Jump to FixPlan"` and
FixPlan's own `"Jump to Playbook"` HYPERLINK formulas assume `Issue Type` lands in
worksheet column A after `reorder_columns()` runs. (This was previously violated —
see fix below.)

**Bug fixed:** Quick Wins' `"Jump to FixPlan"` formula previously matched against
`'FixPlan'!B:B`, which held `Severity` post-reorder, not `Issue Type` — every link
silently fell through to the `IFERROR` fallback (`FixPlan!A1`) instead of the
correct row. It now matches against `'FixPlan'!A:A`.

## SitemapQA — image/changefreq/priority columns

Per sitemap-URL rows on **SitemapQA** (`export_registry.build_sitemapqa_rows`)
carry `Sitemap <lastmod>` / `Sitemap <changefreq>` / `Sitemap <priority>` /
`Sitemap Image Count` / `Sitemap First Image`, computed directly from
`sitemap_meta` (see `docs/data_contracts.md` — Sitemap metadata). `Sitemap First
Image` is in `URL_LIKE_HEADERS` (`layout.py`) so it renders as a fixed-width,
single-line hyperlink-style cell rather than wrapping.

## Autofilter coverage

Actionable workflow sheets in ``AUTO_FILTER_SHEETS`` (``config.py``) always receive
header autofilter during final formatting — including sparse FixPlan / Quick Wins
exports with only a handful of rows. Link Inventory and Content Planner retain
their existing bespoke filter rules.

## Empty-state messaging

FixPlan and Quick Wins write a green-tinted guidance row when the data grid is
blank, pointing readers to Summary / Issue Register rather than implying a broken
export.

## Workbook presentation defaults

Late in ``apply_workbook_toc_and_links`` (``toc.py``): gridlines are disabled on
every tab; ``SHEET_ZOOM_OVERRIDES`` applies a tiered per-sheet zoom so the workbook
is readable on a laptop-sized display without manual resizing — 85% for the two
densest card/triage layouts (Executive Briefing, Main), 90% for essentially every
other operational/data tab, and Excel's default 100% only for the simple/small
pages (Table of Contents, Audit Run Details). All standard data sheets receive CF-based zebra
banding via ``apply_cf_zebra_banding`` (sort/filter-safe); large inventory sheets
(>500 rows) also get a light header grid via ``large_sheet_presentation.py``.

``ensure_print_setup`` (``engine_formatting.py``, called from ``tables_impl.py``
during per-sheet formatting) applies a fit-to-width landscape print layout and an
explicit print area to every sheet, so printing the 217-column Main sheet doesn't
spool dozens of near-blank pages under Excel's default pagination.

``apply_main_column_group_header_tints`` (``layout.py``, called for the Main
sheet only, after the mock-table header styling pass so it isn't overwritten)
tints the header cells of each hidden column-outline group (CWV/Lighthouse,
H-tag content, GSC, schema, E-E-A-T/trust, OpenGraph/Twitter, redirect/canonical,
GSC-index, robots-per-bot) with a distinct pastel + dark-navy text, so a user who
expands the outline sees visible group boundaries instead of a uniform wall of
navy header cells.

## Return strip run metadata

Row 1 on data sheets with a return strip splits ``A1:B1`` (hyperlink back to
Executive Briefing) from ``C1:H1`` (formula subtitle pulling Target Site, URL
count, and audit date from **Audit Run Details**). Applied in
``apply_return_strip_run_metadata`` during export guardrails.

## Issue Register scope branching

`summary_builder.py` treats `IssueRule.scope` values:

- **`url`** — per-URL rows merged into **Issue Register** (Section `Issue Inventory`).
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
- Branding (`brand_colour`, `prepared_by`, `client_name`, `theme`) resolves once in `export_flow`, preferring `HF_REPORT_*` then `HF_PDF_*`, then theme-aware defaults (see *Catppuccin Mocha HTML theme* below).
- `ReportContext.quick_wins` is an additive projection of the Quick Wins sheet rows (`name`, `effort_hours`, `owner`).

### Catppuccin Mocha HTML theme (`HF_REPORT_THEME=mocha`)

When `HF_REPORT_THEME=mocha`, the HTML executive report switches from the default light layout to a **dark Catppuccin Mocha** surface with hype-frog semantic colours. Implementation: `reporter/mocha_theme.py` (palette + CSS helpers) and `html_report_renderer.py` (injects theme CSS and font links).

**Enable** (requires `HF_EXPORT_HTML=1`):

```env
HF_EXPORT_HTML=1
HF_REPORT_THEME=mocha

# Optional overrides (mocha defaults shown)
# HF_REPORT_BRAND_COLOUR=#1e1e2e
# HF_REPORT_ACCENT_COLOUR=#94e2d5
```

**Default theme behaviour:** all CSS is inline; no external network requests. **Mocha theme exception:** loads **JetBrains Mono** from Google Fonts CDN for body and monospace URL cells:

```
https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap
```

JetBrains Mono **Nerd Font** is not used in HTML output (Google Fonts does not ship Nerd patches). For terminals/IDEs, see `JETBRAINS_MONO_NERD_CDN` in `mocha_theme.py`.

**Mocha semantic colours (HTML)**

| Role | Hex | Catppuccin source |
|------|-----|-------------------|
| Page background | `#11111b` | crust |
| Panel / card | `#181825` / `#1e1e2e` | mantle / base |
| Body text | `#cdd6f4` | text |
| Muted text | `#a6adc8` | subtext0 |
| Brand / table headers | `#1e1e2e` | base |
| Accent / CTAs | `#94e2d5` | teal |
| H1 / KPI values (frog green) | `#a6e3a1` | green |
| Critical | `#f38ba8` | red |
| Warning | `#f9e2af` | yellow |
| Good | `#a6e3a1` | green |
| Observation | `#89b4fa` | blue |

Explicit `HF_REPORT_BRAND_COLOUR` / `HF_REPORT_ACCENT_COLOUR` override mocha defaults. Legacy light-theme defaults (`#1e293b`, `#2563eb`) are treated as unset when mocha is active so the palette applies without manual hex editing.

**Combine HTML + Excel mocha:**

```env
HF_EXPORT_HTML=1
HF_REPORT_THEME=mocha
HF_EXCEL_THEME=mocha
```

Presentation conventions shared by both deliverables:
- **Two severity views, clearly distinguished.** The "Pages by Worst Severity" tally counts each page once by its highest-severity issue (with a visible page total); "Top Issues by Impact" counts pages affected by each individual issue (a page may appear under several). Captions in the HTML report make the distinction explicit.
- **Feature parity.** Both the HTML report and the PDF surface the same shared facts: KPIs, Mobile PSI, projected SEO health, Search Console summary, top issues, quick wins, and the sprint/resource plan.
- **RAG is never colour-only.** Status is also conveyed textually (PDF status words + legend; HTML severity counts/totals and numeric cell values) for accessibility and greyscale printing.

Regression guards (`tests/reporter/test_executive_report_parity.py`) lock these invariants in: both deliverables build from a single `ReportContext` (top-issue counts cannot diverge), quick-win effort is always numeric, the severity tally reconciles to the page total, and the PDF audit date comes from the crawl timestamp. The `--full-smoke-test` fixtures (`diagnostics/full_smoke_fixtures.py`) are deterministically enriched to produce a *representative* audit (varied SEO health, AEO readiness, a realistic severity mix, and a populated HTTP status table) rather than an all-missing baseline, so the smoke artefacts exercise the real scoring and reporting paths.

## Content hub — freeze panes

The Hub freezes through column **H** with `freeze_panes = CONTENT_HUB_FREEZE_PANES` (**`"I3"`**, defined in `reporter/sheets/config.py`): banner row 1, headers row 2, data from row 3. `URL` and editorial columns scroll from column **I** onward. Applied via `set_freeze_panes_safe` inside `apply_content_hub_conditional_rules`. (Action Required literals: see the *Content hub — Action Required* section above.)
