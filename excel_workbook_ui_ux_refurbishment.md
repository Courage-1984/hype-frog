# Excel Workbook UI/UX Refurbishment — Phased Implementation Plan

**Status:** Planning (not yet implemented)  
**Scope:** `src/hype_frog/reporter/`, orchestration export builders, reporter tests  
**Objective:** Modernise visual design, information architecture, and UX of generated `.xlsx` audit reports.  
**Language:** UK spelling for all user-visible strings (*Optimisation*, *Colour*, *Categorisation*, etc.).

---

## Governance & constraints

| Rule | Implication |
|------|-------------|
| Reporter owns layout; pipeline owns data | No mutation of upstream row dicts; display aliases only in reporter |
| `docs/excel_reporting_standards.md` | Update in lockstep when behaviour/contracts change |
| `.cursor/rules/excel_engine.mdc` | Update Action Required, TOC, freeze, palette sections after each phase |
| 3-way sheet-name lock | `config.py` constants ↔ `workbook_layout.py` tab order ↔ `engine_guardrails._TOC_FRIENDLY_DESCRIPTIONS` |
| Workbook integrity | Use `set_freeze_panes_safe` + `sanitize_sheet_view_selection`; never raw freeze writes on data sheets |
| Tests before doc finalisation | `uv run pytest tests/reporter/` (+ `--quick-test` smoke after Phase 2+) |
| Git | User maintains commits; agent does not run git commands |

**Macro note:** openpyxl does not ship VBA macro shapes. Phase 2 “hide/unhide advanced tabs” must use **TOC hyperlinks + Dashboard navigation matrix + written instructions** (Home → Format → Hide & Unhide). Do not block delivery on embedded macros.

**Breaking rename:** `Dashboard` + `Executive Dashboard` → **`Executive Briefing`** breaks existing hyperlinks in saved workbooks. Treat as intentional; update every `#'Dashboard'!A1` target and `WORKBOOK_LANDING_SHEET`.

---

## Target design system (canonical constants)

Add to `reporter/sheets/config.py` (replace/alias existing RAG + brand constants; keep `HF_EXCEL_THEME=mocha` override path in `mocha_theme.py`).

### Headers

| Token | Hex | Usage |
|-------|-----|--------|
| `THEME_HEADER_BG` | `#222A35` | Table header fill (replaces `STD_NAVY` `2F3A4A` for data grids) |
| `THEME_HEADER_TEXT` | `#FFFFFF` | Header font |
| Header alignment | — | Text columns: left + wrap; numeric columns: right |

### Muted RAG (conditional formatting + static fills)

| Role | Fill | Font |
|------|------|------|
| Critical / Error | `#FCE8E6` | `#A51D24` |
| Warning / Needs attention | `#FEF3D6` | `#8F6B00` |
| Pass / Good | `#E6F4EA` | `#137333` |

Retain heatmap/data-bar tokens but desaturate where they duplicate RAG (document final hex in `config.py`).

### Tab colours (persona grouping)

| Persona | Hex | Sheets |
|---------|-----|--------|
| Management / Executive | `#7F8C8D` | Executive Briefing, Summary, Playbook, Table of Contents (optional) |
| Content teams | `#2ECC71` | Content Optimisation Hub, Content Planner, Content Hub Metrics |
| Technical SEO / Dev | `#417DC1` | Priority URLs, FixPlan, Quick Wins, SitemapQA, Template & Duplication Risks |
| Inventory / reference | `#95A5A6` | Main, Link Inventory, Broken Link Impact, AIOSEO Recommendations |
| Advanced (hidden) | `#BDC3C7` | All `ADVANCED_WORKBOOK_TAB_ORDER` tabs |
| Historical | `#D5D8DC` | Crawl Log, ResolvedIssues, DeltaFromPreviousRun, Audit Run Details |

Remove legacy primaries: `#4472C4`, `#70AD47`, `#ED7D31`, `#FFC000`, `#7030A0`.

### Large-sheet performance

| Token | Hex | Usage |
|-------|-----|--------|
| `GRID_BORDER` | `#E0E0E0` | Light borders on Link Inventory |
| `ZEBRA_FAINT` | `#FAFAFA` | Alternating rows when row count > 2,000 |

---

## Global vocabulary

```python
# reporter/sheets/config.py (proposed)
STATUS_OPTIONS: tuple[str, ...] = ("To Do", "In Progress", "In Review", "Done")
```

