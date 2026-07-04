# Output Sheet UX/UI Analysis
**Source file:** `SEO_AEO_Audit_africanmarketingconfederation.org_20260701_160038_regen_76bb5b3a_20260701_163112.xlsx`
**Analysis date:** 2026-07-01

---

## 1. Workbook Overview

35 tabs total. 16 are visible by default; 19 are hidden (advanced/historical). The workbook opens on **Executive Briefing** (index 1), with **Table of Contents** pinned at index 0 (left-most). The legacy `Dashboard` tab is hidden.

### Tab Inventory and Colours

| Tab Name | Tab Colour (hex) | Group | Visible? | Freeze | Gridlines |
|---|---|---|---|---|---|
| Table of Contents | _(none)_ | — | Yes | A3 | Yes |
| Executive Briefing | `7F8C8D` (slate) | Management | Yes | A22 | **No** |
| Summary | `7F8C8D` | Management | Yes | C3 | Yes |
| Priority URLs | `417DC1` (blue) | Technical | Yes | C3 | Yes |
| FixPlan | `417DC1` | Technical | Yes | C3 | Yes |
| Quick Wins | `417DC1` | Technical | Yes | C3 | Yes |
| Content Optimisation Hub | `2ECC71` (green) | Content | Yes | I3 | Yes |
| Content Planner | `2ECC71` | Content | Yes | E2 | Yes |
| Content Hub Metrics | `2ECC71` | Content | Yes | C3 | Yes |
| Main | `95A5A6` (medium grey) | Inventory | Yes | C3 | Yes |
| AIOSEO Recommendations | `417DC1` | Technical | Yes | C3 | Yes |
| Link Inventory | `95A5A6` | Inventory | Yes | C3 | **No** |
| Broken Link Impact | `95A5A6` | Inventory | Yes | C3 | Yes |
| SitemapQA | `417DC1` | Technical | Yes | C3 | Yes |
| Template & Duplication Risks | `417DC1` | Technical | Yes | C3 | Yes |
| Playbook | `7F8C8D` | Management | Yes | C3 | Yes |
| Issue Register | `BDC3C7` (light grey) | Advanced | **Hidden** | C3 | Yes |
| Technical Diagnostics | `BDC3C7` | Advanced | **Hidden** | C3 | Yes |
| Content & AI Readiness | `BDC3C7` | Advanced | **Hidden** | C3 | Yes |
| Link Intelligence | `BDC3C7` | Advanced | **Hidden** | C3 | **No** |
| CMS Action URLs | `BDC3C7` | Advanced | **Hidden** | C3 | Yes |
| IssueInventory | `BDC3C7` | Advanced | **Hidden** | C3 | Yes |
| Redirects | `BDC3C7` | Advanced | **Hidden** | C3 | Yes |
| Redirect Map | `BDC3C7` | Advanced | **Hidden** | C3 | Yes |
| Robots.txt Analysis | `BDC3C7` | Advanced | **Hidden** | C3 | Yes |
| Crawl Log | `D5D8DC` (lightest grey) | Historical | **Hidden** | C3 | Yes |
| Link Equity Map | `BDC3C7` | Advanced | **Hidden** | C3 | Yes |
| Anchor Text Audit | `BDC3C7` | Advanced | **Hidden** | C3 | Yes |
| Snippet Opportunities | `BDC3C7` | Advanced | **Hidden** | C3 | Yes |
| Script Inventory | `BDC3C7` | Advanced | **Hidden** | C3 | Yes |
| Image Inventory | `BDC3C7` | Advanced | **Hidden** | C3 | Yes |
| ResolvedIssues | `D5D8DC` | Historical | **Hidden** | C3 | Yes |
| DeltaFromPreviousRun | `D5D8DC` | Historical | **Hidden** | C3 | Yes |
| Audit Run Details | `D5D8DC` | Historical | **Hidden** | C3 | Yes |
| Dashboard | `7F8C8D` | Management | **Hidden** | C3 | **No** |

---

## 2. Colour Palette

### Default Theme (`HF_EXCEL_THEME` not set / anything other than `mocha`)

Defined in `reporter/sheets/config.py`:

