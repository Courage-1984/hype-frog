# Hype Frog — Audit Fix Log
**Source audit:** LI-HF-AUDIT-P0 (26 June 2026)
**Test site:** https://africanmarketingconfederation.org/page-sitemap.xml

---

## Phase Status

| Phase | Title | Status | Test Passed | Notes |
|-------|-------|--------|-------------|-------|
| 0 | Tracking document created | ✅ Done | N/A | |
| 1 | Isolated function fixes (3 bugs) | ✅ Done | ✅ Pass | quick-test-fast 2026-06-26; export blocker fixed separately |
| 2 | CrUX origin data labelling | ✅ Done | ✅ Pass | quick-test-fast 2026-06-26 |
| 3 | Site-level vs URL-level issue scope | ✅ Done | ✅ Pass | quick-test-fast 2026-06-26; IssueInventory 69 rows |
| 4 | CWV severity cascade fix | ✅ Done | ✅ Pass | quick-test-fast 2026-06-26; badges 3 Critical / 7 Warning |
| 5 | WooCommerce / parameter URL filtering | ✅ Done | ✅ Pass | CMS Action URLs tab added; AMC run 0 withheld URLs |
| 6 | FixPlan vs Summary count reconciliation | ✅ Done | ✅ Pass | FixPlan/Summary counts aligned on AMC run |
| 7 | Click Depth null handling | ✅ Done | ✅ Pass | 0 null Click Depth cells on AMC run |
| 8 | Duplicate Main sheet column fix | ⬜ Pending | ⬜ | |

---

## Phase 1 — Isolated Function Fixes

### 1A: 404 pages showing Indexability = "Indexable"
- **File:** `src/hype_frog/crawler/data_assembler.py`
- **Function:** `finalize_row_state` (~line 716)
- **Status:** ✅ Done
- **Change summary:** When `Status Code >= 400`, set `main_values["Indexability"] = "Not Indexable"` alongside the existing `HTTP {code}` indexability reason.

### 1B: GSC unavailable writes 0.0 instead of None
- **File:** `src/hype_frog/pipeline/gsc_coverage.py`
- **Function:** `apply_gsc_coverage_fields` (~line 89)
- **Status:** ✅ Done
- **Change summary:** Unmatched GSC branch now writes `None` for Clicks/Impressions/CTR/Avg Position. Caller fixes: `assemble.py` merge drops `0.0` defaults; `PageRowMetricsModel` / `harden_page_row_metrics` preserve `None` for GSC fields. `_safe_clicks` already handled `None`.

### 1C: Link Inventory has duplicate source→target rows
- **File:** `src/hype_frog/reporter/sheets/merged_builders.py`
- **Function:** `build_link_inventory_rows` (~line 655)
- **Status:** ✅ Done
- **Change summary:** Deduplicate on `(Source URL, Target URL, Anchor Text)` keeping first occurrence.

---

## Phase 2 — CrUX Origin Data Labelling

### 2A: _field_experience_metrics origin detection
- **File:** `src/hype_frog/crawler/psi_engine.py`
- **Function:** `_field_experience_metrics` (~line 204)
- **Status:** ✅ Done
- **Change summary:** Tracks `loadingExperience` vs `originLoadingExperience` fallback; adds `crux_data_level` (`url` | `origin`) to returned metrics dict.

### 2B: CWV Data Source / PSI Data Status / Field vs Lab consistency
- **File:** `src/hype_frog/crawler/psi_engine.py`
- **Function:** `_resolve_cwv_labelling`, `_merge_url_results`
- **Status:** ✅ Done
- **Change summary:** New audit vocabulary (e.g. `PSI + CrUX Field (URL)`, `CrUX Field (Origin)`, `PSI Lab`). Origin appears in `CWV Data Source` when origin CrUX used. Field metrics parsed even when Lighthouse lab absent.

### 2C: Propagation in assemble.py
- **File:** `src/hype_frog/pipeline/assemble.py`, `layout.py`
- **Function:** `row_with_psi_gsc_harden`, `assemble_enriched_row`
- **Status:** ✅ Done
- **Change summary:** Fallback defaults aligned to `N/A` / `None` / `Not available`. `CWV Data Source` added to Main Performance group and enriched main merge.

---

## Phase 3 — Site-level vs URL-level Issue Scope

**`get_summary_rules()` callers updated to `IssueRule` attribute access:**
- `src/hype_frog/rules/scoring.py` — `score_url_health`
- `src/hype_frog/reporter/summary_builder.py` — `build_summary_rows`, `build_issue_inventory_rows`
- `src/hype_frog/reporter/engine_rows.py` — `build_fixplan_rows`
- `src/hype_frog/orchestration/export_flow.py` — export pipeline
- `src/hype_frog/orchestration/enrichment_flow.py` — scoring pass
- `src/hype_frog/orchestration/export_registry.py` — `build_delta_and_trend_rows`
- `src/hype_frog/pipeline/assemble.py` — type hint on `apply_issue_scoring`

### 3A: Add scope metadata to registry rules
- **File:** `src/hype_frog/rules/registry.py`
- **Function:** `get_summary_rules`
- **Status:** ✅ Done
- **Change summary:** Frozen `@dataclass IssueRule(severity, name, fn, scope="url")`. Returns `list[IssueRule]`. `"No ETag Header"` → `scope="server"`; `"AI Crawlers Not Explicitly Allowed"` → `scope="site"`; all others remain `"url"`. Exported from `rules/__init__.py`.

