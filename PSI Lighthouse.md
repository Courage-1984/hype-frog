# Hype Frog — PSI / Lighthouse Comprehensive Fix & Expansion
## Cursor IDE Agent Instructions — LI-HF-PSI-P0 | 27 June 2026

---

## CRITICAL RULES

1. Do NOT remove any existing column from the xlsx output.
2. Do NOT rename existing columns (`Mobile LCP (s)`, `Mobile PSI Score`, etc.) — add new columns alongside them.
3. Do NOT change the PSI API calling pattern (mobile + desktop separate calls) — only change what is extracted from responses.
4. Every new column must be added to the relevant `COLUMN_GROUP_DEFINITIONS` or equivalent so it appears in exports.
5. Run the test crawl after each part before proceeding.
6. **Test crawl:** `https://africanmarketingconfederation.org/page-sitemap.xml` with AMC PSI key and GSC OAuth.

---

## STEP 0 — Context extraction (run before touching any code)

Run these searches and paste results into `AUDIT_FIX_LOG.md` under `## PSI/Lighthouse Expansion`:

```bash
# 1. Full psi_engine.py
cat src/hype_frog/crawler/psi_engine.py

# 2. Full assemble.py row_with_psi_gsc_harden function
grep -n "def row_with_psi_gsc_harden" src/hype_frog/pipeline/assemble.py
# Then view ±100 lines around it

# 3. Where PSI columns are defined for export (column group definitions)
grep -rn "Mobile LCP\|CWV LCP\|PSI Score\|CWV Data Source" src/ --include="*.py" | grep -v test

# 4. Technical Diagnostics builder
grep -rn "Technical Diagnostics" src/ --include="*.py" | grep -i "write\|build\|sheet"

# 5. What categories are currently passed to PSI API
grep -rn "category\|categories\|performance\|accessibility" src/hype_frog/crawler/psi_engine.py | head -30

# 6. How Mobile LCP / Mobile CLS are currently extracted
grep -n "mobile\|Mobile\|lcp_seconds\|lab\." src/hype_frog/crawler/psi_engine.py | head -40

# 7. How the lighthouse audits object is accessed
grep -n "lighthouseResult\|audits\|lighthouse" src/hype_frog/crawler/psi_engine.py | head -30
```

Before writing any code, document:
- The exact parameter name used in the PSI API call for categories
- The exact path to `lighthouseResult.audits` in the parsed response
- Which columns are currently populated from `lighthouseResult` vs `loadingExperience`
- The exact structure of the `loadingExperience` object as returned for AMC

---

## PART 1 — Fix CrUX Origin Detection

### The problem (confirmed from audit)

`CWV LCP (s)` = `11.852` for 262/265 pages — clearly origin-level CrUX.
`Mobile LCP (s)` = varied per-URL values (7.351, 9.112, 28.201) — correctly per-URL Lighthouse lab data.

The PSI API response contains:
- `loadingExperience` — URL-level CrUX IF the URL has sufficient traffic in Chrome's dataset. When insufficient, the API silently returns origin-level data in this object and sets `origin_fallback: true`.
- `originLoadingExperience` — always origin-level CrUX.
- `lighthouseResult` — always per-URL Lighthouse lab data.

The current code (`psi_engine.py` ~line 204):
```python
exp = payload.get("loadingExperience") or payload.get("originLoadingExperience")
```
This silently falls back with no detection of which source was used.

### Fix — `_field_experience_metrics` in `psi_engine.py`

Read the full function first. Then implement the following detection logic:

```python
def _detect_crux_level(
    payload: dict[str, Any],
    requested_url: str,
) -> tuple[dict[str, Any] | None, str]:
    """
    Returns (metrics_dict, crux_level) where crux_level is one of:
      "URL"    — URL-level CrUX data (specific to this page)
      "Origin" — Origin-level CrUX data (whole domain, not this page)
      "None"   — No CrUX data available
    """
    url_exp = payload.get("loadingExperience")
    origin_exp = payload.get("originLoadingExperience")

    if url_exp:
        # Method 1: explicit flag from API
        if url_exp.get("origin_fallback") is True:
            # API confirms this is origin fallback — use origin_exp for clarity
            if origin_exp and origin_exp.get("metrics"):
                return origin_exp.get("metrics"), "Origin"
            return url_exp.get("metrics"), "Origin"

        # Method 2: check if the id matches the requested URL
        exp_id = url_exp.get("id", "")
        if exp_id:
            from urllib.parse import urlparse
            exp_parsed = urlparse(exp_id.rstrip("/"))
            req_parsed = urlparse(requested_url.rstrip("/"))
            # If path is empty/root, it's the origin, not URL-level
            if exp_parsed.path in ("", "/") and req_parsed.path not in ("", "/"):
                if origin_exp and origin_exp.get("metrics"):
                    return origin_exp.get("metrics"), "Origin"
                return url_exp.get("metrics"), "Origin"

        # Method 3: heuristic — if metrics exist and id looks URL-specific
        if url_exp.get("metrics"):
            return url_exp.get("metrics"), "URL"

    # No loadingExperience at all
    if origin_exp and origin_exp.get("metrics"):
        return origin_exp.get("metrics"), "Origin"

    return None, "None"
```