| Token | Hex | Role |
|---|---|---|
| `THEME_HEADER_BG` / `STD_NAVY` | `222A35` | Table header backgrounds, nav bars |
| `THEME_HEADER_TEXT` / `STD_WHITE` | `FFFFFF` | Text on dark header fills |
| `STD_BLUE` | `2F6FA3` | Hyperlinks, return-strip navigation text |
| `STD_FROG_GREEN` | `92D050` | Brand accent (used sparingly; mostly in older code) |
| `GRID_BORDER` | `E0E0E0` | Light grid lines (large inventory sheets) |
| `ZEBRA_FAINT` | `FAFAFA` | CF zebra anchor on high-row-count sheets |
| `ZEBRA_BAND` | `F7F7F7` | Static alternate-row fill (≤500 rows) |
| `RAG_RED` | `FCE8E6` | Critical / fail fill |
| `RAG_RED_FONT` | `A51D24` | Text on red fill |
| `RAG_AMBER` | `FEF3D6` | Warning fill |
| `RAG_AMBER_FONT` | `8F6B00` | Text on amber fill |
| `RAG_GREEN` | `E6F4EA` | Pass / good fill |
| `RAG_GREEN_FONT` | `137333` | Text on green fill |
| `RAG_RED_SOFT` | `FCE8E6` | Same as RAG_RED (duplicate; originally intended as softer) |
| `RAG_AMBER_SOFT` | `FEF3D6` | Same as RAG_AMBER (duplicate) |
| `RAG_NEUTRAL` | `D9D9D9` | Not-applicable / edge-case fill |
| `HEATMAP_LOW` | `F8696B` | Color-scale low (red) |
| `HEATMAP_MID` | `FFEB84` | Color-scale mid (yellow) |
| `HEATMAP_HIGH` | `63BE7B` | Color-scale high (green) |
| `DATA_BAR_BLUE` | `638EC6` | Data bar fill colour |
| `SEVERITY_OBSERVATION_FILL` | `DBEAFE` | Blue for Observation severity |
| `SEVERITY_UNMEASURED_FILL` | `E5E7EB` | Grey for Unmeasured |
| `STATUS_TODO_FILL` | `F8F9FA` | Near-white for To Do status |
| `STATUS_TODO_FONT` | `222A35` | Dark text on To Do |
| `HUB_BANNER_FILL` | `BFE9E4` | Content Hub banner row tint |

### Optional Catppuccin Mocha Theme (`HF_EXCEL_THEME=mocha`)

Defined in `reporter/mocha_theme.py`. Activated when `HF_EXCEL_THEME=mocha` is set in `.env`. Overrides the tokens above at import time via `excel_palette_overrides()`.

| Token | Mocha Hex | Role |
|---|---|---|
| `THEME_HEADER_BG` | `1E1E2E` | Very dark navy base |
| `THEME_HEADER_TEXT` | `CDD6F4` | Pale lavender |
| `RAG_RED` | `F5DCE3` | Rose-tinted red fill |
| `RAG_RED_FONT` | `8B2942` | Deep rose font |
| `RAG_AMBER` | `FEF3D4` | Warm yellow fill |
| `RAG_AMBER_FONT` | `7A5C00` | Dark amber font |
| `RAG_GREEN` | `DFF5DD` | Mint green fill |
| `RAG_GREEN_FONT` | `2D6A3A` | Forest green font |
| `ZEBRA_BAND` | `313244` | Dark surface stripe |
| `HEATMAP_LOW` | `F38BA8` | Mocha red (maroon) |
| `HEATMAP_MID` | `F9E2AF` | Mocha yellow (peach) |
| `HEATMAP_HIGH` | `A6E3A1` | Mocha green |

> **Note**: The Mocha theme is a dark-mode palette designed for terminal/HTML output. When applied to Excel (which renders on a white sheet background), the fills look muted but legible. The HTML executive report has a full dark background (`#11111b`) that makes Mocha shine; in Excel, it is a partial dark-mode that can look inconsistent.

---

## 3. Typography

All sheets use **Calibri** throughout (Excel 2010+ default font). No custom font is injected into Excel (JetBrains Mono is only used in the HTML report via Google Fonts CDN).

| Context | Font | Size | Style | Colour |
|---|---|---|---|---|
| Executive Briefing title (row 1) | Calibri | 16pt | Bold | `222A35` (near-black) |
| Executive Briefing subtitle (row 2) | Calibri | 9pt | Regular, wrap | `374151` (dark grey) |
| TOC title (A1) | Calibri | 14pt | Bold | `222A35` |
| Table header cells (row 2 on data sheets) | Calibri | 11pt | Bold | `FFFFFF` on `222A35` |
| Navigation / return strip (row 1) | Calibri | 11pt | Italic, underline | `2F6FA3` (blue) |
| Hyperlinks / cross-sheet links | Calibri | 11pt | Underline | `2F6FA3` |
| Data cells (general) | Calibri | 11pt | Regular | `000000` or theme colour |
| Severity critical cell text | Calibri | 11pt | Bold | `A51D24` |
| Severity warning cell text | Calibri | 11pt | Bold | `8F6B00` |
| Good status cell text | Calibri | 11pt | Regular | `137333` |
| Content Hub banner instruction | Calibri | 11pt | Bold | `222A35` on `BFE9E4` |
| Content Planner hierarchy labels | Calibri | 11pt | Bold | Varies by column |