| Current surface | Migration |
|-----------------|-----------|
| FixPlan / IssueInventory `Open, In Progress, In Review, Done` | Already aligned |
| Content Hub `Completed` | Map display + DV to `Done`; CF rules accept both during transition |
| AIOSEO `Fixed` | → `Done` |
| Dashboard completion `COUNTIF(...,"Completed")` | → `"Done"` |
| Hub **Action Required** (`Complete`, `Needs Copy`) | **Unchanged** — editorial gate, not workflow Status |

---

## Navigation pattern (replaces trailing column)

**Remove:** `add_back_to_dashboard_link()` appending `BACK TO DASHBOARD` as last column (`navigation.py`).

**Add:** Row-1 return strip on every data sheet (exempt Executive Briefing itself):

```
A1: « Return to Executive Briefing   (HYPERLINK → #'Executive Briefing'!A1)
Style: italic, link blue, no extra column width
```

Content Optimisation Hub: merge return link into row-1 banner (see Phase 4).

Update: `workbook_audit.py`, `tests/reporter/test_main_sheet_navigation.py`, `test_phase2_info_travel.py`, `test_toc_sync.py`.

---

## Phase breakdown

### Phase 0 — Baseline & safety net (prerequisite)

**Goal:** Lock current behaviour in tests before visual churn.

| Task | Files |
|------|-------|
| Snapshot current tab order, landing sheet, freeze targets | `tests/reporter/test_workbook_layout.py` |
| Add regression test: Content Planner freeze = `E2` (not `E194`) | `tests/reporter/test_excel_engine.py` or new `test_view_state.py` |
| Add palette constant smoke test (imports resolve) | `tests/reporter/test_config_palette.py` (new) |

**Exit:** `uv run pytest tests/reporter/` green on main branch.

---

### Phase 1 — Universal theme & colour palette

**Goal:** Single design system; muted RAG; modern headers. No sheet renames yet.

| Task | Primary files |
|------|----------------|
| Add `THEME_*` + muted RAG constants; deprecate inline hex in CF | `sheets/config.py` |
| Mirror overrides | `mocha_theme.py` |
| Header fill/font/alignment in mock tables | `sheets/tables.py` (`apply_mock_table_styling`) |
| Replace RAG in global CF | `engine_formatting.py`, `sheets/conditional.py` |
| Dashboard static fills | `sheets/dashboard_config.py`, `sheets/dashboard.py` |
| Generic row semantic fills | `sheets/conditional.py` (`apply_generic_sheet_coloring`) |
| UK spelling in display aliases | `sheets/layout.py` (`DISPLAY_HEADER_ALIASES`) |
| Document palette table | `docs/excel_reporting_standards.md`, `.cursor/rules/excel_engine.mdc` |

**Exit:** Exported workbook headers use `#222A35`; CF samples use muted pastels; pytest green.

**Risk:** Large diff across `conditional.py` — do not change rule *logic*, only colours/fonts.

---

### Phase 2 — Dashboard consolidation & tab architecture

**Goal:** One landing tab **`Executive Briefing`**; persona tab colours; TOC alignment.

| Task | Primary files |
|------|----------------|
| Define `EXECUTIVE_BRIEFING_SHEET = "Executive Briefing"` | `sheets/config.py` |
| Merge writers: formula KPI block (`dashboard.py`) + visual cards/charts (`executive_dashboard.py`) into single builder | New `sheets/executive_briefing.py` or extend `executive_dashboard.py`; retire duplicate entry in `export_workbook.py` |
| Layout contract: rows 1–5 title + run metadata; 7–20 KPI cards; 22–40 owner table + nav matrix | `executive_briefing` module |
| Remove standalone `Dashboard` sheet from export (or keep as hidden legacy one release — **decision: remove**) | `orchestration/export_workbook.py` |
| Update tab order & colours | `sheets/workbook_layout.py` |
| Landing tab | `WORKBOOK_LANDING_SHEET`, `apply_workbook_active_tab` |
| TOC descriptions & sections | `engine_guardrails.py`, `sheets/toc.py` |
| Advanced tabs panel copy (hide/unhide instructions, high-contrast links) | Executive Briefing nav matrix |
| Retarget all hyperlinks `Dashboard` → `Executive Briefing` | `navigation.py`, `conditional.py` (Hub banner), `links.py`, tests |