### 3B: Branch on scope in IssueInventory builder
- **File:** `src/hype_frog/reporter/summary_builder.py`
- **Function:** `build_issue_inventory_rows`
- **Status:** ✅ Done
- **Change summary:** Non-`url` rules emit one aggregate row (`(site-wide)` / `(server config)`), `Affected URL Count`, stable ID via `stable_issue_id("site"|"server", rule.name)`. Per-URL loop skips aggregate issue names. `Affected URL Count` added to IssueInventory columns in `layout.py`.

### 3C: FixPlan builder scope resolution types
- **File:** `src/hype_frog/reporter/engine_rows.py`
- **Function:** `build_fixplan_rows`
- **Status:** ✅ Done
- **Change summary:** `rule.scope == "server"` → `Resolution Type = "Server Config"`; `rule.scope == "site"` → `"Site Config"` (precedence over Global Template token matching).

**Phase 3 verification (2026-06-26 output):**
- IssueInventory: `No ETag Header` → 1 row, URL `(server config)`, Affected URL Count = 10
- IssueInventory: `AI Crawlers Not Explicitly Allowed` → 1 row, URL `(site-wide)`, Affected URL Count = 10
- FixPlan: same issues → `Server Config` / `Site Config` respectively
- Summary issue counts unchanged (10 each)
- Total IssueInventory rows: 69 (aggregate collapse vs per-URL duplication)
- Unit tests: 6/6 pass (`test_scoring`, `test_issue_inventory_scope`, `test_fixplan_scope`)

---

## Phase 4 — CWV Severity Cascade Fix

**Pre-check:** Phase 3 output confirms `CWV Data Source` labelling from Phase 2 (`PSI API (CrUX)` for URL-level; `CrUX API (Origin-level)` when origin fallback applies).

### 4A: Guard CWV rules against origin-level data
- **File:** `src/hype_frog/rules/registry.py`
- **Function:** CWV rules in `get_summary_rules`
- **Status:** ✅ Done
- **Change summary:** `CWV LCP Above 4.0s`, `CLS Above 0.1`, and `INP Above 100ms` now require `"Origin" not in CWV Data Source`. Added three site-scoped Observation rules for origin CrUX breaches (`… (Origin CrUX — Run PSI Pass for Per-URL Data)`), collapsed by Phase 3 IssueInventory branching.

### 4B: Verify scoring.py needs no change
- **File:** `src/hype_frog/rules/scoring.py`
- **Function:** `score_url_health`
- **Status:** ✅ Confirmed — no change required
- **Notes:** Uses `rule.fn(row)` via `IssueRule` attributes; badge cascade from `matched["Critical"]` is correct once origin guard prevents false per-URL Critical matches.

**Phase 4 verification (2026-06-26 output):**
- Severity badges: **3 Critical / 7 Warning** (was 10/10 Critical in Phase 3 run)
- 3 PSI URLs with URL-level CrUX (`PSI API (CrUX)`, LCP > 4s) remain **Critical**
- Origin CrUX site rules: 0 matches this run (AMC PSI cache returned URL-level CrUX, not origin fallback)
- Unit tests: 5/5 pass (`test_cwv_origin_guard`, `test_scoring`)

---

## Phase 5 — WooCommerce / Parameter URL Filtering

**Config finding:** No separate `crawl_config.yaml`; central constants live in `src/hype_frog/config.py`. Added `EXCLUDED_CMS_ACTION_QUERY_PARAMS` there (not hardcoded only in crawl_runner).

### 5A: Parameter exclusion in crawl candidate filter
- **Files:** `src/hype_frog/config.py`, `src/hype_frog/orchestration/crawl_runner.py`
- **Functions:** `_is_crawlable_html_candidate`, `_candidate_internal_links`, `execute_crawl`
- **Status:** ✅ Done
- **Change summary:** Blocks CMS action query params (`add-to-cart`, `wc-ajax`, `preview`, etc.) from the crawl queue. Safe params (`page`, `lang`, `paged`, `product_cat`, `s`, …) remain allowed. Excluded URLs tracked in `ExcludedCmsActionUrl` on `CrawlExecutionResult`.

### 5B: CMS Action URLs workbook tab (user request)
- **Files:** `export_registry.py`, `export_flow.py`, `workbook_layout.py`, `engine_guardrails.py`
- **Status:** ✅ Done
- **Change summary:** New advanced tab **CMS Action URLs** lists withheld URLs with excluded parameters, discovery source, and review note. Builder merges crawl-time exclusions with internal links found on crawled pages. Tab registered in TOC, dashboard advanced links, and tab colours.

**Phase 5 verification (2026-06-26 output):**
- Main sheet: **10 rows**, no `add-to-cart` URLs
- CMS Action URLs tab: present (0 rows for AMC — site does not expose WooCommerce action links in this crawl)
- Unit tests: 25/25 pass (`test_crawl_runner`, `test_cms_action_urls`)
- `--quick-test-fast`: PASS

---

## Phase 6 — FixPlan vs Summary Count Reconciliation

### 6A: Non-200 Status label alignment for 404 rows
- **File:** `src/hype_frog/rules/scoring.py`
- **Function:** `score_url_health`
- **Status:** ✅ Done
- **Change summary:** 404 early-return now writes `"Non-200 Status"` into matched issues (registry rule name) instead of `"HTTP 404 Not Found"`, so FixPlan/IssueInventory/Summary use the same identifier. Indexability Reason and badges unchanged.

### 6B: Broken Internal Links URL vs instance counts
- **File:** `src/hype_frog/reporter/engine_rows.py`, `layout.py`
- **Function:** `build_fixplan_rows`
- **Status:** ✅ Done
- **Change summary:** `Affected Count` always counts distinct source URLs. For Broken Internal Links, added `Affected Link Instances` column (sum of per-URL broken link counts).

