# Workbook (.xlsx) UI/UX Improvement Plan

> Scope: the multi-sheet Excel deliverable built under `src/hype_frog/reporter/`.
> Goal: **validate → check → optimise → add** across three areas — (1) conditional
> formatting & colours, (2) "Info & Travel" (tooltips, hyperlinks, TOC, tab order,
> visibility), (3) polish (formulas, de-duplication/consolidation, glaring gaps).
>
> **Status:** Phase 1 ✅ done · Phase 2 ✅ done · Phase 3 ⏳ pending. Implementing phase by phase.
>
> **Governance reminders:** `.cursorrules` §4 — diffs spanning **>3 files** need explicit
> approval (most tasks below do; each task lists its blast radius). §6 — workbook integrity
> and client-safe XML are non-negotiable. §8 — British English in user-facing copy. §11 —
> **no git commands** (the user owns repo state). `auto_documentation.mdc` — run `uv run pytest`
> before marking anything done, and sync `docs/excel_reporting_standards.md`.

---

## 0. How the workbook is assembled (orientation)

Finalisation order (per `orchestration/export_flow.py:924-937`):

1. `apply_tab_hyperlinks` (external URL columns) — `export_registry.py:256-257`
2. `apply_workbook_toc_and_links` — builds TOC, reorders tabs, sets visibility, cross-sheet links (`sheets/toc.py:38-257`)
3. `format_sheets` → `adjust_sheet_format` per sheet — CF, colours, tooltips, nav links, number formats (`sheets/tables_impl.py:297-427`)
4. `apply_workbook_export_guardrails` — Action-Required normalisation, freeze policy, dynamic TOC refresh (`engine_guardrails.py:375-382`)
5. `workbook_audit.audit_workbook` — read-only post-write validation (`workbook_audit.py:103-119`)

CF entry points (`tables_impl.adjust_sheet_format`):

```
├─ apply_generic_sheet_coloring → apply_global_conditional_formatting   (most sheets)
├─ apply_main_sheet_heatmaps                                            (Main)
├─ apply_fixplan_workflow_formatting                                    (FixPlan, direct fill)
├─ apply_content_hub_conditional_rules + apply_executive_priority_...   (Content Optimisation Hub)
├─ apply_executive_priority_formatting                                  (Content Hub Metrics)
├─ apply_psi_conditional_rules                                          (PSI Performance, if present)
├─ apply_merged_tabs_conditional_formatting                            (8 merged tabs)
└─ style_dashboard → B20 CF + apply_dashboard_metric_conditional_rules  (Dashboard)
```

Primary modules: `sheets/conditional.py`, `engine_formatting.py`, `sheets/config.py`,
`sheets/dashboard_config.py`, `sheets/workbook_layout.py`, `sheets/toc.py`,
`engine_guardrails.py`, `sheets/validation.py`, `help_layer.py`, `sheets/links.py`,
`sheets/number_formats.py`, `engine_rows.py`, `sheets/merged_builders.py`, `sheets/layout.py`.

---

## 1. Phase 1 — Conditional formatting & colours

### 1.1 Current state (validated)

- CF is defined in **three** places: `conditional.py` (lines 366–1389), `engine_formatting.py`
  (104–492), and one inline rule in `dashboard.py:1016-1025`. No `IconSetRule` anywhere.
- Header-driven global CF (`apply_global_conditional_formatting`, `engine_formatting.py:104-390`)
  runs on every data sheet and colours `Status Code`, load time, `Word Count`, `Priority Score`,
  `SEO Health Score`, `AEO Readiness Score`, `Desktop/Mobile Score`, `Mobile LCP`,
  `Paragraphs 40-60 Words Count`, `Action Needed`, `Severity Badge`, `Status`.
- Main gets an extra heatmap pass (`conditional.py:1091-1310`); the Hub, Content Hub Metrics,
  PSI Performance, and the 8 merged tabs each get bespoke passes.