---

## 4. Row Layout Pattern (Standard Data Sheets)

Most data sheets follow this 3-row header pattern:

```
Row 1  │  "<- Return to Executive Briefing"  (hyperlink, h=20px, merged A:H)
Row 2  │  Column headers  (Calibri 11 bold, white on #222A35)
Row 3+ │  Data rows  (h=auto or calculated from content)
```

**Freeze panes** at `C3` mean columns A–B and rows 1–2 are always visible while scrolling. The URL column is typically B; the first triage-level column is C.

**Exceptions:**
- `Table of Contents`: no return strip, freeze at `A3`
- `Executive Briefing`: no return strip on row 1 (it is the landing page), freeze at `A22`, row 1 = h45, row 2 = h36
- `Content Optimisation Hub`: row 1 = instruction banner (h=28), row 2 = headers, freeze at `I3`
- `Content Planner`: header at row 1 (no return strip at row 1; freeze at `E2`), header row h=42, data rows h=22

---

## 5. Column Width Contract

Defined in `reporter/sheets/layout.py`:

| Column type | Width (chars) | Source |
|---|---|---|
| URL-like (URL, Final URL, Canonical URL, etc.) | 45.0 | `URL_LIKE_HEADERS` frozenset |
| Prose / narrative (Affected URLs, How to Fix, etc.) | 55.0 | `PROSE_HEADERS` frozenset |
| Auto-fit (content-sampled, first 400 rows) | max(10, content+2, header_floor) capped at 48 | `_autofit_column_width` |
| Minimum | 10.0 | `_MIN_COL_WIDTH` |
| Maximum | 48.0 | `_MAX_COL_WIDTH` |
| Header floor | min(len(header)+2, 22) | prevents starvation |

**Content Optimisation Hub density overrides** (hardcoded):

| Header | Width |
|---|---|
| Action Required | 17.43 |
| On-Page Optimization Score | 12.0 |
| Assigned Owner | 15.0 |
| Elementor Builder Link | 18.14 |
| Current OG-Image URL | 15.0 |
| OG Image Health | 42.0 |
| Open in Main | 22.57 |

---

## 6. Row Height Policy

| Context | Height | Set by |
|---|---|---|
| Return strip (row 1 most sheets) | 20px | `add_return_to_briefing_strip` |
| Content Hub instruction banner | 28px | `apply_content_hub_conditional_rules` |
| Content Hub data rows | auto | not explicitly set |
| Content Planner header | 42px | `apply_content_planner_signoff_rules` |
| Content Planner data rows | 22px | `apply_content_planner_signoff_rules` |
| Executive Briefing row 1 | 45px | `dashboard.py` / sheet builder |
| Executive Briefing row 2 | 36px | sheet builder |
| Data rows with wrapped prose | up to 120px (15 × lines) | `apply_wrapped_row_heights` |
| Content Hub Metrics wrapped rows | up to 110px (13 × lines) | `apply_sheet_text_wrap_columns` |
| All other data rows | auto (not set) | Excel default |

---

## 7. Freeze Pane Map

| Freeze value | Applied to |
|---|---|
| `A3` | Table of Contents |
| `A22` | Executive Briefing |
| `C3` | All standard data sheets (return strip + header above grid) |
| `C2` | Standard data sheets without return strip (Priority URLs, Content, Links, etc.) — overrides vary |
| `I3` | Content Optimisation Hub (freeze through Action Required → URL Slug Normalization) |
| `E2` | Content Planner (freeze columns A–D: Primary, Secondary, Tertiary, Page link) |
| `None` | Sheets with <10 rows or <5 columns (TOC logic); sheets when `HF_DISABLE_NON_CORE_FREEZE_PANES=1` |

---

## 8. Conditional Formatting Inventory

### Type usage across sheets