### 6C: Enrichment ordering before Matched Issues
- **Files:** `enrichment_flow.py`, `assemble.py`
- **Status:** ✅ Fixed
- **Confirmed order:** PSI/GSC harden (phase 3) → link status + broken counts (phase 4) → canonical/links + graph + duplicate signals → **`row_with_aeo_readiness_fields`** → **`row_with_seo_health_enrichment`** (Matched Issues) → composite SEO scores.
- **Fix applied:** `AEO Readiness Score` was previously computed after Matched Issues, so `Low AEO Readiness Score` could not match. Added `row_with_aeo_readiness_fields` before scoring.

**Phase 6 verification (2026-06-26 output):**
- FixPlan vs Summary: **0 mismatches** on shared issue names (AMC run)
- Unit tests: 8/8 pass (`test_fixplan_reconciliation`, `test_fixplan_scope`, `test_scoring`)
- `--quick-test-fast`: PASS

---

## Phase 7 — Click Depth Null Handling

### 7A: Homepage detection and unreachable nodes
- **File:** `src/hype_frog/pipeline/graph_engine.py`
- **Function:** `compute_internal_link_intelligence`
- **Status:** ✅ Done
- **Change summary:** Added `_find_homepage()` (path `/` tolerance + shortest-path fallback). Removed synthetic `https://{source_label}/` homepage that could miss the crawl graph. Unreachable nodes use `CLICK_DEPTH_UNREACHABLE` (`-1`) instead of `None`. `Orphan Pages` remains in-degree based (documented in code). Updated `Deep URL (>3 clicks)` rule to use `Click Depth` (was incorrectly using path-segment `URL Depth`).

**Phase 7 verification (2026-06-27 output):**
- Main sheet Click Depth: **0 null cells** (10/10 populated)
- Homepage: Click Depth **0**
- Unit tests: 5/5 pass (`test_graph_engine`)
- `--quick-test-fast`: PASS

---

## Phase 8 — Duplicate Main Sheet Column Fix

### 8A: Prevent double-append of Technical View / BACK TO DASHBOARD
- **Files:** `src/hype_frog/reporter/sheets/style_helpers.py`, `links.py`, `navigation.py`
- **Status:** ✅ Done
- **Root cause:** `export_flow.py` calls `adjust_sheet_format(writer, "Main")` immediately after Main write **and** again in the final `format_sheets` loop — navigation helpers appended duplicate headers; `normalize_table_headers` renamed them to `_1`.
- **Change summary:** Added `header_exists_in_worksheet()`. `apply_cross_sheet_links` reuses existing `Technical View` column when present (still refreshes row formulas). `add_back_to_dashboard_link` skips when `BACK TO DASHBOARD` already in row 1.

**Phase 8 verification (2026-06-27 output):**
- Main sheet: **0** `_1` suffix columns; **1** `Technical View`, **1** `BACK TO DASHBOARD`
- Main column count: **61** (was 63 on Phase 7 run — 2 duplicate columns removed)
- Unit tests: 2/2 pass (`test_main_sheet_navigation`)
- `--quick-test-fast`: PASS

---

## Test Run Log

| Phase | Run Date | URLs Crawled | Output File | Pass/Fail | Issues Found |
|-------|----------|--------------|-------------|-----------|--------------|
| (baseline) | | | | | |
| 1 | 2026-06-26 | 10 | reports/latest/SEO_AEO_Audit_africanmarketingconfederation.org_20260626_204302.xlsx | PASS | Export blocker fixed (partial extraction + empty FixPlan guard) |
| 2 | 2026-06-26 | 10 | reports/latest/SEO_AEO_Audit_africanmarketingconfederation.org_20260626_210356.xlsx | PASS | PSI URLs show new labels; 7 non-PSI URLs = Not available |
| 3 | 2026-06-26 | 10 | reports/latest/SEO_AEO_Audit_africanmarketingconfederation.org_20260626_211740.xlsx | PASS | IssueInventory aggregates server/site rules; 69 rows |
| 4 | 2026-06-26 | 10 | reports/latest/SEO_AEO_Audit_africanmarketingconfederation.org_20260626_213146.xlsx | PASS | Badge spread 3 Critical / 7 Warning |
| 5 | 2026-06-26 | 10 | reports/latest/SEO_AEO_Audit_africanmarketingconfederation.org_20260626_214233.xlsx | PASS | CMS Action URLs tab present; 0 WooCommerce links on AMC |
| 6 | 2026-06-26 | 10 | reports/latest/SEO_AEO_Audit_africanmarketingconfederation.org_20260626_215138.xlsx | PASS | FixPlan/Summary counts aligned |
| 7 | 2026-06-27 | 10 | reports/latest/SEO_AEO_Audit_africanmarketingconfederation.org_20260626_220041.xlsx | PASS | Click Depth nulls=0 |
| 8 | 2026-06-27 | 10 | reports/latest/SEO_AEO_Audit_africanmarketingconfederation.org_20260626_221411.xlsx | PASS | No Technical View_1 / BACK TO DASHBOARD_1; Main cols=61 |

---

## PSI/Lighthouse Expansion — LI-HF-PSI-P0

### Context map (Step 0 — 2026-06-27)