- Palettes exist in `config.py:5-8` (brand), `dashboard_config.py:5-13` (RAG), and
  `workbook_layout.py:25-34/117-146` (tab colours).

### 1.2 Defects / gaps (validated, with citations)

| ID | Severity | Finding | Citation |
|---|---|---|---|
| **C1** | High | `HF_DISABLE_CONDITIONAL_FORMATTING` is only partly honoured: `apply_global_conditional_formatting`, `apply_executive_priority_formatting`, the Dashboard `B20` rule, OG Image Health CF, and **all** imperative cell fills ignore the flag. | `engine_formatting.py:104,422`; `dashboard.py:1016-1025`; `conditional.py:631-645,153-364` |
| **C2** | High | The flag is **undocumented** in `.env.example`. | (grep: absent) |
| **C3** | Med | **No single source of truth for RAG.** ≥4 parallel palettes with near-duplicate hex: reds `FFC7CE/F4CCCC/FFC1C1/FF0000/C00000/F8696B`; greens `C6EFCE/D9EAD3/63BE7B/00FF00/1F7A1F`; ambers `FFEB9C/FFF2CC/FFCC99/FFC000/FFEB84`. | `dashboard_config.py:9-12`; `conditional.py:163-167,436,515,548,1115`; `engine_formatting.py:120,136,407` |
| **C4** | Med | **Same metric coloured differently across sheets** (SEO Health Score: 3 distinct scales; Mobile LCP: 3 variants; Word-count data bar: `638EC6` vs `4472C4`). Clients perceive inconsistency. | `engine_formatting.py:212-220`; `conditional.py:1112-1136,855-872,1138-1153,1178-1187` |
| **C5** | Med | **Stacked/duplicate rules** on Main (`SEO Health Score`, `AEO Readiness Score`, `Status Code`, `Word Count (Body)`, `Severity Badge` get both global + Main rules); Dashboard `B20` rule defined twice. | `conditional.py:1112-1310` vs `engine_formatting.py:207-237`; `dashboard.py:1016-1025` + `conditional.py:1380-1389` |
| **C6** | Med | **Harsh primaries** on Hub (`FF0000`/`00FF00`) vs muted Excel traffic-light tones elsewhere — poor greyscale / colour-blind behaviour. | `conditional.py:515,548` vs `dashboard_config.py:9-11` |
| **C7** | Low | **CF gaps**: Main `Technical Health`, Summary aggregates, Priority URLs `Severity Badge`/`SEO Health Score`, SitemapQA pass/fail, AIOSEO `Status` dropdown, FixPlan `Severity`, and Executive Dashboard KPI cards have no (or only generic) CF. | `tables_impl.py:281-294,299-301`; `layout.py:145-146`; `conditional.py:306-330` |
| **C8** | Low | **Tab-colour gaps**: Link Equity Map, Anchor Text Audit, Snippet Opportunities, Script Inventory, Image Inventory, Competitor Benchmarks (+ legacy PSI/Technical/AEO) get default grey. | `workbook_layout.py:117-146` vs `export_registry.py:211-216` |
| **C9** | Low | Executive Dashboard re-implements section fills inline rather than importing the shared palette. | `executive_dashboard.py:27-30` |

### 1.3 Plan (check / validate / optimise / add)

> **Status:** Phase 1 ✅ **done** (all of P1.1–P1.8). Reporter + full suite green; `ruff` clean on
> touched files (only pre-existing F841s remain elsewhere); regenerated smoke workbook audits
> **PASS** with no harsh `FF0000`/`00FF00` CF fills and advanced inventory tabs coloured.