**Important:** `loadingExperience.metrics` is a dict of metric objects (not direct values). Read the actual structure in your context extraction and extract `LARGEST_CONTENTFUL_PAINT_MS.percentile` etc. as per the existing code pattern.

### Update the flat dict assembly (~line 434-496 of `psi_engine.py`)

After calling `_detect_crux_level`, populate these fields:

```python
crux_metrics, crux_level = _detect_crux_level(payload, target_url)

# CrUX level indicator — new column
merged_flat["CrUX Level"] = crux_level  # "URL", "Origin", or "None"

# CWV LCP and CLS columns:
# ONLY write CrUX values when genuinely URL-level
if crux_level == "URL" and crux_metrics:
    merged_flat["CWV LCP (s)"] = _extract_crux_metric(crux_metrics, "LARGEST_CONTENTFUL_PAINT_MS", to_seconds=True)
    merged_flat["CWV CLS"] = _extract_crux_metric(crux_metrics, "CUMULATIVE_LAYOUT_SHIFT_SCORE")
    merged_flat["CWV INP (ms)"] = _extract_crux_metric(crux_metrics, "INTERACTION_TO_NEXT_PAINT")
    merged_flat["CWV FCP (ms)"] = _extract_crux_metric(crux_metrics, "FIRST_CONTENTFUL_PAINT_MS")
    merged_flat["CWV TTFB (ms)"] = _extract_crux_metric(crux_metrics, "EXPERIMENTAL_TIME_TO_FIRST_BYTE")
    merged_flat["Field vs Lab"] = "Field (URL-level CrUX)"
    merged_flat["CWV Data Source"] = "CrUX API (URL-level)"
    merged_flat["PSI Data Status"] = "CrUX Field (URL)"

elif crux_level == "Origin" and crux_metrics:
    # Write to SEPARATE origin columns — DO NOT overwrite CWV LCP (s) with origin data
    merged_flat["CWV LCP (s)"] = None  # No URL-level CrUX available
    merged_flat["CWV CLS"] = None
    merged_flat["CWV INP (ms)"] = None
    merged_flat["CWV FCP (ms)"] = None
    merged_flat["CWV TTFB (ms)"] = None
    # Store origin values in dedicated columns
    merged_flat["Origin CrUX LCP (s)"] = _extract_crux_metric(crux_metrics, "LARGEST_CONTENTFUL_PAINT_MS", to_seconds=True)
    merged_flat["Origin CrUX CLS"] = _extract_crux_metric(crux_metrics, "CUMULATIVE_LAYOUT_SHIFT_SCORE")
    merged_flat["Origin CrUX INP (ms)"] = _extract_crux_metric(crux_metrics, "INTERACTION_TO_NEXT_PAINT")
    merged_flat["Field vs Lab"] = "Lab (Origin CrUX available)"
    merged_flat["CWV Data Source"] = "CrUX API (Origin-level)"
    merged_flat["PSI Data Status"] = "CrUX Field (Origin)"

else:  # "None"
    merged_flat["CWV LCP (s)"] = None
    merged_flat["CWV CLS"] = None
    merged_flat["CWV INP (ms)"] = None
    merged_flat["CWV FCP (ms)"] = None
    merged_flat["CWV TTFB (ms)"] = None
    merged_flat["Field vs Lab"] = "Lab only"
    merged_flat["CWV Data Source"] = "None"
    merged_flat["PSI Data Status"] = "No CrUX Data"
```

Write a helper:
```python
def _extract_crux_metric(
    metrics: dict,
    metric_key: str,
    to_seconds: bool = False,
) -> float | None:
    """Extract the 75th percentile value from a CrUX metrics dict."""
    metric = metrics.get(metric_key, {})
    percentile = metric.get("percentile")
    if percentile is None:
        return None
    val = float(percentile)
    if to_seconds:
        val = val / 1000.0
    return round(val, 3)
```