**`psi_engine.py` key functions:**
- `_build_endpoint` — PSI API URL (`category=performance&category=seo` today; missing accessibility + best-practices)
- `_lab_strategy_metrics` — reads `lighthouseResult.audits` + `categories` for lab scores/LCP/CLS/INP/TTFB
- `_field_experience_metrics` — reads `loadingExperience` (fallback `originLoadingExperience`); sets `crux_data_level` as `"url"`/`"origin"` but does **not** check `origin_fallback` flag or URL id path
- `_merge_url_results` — merges mobile/desktop; writes `CWV LCP (s)` from field data even when origin-level
- `_resolve_cwv_labelling` — Phase 2 audit labels (`PSI + CrUX Field (Origin)` etc.)

**PSI API category parameter (before fix):** `category=performance&category=seo` (`_build_endpoint` ~L253)

**Categories requested (after fix):** performance, accessibility, best-practices, seo ✅ (Part 2, 2026-06-27)

**`lighthouseResult` path:** `payload["lighthouseResult"]["audits"][audit_id]["numericValue"]`; categories at `["categories"][key]["score"]`

**Columns from `lighthouseResult` (lab):** `Desktop/Mobile Score`, `Mobile LCP/CLS/TTFB`, `Lab Mobile/Desktop INP (ms)`, fallback `CWV LCP/CLS/INP` when no field data

**Columns from `loadingExperience` / CrUX (field):** `Field Mobile LCP/CLS/INP`, `CWV LCP (s)`, `CWV CLS`, `CWV INP (ms)`, `Field vs Lab`, `CWV Data Source`, `PSI Data Status`

**`loadingExperience` structure:** `metrics.LARGEST_CONTENTFUL_PAINT_MS.percentile` (ms), `CUMULATIVE_LAYOUT_SHIFT_SCORE.percentile` (hundredths), INP/FID keys; optional `origin_fallback: true` and `id` URL/origin identifier (to be used in Part 1)

**Technical Diagnostics builder:** `merged_builders.py` → `build_technical_diagnostics_rows()`; column list `TECHNICAL_DIAGNOSTICS_COLUMNS` in `export_registry.py`

**`assemble.py` residue:** ~~`row_with_psi_gsc_harden` falls back `CWV LCP (s)` → `Mobile LCP (s)`~~ fixed Part 1 (2026-06-27)

**Known AMC symptom:** ~~`CWV LCP (s)` = 11.852~~ fixed — now in `Origin CrUX LCP (s)`; `CWV LCP (s)` null when `CrUX Level = Origin`

**`_detect_crux_level` implemented:** 2026-06-27

**Part 1 verification (AMC `SEO_AEO_Audit_africanmarketingconfederation.org_20260627_033907.xlsx`):**
- CrUX Level: Origin=3 PSI URLs, None=7 non-PSI
- `CWV LCP (s)`: 0 non-null on PSI rows
- `Origin CrUX LCP (s)`: 11.852 on PSI rows
- `Mobile LCP (s)`: per-URL lab values preserved
- `PSI Data Status`: `PSI + CrUX Field (Origin)` on PSI rows
- Unit tests: 19/19 pass

**Part 2 verification (AMC `SEO_AEO_Audit_africanmarketingconfederation.org_20260627_034808.xlsx`):**
- `_extract_lighthouse_data` + 4-category PSI endpoint implemented
- Main columns: Lighthouse Performance/Lab LCP/TBT/FCP/Page Size populated on 3 PSI URLs
- `Mobile PSI Score` / `Mobile LCP (s)` backward compat preserved (match lab values)
- Accessibility/Best Practices **null on cached PSI responses** (24h cache from pre-Part-2 fetches; clears on next live API call)
- Main column count: **103** (was 61 pre-PSI expansion)
- Unit tests: 18/18 pass (`test_psi_engine`, `test_psi_assemble`)

**Part 3 verification (AMC `SEO_AEO_Audit_africanmarketingconfederation.org_20260627_035636.xlsx`):**
- `PERFORMANCE_CWV_GROUP_COLUMNS` canonical list (52 columns) drives `MAIN_COLUMN_GROUP_DEFINITIONS` and Main `reorder_columns`
- All Part 1–2 Performance/CWV/Lighthouse columns present on Main in monotonic guide order
- Unit tests: 2/2 pass (`test_main_performance_columns`)
**Part 4 verification (AMC `SEO_AEO_Audit_africanmarketingconfederation.org_20260627_040317.xlsx`):**
- Retired old CWV rules; added CrUX Level + Lighthouse lab rules
- `CWV LCP Above 4.0s (Field Data)` IssueInventory: **0** rows
- `Origin CrUX LCP Above 4.0s…` site row: **1** (Affected URL Count=3)
- `Lab LCP Above 4.0s (Mobile)` + `Lab TBT Above 300ms` + `Low Lighthouse Performance Mobile (<50)` present on PSI URLs
- Unit tests: 7/7 pass (`tests/rules/`)

**Part 5 verification (AMC `SEO_AEO_Audit_africanmarketingconfederation.org_20260627_041028.xlsx`):**
- `TECHNICAL_DIAGNOSTICS_LIGHTHOUSE_COLUMNS` (18 cols) appended after `Mobile TTFB (s)`
- Technical Diagnostics: all lighthouse columns present; Origin PSI rows show Lab LCP + Origin CrUX LCP
- Unit tests: 13/13 pass (`test_merged_sheet_builders`, `test_help_layer_tooltips`)
- `--quick-test-fast`: PASS

**Part 6 verification (2026-06-27):**
- `Performance (PSI)` Health row + KPI card now average `Lighthouse Performance (Mobile)` (fallback `Mobile PSI Score`); Desktop excluded
- Health comparison adds `LCP (Lab Mobile avg)` (projected target **2.5 s**) and `Accessibility (avg)` (projected target **90**)
- Chart row count driven by `layout.health_rows` (6 metrics)
- Unit tests: 10/10 pass (`test_executive_dashboard`)