- [x] **P1.1 (C1/C2)** `HF_DISABLE_CONDITIONAL_FORMATTING` is now honoured **inside** each
      rule-adding helper (`apply_global_conditional_formatting`, `apply_executive_priority_formatting`,
      `apply_main_sheet_heatmaps`, dashboard metric rules, Content Hub passes, PSI/merged passes, OG
      Image Health) so it works regardless of caller. The duplicate inline Dashboard `B20` rule was
      removed (it is owned by `apply_dashboard_metric_conditional_rules`). Static semantic cell fills
      are documented as **layout, not CF** (intentionally unaffected). Added a **Workbook rendering
      toggles** block to `.env.example` documenting this flag and its siblings.
- [x] **P1.2 (C3)** Added the canonical **RAG palette** to `sheets/config.py` (`RAG_RED/AMBER/GREEN`
      + `*_FONT`, `RAG_RED_SOFT`/`RAG_AMBER_SOFT`, `RAG_NEUTRAL`, `ZEBRA_BAND`, `HEATMAP_LOW/MID/HIGH`,
      `DATA_BAR_BLUE`). `dashboard_config` RAG names are now thin aliases of these. Routed scattered
      inline hex in `conditional.py` / `engine_formatting.py` to the constants.
- [x] **P1.3 (C4/C5)** Standardised the word-count data bar to `DATA_BAR_BLUE` (was `4472C4` on Main
      vs `638EC6` elsewhere); unified the Dashboard completion colour scales (B5:B7/B17/B22 all use
      the heatmap triple; `00B050` → `HEATMAP_HIGH`); removed the duplicate `B20` rule; and the global
      pass now takes `skip_headers` so Main's heatmap-owned columns (`Status Code`, `SEO Health
      Score`, `AEO Readiness Score`, `Word Count (Body)`, `Severity Badge`) are no longer double-CF'd.
- [x] **P1.4 (C6)** Hub Action Required CF + the `engine_guardrails` direct fills now use canonical
      RAG (`Needs Copy`→`RAG_RED`/`RAG_RED_FONT`, `Needs Optimisation`→`RAG_AMBER`, `Complete`/`Ready
      to Publish`→`RAG_GREEN`); harsh `FF0000`/`00FF00` removed. Literals unchanged. Updated the
      guardrails colour assertion in `test_excel_engine.py` accordingly.
- [x] **P1.5 (C7)** Generalised the global severity rule to match the plain `Severity` header (covers
      FixPlan) as well as `Severity Badge`, and routed Action Needed / Severity / Status fills to the
      RAG palette. Priority URLs `Severity Badge`/`SEO Health Score` and AIOSEO `Status` were already
      covered by the global pass.
- [x] **P1.6 (C8)** Added `TAB_COLOR_ADVANCED` entries for Link Equity Map, Anchor Text Audit,
      Snippet Opportunities, Competitor Benchmarks, Script Inventory, Image Inventory.
- [x] **P1.7 (C9)** Executive Dashboard section fills now import the shared dashboard palette
      (`VALUE_BLOCK_COLOR`/`LIGHT_HEADER_COLOR`/`PANEL_BG_COLOR`). Saturated chart-slice colours kept
      (distinct context).
- [x] **P1.8 (validation)** Added `tests/reporter/test_conditional_palette.py` (flag disables CF;
      `skip_headers` suppresses owned columns; dashboard RAG aliases == canonical) and extended
      `test_workbook_layout.py` (every ordered tab + the 6 advanced inventory sheets have tab colours).

---

## 2. Phase 2 — Info & Travel (tooltips, hyperlinks, TOC, tab order, visibility)

### 2.1 Current state (validated)

- **TOC** is rebuilt from `VISIBLE_WORKBOOK_TAB_ORDER` + `ADVANCED_WORKBOOK_TAB_ORDER`
  (`toc.py:88-128`), each row a `=HYPERLINK("#'sheet'!A1", …)` with a curated description from
  `engine_guardrails._TOC_FRIENDLY_DESCRIPTIONS` (`engine_guardrails.py:26-141`). Missing sheets
  are skipped; a post-export audit enforces TOC ↔ tab alignment (`workbook_audit.py:103-119`).
- **Tab order/visibility** has a single source of truth (`workbook_layout.py:37-85`): 16 visible
  sheets, 19 advanced sheets hidden by default; TOC forced to index 0. No `veryHidden`.
- **Hyperlinks**: BACK TO DASHBOARD on standard sheets (`navigation.py:25-46`), rich Dashboard
  KPI/quick-nav/advanced-panel links (`dashboard.py:269-957`), and cross-sheet URL nav in
  `links.py`. Internal targets quote-escaped via `excel_sheet_link_target()`.
- **Tooltips**: almost entirely Excel **cell comments**, spread across 6+ registries
  (`validation.py`, `engine_guardrails.py`, `help_layer.py`, `layout.py`, `tables_impl.py`,
  `dashboard_config.py`).

### 2.2 Defects / gaps (validated, with citations)

| ID | Severity | Finding | Citation |
|---|---|---|---|
| **T1** | High | **`refresh_toc_descriptions_dynamic` silently no-ops in production**: it reads column A as plain sheet names, but production TOC stores HYPERLINK **formulas**, so every row is skipped. Descriptions only ever come from the initial append. (Unit test uses plain-text A, masking the bug.) | `engine_guardrails.py:341-350`; `toc.py:77-78`; `tests/reporter/test_excel_engine.py:195-198` |
| **T2** | Med | **Missing curated TOC blurbs** → generic "Diagnostic metrics for …": Broken Link Impact, Link Equity Map, Anchor Text Audit, Snippet Opportunities, Script Inventory, Image Inventory. | `workbook_layout.py:57-77`; `engine_guardrails.py:136-141` |
| **T3** | Low | **Legacy TOC blurbs** retained for retired split tabs (Technical, AEO, Content, Links, PSI Performance, Glossary…). | `engine_guardrails.py:46-93` vs `export_registry.py:185-220` |
| **T4** | Med | **Workbook opens on TOC**, not Dashboard/Executive Dashboard — no `activeTab`/`wb.active`. Decide intended landing tab. | `workbook_audit.py:83-84` (no `activeTab` in reporter) |
| **T5** | Med | **Executive Dashboard is a navigation dead-end**: early return means no BACK TO DASHBOARD, no TOC link, no tooltips, no CF. | `tables_impl.py:299-301` |
| **T6** | Med | **6 advanced tabs reachable via TOC but absent from the Dashboard "Advanced Sheets" panel** (Link Equity Map, Anchor Text Audit, Snippet Opportunities, Competitor Benchmarks, Script Inventory, Image Inventory). | `workbook_layout.py:101-115` vs `57-77` |
| **T7** | Med | **Freeze-policy conflict**: late `apply_freeze_c2_data_sheets` forces `C2` on most sheets, possibly overriding per-sheet freezes set earlier. Confirm intended precedence. | `engine_guardrails.py:358-372`; `view_state.py`; `toc.py:176-257` |
| **T8** | Med | **Tooltips fragmented** across 6+ registries with overwrite ordering on the Hub (`apply_header_tooltips` overwrites row-2 comments). No unified registry. | `tables_impl.py:336-420`; `conditional.py:694-698` |
| **T9** | Med | **Tooltips gated by the wrong flag** (`HF_DISABLE_DATA_VALIDATION` kills all generic header comments). Misleading; should be a dedicated tooltip flag. | `validation.py:393-394` |
| **T10** | Low | **Weak/missing curated help** on important sheets: FixPlan workflow columns, Quick Wins, Broken Link Impact, SitemapQA, Link Inventory, Issue Register history, Template & Duplication Risks. | `tables_impl.py:358-405`; `validation.py:274-381` |
| **T11** | Low | **INDIRECT reference-tab link** can break on special sheet names. | `links.py:257` |
| **T12** | Low | Docs drift: `excel_reporting_standards.md` says TOC descriptions live in `toc.py`; canonical map is in `engine_guardrails.py`. | `docs/excel_reporting_standards.md:39-45` |

### 2.3 Plan (check / validate / optimise / add)

- [x] **P2.1 (T1)** Fixed `refresh_toc_descriptions_dynamic`: a new
      `_toc_sheet_name_from_cell_value` resolves the sheet from the HYPERLINK **target**
      (`#'Sheet'!A1`, unescaping `''`→`'`), with a display-text fallback and a plain-name path.
      The masking test now seeds the production HYPERLINK formula, plus a new quoted-name test.
      _Verified: smoke workbook shows **0 generic TOC blurbs** (refresh now actually runs)._