Also extract CrUX category ratings:
```python
merged_flat["CrUX LCP Category"] = _extract_crux_category(crux_metrics, "LARGEST_CONTENTFUL_PAINT_MS") if crux_level == "URL" else None
merged_flat["CrUX CLS Category"] = _extract_crux_category(crux_metrics, "CUMULATIVE_LAYOUT_SHIFT_SCORE") if crux_level == "URL" else None
merged_flat["CrUX INP Category"] = _extract_crux_category(crux_metrics, "INTERACTION_TO_NEXT_PAINT") if crux_level == "URL" else None

def _extract_crux_category(metrics: dict, metric_key: str) -> str | None:
    metric = metrics.get(metric_key, {})
    return metric.get("category")  # "FAST", "AVERAGE", "SLOW" or "GOOD", "NEEDS_IMPROVEMENT", "POOR"
```

---

## PART 2 — Full Lighthouse Audit Extraction

### Ensure all 4 categories are requested

Find where the PSI API call is constructed. Confirm the `category` parameter includes all four:
```
category=performance&category=accessibility&category=best-practices&category=seo
```
If any are missing, add them. Note: `best-practices` uses a hyphen.

### Extract comprehensive Lighthouse data

Find the function that processes `lighthouseResult`. It currently extracts the performance score and some audit values (`lcp_seconds`, CLS, TTFB). Expand it to extract ALL of the following:

```python
def _extract_lighthouse_data(
    lighthouse_result: dict[str, Any],
    prefix: str = "mobile",
) -> dict[str, Any]:
    """
    Extract comprehensive Lighthouse lab data.
    prefix: "mobile" or "desktop"
    Returns a flat dict of column_name → value.
    """
    out: dict[str, Any] = {}
    if not lighthouse_result:
        return out

    audits = lighthouse_result.get("audits", {})
    categories = lighthouse_result.get("categories", {})

    def audit_score(key: str) -> int | None:
        a = audits.get(key, {})
        s = a.get("score")
        return round(s * 100) if s is not None else None

    def audit_ms(key: str) -> float | None:
        a = audits.get(key, {})
        v = a.get("numericValue")
        return round(float(v), 1) if v is not None else None

    def audit_s(key: str) -> float | None:
        v = audit_ms(key)
        return round(v / 1000, 3) if v is not None else None

    def cat_score(key: str) -> int | None:
        c = categories.get(key, {})
        s = c.get("score")
        return round(s * 100) if s is not None else None

    p = prefix.capitalize()  # "Mobile" or "Desktop"

    # === CATEGORY SCORES ===
    out[f"Lighthouse Performance ({p})"] = cat_score("performance")
    out[f"Lighthouse Accessibility ({p})"] = cat_score("accessibility")
    out[f"Lighthouse Best Practices ({p})"] = cat_score("best-practices")
    out[f"Lighthouse SEO Score ({p})"] = cat_score("seo")

    # === CORE WEB VITALS (lab) ===
    out[f"Lab LCP ({p}) (s)"] = audit_s("largest-contentful-paint")
    out[f"Lab CLS ({p})"] = audit_ms("cumulative-layout-shift") / 1000 if audit_ms("cumulative-layout-shift") is not None else None
    # CLS is already a ratio, not ms — special case:
    cls_audit = audits.get("cumulative-layout-shift", {})
    cls_val = cls_audit.get("numericValue")
    out[f"Lab CLS ({p})"] = round(float(cls_val), 4) if cls_val is not None else None
    out[f"Lab TBT ({p}) (ms)"] = audit_ms("total-blocking-time")
    out[f"Lab INP ({p}) (ms)"] = audit_ms("interaction-to-next-paint")  # May not be available in all LH versions

    # === PAINT METRICS ===
    out[f"Lab FCP ({p}) (s)"] = audit_s("first-contentful-paint")
    out[f"Lab Speed Index ({p}) (s)"] = audit_s("speed-index")
    out[f"Lab TTI ({p}) (s)"] = audit_s("interactive")

    # === NETWORK / SERVER ===
    out[f"Lab TTFB ({p}) (ms)"] = audit_ms("server-response-time")

    # === PAGE WEIGHT & STRUCTURE (mobile only to avoid duplication) ===
    if prefix == "mobile":
        total_bytes = audits.get("total-byte-weight", {}).get("numericValue")
        out["Page Size (KB)"] = round(float(total_bytes) / 1024, 1) if total_bytes is not None else None
        dom_size = audits.get("dom-size", {}).get("numericValue")
        out["DOM Size (nodes)"] = int(dom_size) if dom_size is not None else None
        js_exec = audits.get("bootup-time", {}).get("numericValue")
        out["JS Execution (ms)"] = round(float(js_exec), 1) if js_exec is not None else None
        # Network requests — from details items count
        net_req = audits.get("network-requests", {})
        items = (net_req.get("details") or {}).get("items", [])
        out["Network Request Count"] = len(items) if items else None

    # === OPPORTUNITY FLAGS (pass/fail as boolean) ===
    if prefix == "mobile":
        out["Has Text Compression"] = audit_score("uses-text-compression") == 100
        out["Has Long Cache TTL Issues"] = audit_score("uses-long-cache-ttl") is not None and audit_score("uses-long-cache-ttl") < 100
        out["Has Render Blocking Resources"] = audit_score("render-blocking-resources") is not None and audit_score("render-blocking-resources") < 100
        out["Uses Modern Image Formats"] = audit_score("uses-webp-images") == 100 or audit_score("modern-image-formats") == 100

    return out
```