**Exit:** Workbook opens on Executive Briefing; no separate Dashboard/Executive Dashboard tabs; TOC lists 34 tabs; `--quick-test` workbook audit passes.

**Risk:** Highest blast radius — coordinate with `workbook_audit.py` and `test_executive_dashboard.py`.

---

### Phase 3 — Data density, Main grouping, navigation strip

**Goal:** Main readable at open; no trailing nav column.

| Task | Primary files |
|------|----------------|
| Main: only cols A–K visible by default; collapse Metadata, Performance & CWV, Schema, E-E-A-T, OG, etc. | `sheets/layout.py` (`MAIN_COLUMN_GROUP_DEFINITIONS`, `apply_column_grouping`, `collapse_technical_deep_dive_columns`) |
| Verify outline levels survive export open in Excel desktop | Manual smoke + test if openpyxl exposes outline state |
| Remove `add_back_to_dashboard_link` last-column pattern | `sheets/navigation.py`, `tables_impl.py` |
| Add `add_return_to_briefing_strip()` row-1 helper | `sheets/navigation.py` |
| Strip `BACK TO DASHBOARD` from export column builders / row appenders | `orchestration/export_row_builders.py`, `engine_rows.py`, merged builders |
| Update preferred column orders (remove nav column) | `sheets/layout.py`, `merged_builders.py` |

**Exit:** Main opens with 11 visible triage columns; no sheet has trailing BACK TO DASHBOARD column; row-1 return link present.

---

### Phase 4 — Sheet-specific layout fixes

**Goal:** Hub header condensing; Content Planner freeze; large-sheet performance.

#### 4A — Content Optimisation Hub (2-row header)

| Task | Primary files |
|------|----------------|
| Remove row-3 scope-note merge; move scope copy to header comments | `sheets/conditional.py` (`apply_content_hub_conditional_rules`) |
| Row 1: merged banner + inline « Return to Executive Briefing | same |
| Row 2: headers only; data from row 3 | same; update `CONTENT_HUB_FREEZE_PANES` → `I3` |
| Adjust CF row offsets (currently data starts row 4) | `conditional.py`, `engine_rows.py` |
| AutoFilter header row | `engine_formatting.py` (`ensure_auto_filter`) |

#### 4B — Content Planner view state

| Task | Primary files |
|------|----------------|
| Root cause: exempt sheet never re-applies `E2` after `apply_mock_table_styling` may set `A2` | `sheets/tables.py`, `engine_guardrails.py` |
| **Fix:** After all formatting, `set_freeze_panes_safe(ws, "E2")` for Content Planner in `apply_workbook_export_guardrails` | `engine_guardrails.py` |
| Clear orphaned `sheetView.selection` if freeze was corrupted | `sheets/view_state.py` |
| Regression test freeze = `E2` | `tests/reporter/` |

#### 4C — Link Inventory & AIOSEO (2k+ rows)

| Task | Primary files |
|------|----------------|
| Skip multi-rule CF when `max_row > 2000` (status code + severity only) | `engine_formatting.py`, `conditional.py` |
| Enable faint zebra `#FAFAFA` for sheets > 500 rows (override current skip) | `sheets/tables.py` |
| Optional light grid borders | `sheets/tables_impl.py` or new `sheet_borders.py` helper |
| Document performance trade-off | `docs/excel_reporting_standards.md` |

**Exit:** Hub shows data from row 3; Planner freeze `E2`; Link Inventory opens without UI lock (manual Excel smoke).

---

### Phase 5 — Status vocabulary unification

**Goal:** One `STATUS_OPTIONS` list everywhere.

| Task | Primary files |
|------|----------------|
| Central `STATUS_OPTIONS` + `STATUS_DV_FORMULA` | `sheets/config.py` |
| Wire data validation | `sheets/validation.py`, `tables_impl.py` |
| CF expression updates (`Done` not `Completed`/`Fixed`) | `conditional.py`, `engine_formatting.py` |
| Dashboard `COUNTIF` for completion metrics | `sheets/dashboard.py` / Executive Briefing builder |
| Guardrail normalisation | `engine_guardrails.py` |
| Content Hub Status DV: `To Do, In Progress, In Review, Done` | `conditional.py` |
| Tests for DV strings + CF mapping | `tests/reporter/` |