- [x] **P2.2 (T2/T3)** Added curated blurbs for the 5 inventory sheets (Link Equity Map, Anchor
      Text Audit, Snippet Opportunities, Script Inventory, Image Inventory; Broken Link Impact
      already had one). **Decision:** retained inert legacy keys (e.g. `Technical`) — they only
      apply when a sheet of that name exists, a passing test depends on `Technical`, and
      `.cursorrules §4` discourages deleting legacy material for no functional gain.
- [x] **P2.3 (T4)** `apply_workbook_active_tab` opens the workbook on **Dashboard** (TOC stays
      index 0); invoked last in `apply_workbook_export_guardrails` so nothing overrides it.
      _Verified: smoke workbook `wb.active == "Dashboard"`, `sheetnames[0] == "Table of Contents"`._
- [x] **P2.4 (T5)** Executive Dashboard now carries `BACK TO DASHBOARD` / `BACK TO CONTENTS`
      links (column N, frozen header rows) + curated KPI-card tooltips. `tables_impl` keeps its
      early-return; the links live in the exec-dashboard builder which owns its layout.
- [~] **P2.5 (T6)** **Documented intentional subset** rather than expand the panel: the
      Dashboard "Advanced Sheets" panel and the Owner Issue Summary already share columns I–K
      (a **pre-existing layout overlap**, logged for Phase 3 follow-up), so growing the panel was
      not a clean win. The TOC advanced section remains the complete index. Documented in
      `excel_reporting_standards.md`.