**Part 7 verification (2026-06-27):**
- `finalize_row_state`: string request failures (`Timeout`, `Connection Error`, `DNS Error`, `Error`) now set `Indexability = Not Indexable` and `Indexability Reason = Request {status}`
- Case-insensitive match on string status codes; runs before HTTP `>= 400` branch
- Unit tests: 16/16 pass (`test_data_assembler`, includes 6 parametrized request-failure cases)

**Part 8 verification (2026-06-27):**
- `compute_internal_link_intelligence`: `Reachable from Homepage = (Click Depth != -1)`; `Orphan Pages` in-degree logic unchanged
- Main: column in `PERFORMANCE_CWV_GROUP_COLUMNS` (after `Uses Modern Image Formats`)
- Technical Diagnostics: `Reachable from Homepage` column populated from Main/Extra merge
- Unit tests: graph engine + merged builders + performance column contract pass

### Part status
| Part | Description | Status | Test Passed |
|------|-------------|--------|-------------|
| 1 | CrUX origin detection | ✅ Done | ✅ 2026-06-27 |
| 2 | Lighthouse full extraction | ✅ Done | ✅ 2026-06-27 |
| 3 | New columns in Main | ✅ Done | ✅ 2026-06-27 |
| 4 | Registry rules update | ✅ Done | ✅ 2026-06-27 |
| 5 | Technical Diagnostics update | ✅ Done | ✅ 2026-06-27 |
| 6 | Exec Dashboard source data | ✅ Done | ✅ 2026-06-27 |
| 7 | Timeout indexability fix | ✅ Done | ✅ 2026-06-27 |
| 8 | Orphan/depth distinction | ✅ Done | ✅ 2026-06-27 |

### AMC test results (after all parts)
- CrUX Level distribution: Origin=3, None=7 (Part 1; 3-URL PSI cap)
- Lab LCP (Mobile) on PSI URLs: 7.351, 9.112, 14.257
- Lighthouse Performance (Mobile): 28, 44, 39
- Severity Badge distribution: Critical=10 (Broken Internal Links site-wide; not CWV-driven)
- CWV LCP Above 4.0s (Field Data) rows: **0**
- Lab LCP Above 4.0s (Mobile) rows: **3** PSI URLs in IssueInventory

---

## Top 8 Expansion — Context Map (LI-HF-EXPAND-P0)

| Area | Location |
|------|----------|
| JSON-LD extraction | `src/hype_frog/extractors/schema.py` — `parse_jsonld_summary`, `extract_json_ld_blocks` |
| Schema validation | `src/hype_frog/validators/schema_validator.py` — integrated in `data_assembler.py` |
| Probable Draft rule (legacy) | `src/hype_frog/rules/registry.py` — replaced by thin / near-dup / draft rules |
| Duplicate enrichment (legacy) | `src/hype_frog/pipeline/content_duplicates.py` |
| Simhash near-duplicate pass | `src/hype_frog/analysis/content_similarity.py` — `enrichment_flow.py` |
| BFS queue / checkpoint | `src/hype_frog/orchestration/crawl_runner.py`, `src/hype_frog/checkpoint/store.py` |
| HTTP headers | `src/hype_frog/crawler/fetcher.py` → `Last-Modified`, freshness in `extractors/freshness.py` |
| OG tags | `src/hype_frog/crawler/data_assembler.py` — `resolve_best_og_image_url` |
| Link Inventory builder | `src/hype_frog/reporter/sheets/merged_builders.py` — `build_link_inventory_rows` |
| Main conditional formatting | `src/hype_frog/reporter/sheets/conditional.py` — `apply_main_sheet_heatmaps` |
| Sheet registration | `export_registry.py`, `export_flow.py`, `workbook_layout.py`, `engine_guardrails.py` |
| Main column groups | `src/hype_frog/reporter/sheets/layout.py` — `MAIN_COLUMN_GROUP_DEFINITIONS` |

## Top 8 Expansion — LI-HF-EXPAND-P0

| Part | Description | Status | Test Passed |
|------|-------------|--------|-------------|
| 1 | Schema validation | ✅ Done | ⬜ |
| 2 | E-E-A-T signal capture | ✅ Done | ⬜ |
| 3 | Proper duplicate detection | ✅ Done | ⬜ |
| 4 | Checkpoint/resume (BFS queue) | ✅ Done | ⬜ |
| 5 | Conditional formatting Main | ✅ Done | ⬜ |
| 6 | Quick Wins tab | ✅ Done | ⬜ |
| 7 | Broken Link Impact tab | ✅ Done | ⬜ |
| 8 | Content freshness signals | ✅ Done | ⬜ |

---

## Full Backlog — D4 / D5

### D4 — Status Code Normalisation 🟡 P2

- **File:** `src/hype_frog/core/status_codes.py`
- **Status:** ✅ Done
- **Change summary:** Central helpers (`normalise_status_code`, `is_error_status`, `is_success_status`, etc.) wired into `fetcher.py`, `registry.py` (Non-200 Status), `scoring.py`, and `enrichment_flow.py`. Fixes Timeout/Request Failed treated as success regressions.
- **Tests:** `tests/core/test_status_normalisation.py` — 5 tests pass

### D5 — Test Suite Foundation 🟡 P2