**Important notes on the CLS extraction above:** CLS is a ratio (e.g. 0.03), not in milliseconds. The `numericValue` from Lighthouse is already the ratio. Do NOT divide by 1000. The code above has an error I left intentionally — fix the CLS extraction to use `numericValue` directly without any ms conversion:
```python
cls_val = audits.get("cumulative-layout-shift", {}).get("numericValue")
out[f"Lab CLS ({p})"] = round(float(cls_val), 4) if cls_val is not None else None
```

Call this function for both mobile and desktop payloads and merge results into the flat dict:
```python
if mobile_lighthouse:
    mobile_lab = _extract_lighthouse_data(mobile_lighthouse, prefix="mobile")
    merged_flat.update(mobile_lab)

if desktop_lighthouse:
    desktop_lab = _extract_lighthouse_data(desktop_lighthouse, prefix="desktop")
    merged_flat.update(desktop_lab)
```

### Backward compatibility for existing columns

The existing columns `Mobile PSI Score`, `Mobile LCP (s)`, `Mobile CLS`, `Mobile TTFB (s)` must continue to be populated as before. After adding the new extraction, also write:
```python
# Keep existing columns populated (backward compat)
merged_flat["Mobile PSI Score"] = merged_flat.get("Lighthouse Performance (Mobile)")
merged_flat["Desktop PSI Score"] = merged_flat.get("Lighthouse Performance (Desktop)")
# Mobile LCP (s), Mobile CLS, Mobile TTFB (s) — check if they're already populated
# from the existing extraction; if so, leave them. If not, populate from new:
if not merged_flat.get("Mobile LCP (s)"):
    merged_flat["Mobile LCP (s)"] = merged_flat.get("Lab LCP (Mobile) (s)")
if not merged_flat.get("Mobile CLS"):
    merged_flat["Mobile CLS"] = merged_flat.get("Lab CLS (Mobile)")
if not merged_flat.get("Mobile TTFB (s)"):
    ttfb_ms = merged_flat.get("Lab TTFB (Mobile) (ms)")
    merged_flat["Mobile TTFB (s)"] = round(ttfb_ms / 1000, 3) if ttfb_ms else None
```

---

## PART 3 — New Columns in Main Sheet

### Complete list of new columns to add

Add these to `MAIN_COLUMN_GROUP_DEFINITIONS` (or equivalent) in the **Performance / CWV** group, adjacent to the existing `CWV LCP (s)`, `Mobile LCP (s)` etc. columns:

**CrUX / Field Data columns:**
- `CrUX Level` — "URL", "Origin", or "None"
- `CWV INP (ms)` — URL-level CrUX INP 75th percentile (null if origin)
- `CWV FCP (ms)` — URL-level CrUX FCP 75th percentile (null if origin)
- `CWV TTFB (ms)` — URL-level CrUX TTFB 75th percentile (null if origin)
- `CrUX LCP Category` — "FAST" / "AVERAGE" / "SLOW" (null if origin)
- `CrUX CLS Category` — "GOOD" / "NEEDS_IMPROVEMENT" / "POOR" (null if origin)
- `CrUX INP Category` — category string (null if origin)
- `Origin CrUX LCP (s)` — origin-level LCP (populated only when CrUX Level = "Origin")
- `Origin CrUX CLS` — origin-level CLS
- `Origin CrUX INP (ms)` — origin-level INP