- [x] **P2.6 (T7)** **Confirmed precedence** (no behaviour change): `apply_freeze_c2_data_sheets`
      is the final freeze authority for data sheets; exemptions are now a named constant
      `FREEZE_C2_EXEMPT_SHEETS` (TOC, Hub, Executive Dashboard) with a docstring + regression test.
- [x] **P2.7 (T9)** Added dedicated **`HF_DISABLE_TOOLTIPS`** flag gating header comments
      (`_DISABLE_TOOLTIP_COMMENTS = HF_DISABLE_TOOLTIPS or HF_DISABLE_DATA_VALIDATION`); dropdowns
      stay on `HF_DISABLE_DATA_VALIDATION`. Documented both in `.env.example`. **Deferred:** full
      T8 multi-registry consolidation (large >3-file refactor) — logged for a later pass.
- [x] **P2.8 (T10)** Added curated help bodies for FixPlan, Quick Wins, Broken Link Impact, Link
      Inventory and SitemapQA key columns (`_SHEET_CURATED_HEADER_HELP`); the contract test now
      validates these keys against the authoritative export column sources.
- [x] **P2.9 (T11)** Extracted `_reference_tab_jump_formula`: wraps the runtime sheet name in
      single quotes for **both** HYPERLINK and INDIRECT and `SUBSTITUTE`-escapes apostrophes;
      added a unit test for spaced/quoted names.
- [x] **P2.10 (T12)** Synced `docs/excel_reporting_standards.md` to the real TOC-description
      source (`engine_guardrails._TOC_FRIENDLY_DESCRIPTIONS`) plus landing-tab, freeze precedence,
      tooltip-flag, and advanced-subset notes.