- **Status:** ✅ Done
- **Change summary:** Minimum viable suite under `tests/` mirroring `src/hype_frog/` layout (not `tests/unit/`). Shared fixtures in `tests/fixtures/` (`sample_page.html`, `sample_schema.json`, `sample_psi_response.json`). Parametrised trigger matrix for all registry rules; checkpoint save/load/delete round-trip; E-E-A-T extraction; offline assemble + PSI merge smoke tests.
- **New test files:**
  - `tests/rules/test_registry_rules.py` — all ~67 registry rules
  - `tests/checkpoint/test_store.py` — BFS queue checkpoint round-trip
  - `tests/extractors/test_eeat.py` — author/byline/privacy/terms extraction
  - `tests/integration/test_sample_page_pipeline.py` — assemble + schema + PSI merge
- **Pre-existing (Top 8 / D4):** `tests/validators/test_schema_validator.py`, `tests/analysis/test_content_similarity.py`, `tests/core/test_status_normalisation.py`, `tests/crawler/test_psi_engine.py`
- **Tests:** Full suite **388 passed** (2026-06-27)

### A1 — Open Graph & Social Card Audit 🔴 P1

- **Status:** ✅ Done
- **Files:** `src/hype_frog/extractors/og_social.py`, `src/hype_frog/pipeline/og_image_validation.py`, `data_assembler.py`, `models.py`, `assemble.py`, `registry.py`, `layout.py` (Social Cards group), `enrichment_flow.py`, `run_config.py`, `cli.py`, `main.py` (`--check-og-images`)
- **Change summary:** Full og:* and twitter:* extraction; Main Social Cards column group; OG Completeness Score (0–5); optional async OG image HTTP/dimension validation gated by `--check-og-images` / interactive prompt / `CHECK_OG_IMAGES=1`; eight new registry rules.
- **Tests:** `tests/extractors/test_og_social.py`, `tests/pipeline/test_og_image_validation.py`, registry matrix extended

### C1 — Comprehensive Delta Tracking 🔴 P1

- **Status:** ✅ Done
- **Files:** `src/hype_frog/analysis/delta_engine.py`, `export_flow.py`, `export_registry.py`, `main.py` (`--previous-run`), `crawl_runner.py`
- **Change summary:** Multi-section `DeltaFromPreviousRun` tab (summary, new/resolved issues, metric changes, SEO health trend); compact `_delta_summary.json` auto-saved beside each xlsx; prior run load from JSON sidecar or legacy xlsx.
- **Tests:** `tests/analysis/test_delta_engine.py`, updated `tests/orchestration/test_export_registry_delta.py`

### A3 — Full Redirect Chain Mapping 🔴 P1

- **Status:** ✅ Done
- **Files:** `src/hype_frog/crawler/redirect_chain.py`, `network_engine.py`, `fetcher.py`, `models.py`, `assemble.py`, `registry.py`, `merged_builders.py`, `export_flow.py`, `export_registry.py`, `layout.py`, `workbook_layout.py`, `toc.py`, `engine_guardrails.py`
- **Change summary:** Per-hop redirect capture (301 vs 302) from aiohttp history; Main **Redirects** column group; **Redirect Map** sheet (hop URL/status columns, SEO risk); Redirects tab now written on export; rules for 302, mixed chain, and redirect loop.
- **Tests:** `tests/crawler/test_redirect_chain.py`, registry matrix extended for A3 rules

### B1 — Canonical Chain Tracing 🔴 P1

- **Status:** ✅ Done
- **Files:** `analysis/canonical_chain.py`, `models.py`, `assemble.py`, `enrichment_flow.py`, `registry.py`, `layout.py`
- **Change summary:** Post-crawl canonical graph resolution (depth, chain display, loop/redirect/broken-target flags); Main **Canonical Chain** group; four registry rules.
- **Tests:** `tests/analysis/test_canonical_chain.py`

### B4 — GSC Coverage & Index Status Integration 🔴 P1

- **Status:** ✅ Done
- **Files:** `pipeline/gsc_inspection.py`, `crawler/gsc_engine.py`, `enrichment_flow.py`, `models.py`, `assemble.py`, `registry.py`, `layout.py`, `main.py` (`--gsc-url-inspection`, `--gsc-url-inspection-full`)
- **Change summary:** URL Inspection API gated by CLI (limited 50 URLs or full); B4 Main/GSC columns (`GSC Index Status`, last crawl, mobile usability, rich results, coverage reason, days since crawl); four registry rules. Default runs skip inspection unless flag set.
- **Tests:** `tests/pipeline/test_gsc_inspection.py`, registry matrix extended

### D1 — Memory Management for Large Sites 🔴 P1

- **Status:** ✅ Done (Phase 1 + 3)
- **Files:** `core/memory_guard.py`, `crawl_runner.py`, `run_setup.py`, `main.py` (`--max-memory-mb`, `--streaming`)
- **Change summary:** Cache-first crawl persistence (rows reloaded from SQLite at end); pre-crawl memory estimate warning (>2 GB); optional RSS abort cap; `--streaming` flag for cache-first mode logging.
- **Tests:** `tests/core/test_memory_guard.py`

### A5 — robots.txt Rule Mapping Against Crawled URLs 🟡 P2

- **Status:** ✅ Done
- **Files:** `crawler/robots_mapping.py`, `fetcher.py`, `crawl_runner.py`, `enrichment_flow.py`, `models.py`, `assemble.py`, `registry.py`, `layout.py`, `export_flow.py`, `export_registry.py`
- **Change summary:** Per-URL robots.txt access for Googlebot/Bingbot/GPTBot/ClaudeBot/PerplexityBot; **Robots.txt Analysis** sheet (raw rules, blocked URLs, sitemap conflicts); six registry rules.
- **Tests:** `tests/crawler/test_robots_mapping.py`, registry matrix extended