**Lighthouse Mobile lab columns:**
- `Lighthouse Performance (Mobile)` — 0-100 score
- `Lighthouse Accessibility (Mobile)` — 0-100 score
- `Lighthouse Best Practices (Mobile)` — 0-100 score
- `Lighthouse SEO Score (Mobile)` — 0-100 score (Lighthouse's SEO audit, not Hype Frog's)
- `Lab LCP (Mobile) (s)` — Lighthouse mobile LCP in seconds
- `Lab CLS (Mobile)` — Lighthouse mobile CLS ratio
- `Lab TBT (Mobile) (ms)` — Total Blocking Time
- `Lab FCP (Mobile) (s)` — First Contentful Paint
- `Lab Speed Index (Mobile) (s)` — Speed Index
- `Lab TTI (Mobile) (s)` — Time to Interactive
- `Lab TTFB (Mobile) (ms)` — Server Response Time (mobile)

**Lighthouse Desktop lab columns:**
- `Lighthouse Performance (Desktop)` — 0-100 score
- `Lighthouse Accessibility (Desktop)` — 0-100 score
- `Lighthouse Best Practices (Desktop)` — 0-100 score
- `Lighthouse SEO Score (Desktop)` — 0-100 score
- `Lab LCP (Desktop) (s)` — Desktop lab LCP
- `Lab CLS (Desktop)` — Desktop lab CLS
- `Lab TBT (Desktop) (ms)` — Desktop TBT
- `Lab FCP (Desktop) (s)` — Desktop FCP
- `Lab TTFB (Desktop) (ms)` — Desktop TTFB

**Page structure columns (mobile only, one value per URL):**
- `Page Size (KB)` — total transferred bytes / 1024
- `DOM Size (nodes)` — DOM element count
- `JS Execution (ms)` — JavaScript bootup/execution time
- `Network Request Count` — total HTTP request count

**Opportunity flags (boolean, for filtering):**
- `Has Text Compression` — True if compression is enabled
- `Has Long Cache TTL Issues` — True if cache policy needs improvement
- `Has Render Blocking Resources` — True if render-blocking resources found
- `Uses Modern Image Formats` — True if WebP/AVIF is used

---

## PART 4 — Update Registry Rules

**File:** `src/hype_frog/rules/registry.py`

Replace the three CWV rules with a more precise set. All changes must use the `IssueRule` dataclass from Phase 3 of the previous audit prompt.