- [x] **P2.11 (validation)** New `tests/reporter/test_phase2_info_travel.py` (TOC blurbs
      non-generic, active tab = Dashboard, ref-tab escaping, tooltip flag, freeze precedence) +
      updated help-layer contract test. Full `uv run pytest` green; smoke workbook regenerated and
      inspected; `ruff` clean on all edited files (2 pre-existing F841s in `executive_dashboard.py`
      left untouched).

---

## 3. Phase 3 — Polish (formulas, de-dupe/consolidate, glaring gaps)

### 3.1 Current state (validated)

- Live formulas are concentrated on **Content Optimisation Hub** (Action Required, On-Page
  Optimization Score, Title/Meta/Hn Health, HYPERLINK nav), **Main** (`Technical Health` VLOOKUP),
  **Dashboard** (KPI block `B5:B24` mostly formula-driven), **Link Intelligence** (SUMPRODUCT
  broken-link counts), and **TOC** (HYPERLINK rows). Inventory cited in detail by the analysis.
- Column-order sources: `layout.py`, `merged_builders.py`, `engine_rows.py`,
  `export_registry.py`. Pipeline rows are **append-only**, so consolidation must happen at the
  **reporter display layer**, never by renaming/removing row keys.
- Number formatting is a small allowlist (`number_formats.py:12-62`); many numeric columns render
  raw floats.

### 3.2 Defects / gaps (validated, with citations)

| ID | Severity | Finding | Citation |
|---|---|---|---|
| **F1** | **High (bug)** | **FixPlan → "Hub Status" formula joins on the wrong column**: it `MATCH`es on `'Content Optimisation Hub'!F:F` and returns `C:C`, but after reorder Hub URL is column **I** and Status is **F** → it matches Status text as if it were URLs and returns SEO Score. Should INDEX Status (F) / MATCH URL (I). Dashboard B17 already uses F for Status. | `links.py:296-316`; cf. `dashboard.py:57-69` |
| **F2** | Med | **Hardcoded column refs** risk `#REF!` on reorder: Main `Technical Health` VLOOKUP `$A:$E,5`; Dashboard B21 `'Link Intelligence'!$O:$O`/`$B:$B`; Link Inventory SUMPRODUCT cols E/F capped at row 50,000. | `tables_impl.py:281-294`; `dashboard.py:359`; `broken_links.py:88-90` |
| **F3** | Low | `_xlfn.IMAGE` may show `#NAME?` on older Excel; needs a graceful fallback. | `conditional.py:670` |
| **F4** | Low | `COUNTIFS(... "Needs Work")` legacy severity label may under-count if pipeline emits only `Warning`. | `dashboard.py:304` |
| **F5** | Low | Dashboard **side panels** (D5:E14 status/severity counts, M5:N8, owner table H24:K31, top-issue counts) are **static Python values** where `COUNTIF(S)` would stay live. | `dashboard.py:675-722,765-768,899` |
| **D1** | Med | **Issue roll-up duplication**: both **IssueInventory** and **Issue Register** ship the same issues (Register is the superset with history). Clients can't tell which is canonical. | `export_flow.py:312-322`; `merged_builders.py:563-570` |
| **D2** | Med | **Wide PSI/CWV duplication**: full performance block on Main (mostly hidden in column groups) **and** Technical Diagnostics. Consider Main display-projection (TD as source of truth). | `layout.py:13-68,388,695-708`; `merged_builders.py` |
| **D3** | Low | **Hub static SEO/Technical/Copy Score** duplicate Main without a live link (only Main `Technical Health` is linked). Could `INDEX/MATCH` from Main. | `engine_rows.py:722-724`; `tables_impl.py:281-294` |
| **D4** | Low | **Legacy dead column defs** (`Technical`, `Content`, `Links`, `AEO`, `Indexability`, `Media`, `Security`) still defined and branched on though those sheets aren't in the full suite. | `layout.py:89-261`; `export_registry.py:72-155,185-220`; `config.py:30-39` |
| **P1** | Med | **Number formats missing** for PSI scores, LCP/CLS/TTFB, `Entity Density (%)`, `Image Alt Coverage (%)`, GSC CTR (outside Priority URLs), Hub Metrics ROI columns, `Page Size (KB)`, DOM size, durations; booleans export as TRUE/FALSE text. | `number_formats.py:12-62` |
| **P2** | Med | **British/American spelling**: sheet "Content Optimisation Hub" (UK) vs column "On-Page **Optimization** Score" (US); CF accepts both spellings as a workaround. §8 wants British English. | `layout.py:205`; `conditional.py:524-535` |
| **P3** | Low | Fragile naming workaround: `"Citation Candidate Count"` dodges date-formatting only because the allowlist matches the `"date"` substring. | `engine_rows.py:729-731` |
| **P4** | Low | Misc: `Assigned Owner` (Hub) vs `Owner` (elsewhere) naming; Link Inventory frog-green header vs navy mock-table style elsewhere; possible orphaned rows under the Dashboard action-hub block. | `engine_rows.py:738`; `tables_impl.py:184-201`; `dashboard.py:522-523` |
| **P5** | Med | **Dashboard panel overlap (found in Phase 2):** `style_dashboard` writes the **Owner Issue Summary** (`G22:K31`) and the **Advanced Sheets** panel (`I20:J35`) into the same I–K columns; the later-written advanced panel overwrites part of the owner table. Relocate one panel before expanding either. | `dashboard.py:726-776` vs `940-956` |