### D7 — Error Reporting & Crawl Log 🟡 P2

- **Status:** ✅ Done
- **Files:** `core/crawl_log.py`, `fetcher.py`, `crawl_runner.py`, `enrichment_flow.py`, `export_flow.py`, `export_registry.py`
- **Change summary:** **Crawl Log** sheet records fetch/render/extract/intent/PSI/GSC errors and warnings with timestamp, phase, detail, and recovery action.
- **Tests:** `tests/core/test_crawl_log.py`

### A2 — Third-Party Script Inventory 🟡 P2

- **Status:** ✅ Done
- **Files:** `analysis/third_party_scripts.py`, `crawler/psi_engine.py`, `enrichment_flow.py`, `assemble.py`, `export_flow.py`, `registry.py`
- **Change summary:** PSI `network-requests` parsed per URL; Main third-party columns; **Script Inventory** sheet; three registry rules.
- **Tests:** `tests/analysis/test_third_party_scripts.py`

### A4 — Broken / Oversized Image Detection 🟡 P2

- **Status:** ✅ Done
- **Files:** `pipeline/image_inventory.py`, `crawler/data_assembler.py`, `enrichment_flow.py`, `main.py` (`--check-images`), `assemble.py`, `export_flow.py`, `registry.py`
- **Change summary:** Content `<img>` inventory with optional HTTP probe; broken/oversized counts on Main; **Image Inventory** sheet; two registry rules.
- **Tests:** (covered via enrichment/export smoke)

### B2 — Internal Link Equity Distribution 🟡 P2

- **Status:** ✅ Done
- **Files:** `analysis/link_equity.py`, `enrichment_flow.py`, `export_flow.py`, `assemble.py`, `registry.py`
- **Change summary:** PageRank percentile, equity tier, inbound/generic-anchor metrics; **Link Equity Map** and **Anchor Text Audit** sheets; two registry rules.
- **Tests:** `tests/analysis/test_link_equity.py`

### B3 — Featured Snippet & PAA Opportunities 🟡 P2

- **Status:** ✅ Done
- **Files:** `analysis/snippet_opportunities.py`, `enrichment_flow.py`, `assemble.py`, `export_flow.py`
- **Change summary:** Snippet type/readiness scoring, GSC position opportunity flag; **Snippet Opportunities** sheet.
- **Tests:** `tests/analysis/test_snippet_opportunities.py`

### D3 — PSI Request Delay Jitter 🟡 P2

- **Status:** ✅ Done
- **Files:** `crawler/psi_engine.py`, `config_defaults.py`, `main.py` (`--psi-delay`)
- **Change summary:** Jittered spacing between PSI HTTP calls via `_PsiRequestPacer`; retry and mobile/desktop strategy gaps use `_jittered_delay()`; CLI and YAML override for base delay.
- **Tests:** `tests/crawler/test_psi_engine.py` (jitter bounds)

### D6 — Configuration Centralisation 🟢 P3

- **Status:** ✅ Done
- **Files:** `config_defaults.py`, `config_loader.py`, `config.py`; wired into registry, content similarity, freshness, Quick Wins, crawl/PSI pacing
- **Change summary:** Central defaults for thresholds and crawl settings; optional `hype_frog.config.yaml` overrides at project root.
- **Tests:** `tests/config/test_config_loader.py`

### D8 — Dependency Version Pinning & Environment Documentation 🟢 P3

- **Status:** ✅ Done
- **Files:** `pyproject.toml`, `uv.lock`, `README.md`, `CHANGELOG.md`
- **Change summary:** Runtime dependencies pinned to lockfile versions; README documents Python/OS setup, `uv sync`, API keys, YAML config, and PSI delay flag; changelog from LI-HF-AUDIT-P0 baseline.

---

## Governance Sync — Investigation Output

*LI-HF-DOCSYNC-P0 | 27 June 2026 — source of truth for documentation updates.*

### 1.1 Directories under `src/hype_frog/`

Present: `analysis/`, `checkpoint/`, `core/`, `crawler/`, `extractors/`, `orchestration/`, `pipeline/`, `reporter/`, `rules/`, `validators/`. No `junk-drawer` packages. `analysis/` and `validators/` were under-documented in governance.

### 1.2 Rules engine

- `IssueRule` is a frozen `@dataclass` in `rules/registry.py`: `severity`, `name`, `fn`, `scope` (default `"url"`).
- `get_summary_rules()` returns `list[IssueRule]`.
- **99** rules total: **90** `url`, **8** `site`, **1** `server`.
- Site/server scopes aggregate in `summary_builder.py` (`IssueInventory`, `Issue Register`) with `(site-wide)` / `(server config)` labels and `Affected URL Count`.

### 1.3 PSI / CrUX

- API requests all four Lighthouse categories: `performance`, `accessibility`, `best-practices`, `seo` (`_PSI_CATEGORIES`).
- Mobile + desktop strategies; SQLite cache per URL/strategy.
- CrUX URL vs origin via `originLoadingExperience` / `origin_fallback`; `crux_data_level` → `CrUX Level` (`URL` | `Origin`).
- `PSI Data Status` labels include `PSI + CrUX Field (URL)`, `PSI Lab`, `Not available`, etc.
- `PSI_LIGHTHOUSE_EXPORT_KEYS` + `PSI Network Items` / render-blocking URLs exported when PSI runs.

### 1.4 Indexability / status codes

- `finalize_row_state` handles string statuses: `timeout`, `error`, `connection error`, `dns error` → Not Indexable.
- Integer `>= 400` → Not Indexable.

### 1.5 GSC coverage