| CF type | Used on |
|---|---|
| `ColorScaleRule` (3-stop, 0→50→100) | SEO Health Score, Desktop/Mobile PSI Score, AEO Readiness Score, Lighthouse scores, all Content Hub score columns |
| `ColorScaleRule` (lower-is-better) | Mobile LCP (s), Mobile TTFB (s), Mobile CLS |
| `DataBarRule` (blue) | Word Count (Body), Priority Score, Inlinks Count, Internal PageRank, Internal Links Count, Redirect Chain Length, Image Count, Inbound Link Count |
| `CellIsRule` (status codes) | Status Code ≥400 → red; Timeout → amber; on Main and many merged tabs |
| `CellIsRule` (threshold) | Days Open >60→red, 31–60→amber on Issue Register; Effort ≤2→green on Quick Wins; Schema Error Count >0→red |
| `FormulaRule` (text match) | Severity/health strings: "Critical"→red, "Warning"→amber, "OK"/"Perfect"→green, "MISSING"/"FIX"→red, "SHORT"/"LONG"→amber across Content Hub health columns |
| `FormulaRule` (owner role) | Assigned Owner: "copy writer"→green, "developer"→blue, "server"→orange on Content Hub |
| `FormulaRule` (sign-off status) | Content Planner F2:S{last}: "signed off"→green, "in progress"→amber, "not signed off"→red |
| `CellIsRule` (severity badge) | Severity Badge: Critical→RAG_RED_SOFT, Warning→RAG_AMBER_SOFT, Observation→DBEAFE, Unmeasured→E5E7EB on Main |

### Sheets with no conditional formatting

`Table of Contents`, `Executive Briefing`, `Playbook`, `Audit Run Details`, `Crawl Log`, `Quick Wins` (only effort CF), `FixPlan` (minimal), `CMS Action URLs`.

---

## 9. Sheet-by-Sheet Style Details

### Table of Contents
- A1: `"Table of Contents"` — Calibri 14 bold, `222A35`, no fill
- A2/B2/C2: `"Section"`, `"Open"`, `"Description"` — Calibri 11 bold white on `222A35`
- A3+: Section label rows (bold, `222A35`) and hyperlink rows (blue underlined)
- Col widths: A=40, B=12, C=70
- Row 1 height: 18.75px (auto from 14pt font)
- No conditional formatting, no autofilter, no tab colour

### Executive Briefing
- Row 1: Emoji-prefixed title `🐸 HYPE FROG: SEO & AEO Intelligence` — Calibri 16 bold, `222A35`, left aligned, row h=45
- Row 2: SEO health summary sentence — Calibri 9, colour `374151`, `wrap_text=True`, row h=36, merged A2:L2
- Row 3: Formula pulling domain/date — Calibri 10 bold, `222A35`, left, merged A3:L3
- Row 4: Sub-section header `Audit Run Details` — Calibri 11 bold black, fill `E5E7EB`, centered
- Dense layout: many merged cell blocks (A16:L16, A10:L10, G7:H7, I7:J7 etc.) creating a card-like structure across columns A–N
- Freeze at A22 (entire audit card block stays pinned)
- **Gridlines disabled**
- Tab colour: `7F8C8D`

### Summary
- Row 1: Return strip (blue italic hyperlink)
- Row 2: Headers on `222A35` — Section, Severity, Issue, Affected URL Count, Reference Tab, Affected URLs (sample)
- 128 data rows (130 total)
- CF on B3:B130 (Severity): 3 rules — Critical→red, Warning→amber, Observation→grey/blue
- Prose column "Affected URLs (sample)" width 55
- Tab colour: `7F8C8D`

### Priority URLs
- 20 data rows, 21 columns (U)
- 4 CF range groups: Business Risk Score (C), SEO Health Score (D), Status (L), AEO Readiness Score (O)
- Col C freeze visible; columns A–B pinned (URL, Business Risk Score)

### FixPlan
- Only 3 rows total (1 header + 2 data rows in this crawl with 20 URLs)
- CF on B3 (Priority Score): 3 rules
- Intelligent sorting by priority score descending

### Quick Wins
- Only 2 rows (1 header + 1 data row)
- CF on Effort column when present
- Tab colour: `417DC1`

### Content Optimisation Hub
- Row 1: Teal banner (`BFE9E4`) with instruction text + return link; h=28
- Row 2: Headers on `222A35`; 17 data rows
- 37 columns (AK), freeze at I3
- Dense CF: color scales on scores, FormulaRules on 8 health columns, owner-role colours, Action Required RAG
- Cell comments (openpyxl `Comment`) on every header in row 2
- Data validation dropdown on Status column (To Do / In Progress / In Review / Done)
- IMAGE() formula in OG Image Preview column