### 3.3 Plan (check / validate / improve / implement)

- [ ] **P3.1 (F1 — bug, do first)** Fix the FixPlan Hub-Status formula to INDEX `Status` / MATCH on
      Hub `URL`, using the dynamic `content_hub_column_letter()` helper rather than literal columns;
      add a test asserting the join resolves to a Status literal, not a score. _Blast radius:
      `links.py` + test._
- [ ] **P3.2 (F2)** Replace hardcoded cross-sheet column letters with header-resolved lookups
      (reuse the Dashboard dynamic-column helpers); raise/parametrise the Link Inventory row cap.
      _Blast radius: `tables_impl.py`, `dashboard.py`, `broken_links.py` (>3 → needs approval)._
- [ ] **P3.3 (P1 — additive)** Extend `number_formats.py` allowlist to cover PSI/LCP/ms/%/ROI and
      replace the `"date"` substring hack (P3) with explicit per-column format mapping. _Blast
      radius: `number_formats.py` (+ maybe `engine_rows.py`)._
- [ ] **P3.4 (P2)** Standardise British English in **headers/labels** ("Optimisation"); keep the
      pipeline **row key** unchanged (append-only contract) by mapping key→display label at the
      reporter layer; once headers are canonical, drop the dual-spelling CF workaround. _Blast
      radius: `layout.py`/`config.py` + `conditional.py`; verify no broken header-keyed lookups._
- [ ] **P3.5 (F5)** Convert Dashboard static side-panels to live `COUNTIF(S)` aligned with the
      existing B9–B12 patterns (so in-sheet edits stay consistent). _Blast radius: `dashboard.py`._
- [ ] **P3.6 (D1)** Consolidate issue roll-ups: keep **Issue Register** canonical; hide
      **IssueInventory** from the visible set/TOC (or merge), and update Dashboard/links that target
      it. _Blast radius: `workbook_layout.py` + `links.py` + `export_flow.py` (>3 → needs approval)._
- [ ] **P3.7 (D2/D3 — display projection)** Add a reporter-layer column projection so Main hides the
      duplicated PSI/CWV block (TD remains source of truth) and the Hub shows live `INDEX/MATCH`
      scores instead of static copies. **No pipeline key changes.** _Blast radius: `layout.py` +
      `engine_rows.py`._
- [ ] **P3.8 (D4)** Remove/quarantine legacy dead column definitions and the formatting branches
      that reference non-exported sheets. _Blast radius: `layout.py`, `export_registry.py`,
      `config.py`, `tables_impl.py` (>3 → needs approval)._
