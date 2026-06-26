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
| 6 | FixPlan vs Summary count reconciliation | ⬜ Pending | ⬜ | |
| 7 | Click Depth null handling | ⬜ Pending | ⬜ | |
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

### 6A: Align HTTP 404 / Non-200 Status label mismatch
- **Files:** `src/hype_frog/rules/scoring.py`, `src/hype_frog/reporter/engine_rows.py`
- **Status:** ⬜ Pending

### 6B: Fix Broken Internal Links instance vs URL count
- **File:** `src/hype_frog/reporter/engine_rows.py`
- **Function:** `build_fixplan_rows`
- **Status:** ⬜ Pending

### 6C: Verify enrichment ordering
- **Files:** `src/hype_frog/pipeline/assemble.py`, `src/hype_frog/orchestration/enrichment_flow.py`
- **Status:** ⬜ Pending

---

## Phase 7 — Click Depth Null Handling

### 7A: Improve homepage detection in graph engine
- **File:** `src/hype_frog/pipeline/graph_engine.py`
- **Function:** `compute_internal_link_intelligence` (~line 76)
- **Status:** ⬜ Pending

---

## Phase 8 — Duplicate Main Sheet Column Fix

### 8A: Prevent double-append of Technical View / BACK TO DASHBOARD
- **Files:** `src/hype_frog/reporter/sheets/links.py`, `src/hype_frog/reporter/sheets/navigation.py`
- **Status:** ⬜ Pending

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
| 6 | | | | | |
| 7 | | | | | |
| 8 | | | | | |