### Content Planner
- Header row 1 (no return strip); height=42px
- Teal accent headers (Primary/Secondary/Tertiary): fill `BFE9E4`, font `1A4A47`
- Copy Doc header: fill `FFF3CD`, font `7A5C00`
- Sign-off columns (F-S) headers: fill `E8EAF6`, font `1A237E`
- Data rows height=22px; sign-off cells centred
- CF on F2:S{last}: signed off→green, in progress→amber, not signed off→red
- Freeze at E2; autofilter

### Main
- 217 columns (HI), 20 data rows
- Columns A–K visible (triage block): Health Icon, URL, Status Code, Indexability, Load Time, Title, Meta Description, Word Count, SEO Health Score, Severity Badge, Action Needed
- Columns L+ grouped and **hidden by default** (outline level 1)
- Sub-groups within hidden area (Metadata, Heading Structure, Performance/CWV, GSC, Schema, E-E-A-T, etc.) at outline level 2
- 21 CF ranges; heatmaps on SEO Health Score, Status Code, Word Count (data bar), Severity Badge
- Sorted by Discovery Rank
- Tab colour: `95A5A6`; gridlines on

### AIOSEO Recommendations
- 151 rows (150 issues), 20 columns
- Sorted by Severity→Priority Score→Panel→URL
- CF on Severity (E), Action Needed (G), Status (M), AEO Readiness (O)
- Data validation on Status column

### Link Inventory
- 623 rows (622 links), 7 columns
- CF: alternate row highlight (A3:G623), link type (E), status code (F), crawlable (G)
- **Gridlines disabled**
- Autofilter present

### Link Intelligence
- 958 rows (957 links), 22 columns
- CF: zebra row (A3:V958), link type (B), status code (E), record type (F), generic anchor (G)
- **Gridlines disabled**

### Dashboard (hidden)
- Legacy formula sheet; hidden but retained
- 46 rows, 15 columns (O)
- Specific CF on B5:B7, B8, B17, B20, B22 (completion scales, red alerts)
- Column widths hardcoded: A=35, B=15, C=5, D=30, etc.
- Custom palette: LIGHT_HEADER_COLOR=`E5E7EB`, TABLE_HEADER_COLOR=`ADD8E6`, VALUE_BLOCK_COLOR=`DCE3EA`, PANEL_BG_COLOR=`F5F7FA`
- Uses a distinct colour vocabulary separate from the main RAG palette

---

## 10. Navigation System

- **Row 1 return strip**: Present on all data sheets except Table of Contents and Executive Briefing. Text: `"<- Return to Executive Briefing"`. Font: Calibri 11, italic, underline, `2F6FA3`. Merged across A1:H1. Hyperlink to `#'Executive Briefing'!A1`.
- **TOC hyperlinks**: Each row links to the target sheet's A1. `HYPERLINK()` formula so links survive column reorders. "Open" button (column B) duplicates the link.
- **Cross-sheet links**: Reference Tab columns on Summary, FixPlan, Issue Register, and AIOSEO hyperlink directly to their detail tab.
- **Content Hub "Open in Main"**: Per-URL column using `TRIM(HYPERLINK(...))` to jump to the URL row on Main.
- **Content Hub "Elementor Builder Link"**: Per-URL edit link (external URL to WordPress admin).

---

## 11. Data Validation Dropdowns

| Sheet | Column | Options |
|---|---|---|
| Content Optimisation Hub | Status | To Do / In Progress / In Review / Done |
| AIOSEO Recommendations | Status | To Do / In Progress / In Review / Done |
| Content Planner | Sign-off cols (F-S) | Signed off / In progress / Not signed off |
| IssueInventory | Status | To Do / In Progress / In Review / Done |

Controlled by `HF_DISABLE_DATA_VALIDATION=1` env flag.

---

## 12. Autofilter Coverage

| Sheet | Has Autofilter |
|---|---|
| Link Inventory | Yes |
| Link Intelligence | Yes |
| Issue Register | Yes (added by merged CF pass) |
| Content Planner | Yes |
| Most others | **No** |

---

## 13. Known UX/UI Problems

The following are concrete, observable issues in the current output — not hypothetical.

---

### P1 — Critical UX Breaks

**13.1 — Gridline inconsistency**
Three data sheets have gridlines explicitly **disabled** (Executive Briefing, Link Inventory, Link Intelligence, Dashboard) while all others leave them on. This is not intentional persona-grouping — it is a side effect of openpyxl's `showGridLines=False` being set in some code paths and not others. The result is a jarring visual switch between tabs.
- Source: `showGridLines` property in `sheetView`; set in `links.py` / sheet builders
- Fix needed: Either disable gridlines globally (cleaner) or enable them globally. Disabling creates a more polished output.

