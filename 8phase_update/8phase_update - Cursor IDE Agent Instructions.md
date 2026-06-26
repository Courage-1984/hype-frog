# Hype Frog — Phased Bug-Fix & Quality Improvement Prompt

## Cursor IDE Agent Instructions

---

## CRITICAL RULES — READ BEFORE TOUCHING ANY CODE

1. **Do not refactor anything outside the exact files and functions listed per phase.** No opportunistic cleanup, no renames, no restructuring of unrelated code.
2. **Do not modify any data model / Pydantic schema fields without checking all callers first.** If a field name changes, it must change everywhere it is read and written.
3. **Do not delete any existing column from the output .xlsx.** You may add new columns; never remove or rename existing ones — downstream consumers (formulas, cross-sheet links, client reports) depend on them.
4. **Commit or checkpoint after EACH phase.** Each phase must leave the codebase in a fully runnable state.
5. **Run the test crawl after EVERY phase** before moving on. Instructions are at the bottom of this document.
6. **Create the tracking document (Step 0) before touching any code.**
7. If you encounter something unexpected in any file that contradicts the code map, stop and flag it — do not guess.

---

## STEP 0 — CREATE TRACKING DOCUMENT (do this first, before any code change)

Create a new file at the root of the repository:

**File:** `AUDIT_FIX_LOG.md`

Populate it with the following template exactly:

```markdown
# Hype Frog — Audit Fix Log
**Source audit:** LI-HF-AUDIT-P0 (26 June 2026)
**Test site:** https://africanmarketingconfederation.org/page-sitemap.xml

---

## Phase Status

| Phase | Title | Status | Test Passed | Notes |
|-------|-------|--------|-------------|-------|
| 0 | Tracking document created | ✅ Done | N/A | |
| 1 | Isolated function fixes (3 bugs) | ⬜ Pending | ⬜ | |
| 2 | CrUX origin data labelling | ⬜ Pending | ⬜ | |
| 3 | Site-level vs URL-level issue scope | ⬜ Pending | ⬜ | |
| 4 | CWV severity cascade fix | ⬜ Pending | ⬜ | |
| 5 | WooCommerce / parameter URL filtering | ⬜ Pending | ⬜ | |
| 6 | FixPlan vs Summary count reconciliation | ⬜ Pending | ⬜ | |
| 7 | Click Depth null handling | ⬜ Pending | ⬜ | |
| 8 | Duplicate Main sheet column fix | ⬜ Pending | ⬜ | |

---

## Phase 1 — Isolated Function Fixes

### 1A: 404 pages showing Indexability = "Indexable"
- **File:** `src/hype_frog/crawler/data_assembler.py`
- **Function:** `finalize_row_state` (~line 716)
- **Status:** ⬜ Pending
- **Change summary:** (agent fills in after implementation)

### 1B: GSC unavailable writes 0.0 instead of None
- **File:** `src/hype_frog/pipeline/gsc_coverage.py`
- **Function:** `apply_gsc_coverage_fields` (~line 89)
- **Status:** ⬜ Pending
- **Change summary:** (agent fills in after implementation)

### 1C: Link Inventory has duplicate source→target rows
- **File:** `src/hype_frog/reporter/sheets/merged_builders.py`
- **Function:** `build_link_inventory_rows` (~line 655)
- **Status:** ⬜ Pending
- **Change summary:** (agent fills in after implementation)

---

## Phase 2 — CrUX Origin Data Labelling

### 2A: _field_experience_metrics origin detection
- **File:** `src/hype_frog/crawler/psi_engine.py`
- **Function:** `_field_experience_metrics` (~line 204)
- **Status:** ⬜ Pending

### 2B: CWV Data Source / PSI Data Status / Field vs Lab consistency
- **File:** `src/hype_frog/crawler/psi_engine.py`
- **Function:** values written at ~line 434-496
- **Status:** ⬜ Pending

### 2C: Propagation in assemble.py
- **File:** `src/hype_frog/pipeline/assemble.py`
- **Function:** `row_with_psi_gsc_harden` (~line 275)
- **Status:** ⬜ Pending

---

## Phase 3 — Site-level vs URL-level Issue Scope

### 3A: Add scope metadata to registry rules
- **File:** `src/hype_frog/rules/registry.py`
- **Function:** `get_summary_rules`
- **Status:** ⬜ Pending

### 3B: Branch on scope in IssueInventory builder
- **File:** `src/hype_frog/reporter/summary_builder.py`
- **Function:** `build_issue_inventory_rows`
- **Status:** ⬜ Pending

### 3C: Branch on scope in FixPlan builder
- **File:** `src/hype_frog/reporter/engine_rows.py`
- **Function:** `build_fixplan_rows`
- **Status:** ⬜ Pending

---

## Phase 4 — CWV Severity Cascade Fix

### 4A: Guard CWV rules against origin-level data
- **File:** `src/hype_frog/rules/registry.py`
- **Function:** CWV rules in `get_summary_rules`
- **Status:** ⬜ Pending

### 4B: Verify scoring.py needs no change
- **File:** `src/hype_frog/rules/scoring.py`
- **Function:** `score_url_health`
- **Status:** ⬜ Pending (confirm only)

---

## Phase 5 — WooCommerce / Parameter URL Filtering

### 5A: Add parameter exclusion to crawl candidate filter
- **File:** `src/hype_frog/orchestration/crawl_runner.py`
- **Function:** `_is_crawlable_html_candidate` (~line 85)
- **Status:** ⬜ Pending

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
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |
| 6 | | | | | |
| 7 | | | | | |
| 8 | | | | | |
```