**Exit:** No exported sheet offers `Completed` or `Fixed` in Status dropdowns; legacy values normalised on write.

---

## File touch matrix (summary)

| Module | Phases |
|--------|--------|
| `reporter/sheets/config.py` | 1, 2, 5 |
| `reporter/sheets/workbook_layout.py` | 2 |
| `reporter/sheets/conditional.py` | 1, 4, 5 |
| `reporter/engine_formatting.py` | 1, 4, 5 |
| `reporter/sheets/tables.py` | 1, 4 |
| `reporter/sheets/tables_impl.py` | 3, 4 |
| `reporter/sheets/layout.py` | 1, 3 |
| `reporter/sheets/navigation.py` | 2, 3 |
| `reporter/sheets/view_state.py` | 4 |
| `reporter/engine_guardrails.py` | 2, 4, 5 |
| `reporter/sheets/dashboard.py` | 1, 2 (merge → retire) |
| `reporter/sheets/executive_dashboard.py` | 2 (merge → retire) |
| `reporter/sheets/toc.py` | 2 |
| `reporter/workbook_audit.py` | 2, 3 |
| `orchestration/export_workbook.py` | 2 |
| `docs/excel_reporting_standards.md` | 1, 2, 4 |
| `.cursor/rules/excel_engine.mdc` | 1, 2, 5 |
| `tests/reporter/*` | All phases |

---

## Verification checklist (per phase)

```powershell
uv run pytest tests/reporter/
uv run pytest tests/reporter/test_workbook_layout.py tests/reporter/test_toc_sync.py -q
uv run hype-frog --quick-test   # after Phase 2+
```

Manual Excel desktop checks:

1. Open on **Executive Briefing**; KPI cards and nav matrix readable.
2. **Main:** only A–K visible; groups expand correctly.
3. **Content Optimisation Hub:** 2 header rows; freeze at `I3`; data row 3.
4. **Content Planner:** freeze `E2`; no scroll jump to row 194.
5. **Link Inventory:** scroll 11k rows without hang; faint zebra visible.
6. Status dropdown shows unified four options on FixPlan, Hub, AIOSEO.

---

## Suggested implementation order

```
Phase 0 → Phase 1 → Phase 5 (can parallel CF colour work with Phase 1)
         → Phase 3 (navigation + Main; independent of dashboard merge)
         → Phase 4 (Hub + Planner + performance)
         → Phase 2 last OR first after Phase 1 if landing experience is priority
```

**Recommendation:** Phase 1 → Phase 4B (quick freeze win) → Phase 3 → Phase 5 → Phase 4A/4C → **Phase 2** (dashboard merge is largest; do when palette and nav patterns are stable).

---

## Open decisions (confirm before Phase 2)

**Finalised (2026-06-29):**

1. **Dashboard migration:** Retire `Dashboard` from primary workflow; keep as **hidden alias for one release** while `Executive Briefing` becomes the landing tab.
2. **Executive Briefing layout:** Charts and KPI cards in **rows 7–20**; raw chart-feed tables at **row 60+**.
3. **AIOSEO tab colour:** **Technical persona** — Steel Blue `#417DC1`.
4. **Large-sheet zebra:** CF formula (`MOD(ROW(),2)`) on **all sheets > 500 rows** — no cell-by-cell static fills (Phase 4C).

---

*Generated for Cursor agent execution. Update this file when phases complete.*

### Phase completion log

| Phase | Status | Notes |
|-------|--------|-------|
| 0 | Done | `test_config_palette.py`, `test_view_state.py` |
| 1 | Done | Muted RAG, `#222A35` headers, persona tab colours, AIOSEO → technical |
| 4B | Done | `apply_bespoke_freeze_panes` post-pass; Content Planner `E2` |
| 3 | Pending | | 
| 5 | Pending | |
| 4A/4C | Pending | CF zebra for sheets > 500 rows |
| 2 | Pending | Executive Briefing merge |

---

*Earlier open questions (superseded by table above):*

1. ~~Retire `Dashboard` tab entirely~~ → hidden alias one release.
2. ~~Executive Briefing row map~~ → charts 7–20, data 60+.
3. ~~AIOSEO tab colour~~ → `#417DC1` technical.
4. ~~Zebra scope~~ → all sheets > 500 rows via CF only.

---

*Original plan body continues below.*