**13.2 — No zoom level is set on any sheet**
Every tab opens at Excel's default 100% zoom. The Executive Briefing (dense card layout spanning 14 columns) needs a custom zoom (e.g. 85%) to fit the card on screen without horizontal scrolling. The Main sheet (217 columns, 10 visible) should also be at 80–85% so the triage block fills the screen without dead space.
- Source: `ws.sheet_view.zoomScale` is never set anywhere in the codebase
- Fix needed: Set zoom per sheet type in `toc.py` or sheet builders

**13.3 — Static cell fills conflict with conditional formatting on same cells**
`apply_generic_sheet_coloring` in `conditional.py` writes static `PatternFill` directly onto data cells (for Severity, Status Code, boolean flags, score thresholds). After that, `apply_merged_tabs_conditional_formatting` and `apply_main_sheet_heatmaps` add CF rules on the same columns. Excel evaluates CF rules on top of static fills, but CF priority order and stopIfTrue flags create unpredictable results when users sort or filter — the static fills don't move with rows, the CF rules do.
- Source: `apply_generic_sheet_coloring` at `conditional.py:201` vs CF rules at `conditional.py:1010+`
- Fix needed: Remove static per-cell fills from `apply_generic_sheet_coloring` for columns that are also covered by CF. Use CF exclusively for all semantic colouring so sort/filter preserves colour meaning.

**13.4 — RAG_RED_SOFT and RAG_AMBER_SOFT are identical to RAG_RED and RAG_AMBER**
In `sheets/config.py` (lines 35–37), `RAG_RED_SOFT = "FCE8E6"` and `RAG_AMBER_SOFT = "FEF3D6"` are set to the exact same hex values as `RAG_RED` and `RAG_AMBER`. The intended visual hierarchy (soft pastel row-level vs. strong per-cell fill) is completely lost. Users cannot distinguish a "soft warning stripe" from a "hard warning cell."
- Source: `config.py:35–37`
- Fix needed: Define genuinely softer variants, e.g. RAG_RED_SOFT=`FFF0F0`, RAG_AMBER_SOFT=`FFFAED`

**13.5 — Autofilter absent on most actionable sheets**
Priority URLs, Summary, FixPlan, AIOSEO Recommendations, Technical Diagnostics, Content Hub Metrics, and Broken Link Impact all lack autofilter. These are the sheets users actually work in — filtering by severity, owner, or status is a primary workflow action. Without autofilter headers, users must add filters manually every time.
- Source: No `ws.auto_filter.ref` call in builders for these sheets
- Fix needed: Add autofilter to all data sheets that have ≥2 rows (mirror the pattern already used in Issue Register and Content Planner)

---

### P2 — Significant UX Friction

**13.6 — Executive Briefing has no zoom and a jarring font-size jump**
The title is 16pt; the subtitle immediately below is 9pt — a ratio of 1.78× in consecutive rows with no mid-level scale. The subtitle (`"SEO health is 0% across 20 crawled..."`) is the most important headline metric and it is rendered in the smallest font on the page.
- Source: `dashboard.py` title row (16pt) vs. subtitle row (9pt)
- Fix needed: Title 18pt, subtitle 13pt, stat callouts 12pt. Set zoom to 85%.

**13.7 — Tab colour palette provides poor differentiation**
Three of the six group colours are variations of grey: Management `7F8C8D`, Inventory `95A5A6`, Advanced `BDC3C7`, Historical `D5D8DC`. These four grey bands are indistinguishable at a glance in the tab bar, especially at small tab sizes. On a 1920×1080 monitor with 16 visible tabs the colour coding adds no meaningful visual grouping.
- Source: `workbook_layout.py:28–33`
- Fix needed: Use 4 colours with genuine hue contrast — e.g. Management=`2C3E50` (dark blue-grey), Content=`27AE60` (green), Technical=`2980B9` (blue), Inventory/Raw=`E67E22` (orange), Advanced=`8E44AD` (purple), Historical=`95A5A6` (grey). Reserve grey only for truly archival tabs.

**13.8 — Return strip text uses ASCII `<-` arrow**
`"<- Return to Executive Briefing"` uses two ASCII characters for the arrow. This looks dated compared to `"← Return to Executive Briefing"` (U+2190) or `"↩ Return"`.
- Source: `config.py:47` `RETURN_TO_BRIEFING_LABEL`
- Fix needed: Replace with `"← Return to Executive Briefing"` (single-character Unicode left arrow)