Update AUDIT_FIX_LOG.md with actual implementation details and test results as you complete each phase.

---
---

## PHASE 1 — Isolated Function Fixes

These are three independent, low-risk bug fixes in well-isolated functions. All three can be done before running the Phase 1 test crawl.

---

### 1A — Fix: 404 pages marked "Indexable"

**Root cause (confirmed from code map):**
`finalize_row_state` in `data_assembler.py` writes `Indexability Reason = "HTTP 404"` correctly but never updates `main_values["Indexability"]` — that column is only set by `resolve_indexability_directive`, which only checks meta robots and X-Robots-Tag, not the HTTP status code.

**File:** `src/hype_frog/crawler/data_assembler.py`
**Function:** `finalize_row_state` (~lines 716-739)

**What to do:**
Inside `finalize_row_state`, after the block that appends `f"HTTP {status_int}"` to `indexability_reasons` (when `status_int >= 400`), also update the main row's `Indexability` field to `"Not Indexable"`:

```python
if status_int is not None and status_int >= 400:
    indexability_reasons.append(f"HTTP {status_int}")
    main_data["Indexability"] = "Not Indexable"  # ADD THIS LINE
```

Read the exact structure of `main_data` at that point. If it is a Pydantic model, use attribute assignment instead of dict key assignment. The value must be `"Not Indexable"` to match whatever the rest of the code expects — check what string the noindex path uses and be consistent.

**Do NOT touch** `resolve_indexability_directive` in `robots.py`. The fix belongs only in `finalize_row_state`.

**Verify:** After the fix, `Indexability = "Indexable"` must never appear for any URL with Status Code >= 400.

---

### 1B — Fix: GSC unavailable writes 0.0 instead of None/blank

**Root cause (confirmed from code map):**
`apply_gsc_coverage_fields` in `gsc_coverage.py` (lines 89-134) has an `else` branch that writes `0.0` to GSC columns when no GSC data is available. `0.0` is indistinguishable from "we checked and found zero traffic".

**File:** `src/hype_frog/pipeline/gsc_coverage.py`
**Function:** `apply_gsc_coverage_fields` (~lines 89-134)

**What to do:**
In the `else` branch (when GSC is unavailable), change the hardcoded `0.0` values to `None`:

```python
# BEFORE:
row_values["GSC Clicks"] = 0.0
row_values["GSC Impressions"] = 0.0
row_values["GSC CTR"] = 0.0
row_values["GSC Avg Position"] = 0.0

# AFTER:
row_values["GSC Clicks"] = None
row_values["GSC Impressions"] = None
row_values["GSC CTR"] = None
row_values["GSC Avg Position"] = None
```

**IMPORTANT — check all downstream callers BEFORE changing:**

Search the entire codebase for all references to `"GSC Clicks"`, `"GSC Impressions"`, `"GSC CTR"`, `"GSC Avg Position"` in Python files. Check specifically:

1. `_safe_clicks` in `src/hype_frog/core/scoring.py` (~line 64) — the code map shows it returns `0` if `numeric is None`. Verify it handles Python `None` input (not just `0.0`). If it does `int(value)` without a None check, it will raise `TypeError`. Confirm and fix `_safe_clicks` if necessary.

2. `calculate_executive_roi` in `src/hype_frog/reporter/engine_rows.py` (~line 592) — passes `clicks_raw` through `_safe_clicks`. Once `_safe_clicks` handles None, this should propagate cleanly.

3. Any sort, comparison (`<`, `>`, arithmetic) using these column values anywhere — `None` in a numeric comparison raises TypeError in Python. Add `or 0` guards where needed.

If any caller cannot be safely patched to handle `None`, make that caller treat `None` as `0` or skip the computation — do NOT revert the `None` write. The goal is blank cells in xlsx, not `0`.

Also check `GSC Data Freshness` — if it is currently set to an empty string in the else branch, change to `None`.

---

### 1C — Fix: Link Inventory has duplicate source→target rows

**Root cause (confirmed from code map):**
`build_link_inventory_rows` in `merged_builders.py` (lines 655-687) iterates every anchor in `Link Details` with no deduplication. A link in nav + footer + body generates 3 identical rows.

**File:** `src/hype_frog/reporter/sheets/merged_builders.py`
**Function:** `build_link_inventory_rows` (~lines 655-687)

**What to do:**
Read `LINK_INVENTORY_COLUMNS` in this file first to get the exact column name strings. Then add a deduplication pass at the end of the function using the exact column names for Source URL, Target URL, and Anchor Text:

```python
# After building the full rows list, before returning:
seen_keys: set[tuple] = set()
deduped: list[dict] = []
for row in rows:
    key = (
        row.get("Source URL"),    # use exact column name from LINK_INVENTORY_COLUMNS
        row.get("Target URL"),    # use exact column name
        row.get("Anchor Text"),   # use exact column name
    )
    if key not in seen_keys:
        seen_keys.add(key)
        deduped.append(row)
return deduped
```