- When unmatched: `GSC Clicks`, `Impressions`, `CTR`, `Avg Position` → **`None`** (not `0.0`).
- `GSC Coverage Note` still uses `resolve_gsc_coverage_note` with zero impressions/clicks for messaging.

### 1.6 CMS action URL exclusion

- `EXCLUDED_CMS_ACTION_QUERY_PARAMS` in `config_defaults.py`: `add-to-cart`, `removed_item`, `undo_item`, `wc-ajax`, `add_to_wishlist`, `share_token`, `preview_id`, `preview_nonce`, `preview`.
- Applied in `crawl_runner.cms_action_exclusion_keys` for BFS queue and internal-link discovery; excluded URLs surface on **CMS Action URLs** sheet.

### 1.7 Link Inventory dedup

- `build_link_inventory_rows` in `merged_builders.py` dedupes on `(Source URL, Target URL, Anchor Text)`.

### 1.8 Click depth / orphans

- `CLICK_DEPTH_UNREACHABLE = -1` for no path from detected homepage.
- `Orphan Pages` = zero in-degree in crawl graph (distinct from click depth).
- `Reachable from Homepage` = click depth ≠ -1.

### 1.9 Duplicate column prevention

- `header_exists_in_worksheet` in `style_helpers.py`; `navigation.py` guards **BACK TO DASHBOARD**.

### 1.10 Workbook sheets (full-suite)

From `workbook_layout.py` — **visible:** Table of Contents, Dashboard, Executive Dashboard, Summary, Priority URLs, FixPlan, Quick Wins, Content Optimisation Hub, Content Hub Metrics, Main, AIOSEO Recommendations, Link Inventory, Broken Link Impact, SitemapQA, Template & Duplication Risks, Playbook.

**Advanced (hidden by default):** Issue Register, Technical Diagnostics, Content & AI Readiness, Link Intelligence, CMS Action URLs, IssueInventory, Redirects, Redirect Map, Robots.txt Analysis, Crawl Log, Link Equity Map, Anchor Text Audit, Snippet Opportunities, Competitor Benchmarks, Script Inventory, Image Inventory, ResolvedIssues, DeltaFromPreviousRun, Audit Run Details.

### 1.11 Checkpoint

- `checkpoint/store.py` — JSON checkpoint save/load/delete for resume runs.

### 1.12 New modules confirmed

- **validators/** — `schema_validator.py` (JSON-LD validation).
- **analysis/** — canonical chain, hreflang, link equity, third-party scripts, snippet opportunities, topical authority, content similarity, competitor benchmarks, delta engine, content hub recommendations.
- **extractors/** — `eeat.py`, `freshness.py`, semantic engine, OG/social, heading outline.

### 1.13 Pydantic whitelist

- `ENRICHMENT_PIPELINE_DEFAULTS` in `models.py` registers post-crawl keys (A2–A6, B2–B3, B6, PSI network items, content images) so `ExtraRowPayload.model_validate()` does not strip enrichment fields.

### 1.14 Dependencies (`pyproject.toml`)

- Present: `simhash`, `python-dateutil`, `reportlab`, `pyyaml`, `scipy`, `networkx`, `playwright`, Google API clients.
- No `CACHE_VERSION` constant found in codebase.

### 1.15 Tests

- **77** test modules under `tests/` mirroring `src/hype_frog/` layout.

### 1.16 Main columns

- `MAIN_COLUMN_GROUP_DEFINITIONS` in `reporter/sheets/layout.py` (grouped URL, extraction, health, CWV, PSI Lighthouse, GSC, enrichment merges).

### 1.17 Main conditional formatting

- `apply_main_sheet_heatmaps` in `conditional.py`: colour scales on SEO Health, PSI, Lighthouse, AEO scores; inverted scale on Lab LCP; Status Code ≥400 highlight.

### 1.18 FixPlan

- `build_fixplan_rows` in `engine_rows.py` includes **`Affected Link Instances`** (sum of broken/unresolved internal links).

### 1.19 IssueInventory scope

- `summary_builder.py` branches on `rule.scope != "url"` for aggregate rows with `Affected URL Count`.

### 1.20 Quick test

- `--quick-test` / `--quick-test-fast` in `main.py`; preset in `core/quick_test.py` and `core/run_config.py` (10 URLs, BFS depth 2, full suite).

---

## Governance Sync — LI-HF-DOCSYNC-P0

### Investigation completed: 27 June 2026

### Files updated:

- [x] docs/system_architecture.md
- [x] docs/data_contracts.md
- [x] docs/excel_reporting_standards.md
- [x] .cursorrules
- [x] .cursor/rules/architecture.mdc
- [x] .cursor/rules/auto_documentation.mdc
- [x] .cursor/rules/crawler_engine.mdc
- [x] .cursor/rules/excel_engine.mdc
- [x] README.md
- [x] pyproject.toml (version 0.3.0)
- [x] .cursorignore

### Key findings:

- Governance lagged behind `analysis/`, `validators/`, merged diagnostic sheets, enrichment pipeline defaults, and expanded CLI.
- `IssueRule.scope` and GSC `None` semantics were not documented.
- PSI four-category + CrUX origin fallback were implemented but not in architecture docs.

### New directories documented: `analysis/`, `validators/`

### New sheets documented: Technical Diagnostics, Content & AI Readiness, Issue Register, CMS Action URLs, Script/Image Inventory, Snippet Opportunities, Competitor Benchmarks, etc.

### Features NOT found: dedicated `CACHE_VERSION` bump constant; legacy per-tab Technical/Content/AEO sheets are not written in full-suite mode (merged tabs supersede).