**13.9 — Content Optimisation Hub instruction banner is too low-contrast**
The banner fill `BFE9E4` (teal-grey) against Calibri 11 in `222A35` (near-black) is adequate for contrast ratio, but the instruction text is packed with semicolons and pipes into a single cell. Users miss the important security note (`"NOTE: If images show '#BLOCKED!'"`) because it blends into the instruction stream.
- Source: `conditional.py:469–473`
- Fix needed: Split into separate merged cells: one for the return link, one short instruction, one highlighted note with a distinct fill (e.g. `FEF3D6` amber background for the security note).

**13.10 — Dashboard tab is hidden but TOC lists it as a quick link under some code paths**
The legacy `Dashboard` sheet is in `LEGACY_HIDDEN_SHEETS` and therefore hidden, but `dashboard_config.py:52–60` still defines `QUICK_LINKS` pointing to `#Summary!A1`, `#FixPlan!A1`, etc. These links are written into the Dashboard sheet which is hidden. If a user unhides Dashboard they find a partially stale UI built on a dead code path.
- Source: `dashboard_config.py`, `workbook_layout.py:92–93`
- Fix needed: Either remove the Dashboard sheet entirely or promote it back to visible with a proper redesign.

**13.11 — FixPlan and Quick Wins are near-empty on this crawl (3 and 2 rows)**
These tabs are high-visibility (blue tab colour, prominent in TOC) but open to essentially empty sheets when the crawl returns few issues or a small sitemap. The sheet builders do not render a placeholder/empty-state message explaining why data is sparse. Users assume the sheet is broken.
- Source: No empty-state guard in FixPlan/Quick Wins builders
- Fix needed: When row count ≤ data_start+2, write an empty-state block: "No issues qualified for this view. See Summary for the full issue register." styled with `RAG_GREEN` fill.

---

### P3 — Quality-of-Life Issues

**13.12 — Zebra banding drops off above 500 rows**
`apply_generic_sheet_coloring` at `conditional.py:438` only applies static zebra fills when `max_row - header_row <= 500`. Link Inventory (622 rows) and Link Intelligence (957 rows) — the two largest data sheets — therefore receive **no** row striping at all. These are the hardest sheets to scan visually.
- Source: `conditional.py:438`
- Fix needed: Use a CF-based zebra rule (`FormulaRule(formula=["MOD(ROW(),2)=0"])`) for all sheets instead of static fills. This removes the row-count threshold and correctly follows rows through sort/filter.

**13.13 — No explicit row height on standard data rows**
Most data sheets leave row height at Excel's auto (13.5pt, ~18px). This results in cramped rows when cell alignment is `vertical="top"` (the default applied by `apply_generic_sheet_coloring`) — the text sits at the top of a minimum-height row. A consistent minimum of 18–20px would give cells breathing room.
- Source: No `ws.row_dimensions[row_idx].height` call in `apply_generic_sheet_coloring`
- Fix needed: Set `worksheet.row_dimensions[row_idx].height = 18` for all non-prose data rows in the generic coloring pass.

**13.14 — Column groups on Main are hidden at level 1 and level 2 with no label**
Main has 217 columns compressed into 11 visible columns using outline groups (level 1 = all non-triage, level 2 = sub-groups within that). Users who expand the outline see an unlabelled wall of columns with no visual group separator or colour break. The sub-group names (Metadata Group, Performance & CWV Group, etc.) exist in code but are never written into the sheet as visible group labels or header row separators.
- Source: `layout.py:749–799` `apply_column_grouping`
- Fix needed: Add a merged "group separator" row above each column group within the hidden area, or colour-band column headers by group using a secondary fill cycle.

**13.15 — Zoom state and gridlines on Executive Briefing inconsistent with actual content density**
The Executive Briefing has the highest information density of any sheet (many merged cells, a prose subtitle, a stats card, a quick-links block), yet it opens at 100% zoom with no gridlines. Without gridlines or zoom calibration, the user sees a dense block of text with no visual anchors. Setting zoom to 80% and enabling subtle gridlines between the card blocks would make it scannable.

**13.16 — No print area or page setup defined on any sheet**
None of the sheets set a print area (`ws.print_area`), page orientation, or scaling. If a client prints directly from Excel they get unpredictable pagination — the wide Main sheet (217 cols) will produce dozens of pages.
- Source: No `ws.page_setup` / `ws.print_area` calls in any builder
- Fix needed: Set `ws.page_setup.fitToPage = True`, `ws.page_setup.fitToWidth = 1`, `ws.page_setup.fitToHeight = 0` on key sheets; set explicit print areas on Executive Briefing and Summary.