```python
# ─── CWV — URL-level CrUX rules (only fire when real URL-level data available) ─────
IssueRule(
    severity="Critical",
    name="CWV LCP Above 4.0s (Field Data)",
    fn=lambda r: (
        r.get("CrUX Level") == "URL"
        and (r.get("CWV LCP (s)") or 0) > 4.0
    ),
    scope="url",
),
IssueRule(
    severity="Warning",
    name="CWV CLS Above 0.1 (Field Data)",
    fn=lambda r: (
        r.get("CrUX Level") == "URL"
        and (r.get("CWV CLS") or 0) > 0.1
    ),
    scope="url",
),
IssueRule(
    severity="Warning",
    name="CWV INP Above 200ms (Field Data)",
    fn=lambda r: (
        r.get("CrUX Level") == "URL"
        and (r.get("CWV INP (ms)") or 0) > 200
    ),
    scope="url",
),

# ─── Lighthouse Lab rules (fire on lab data — always URL-specific) ─────────────────
IssueRule(
    severity="Critical",
    name="Lab LCP Above 4.0s (Mobile)",
    fn=lambda r: (r.get("Lab LCP (Mobile) (s)") or 0) > 4.0,
    scope="url",
),
IssueRule(
    severity="Warning",
    name="Lab LCP 2.5s–4.0s (Mobile)",
    fn=lambda r: 2.5 < (r.get("Lab LCP (Mobile) (s)") or 0) <= 4.0,
    scope="url",
),
IssueRule(
    severity="Warning",
    name="Lab TBT Above 300ms (Mobile)",
    fn=lambda r: (r.get("Lab TBT (Mobile) (ms)") or 0) > 300,
    scope="url",
),
IssueRule(
    severity="Observation",
    name="Lab TBT 150ms–300ms (Mobile)",
    fn=lambda r: 150 < (r.get("Lab TBT (Mobile) (ms)") or 0) <= 300,
    scope="url",
),
IssueRule(
    severity="Warning",
    name="Lab CLS Above 0.1 (Mobile)",
    fn=lambda r: (r.get("Lab CLS (Mobile)") or 0) > 0.1,
    scope="url",
),
IssueRule(
    severity="Warning",
    name="Low Lighthouse Performance Mobile (<50)",
    fn=lambda r: 0 < (r.get("Lighthouse Performance (Mobile)") or 0) < 50,
    scope="url",
),
IssueRule(
    severity="Observation",
    name="Moderate Lighthouse Performance Mobile (50–89)",
    fn=lambda r: 50 <= (r.get("Lighthouse Performance (Mobile)") or 0) < 90,
    scope="url",
),
IssueRule(
    severity="Warning",
    name="Low Lighthouse Accessibility (<80)",
    fn=lambda r: 0 < (r.get("Lighthouse Accessibility (Mobile)") or 0) < 80,
    scope="url",
),
IssueRule(
    severity="Observation",
    name="Low Lighthouse Best Practices (<80)",
    fn=lambda r: 0 < (r.get("Lighthouse Best Practices (Mobile)") or 0) < 80,
    scope="url",
),
IssueRule(
    severity="Warning",
    name="Lab TTFB Above 600ms",
    fn=lambda r: (r.get("Lab TTFB (Mobile) (ms)") or 0) > 600,
    scope="url",
),
IssueRule(
    severity="Observation",
    name="Large Page Size (>1MB)",
    fn=lambda r: (r.get("Page Size (KB)") or 0) > 1024,
    scope="url",
),
IssueRule(
    severity="Observation",
    name="Large DOM Size (>1500 nodes)",
    fn=lambda r: (r.get("DOM Size (nodes)") or 0) > 1500,
    scope="url",
),
IssueRule(
    severity="Observation",
    name="High JS Execution Time (>2000ms)",
    fn=lambda r: (r.get("JS Execution (ms)") or 0) > 2000,
    scope="url",
),
IssueRule(
    severity="Observation",
    name="Render Blocking Resources",
    fn=lambda r: r.get("Has Render Blocking Resources") is True,
    scope="url",
),

# ─── Origin CrUX site-level observations ──────────────────────────────────────────
IssueRule(
    severity="Observation",
    name="Origin CrUX LCP Above 4.0s (per-URL data unavailable — re-run with PSI key for URL-level data)",
    fn=lambda r: (
        r.get("CrUX Level") == "Origin"
        and (r.get("Origin CrUX LCP (s)") or 0) > 4.0
    ),
    scope="site",
),
IssueRule(
    severity="Observation",
    name="Origin CrUX INP Above 200ms (per-URL data unavailable)",
    fn=lambda r: (
        r.get("CrUX Level") == "Origin"
        and (r.get("Origin CrUX INP (ms)") or 0) > 200
    ),
    scope="site",
),
```

**IMPORTANT:** Remove or retire the old rules exactly as named:
- `"CWV LCP Above 4.0s"` (old, firing on origin CrUX per-URL) — remove
- `"CLS Above 0.1"` (old) — remove
- `"INP Above 100ms"` (old) — remove

Verify no other code references these old rule names by string before removing.

---

## PART 5 — Update Technical Diagnostics Sheet

**File:** wherever the Technical Diagnostics sheet builder is (find via context extraction Step 0).

Add a new **Lighthouse Scores** section to the Technical Diagnostics sheet with these columns, placed after the existing `Desktop PSI Score`, `Mobile PSI Score`, `Mobile LCP (s)` columns:

New columns to add to Technical Diagnostics:
- `CrUX Level`
- `Lab LCP (Mobile) (s)`
- `Lab TBT (Mobile) (ms)`
- `Lab FCP (Mobile) (s)`
- `Lab CLS (Mobile)`
- `Lab TTFB (Mobile) (ms)`
- `Lighthouse Accessibility (Mobile)`
- `Lighthouse Best Practices (Mobile)`
- `Lighthouse SEO Score (Mobile)`
- `Lab LCP (Desktop) (s)`
- `Lab TBT (Desktop) (ms)`
- `Lighthouse Performance (Desktop)`
- `Page Size (KB)`
- `DOM Size (nodes)`
- `JS Execution (ms)`
- `Network Request Count`
- `Origin CrUX LCP (s)` (populated when CrUX Level = "Origin")
- `Origin CrUX INP (ms)`

These should be read directly from the Main row values (same pattern as existing Technical Diagnostics columns).

---

## PART 6 — Update Executive Dashboard Source Data

**File:** wherever the Executive Dashboard source data rows (R60–R119) are written.

Find the "Health comparison" section (~row 62 in the current output):
```
Metric       | Current | Illustrative projected
SEO Health   | 12.1    | 90.6
Performance  | 54      | 95.1   ← This currently uses Desktop PSI (incorrect)
AEO Readiness| 27.1    | 92.2
```