- [ ] **P3.9 (F3/F4/P4)** Add `_xlfn.IMAGE` fallback; drop/whitelist the `Needs Work` COUNTIFS
      label; reconcile `Assigned Owner`/`Owner`; tidy orphaned Dashboard rows; align header styling.
- [ ] **P3.10 (validation)** Tests for: Hub-Status join correctness; number formats applied to key
      numeric columns; British-English headers; IssueInventory no longer visible (if hidden);
      Dashboard side-panel formulas present.

---

## 4. Sequencing & risk

1. **Phase 3 bug-first slice** — P3.1 (F1) and F2/F4 are correctness fixes with small diffs; ship
   these first to stop wrong client-facing numbers.
2. **Phase 2 correctness** — P2.1 (TOC refresh) + P2.2/P2.3 (descriptions, landing tab) are
   low-risk, high-trust wins.
3. **Phase 1 consolidation** — P1.1/P1.2 (flag + palette) are structural; treat as a single
   reviewable diff, then layer P1.3–P1.7.
4. **Additive polish** — number formats, tooltips, tab colours, spelling.
5. **Consolidation** (D1/D2/D3/D4) last — largest blast radius, most review.

Every phase: `uv run pytest` (reporter + full-smoke), `ruff` clean, regenerate a smoke workbook and
eyeball it, then sync `docs/excel_reporting_standards.md` and `.cursor/rules/excel_engine.mdc`.

---

## 5. Defect → fix traceability

| ID | Area | Symptom | File(s) | Task |
|---|---|---|---|---|
| C1/C2 | CF | Disable flag not honoured / undocumented | `conditional.py`, `engine_formatting.py`, `dashboard.py`, `.env.example` | P1.1 |
| C3/C4/C5 | Colour | Many palettes, inconsistent per-metric colour, double-CF | config, `conditional.py`, `engine_formatting.py` | P1.2/P1.3 |
| C6 | Colour | Harsh Hub primaries | `conditional.py` | P1.4 |
| C7/C8/C9 | CF/Colour | CF & tab-colour gaps | `conditional.py`, `workbook_layout.py`, `executive_dashboard.py` | P1.5–P1.7 |
| T1 | TOC | Dynamic refresh no-ops | `engine_guardrails.py` (+test) | P2.1 |
| T2/T3 | TOC | Missing/legacy blurbs | `engine_guardrails.py` | P2.2 |
| T4 | Nav | Opens on TOC | `workbook_layout.py`/`toc.py` | P2.3 |
| T5 | Nav | Exec Dashboard dead-end | `executive_dashboard.py` | P2.4 |
| T6 | Nav | Advanced panel incomplete | `workbook_layout.py`, `dashboard.py` | P2.5 |
| T7 | Layout | Freeze precedence conflict | `engine_guardrails.py`, `view_state.py` | P2.6 |
| T8/T9/T10 | Tooltips | Fragmented, wrong flag, gaps | validation/guardrails/help layers | P2.7/P2.8 |
| F1 | Formula | **FixPlan Hub-Status wrong join** | `links.py` | P3.1 |
| F2 | Formula | Hardcoded refs / row cap | `tables_impl.py`, `dashboard.py`, `broken_links.py` | P3.2 |
| F5 | Formula | Static Dashboard panels | `dashboard.py` | P3.5 |
| D1–D4 | Dedup | Issue roll-ups, PSI/CWV, Hub scores, legacy defs | layout/registry/links/export_flow | P3.6–P3.8 |
| P1–P4 | Polish | Number formats, spelling, naming, styling | `number_formats.py`, `layout.py`, `dashboard.py`, … | P3.3/P3.4/P3.9 |

---

_Analysis basis: read-only audits of `src/hype_frog/reporter/` across CF/colours, Info & Travel,
and formulas/dedupe/polish. All findings carry file:line citations above. No code changed yet._
