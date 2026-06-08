# Cursor `/loop` commands for hype-frog

Practical [Cursor `/loop`](https://cursor.com) prompts for this repository: API health, regression tests, workbook integrity, and crawl output monitoring.

## Prerequisites (Windows PowerShell)

Prefix agent-run commands with:

```powershell
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
```

Common commands used by loops below:

```powershell
uv run hype-frog --validate
uv run hype-frog --validate --validate-url "https://africanmarketingconfederation.org/"
uv run hype-frog --quick-test
uv run pytest -q
```

Workbook output: `reports/latest/SEO_AEO_Audit*.xlsx`

---

## How `/loop` fits this repo

`/loop [interval] <prompt>` wakes the agent on a schedule. In hype-frog, loops are especially useful for:

| Area | Why loop it |
|------|-------------|
| **API health** (`--validate`) | GSC tokens expire; PSI quotas change |
| **Regression tests** | No GitHub CI in repo — loops act as a safety net |
| **Workbook integrity** | 25+ tabs with freeze panes, TOC, conditional formatting |
| **Crawl output** | `--quick-test` takes minutes; a watcher beats manual polling |

**Stopping a loop:** say *"stop the loop"* (or name which one). The agent should kill the background sleeper/watcher.

**Syntax reminder:**

- Fixed interval: `/loop 30m <prompt>` or `/loop 1d <prompt>`
- Dynamic (event- or self-paced): `/loop <prompt>` with no interval

---

## Tier 1 — Run often (low cost)

### 1. Integration health (daily or before client crawls)

```
/loop 1d Run `uv run hype-frog --validate --validate-url "https://africanmarketingconfederation.org/"`. Summarise PASS/FAIL/WARN for GSC OAuth, token, API probe, PSI key, and optional LLM keys. If GSC token fails, tell me to run `uv run hype-frog --gsc-auth`. Do not start a crawl.
```

**Shorter variant** (no GSC property check):

```
/loop 12h Run `uv run hype-frog --validate`. Report only failures and warnings; stay silent if all PASS.
```

---

### 2. Fast regression gate (after any code edit)

```
/loop 30m Run `uv sync --extra dev` then `uv run pytest tests/extractors/test_heading_outline.py tests/core/test_discovery_order.py tests/reporter/test_content_hub_columns.py tests/reporter/test_excel_engine.py -q`. If anything fails, show the failing test name and the smallest fix. If all pass, reply "regression gate OK" only.
```

**Broader nightly sweep:**

```
/loop 1d Run full `uv run pytest -q`. On failure, triage by layer (crawler / pipeline / reporter) and suggest one fix per failure. On success, one-line summary with test count.
```

---

## Tier 2 — Workbook quality (after `--quick-test` or full crawls)

Audit workbooks land under `reports/latest/` as `SEO_AEO_Audit*.xlsx`. Tab order follows `PREFERRED_WORKBOOK_TAB_ORDER` in `src/hype_frog/reporter/sheets/toc.py` (Dashboard → Content Optimisation Hub → Main → Technical → …).

### 3. Post-crawl workbook audit

Run once after each crawl, or on an interval during active reporter work.

```
/loop 2h Find the newest `SEO_AEO_Audit*.xlsx` under `reports/latest/`. Open it with openpyxl (do not use Excel GUI). Check: (1) TOC tab lists every sheet in preferred order with non-generic descriptions; (2) Content Optimisation Hub has `freeze_panes == 'I3'` and columns through `URL Slug Normalization` are frozen; (3) `Action Required` uses only `Ready to Publish` / `Needs Copy` with red fill on `Needs Copy`; (4) Main, Technical, and Technical Diagnostics sort by ascending `Discovery Rank`. Report violations with sheet, column, and row. If no xlsx exists, say so and skip.
```

---

### 4. H-tag extraction spot-check

Validates heading discovery (`extract_heading_outline`, Content tab, Content Optimisation Hub).

```
/loop 4h On the latest workbook in `reports/latest/`, sample 5 URLs from the Content tab. For each, compare `H1 Count`, `Current H-Tag Structure`, `Missing H1 Flag`, and `Multiple H1 Flag` against `H1`–`H6` columns on Content Optimisation Hub. Flag pages where hub H-columns are empty but structure has headings, or where multiple H1s are not flagged. Suggest extractor fixes only if pattern repeats.
```

---

### 5. Discovery rank ordering audit

```
/loop 6h On the latest audit xlsx, read Main tab `Discovery Rank` and `URL` columns. Confirm ranks are strictly increasing (1, 2, 3…) with no duplicates, and that sitemap-seeded URLs (low ranks) appear before BFS-discovered URLs (higher ranks). Compare first 10 URLs to the source sitemap order if `SitemapQA` tab exists. Report any inversions.
```

---

## Tier 3 — Pipeline smoke (heavier; use during active development)

### 6. Full pipeline smoke + workbook check

~10 URLs, Playwright, full suite — allow several minutes per tick.

```
/loop 6h Run `uv run hype-frog --quick-test` (ensure Playwright chromium is installed). When it finishes, run `uv run pytest tests/reporter/test_excel_engine.py -q` against the new workbook path. Summarise: URL count, output filename, any pytest failure, and whether Dashboard executive formulas reference sheets that exist.
```

---

### 7. Reporter-only isolation (faster than full crawl)

```
/loop 3h Run `uv run pytest tests/reporter/ -q`. If failures touch freeze panes, TOC, or Content Hub columns, cross-check against `docs/excel_reporting_standards.md` and `reporter/sheets/config.py` (`CONTENT_HUB_FREEZE_PANES`). Propose minimal diffs only.
```

---

## Tier 4 — Dynamic loops (no fixed interval)

Use when work is **event-driven** rather than time-driven.

### 8. Watch for new workbook after a long crawl

```
/loop Watch `reports/latest/` for a new or updated `SEO_AEO_Audit*.xlsx`. When file mtime changes, run the Tier 2 workbook audit prompt (#3) once, then stop the loop.
```

---

### 9. Watch for code changes in reporter layer

```
/loop Watch `src/hype_frog/reporter/` and `tests/reporter/` for file changes. After each change batch, run `uv run pytest tests/reporter/ -q` and note any Content Hub / TOC / freeze-pane regressions. Self-pace: re-check only when files change.
```

---

### 10. Doc-sync guard (architecture rule #8)

```
/loop Watch `src/hype_frog/core/models.py`, `src/hype_frog/extractors/`, and `src/hype_frog/reporter/`. If contracts or crawl behaviour changed but `docs/data_contracts.md`, `docs/system_architecture.md`, or `docs/excel_reporting_standards.md` were not updated in the same session, list the drift and draft the doc edits needed. Do not edit docs unless I say so.
```

---

## Tier 5 — Client / multi-site ops

### 11. Rotate validation across sitemap targets

```
/loop 1d Validate integrations against alternate crawl targets: today `https://africanmarketingconfederation.org/`, tomorrow `https://ticonafrica.org/`. Run `uv run hype-frog --validate --validate-url "<target>"`. Track whether GSC property visibility differs per domain. Alternate targets each tick.
```

Example sitemaps (from project notes):

- `https://africanmarketingconfederation.org/page-sitemap.xml`
- `https://ticonafrica.org/page-sitemap.xml`

---

### 12. PSI quota probe (only if PSI is enabled in crawls)

```
/loop 8h Run `uv run hype-frog --validate --psi-probe-url "https://africanmarketingconfederation.org/"`. Report HTTP status, latency, and any 429/403. If PSI fails but GSC passes, isolate PSI_API_KEY / API enablement — do not blame the crawl.
```

---

## Recommended starter set (three loops)

If you only want a minimal daily playbook:

| # | Command | Purpose |
|---|---------|---------|
| 1 | `/loop 12h` — integration validate (#2 short) | API/token health |
| 2 | `/loop 30m` — focused pytest gate (#2 narrow) | Safe edits while coding |
| 3 | `/loop` dynamic — watch `reports/latest/` (#8) | Audit workbook when a crawl finishes |

---

## Operational tips

- **Avoid overlap:** do not run **#6** (full `--quick-test`) and **#3** (workbook audit) on the same short interval; both touch the workbook and one triggers crawls.
- **Cache invalidation:** after breaking changes to `core/models.py` or cached JSON shape, run a one-off check: *"Does `.cache/*.sqlite` need deleting per `docs/data_contracts.md`?"* before resuming crawls.
- **Delta runs:** when crawling with a previous audit path, use: *"On latest xlsx, summarise `DeltaFromPreviousRun` — new issues, resolved issues, top 5 URL regressions."*
- **GSC re-auth:** if validate reports token failure → `uv run hype-frog --gsc-auth`

---

## Quick reference — workbook invariants

The agent should enforce these when running Tier 2 audits:

| Check | Expected |
|-------|----------|
| Content Hub freeze | `freeze_panes = 'I3'` (`CONTENT_HUB_FREEZE_PANES` in `reporter/sheets/config.py`) |
| Frozen columns | Through `URL Slug Normalization` (after `Assigned Owner`) |
| Action Required literals | `Ready to Publish` / `Needs Copy` only; red fill on `Needs Copy` |
| URL sort (Main, Technical, Technical Diagnostics) | Ascending `Discovery Rank` |
| TOC descriptions | No generic fallbacks like *"Detailed URL diagnostic data"* |

---

## Related project docs

- `commands.md` — local setup and run commands
- `README.md` — `--validate` and `--quick-test` usage
- `docs/excel_reporting_standards.md` — workbook integrity rules
- `docs/data_contracts.md` — payload and cache contracts