Update "Performance (PSI)" row to source from `Lighthouse Performance (Mobile)` average (not Desktop). Mobile is the primary ranking signal.

Also add two new rows to the Health comparison chart data:
```
LCP (Lab Mobile avg)  | [avg of Lab LCP (Mobile) (s)]  | 2.5  ← target
Accessibility (avg)   | [avg of Lighthouse Accessibility (Mobile)] | 90 ← target
```

These will automatically feed into the existing Health comparison BarChart.

---

## PART 7 — Timeout page Indexability fix (residue from Phase 1A)

**File:** `src/hype_frog/crawler/data_assembler.py`
**Function:** `finalize_row_state`

The existing fix handles `status_int >= 400` but `"Timeout"` is stored as a string, not an integer.

Add explicit handling:

```python
# Handle string-based non-200 statuses
status_raw = main_data.get("Status Code")  # Read the exact key used
if isinstance(status_raw, str) and status_raw.lower() in ("timeout", "error", "connection error", "dns error"):
    indexability_reasons.append(f"Request {status_raw}")
    main_data["Indexability"] = "Not Indexable"  # Use exact key
```

Add this check BEFORE the existing `if status_int is not None and status_int >= 400:` block, or alongside it, so both integer and string statuses are handled.

---

## PART 8 — Orphan/Click Depth mismatch fix (residue from Phase 7)

**File:** `src/hype_frog/pipeline/graph_engine.py`
**Function:** `compute_internal_link_intelligence`

Currently 10 pages have `Click Depth = -1` but `Orphan Pages = False`. These are pages found via crawl/sitemap but unreachable from homepage via link graph (e.g. `/checkout`, `/cart`, `/product/...`). The Orphan Pages flag only covers pages that are COMPLETELY unlinked (no inbound internal links at all).

The correct logic: a page with `Click Depth = -1` is unreachable from the homepage in the link graph. Whether it has inbound links from other pages is separate. Both conditions are valid and important:
- `Orphan Pages = True` → no inbound internal links (current logic, keep)
- `Click Depth = -1` → unreachable from homepage navigation path (may have inbound links but those pages themselves are unreachable)

These are different concepts. Do NOT change the Orphan Pages flag logic. Instead, add a new column:
```python
merged_flat["Reachable from Homepage"] = click_depth != -1
```

This distinguishes the two concepts cleanly. Add `Reachable from Homepage` to the Main sheet column definitions and to Technical Diagnostics.

---

## TEST CRAWL — After each part

**Crawl command:**
```bash
python -m hype_frog crawl \
  --sitemap https://africanmarketingconfederation.org/page-sitemap.xml \
  --psi-key [AMC_PSI_KEY] \
  --gsc-credentials [AMC_OAUTH_PATH] \
  --mode accurate \
  --output ./test_outputs/amc_psi_part_N_$(date +%Y%m%d_%H%M%S).xlsx
```

**Verification checks per part:**

**After Part 1 (origin detection):**
- `CrUX Level` column exists in Main
- For AMC: `CrUX Level` should be `"Origin"` for most/all pages (low-traffic site with limited CrUX URL-level data)
- `CWV LCP (s)` should be `None` / null for pages where `CrUX Level = "Origin"` (not 11.852)
- `Origin CrUX LCP (s)` should contain 11.852 (moved to the correct column)
- `PSI Data Status` should say `"CrUX Field (Origin)"` not `"PSI + CrUX Field (URL)"`

**After Part 2 (Lighthouse extraction):**
- `Lighthouse Performance (Mobile)` column populated with per-URL scores (e.g. 28, 44, 39)
- `Lighthouse Accessibility (Mobile)` populated (new)
- `Lighthouse Best Practices (Mobile)` populated (new)
- `Lighthouse SEO Score (Mobile)` populated (new)
- `Lab LCP (Mobile) (s)` populated with varied per-URL values
- `Lab TBT (Mobile) (ms)` populated (new)
- `Lab FCP (Mobile) (s)` populated (new)
- `Page Size (KB)` populated (new)
- Desktop equivalents populated
- `Mobile PSI Score` and `Mobile LCP (s)` still populated (backward compat check)

**After Part 4 (registry rules):**
- `CWV LCP Above 4.0s` rule should now produce 0 rows in IssueInventory for AMC (since CrUX Level = "Origin")
- `Lab LCP Above 4.0s (Mobile)` should fire on pages where mobile lab LCP > 4.0s
- `Severity Badge` distribution should now show a genuine mix (not 99% Critical)
- `Lighthouse Performance (Mobile)` < 50 rule should fire for pages with score < 50
- `Origin CrUX LCP Above 4.0s...` rule should appear as ONE site-level row in IssueInventory