**13.17 — Data Validation `showInputMessage` disabled on Content Hub Status**
`conditional.py:521` explicitly sets `dv.showInputMessage = False` on the Status dropdown. This means users hovering the Status cell see no tooltip explaining what the dropdown options mean. The comment workaround (cell comments on row 2 headers) does not help data cells in rows 3+.
- Source: `conditional.py:521`
- Fix needed: Enable `showInputMessage=True`, set `dv.promptTitle` and `dv.prompt` to a short one-liner ("Track workflow state: To Do → In Progress → In Review → Done").

**13.18 — Executive Briefing freeze at A22 hides the SEO narrative from view on a standard monitor**
At 100% zoom on a 1080p screen, Excel shows roughly 30 rows. Freezing at A22 means the 21 rows of the briefing card are always visible, but row 22+ (which contains section headers and tables below the card) falls below the visible area. If a user scrolls down they lose the top summary. The freeze target should probably be `A4` or `A6` (after the one-liner headline) rather than A22.
- Source: `config.py:110` `EXECUTIVE_BRIEFING_FREEZE_PANES = "A22"`, `toc.py:189`

**13.19 — No sheet-level "last updated" or run metadata visible on data sheets**
The only place run metadata appears is the `Audit Run Details` tab (hidden by default) and row 3 of Executive Briefing (a formula pulling from Audit Run Details). Standard data sheets (Main, Priority URLs, etc.) show no crawl date, domain, or URL count in the header area. A one-line subtitle row with `"africanmarketingconfederation.org — 20 URLs crawled — 2026-07-01"` on each data sheet would orient users who navigate directly to a tab via the TOC.

**13.20 — Mocha theme applies dark fills to Excel but the sheet background remains white**
When `HF_EXCEL_THEME=mocha` is active, the table header fill becomes `1E1E2E` (very dark) and the zebra band becomes `313244` (also very dark). These fills look correct in Excel because the text colours (`CDD6F4` lavender on dark) were designed for the HTML dark report. However, the **sheet background** in Excel is always white — there is no openpyxl API to set the sheet canvas colour. The result is dark fills on a white canvas with no surrounding dark background, which looks inconsistent and can be hard to read compared to the HTML output.
- Source: `mocha_theme.py` design intent vs. openpyxl limitations
- Fix needed: Either document this limitation explicitly and default to the light theme for Excel, or provide a separate `HF_EXCEL_THEME=mocha-light` that uses Mocha accent hues with light backgrounds suitable for white-canvas Excel.

---

## 14. Code Locations for Priority Fixes

| Fix | File | Key symbols |
|---|---|---|
| Enable gridlines globally | `reporter/sheets/view_state.py`, `reporter/sheets/toc.py` | `ws.sheet_view.showGridLines` |
| Set zoom per sheet | `reporter/sheets/toc.py`, sheet builders | `ws.sheet_view.zoomScale` |
| Replace static fills with CF | `reporter/sheets/conditional.py:201–443` | `apply_generic_sheet_coloring` |
| Fix RAG_RED_SOFT / RAG_AMBER_SOFT | `reporter/sheets/config.py:35–37` | `RAG_RED_SOFT`, `RAG_AMBER_SOFT` |
| Add autofilter to actionable sheets | Sheet builders and `reporter/sheets/merged_builders.py` | `ws.auto_filter.ref` |
| Fix Executive Briefing font hierarchy | `reporter/sheets/dashboard.py` or `reporter/orchestration/export_executive_reports.py` | title/subtitle row font sizes |
| Update tab colours | `reporter/sheets/workbook_layout.py:28–33` | `TAB_COLOR_*` constants |
| Unicode return arrow | `reporter/sheets/config.py:47` | `RETURN_TO_BRIEFING_LABEL` |
| Split Content Hub banner | `reporter/sheets/conditional.py:469–503` | `apply_content_hub_conditional_rules` |
| CF-based zebra banding | `reporter/sheets/conditional.py:436–441` | `apply_generic_sheet_coloring` loop |
| Set row height minimums | `reporter/sheets/conditional.py:281–443` | `apply_generic_sheet_coloring` |
| Print area / page setup | Any sheet builder (after column widths applied) | `ws.page_setup`, `ws.print_area` |
| Enable DV input message | `reporter/sheets/conditional.py:521` | `dv.showInputMessage` |
| Fix Executive Briefing freeze | `reporter/sheets/config.py:110` | `EXECUTIVE_BRIEFING_FREEZE_PANES` |
| Empty-state blocks | FixPlan/Quick Wins builders | Sheet row builders |
| Mocha light variant | `reporter/mocha_theme.py` | `excel_palette_overrides` |