Keep the first occurrence of each key. Do not deduplicate on Status Code — a link pair found multiple times with different status codes should keep the first occurrence (the crawler's first resolved result).

---

### After Phase 1 — Run Test Crawl (see TEST CRAWL section)

**Verify in the Phase 1 output sheet:**
- Main sheet: no 404-status URL has `Indexability = "Indexable"`.
- Main sheet: GSC Clicks/Impressions/CTR/Position columns show blank cells (not `0`) when GSC was not connected. (For AMC with OAuth, these should show real values.)
- Dashboard: `Total Potential Traffic Lift` shows a real value for AMC (not 0 from None — `_safe_clicks` should return 0 for None so the ROI calc still works).
- Link Inventory: no duplicate rows with identical Source URL + Target URL + Anchor Text.

---
---

## PHASE 2 — CrUX Origin Data Labelling

Goal: When the PSI API falls back to origin-level `originLoadingExperience`, the CWV Data Source, PSI Data Status, and Field vs Lab columns must reflect this explicitly. No CWV rule changes yet — that is Phase 4.

---

### 2A — Fix: Detect and label origin CrUX fallback

**File:** `src/hype_frog/crawler/psi_engine.py`
**Function:** `_field_experience_metrics` (~line 204)

**Current code:**
```python
exp = payload.get("loadingExperience") or payload.get("originLoadingExperience")
```
This silently falls back to origin data. The caller has no way to know which was used.

**What to do:**
Modify `_field_experience_metrics` (or its immediate caller in `_merge_url_results`) to track which source was used. The minimal approach: add a key `"crux_data_level"` to the returned metrics dict:

```python
used_origin = False
exp = payload.get("loadingExperience")
if not exp:
    exp = payload.get("originLoadingExperience")
    used_origin = bool(exp)

# ... rest of function ...

# Before returning metrics dict:
metrics["crux_data_level"] = "origin" if used_origin else "url"
return metrics
```

Read the full function before implementing — do not assume the structure. The `crux_data_level` key will be consumed in Phase 2B.

---

### 2B — Fix: CWV Data Source / PSI Data Status / Field vs Lab must be consistent

**File:** `src/hype_frog/crawler/psi_engine.py`
**Relevant lines:** ~434-496 (where these fields are assembled into the merged flat dict)

**Current broken state:** When no PSI key is configured and origin CrUX fires as fallback:
- `Field vs Lab = "Field"` (because `has_field = True` when origin data exists)
- `PSI Data Status = "Not measured"` (because PSI lab was not run)
- These contradict each other. Neither says "origin-level".

**New labelling rules — implement these exactly:**

| Condition | PSI Data Status | Field vs Lab | CWV Data Source |
|-----------|-----------------|--------------|-----------------|
| No PSI key, URL-level CrUX available | `"CrUX Field (URL)"` | `"Field"` | `"CrUX API (URL-level)"` |
| No PSI key, only origin CrUX available | `"CrUX Field (Origin)"` | `"Field (Origin)"` | `"CrUX API (Origin-level)"` |
| PSI key present, lab data fetched | `"PSI Lab"` | `"Lab"` | `"PSI API (Lighthouse)"` |
| PSI key present, URL CrUX also available | `"PSI + CrUX Field (URL)"` | `"Field"` | `"PSI API (CrUX)"` |
| No PSI key, no CrUX data at all | `"Not available"` | `"N/A"` | `"None"` |

The critical requirement: the word `"Origin"` must appear in `CWV Data Source` whenever origin CrUX is the source. Phase 4 will use `"Origin" in row.get("CWV Data Source", "")` as its guard condition in rule lambdas.

**Do NOT rename the column headers** — `PSI Data Status`, `Field vs Lab`, and `CWV Data Source` must remain those exact strings.

---

### 2C — Fix: Propagation in assemble.py

**File:** `src/hype_frog/pipeline/assemble.py`
**Function:** `row_with_psi_gsc_harden` (~lines 275-333)

Check that the new label strings from 2B pass through this merge function correctly. Specifically:
- Find any hardcoded fallback values like `psi.get("Field vs Lab", "Lab")` — update the fallback string to match the new vocabulary from 2B.
- Confirm `"CWV Data Source"` is included in the merged dict. If it is not, add it.
- Confirm `"CWV LCP (s)"` and `"CWV CLS"` numeric values are unchanged — only the metadata labels are changing.
- Check if `"CWV Data Source"` is listed in `MAIN_COLUMN_GROUP_DEFINITIONS` (in layout.py or equivalent). If not, add it adjacent to `"Field vs Lab"`.

---

### After Phase 2 — Run Test Crawl

**Verify in the Phase 2 output:**
- For AMC URLs with URL-level CrUX: `CWV Data Source` does NOT contain `"Origin"`. `PSI Data Status = "CrUX Field (URL)"` or `"PSI Lab"` depending on key.
- For any URL where only origin CrUX was the fallback: `"Origin"` appears in `CWV Data Source` and `Field vs Lab`.
- `CWV LCP (s)` and `CWV CLS` numeric values are still present and accurate.
- No existing column removed or renamed.

---
---

## PHASE 3 — Site-level vs URL-level Issue Scope

Goal: Add a `scope` field to issue rules so that server/site-wide issues generate one aggregate row in IssueInventory, not N identical per-URL rows. This is the most architecturally significant change — be extra careful.

---

### 3A — Add scope metadata to registry rules

**File:** `src/hype_frog/rules/registry.py`
**Function:** `get_summary_rules` (~lines 18-56)

**Before changing anything:** Search the entire codebase for every caller of `get_summary_rules()`. Expected callers: `scoring.py`, `summary_builder.py`, `engine_rows.py`, possibly `assemble.py`. List them in `AUDIT_FIX_LOG.md`.

**Approach — use a dataclass to avoid breaking existing 3-tuple unpackers:**

```python
from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass(frozen=True)
class IssueRule:
    severity: str
    name: str
    fn: Callable[[dict[str, Any]], bool]
    scope: str = "url"  # values: "url" | "site" | "server" | "template"
```

Change `get_summary_rules` to return `list[IssueRule]`. Update all callers to use attribute access (`.severity`, `.name`, `.fn`, `.scope`) instead of tuple unpacking. Do this in Phase 3A — do not leave any caller using old tuple unpacking syntax.

**Scope assignments for this phase:**

| Issue Name | Scope |
|---|---|
| `"No ETag Header"` | `"server"` |
| `"AI Crawlers Not Explicitly Allowed"` | `"site"` |
| `"CWV LCP Above 4.0s"` | `"url"` (Phase 4 adds the origin guard) |
| `"INP Above 100ms"` | `"url"` (Phase 4) |
| `"CLS Above 0.1"` | `"url"` (Phase 4) |
| All other rules | `"url"` |

Do NOT change CWV rules to `"site"` scope in Phase 3. They stay `"url"` here.

---

### 3B — Branch on scope in IssueInventory builder

**File:** `src/hype_frog/reporter/summary_builder.py`
**Function:** `build_issue_inventory_rows` (~lines 192-236)

**New behaviour for rules where `rule.scope != "url"`:**
- Do NOT emit one row per matching URL.
- Emit exactly ONE aggregate row with:
  - `"URL"`: `"(site-wide)"` for scope `"site"`, `"(server config)"` for scope `"server"`
  - `"Issue"`: `rule.name`
  - `"Severity"`: `rule.severity`
  - Add a new column `"Affected URL Count"` to this row dict with the count of matching URLs. Check `ISSUE_INVENTORY_COLUMNS` in the codebase — if `"Affected URL Count"` is not already a column, add it. If adding it, also add it to the IssueInventory sheet column list in the export configuration.
  - `"Stable Issue ID"`: `stable_issue_id("site", rule.name)` or equivalent — check the function signature.

**For `scope == "url"` rules:** behaviour is completely unchanged.

---

### 3C — FixPlan builder: document scope in FixPlan rows

**File:** `src/hype_frog/reporter/engine_rows.py`
**Function:** `build_fixplan_rows` (~lines 256-267)

FixPlan already emits one row per issue (not per URL), so the IssueInventory problem does not apply here. The main change in 3C is:

- For rules where `rule.scope == "server"` or `rule.scope == "site"`, set `Resolution Type` in the FixPlan row to `"Server Config"` or `"Site Config"` respectively. Check the existing `Resolution Type` values used elsewhere in FixPlan and match the vocabulary.
- The `affected_count` calculation is unchanged — it still counts matching URLs.

---

### After Phase 3 — Run Test Crawl

**Verify in Phase 3 output:**
- IssueInventory: `"No ETag Header"` appears as ONE row with `URL = "(server config)"` and an `Affected URL Count` column showing the correct number of affected URLs.
- IssueInventory: `"AI Crawlers Not Explicitly Allowed"` similarly has ONE row.
- All per-URL issues (Missing Title, Multiple H1, etc.) still have one row per affected URL.
- Summary sheet: `"No ETag Header"` and `"AI Crawlers Not Explicitly Allowed"` counts are identical to pre-Phase 3 (the Summary re-runs rule lambdas independently, so it should be unaffected).
- Total IssueInventory row count has dropped significantly compared to Phase 2 output.

---
---

## PHASE 4 — CWV Severity Cascade Fix

Goal: CWV rules should not fire on per-URL severity badges when the underlying data is origin-level CrUX. Depends on Phase 2 (origin labelling) and Phase 3 (scope infrastructure) being complete and tested.

Before starting Phase 4: open the Phase 3 test output and verify that `CWV Data Source` contains `"Origin"` for any URL where origin CrUX was the fallback. If it does not, Phase 2 did not propagate correctly — go back before continuing.

---

### 4A — Add origin-aware guard to CWV registry rules

**File:** `src/hype_frog/rules/registry.py`
**Function:** `get_summary_rules`

**Replace the three CWV rules** with origin-guarded versions:

```python
IssueRule(
    severity="Critical",
    name="CWV LCP Above 4.0s",
    fn=lambda r: (
        (r.get("CWV LCP (s)") or 0) > 4.0
        and "Origin" not in (r.get("CWV Data Source") or "")
    ),
    scope="url",
),
IssueRule(
    severity="Observation",
    name="CLS Above 0.1",
    fn=lambda r: (
        (r.get("CWV CLS") or 0) > 0.1
        and "Origin" not in (r.get("CWV Data Source") or "")
    ),
    scope="url",
),
IssueRule(
    severity="Observation",
    name="INP Above 100ms",
    fn=lambda r: (
        (r.get("CWV INP (ms)") or 0) > 100
        and "Origin" not in (r.get("CWV Data Source") or "")
    ),
    scope="url",
),
```

Also add three new site-scoped rules for the origin-CrUX case (so the information is not lost — it just becomes a site-level note rather than per-URL Critical):

```python
IssueRule(
    severity="Observation",
    name="CWV LCP Above 4.0s (Origin CrUX — Run PSI Pass for Per-URL Data)",
    fn=lambda r: (
        (r.get("CWV LCP (s)") or 0) > 4.0
        and "Origin" in (r.get("CWV Data Source") or "")
    ),
    scope="site",
),
IssueRule(
    severity="Observation",
    name="CLS Above 0.1 (Origin CrUX — Run PSI Pass for Per-URL Data)",
    fn=lambda r: (
        (r.get("CWV CLS") or 0) > 0.1
        and "Origin" in (r.get("CWV Data Source") or "")
    ),
    scope="site",
),
IssueRule(
    severity="Observation",
    name="INP Above 100ms (Origin CrUX — Run PSI Pass for Per-URL Data)",
    fn=lambda r: (
        (r.get("CWV INP (ms)") or 0) > 100
        and "Origin" in (r.get("CWV Data Source") or "")
    ),
    scope="site",
),
```

Because these new rules have `scope="site"`, Phase 3's IssueInventory branching will automatically collapse them to single aggregate rows.

---

### 4B — Scoring.py: confirm no change needed

Open `src/hype_frog/rules/scoring.py` and read `score_url_health`. Confirm:
- It calls `rule.fn(row)` (using the IssueRule attribute, not tuple unpacking — Phase 3A should have updated this already).
- Badge logic: `if matched["Critical"]: badge = "Critical"` — this is correct. With the origin guard in place, URLs with only origin CrUX data will not match the "CWV LCP Above 4.0s" rule, so they won't get Critical from CWV.
- No changes needed here. Document "confirmed no change required" in AUDIT_FIX_LOG.md.

---

### After Phase 4 — Run Test Crawl

**Verify in Phase 4 output:**
- Severity badge distribution: must no longer be 100% Critical. Expect a genuine spread across Critical/Warning/Observation for the AMC site.
- For AMC URLs with actual per-URL PSI/CrUX data: if LCP > 4.0s for a specific URL, it should still show Critical for that URL.
- IssueInventory: the three "CWV ... (Origin CrUX — Run PSI Pass)" issues each appear as ONE site-level aggregate row (if AMC returns any origin-level data).
- Executive Dashboard: Critical URL count is a realistic number, not equal to total URL count.

---
---

## PHASE 5 — WooCommerce / Parameter URL Filtering

Goal: Prevent WooCommerce action parameter URLs (`?add-to-cart=`, etc.) from being crawled as distinct pages.

---

### 5A — Add configurable parameter exclusion to crawl candidate filter

**File:** `src/hype_frog/orchestration/crawl_runner.py`

**First:** Read `_is_crawlable_html_candidate` in full (~line 85). Read `_candidate_internal_links` (~line 116). Read `_NON_HTML_PATH_EXTENSIONS` — understand the current filter model before adding to it.

**Check for existing config file:** Look for `config.yaml`, `settings.py`, `crawl_config.py`, or similar at the project root or in a `config/` directory. If a configurable exclusion mechanism already exists, add the new parameters there rather than hardcoding. Document your finding in AUDIT_FIX_LOG.md.

**If no config mechanism exists, add the following at module level in `crawl_runner.py`**, near `_NON_HTML_PATH_EXTENSIONS`:

```python
_EXCLUDED_QUERY_PARAMS: frozenset[str] = frozenset({
    "add-to-cart",
    "removed_item",
    "undo_item",
    "wc-ajax",
    "add_to_wishlist",
    "share_token",
    "preview_id",
    "preview_nonce",
    "preview",
})
```

**Modify `_is_crawlable_html_candidate`:**

```python
def _is_crawlable_html_candidate(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    path = parsed.path.lower()
    # Existing extension block (do not change):
    if any(path.endswith(ext) for ext in _NON_HTML_PATH_EXTENSIONS):
        return False
    # NEW: block CMS action query parameters:
    if parsed.query:
        from urllib.parse import parse_qs
        query_keys = set(parse_qs(parsed.query).keys())
        if query_keys & _EXCLUDED_QUERY_PARAMS:
            return False
    return True
```

**Do NOT add** `_wp_link_placeholder` to the exclusion list — it is a path token, not a query param, and it's already handled by returning 404.

**Safe parameters that must NOT be blocked:** `page`, `lang`, `language`, `category`, `tag`, `s` (WordPress search), `paged`, `orderby`, `order`, `product_cat`, `filter_color`, `filter_size`. These are content-disambiguating parameters.

---

### After Phase 5 — Run Test Crawl

**Verify:**
- If AMC uses WooCommerce with add-to-cart links: no `?add-to-cart=` URLs appear in Main sheet.
- If AMC does not use WooCommerce: URL count is unchanged from Phase 4 run.
- Real paginated URLs (e.g. `?page=2`) still appear in the crawl.
- No legitimate content pages are missing from the output.

---
---

## PHASE 6 — FixPlan vs Summary Count Reconciliation

Goal: Make FixPlan `Affected Count` match Summary `Affected URL Count` for the same issue name across all issues.

---

### 6A — Fix "HTTP 404 Not Found" vs "Non-200 Status" label mismatch

**Root cause (from code map):**
- `score_url_health` in `scoring.py` (line ~22) adds `"HTTP 404 Not Found"` to `matched["Critical"]` via the early-return path for 404 status.
- Registry has a rule named `"Non-200 Status"` (line ~18).
- `build_fixplan_rows` looks for `"Non-200 Status"` in `Matched Issues` strings — but the string contains `"HTTP 404 Not Found"` — so FixPlan can't count these URLs.
- `build_issue_inventory_rows` splits `Matched Issues` and uses whatever is in there — so IssueInventory uses `"HTTP 404 Not Found"`.
- Summary re-runs the rule lambda directly — correct.

**Fix (Option A — least invasive):**
In `score_url_health` in `scoring.py` (~line 22-28), change the 404 early-return so the string added to `matched["Critical"]` matches the registry rule name:

```python
# BEFORE:
if status_code == 404:
    return (0, "Critical", "FAIL 🔴", {"Critical": ["HTTP 404 Not Found"], ...})

# AFTER:
if status_code == 404:
    return (0, "Critical", "FAIL 🔴", {"Critical": ["Non-200 Status"], ...})
```

Check if `"HTTP 404 Not Found"` appears anywhere else in the codebase (Summary labels, client-facing text, FixPlan row text). If it does, leave those references alone — only change the `Matched Issues` string used for counting. The Severity Badge and Indexability Reason strings can keep saying "HTTP 404 Not Found" — only the `Matched Issues` field used for counting must say `"Non-200 Status"`.

---

### 6B — Fix "Broken Internal Links" instance vs URL count

**Root cause (from code map):**
`build_fixplan_rows` for `"Broken Internal Links"` sums `Broken Internal Links Count` (link instances) across affected URLs, rather than counting distinct source URLs.

**File:** `src/hype_frog/reporter/engine_rows.py`
**Function:** `build_fixplan_rows` (~lines 256-267)

**What to do:**
Change the special-case logic for `"Broken Internal Links"` to count distinct source URLs:

```python
# BEFORE:
if issue_name == "Broken Internal Links":
    affected_count = sum(
        int(r.values.get("Broken Internal Links Count") or 0) for r in affected
    )
else:
    affected_count = len(affected)

# AFTER:
affected_count = len(affected)  # Always count distinct source URLs

# If the instance count is useful, add it as a separate field:
if issue_name == "Broken Internal Links":
    instance_count = sum(
        int(r.values.get("Broken Internal Links Count") or 0) for r in affected
    )
    # Add to the FixPlan row dict if "Affected Link Instances" is not already a column:
    fixplan_row["Affected Link Instances"] = instance_count
```

Check `FIXPLAN_COLUMNS` in the codebase before adding a new column. If `"Affected Link Instances"` would be a new column, add it to the column list and the export configuration.

---

### 6C — Verify enrichment ordering (audit only, fix if needed)

**Files:** `src/hype_frog/pipeline/assemble.py`, `src/hype_frog/orchestration/enrichment_flow.py`

Read the call order in the pipeline — specifically: is `row_with_seo_health_enrichment` (which writes `Matched Issues`) called AFTER `row_with_psi_gsc_harden` (which writes PSI/CWV data)? If any enrichment data that feeds into rule lambdas is added after `Matched Issues` is written, then `Matched Issues` will be incomplete.

Confirm the order and document it in `AUDIT_FIX_LOG.md`. If the order is wrong, reorder the calls so all data enrichment happens before `Matched Issues` is computed. If the order is correct, document "confirmed correct order" and make no code changes.

---

### After Phase 6 — Run Test Crawl

**Verify:**
- For every issue in the FixPlan: `Affected Count` must equal `Affected URL Count` in Summary for the same issue name.
- `"Non-200 Status"` in FixPlan now correctly shows the count of 4xx/5xx URLs.
- `"Broken Internal Links"` in FixPlan now shows source URL count, not link instance sum.

---
---

## PHASE 7 — Click Depth Null Handling

Goal: Eliminate null values in Click Depth so the "Deep URL (>3 clicks)" warning is reliable for all URLs.

---

### 7A — Improve homepage detection and handle unreachable nodes

**File:** `src/hype_frog/pipeline/graph_engine.py`
**Function:** `compute_internal_link_intelligence` (~lines 76-92)

**Root cause (from code map):** If the homepage URL is not found in `crawled_urls` (due to normalization mismatch), `homepage_candidates` is empty. The `nx.single_source_shortest_path_length` call is skipped, and all nodes get `click_depth[node] = None`.

**Step 1:** Read the URL normalization function used before URLs enter `crawled_urls`. Confirm whether `https://example.com/` and `https://example.com` are the same key. Also check if trailing slashes are stripped.

**Step 2:** Replace the homepage detection with a more robust version:

```python
def _find_homepage(crawled_urls: list[str]) -> str | None:
    """Find the homepage URL using path matching with trailing-slash tolerance."""
    for u in crawled_urls:
        p = urlparse(u)
        if p.path in {"", "/", "//"}:
            return u
    # Fallback: the shortest crawled URL is usually the root
    if crawled_urls:
        return min(crawled_urls, key=lambda u: (len(urlparse(u).path), len(u)))
    return None

homepage = _find_homepage(list(crawled_urls))
```

**Step 3:** For nodes unreachable from the homepage (or when no homepage exists), assign `Click Depth = -1` instead of `None`:

```python
if homepage and homepage in graph:
    lengths = nx.single_source_shortest_path_length(graph, homepage)
    for node in graph.nodes:
        click_depth[node] = lengths.get(node, -1)  # -1 = orphan (unreachable)
else:
    for node in graph.nodes:
        click_depth[node] = -1  # no homepage found — all orphan
```

**Step 4:** Check where `Orphan Pages` flag is set in the codebase. Confirm that `click_depth == -1` maps to `Orphan Pages = True`. If orphan detection uses a different mechanism, leave it — but add a comment explaining the `-1` convention.

**Do NOT change** the "Deep URL (>3 clicks)" rule lambda — `(r.get("Click Depth") or 0) > 3` already correctly evaluates to `False` for `-1` (since `-1 > 3` is False). Confirm this.

---

### After Phase 7 — Run Test Crawl

**Verify:**
- `Click Depth` column: zero null cells.
- Orphan pages: `Click Depth = -1`, `Orphan Pages = True`.
- "Deep URL (>3 clicks)" fires only for URLs with `Click Depth >= 4`.
- Homepage URL: `Click Depth = 0`.

---
---

## PHASE 8 — Duplicate Main Sheet Column Fix

Goal: Remove the `Technical View_1` and `BACK TO DASHBOARD_1` duplicate columns from the Main sheet.

---

### 8A — Prevent double-append of navigation columns

**Files to read FIRST (all three, in full):**
- `src/hype_frog/reporter/sheets/links.py` — `apply_cross_sheet_links` (~line 190)
- `src/hype_frog/reporter/sheets/navigation.py` — `add_back_to_dashboard_link` (~line 22)
- `src/hype_frog/reporter/sheets/tables.py` — `normalize_table_headers` (~line 18)
- `layout.py` (or wherever `MAIN_COLUMN_GROUP_DEFINITIONS` is defined) — check what columns it lists

**Root cause (from code map):**
`apply_cross_sheet_links` unconditionally appends "Technical View" as a new column in row 1. `MAIN_COLUMN_GROUP_DEFINITIONS` already lists "Technical View". When `normalize_table_headers` runs and finds two cells in row 1 with value "Technical View", it renames the second one to "Technical View_1". Same for "BACK TO DASHBOARD".

**Fix — add a column-existence check before appending:**

Add a helper (in a shared utility module if one exists, otherwise in-file):

```python
def _header_exists_in_worksheet(worksheet, header_name: str) -> bool:
    """Return True if header_name already exists in row 1 of worksheet."""
    for cell in worksheet[1]:
        if cell.value == header_name:
            return True
    return False
```

In `apply_cross_sheet_links` (~line 190), before appending "Technical View":

```python
if sheet_name == "Main":
    url_col = headers.get("URL")
    if url_col and not _header_exists_in_worksheet(worksheet, "Technical View"):
        target_col = worksheet.max_column + 1
        worksheet.cell(row=1, column=target_col, value="Technical View")
        # ... rest of link-writing code
```

In `add_back_to_dashboard_link` (~line 22), before appending "BACK TO DASHBOARD":

```python
if not _header_exists_in_worksheet(worksheet, "BACK TO DASHBOARD"):
    target_col = worksheet.max_column + 1
    target_ref = f"{get_column_letter(target_col)}1"
    worksheet[target_ref] = "BACK TO DASHBOARD"
    # ... rest of link-writing code
```

**IMPORTANT:** Before implementing, confirm that the cross-sheet link values (hyperlinks under "Technical View") and the BACK TO DASHBOARD links are being written to the correct rows even with this guard. The guard only skips appending the header in row 1 — the hyperlinks in data rows must still be written. Read the full implementations carefully; the row-1 append and the data-row link-writing may be in the same block or separate blocks.

If they are in the same block (header append + data row links together), you must split the logic so:
- Header append is guarded (skip if already exists)
- Data-row link writing still happens regardless of whether the header was appended, because the column already exists at the correct position

---

### After Phase 8 — Final Test Crawl

**Verify:**
- Main sheet: no columns with `_1` suffix.
- Column count matches Phase 7 output minus 2 (the two duplicate columns removed).
- Cross-sheet "Technical View" links in Main → Technical Diagnostics still work (click one, confirm navigation).
- "BACK TO DASHBOARD" links still work.
- All other sheets are unaffected.
- Export and open in both Excel and LibreOffice to confirm visual rendering.

---
---

## TEST CRAWL INSTRUCTIONS

Run after every phase. Use exactly this site:

**Sitemap URL:** `https://africanmarketingconfederation.org/page-sitemap.xml`
**PSI API key:** use your AMC PSI key
**OAuth/GSC credentials:** use the AMC OAuth file

This site is chosen because:
- PSI API key and GSC OAuth are available — per-URL lab data and real GSC metrics will be returned
- This gives a more realistic and complete output than a key-less run
- Any regression in CWV handling, GSC integration, or severity badges will be visible

**Suggested crawl command** (adjust for your actual CLI):

```bash
python -m hype_frog crawl \
  --sitemap https://africanmarketingconfederation.org/page-sitemap.xml \
  --psi-key YOUR_AMC_PSI_KEY \
  --gsc-credentials PATH_TO_AMC_OAUTH_FILE \
  --mode accurate \
  --output ./test_outputs/amc_phase_N_$(date +%Y%m%d_%H%M%S).xlsx
```

Replace `phase_N` with the current phase number. Store all test outputs in `./test_outputs/` — do not delete previous phase outputs, they are needed for comparison.

**Minimum checks after every crawl:**

| Check | How to verify |
|-------|---------------|
| Output file opens without errors | Open in Excel/LibreOffice — no corruption |
| URL count is stable (within ±2 of previous run) | Dashboard → URL Count |
| No Python exceptions in crawl logs | Check terminal output |
| Main sheet has correct column count (no _1 columns after Phase 8) | Row 1, count columns |
| Severity badge is not 100% Critical (after Phase 4) | Dashboard → Critical URL Rate |
| IssueInventory row count drops after Phase 3 | Count rows vs Phase 2 output |
| GSC Clicks column shows real values (not 0, not all blank) for AMC | Main sheet spot-check |
| Link Inventory: no duplicate source+target+anchor rows | Sort columns, scan for adjacents |
| Click Depth column: zero null cells (after Phase 7) | Filter blanks in Excel |
| 404 URLs show Indexability = "Not Indexable" (after Phase 1) | Filter Status Code = 404 |

**If a test crawl fails:**
1. Do NOT proceed to the next phase.
2. Revert the current phase changes (git reset or manual undo).
3. Log the failure and symptoms in `AUDIT_FIX_LOG.md` for the relevant phase.
4. Diagnose, re-implement, and retest before continuing.

---
---

## THINGS YOU MUST NOT DO

- Do not rename any existing xlsx column. Clients and cross-sheet formulas depend on exact column name strings.
- Do not remove any existing sheet from the xlsx output.
- Do not change the `stable_issue_id` hashing logic — IDs must be stable across audit runs for delta tracking.
- Do not modify Pydantic model field names without auditing all callers first.
- Do not merge Phase 3 and Phase 4 — they must be separately testable.
- Do not change CWV rule scope to "site" in Phase 3 — that happens in Phase 4 only.
- Do not add the WooCommerce exclusion to `robots.py` — it belongs in `crawl_runner.py`.
- Do not skip the test crawl between phases, even if a phase seems trivial.
- Do not implement more than one phase without a test crawl between them.

---

## QUICK FILE REFERENCE

| What you are fixing | File | Function | Lines (approx) |
|---|---|---|---|
| 404 → Indexable bug | `src/hype_frog/crawler/data_assembler.py` | `finalize_row_state` | 716-739 |
| GSC 0 vs None | `src/hype_frog/pipeline/gsc_coverage.py` | `apply_gsc_coverage_fields` | 89-134 |
| Link Inventory dupes | `src/hype_frog/reporter/sheets/merged_builders.py` | `build_link_inventory_rows` | 655-687 |
| CrUX origin detection | `src/hype_frog/crawler/psi_engine.py` | `_field_experience_metrics` | 204 |
| CWV label fields | `src/hype_frog/crawler/psi_engine.py` | assembled values | 434-496 |
| CWV label propagation | `src/hype_frog/pipeline/assemble.py` | `row_with_psi_gsc_harden` | 275-333 |
| Issue scope system | `src/hype_frog/rules/registry.py` | `get_summary_rules` | 18-56 |
| IssueInventory branching | `src/hype_frog/reporter/summary_builder.py` | `build_issue_inventory_rows` | 192-236 |
| FixPlan scope labels | `src/hype_frog/reporter/engine_rows.py` | `build_fixplan_rows` | 256-267 |
| CWV severity guard | `src/hype_frog/rules/registry.py` | CWV rules in `get_summary_rules` | 25-29 |
| WooCommerce filter | `src/hype_frog/orchestration/crawl_runner.py` | `_is_crawlable_html_candidate` | 85-93 |
| 404 label mismatch | `src/hype_frog/rules/scoring.py` | `score_url_health` | 22-28 |
| Broken link count | `src/hype_frog/reporter/engine_rows.py` | `build_fixplan_rows` | 256-267 |
| Click Depth nulls | `src/hype_frog/pipeline/graph_engine.py` | `compute_internal_link_intelligence` | 76-92 |
| Duplicate columns (links) | `src/hype_frog/reporter/sheets/links.py` | `apply_cross_sheet_links` | 190-202 |
| Duplicate columns (nav) | `src/hype_frog/reporter/sheets/navigation.py` | `add_back_to_dashboard_link` | 22-41 |
| safe_clicks None handling | `src/hype_frog/core/scoring.py` | `_safe_clicks` | ~64 |