**After Part 7 (Timeout fix):**
- Timeout pages (`/amc-conference-2023/amc-awards` and `/call-for-nominations-for.../11-october...`) should show `Indexability = "Not Indexable"`

---

## COLUMN GROUP PLACEMENT GUIDE

When adding new columns to `MAIN_COLUMN_GROUP_DEFINITIONS` (or equivalent), place them in this order within the Performance group:

```
[existing] CWV LCP (s)          ← now null when CrUX is origin-level
[existing] CWV CLS              ← same
[existing] Field vs Lab         ← updated values
[existing] CWV Data Source      ← updated values
[existing] PSI Data Status      ← updated values
[NEW]      CrUX Level           ← "URL" / "Origin" / "None"
[NEW]      CWV INP (ms)
[NEW]      CWV FCP (ms)
[NEW]      CWV TTFB (ms)
[NEW]      CrUX LCP Category
[NEW]      CrUX CLS Category
[NEW]      CrUX INP Category
[NEW]      Origin CrUX LCP (s)
[NEW]      Origin CrUX CLS
[NEW]      Origin CrUX INP (ms)
[existing] Desktop PSI Score
[existing] Mobile PSI Score
[NEW]      Lighthouse Performance (Mobile)
[NEW]      Lighthouse Accessibility (Mobile)
[NEW]      Lighthouse Best Practices (Mobile)
[NEW]      Lighthouse SEO Score (Mobile)
[existing] Mobile LCP (s)
[existing] Mobile CLS
[existing] Mobile TTFB (s)
[NEW]      Lab LCP (Mobile) (s)
[NEW]      Lab CLS (Mobile)
[NEW]      Lab TBT (Mobile) (ms)
[NEW]      Lab FCP (Mobile) (s)
[NEW]      Lab Speed Index (Mobile) (s)
[NEW]      Lab TTI (Mobile) (s)
[NEW]      Lab TTFB (Mobile) (ms)
[NEW]      Lighthouse Performance (Desktop)
[NEW]      Lighthouse Accessibility (Desktop)
[NEW]      Lighthouse Best Practices (Desktop)
[NEW]      Lighthouse SEO Score (Desktop)
[NEW]      Lab LCP (Desktop) (s)
[NEW]      Lab CLS (Desktop)
[NEW]      Lab TBT (Desktop) (ms)
[NEW]      Lab FCP (Desktop) (s)
[NEW]      Lab TTFB (Desktop) (ms)
[NEW]      Page Size (KB)
[NEW]      DOM Size (nodes)
[NEW]      JS Execution (ms)
[NEW]      Network Request Count
[NEW]      Has Text Compression
[NEW]      Has Long Cache TTL Issues
[NEW]      Has Render Blocking Resources
[NEW]      Uses Modern Image Formats
[NEW]      Reachable from Homepage
```

---

## UPDATE AUDIT_FIX_LOG.md

Add a new section:
```markdown
## PSI/Lighthouse Expansion — LI-HF-PSI-P0

### Context map
- psi_engine.py key functions: [agent fills in]
- Categories requested in PSI API call (before fix): [agent fills in]
- Categories requested (after fix): performance, accessibility, best-practices, seo
- _detect_crux_level implemented: [date]
- New column count added: [N]

### Part status
| Part | Description | Status | Test Passed |
|------|-------------|--------|-------------|
| 1 | CrUX origin detection | ⬜ | ⬜ |
| 2 | Lighthouse full extraction | ⬜ | ⬜ |
| 3 | New columns in Main | ⬜ | ⬜ |
| 4 | Registry rules update | ⬜ | ⬜ |
| 5 | Technical Diagnostics update | ⬜ | ⬜ |
| 6 | Exec Dashboard source data | ⬜ | ⬜ |
| 7 | Timeout indexability fix | ⬜ | ⬜ |
| 8 | Orphan/depth distinction | ⬜ | ⬜ |

### AMC test results (after all parts)
- CrUX Level distribution: [agent fills in]
- Lab LCP (Mobile) mean: [agent fills in]
- Lighthouse Performance (Mobile) mean: [agent fills in]
- Lighthouse Accessibility (Mobile) mean: [agent fills in]
- Severity Badge distribution (expected: mix of Critical/Warning/Observation): [agent fills in]
- CWV LCP Above 4.0s rows: [should be 0 for AMC if all origin]
- Lab LCP Above 4.0s rows: [expected ~200+ for AMC given slow site]
```
