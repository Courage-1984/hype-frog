# hype-frog — command cheat sheet

PowerShell-first (Windows). Bash equivalents noted where they differ.

---

## Session bootstrap (every new terminal)

```powershell
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
.\.venv\Scripts\activate
```

```bash
export PATH="$HOME/.local/bin:$PATH"
source .venv/bin/activate
```

---

## Fresh clone / full toolchain

```powershell
uv sync --extra semantic --extra render --extra dev
uv run playwright install chromium
uv run hype-frog --install-semantic
uv run hype-frog --validate
```

Semantic only (spaCy NER — optional; keyword fallback works without it):

```powershell
uv sync --extra semantic
uv run hype-frog --install-semantic
```

Rendered crawl only:

```powershell
uv sync --extra render
uv run playwright install chromium
```

---

## Validate (no crawl)

```powershell
uv run hype-frog --validate
uv run hype-frog --validate --validate-url "https://africanmarketingconfederation.org/"
uv run hype-frog --gsc-auth    # OAuth only → secrets/token.json
```

---

## Run audits

### Structured CLI (recommended)

```powershell
uv run hype-frog crawl --url "https://example.com/sitemap.xml" --mode fast
uv run hype-frog crawl --url "https://example.com/" --mode accurate --streaming
uv run hype-frog crawl                              # interactive prompts (same as bare hype-frog)
uv run hype-frog validate --url "https://example.com/"
uv run hype-frog auth gsc
uv run hype-frog setup playwright
uv run hype-frog setup semantic
uv run hype-frog test quick
uv run hype-frog test full-smoke --fast
```

Legacy flags remain supported (`--quick-test`, `--gsc-auth`, `--validate`, etc.).

```powershell
uv run hype-frog                              # interactive prompts
uv run hype-frog --quick-test                 # preflight + pytest + 10-URL crawl + workbook audit
uv run hype-frog --quick-test-fast            # crawl + workbook audit only (~5 min)
```

**Pre-export full smoke** (run before a long production crawl — catches late export failures):

```powershell
uv run hype-frog --full-smoke-test            # OAuth + live PSI probe + pytest + ~80-URL sim + audit (~8–15 min)
uv run hype-frog --full-smoke-test-fast       # mocked crawl + export + audit only (~3–6 min)
```

Requires `PSI_API_KEY` and GSC OAuth (`secrets/token.json`) for the full gate. Crawl HTTP/PSI batch are mocked at sitemap scale with **no `max_urls` cap**; enrichment, scoring, and export run for real.

| Flag | Effect |
|------|--------|
| `--full-smoke-test-skip-preflight` | Skip GSC/PSI preflight |
| `--full-smoke-test-skip-pytest` | Skip pytest subset |
| `--full-smoke-test-skip-audit` | Skip workbook audit |

Tune synthetic volume: `HF_FULL_SMOKE_URL_COUNT=120 uv run hype-frog --full-smoke-test-fast`

Quick-test flags (combine with `--quick-test`):

| Flag | Effect |
|------|--------|
| `--quick-test-skip-preflight` | Skip GSC/PSI preflight |
| `--quick-test-skip-pytest` | Skip pytest subset |
| `--quick-test-skip-audit` | Skip workbook audit |

Override preset BFS depth: `HF_MAX_DEPTH=1 uv run hype-frog --quick-test-fast`

Useful crawl flags (see `uv run hype-frog --help`):

`--check-images` · `--check-og-images` · `--gsc-url-inspection` · `--gsc-url-inspection-full` · `--competitors domain.com` · `--previous-run path.xlsx` · `--regen-report` · `--snapshot-id <uuid>` · `--streaming` · `--export-pdf` · `--psi-delay 2.5`

Output defaults to `reports/latest/` unless `HF_OUTPUT_FILENAME` is set.

---

## HTML / Excel theming (Catppuccin Mocha)

Optional **Hype Frog × Catppuccin Mocha** palette. Canonical reference: [`docs/excel_reporting_standards.md`](docs/excel_reporting_standards.md) (*Catppuccin Mocha theme*).

**Dark HTML executive report + JetBrains Mono:**

```powershell
$env:HF_EXPORT_HTML = "1"
$env:HF_REPORT_THEME = "mocha"
uv run hype-frog --quick-test-fast
```

**Mocha RAG colours in the xlsx workbook** (set before export — resolved at import):

```powershell
$env:HF_EXCEL_THEME = "mocha"
```

**Full mocha stack** (add to `.env`):

```env
HF_EXPORT_HTML=1
HF_REPORT_THEME=mocha
HF_EXCEL_THEME=mocha
# HF_REPORT_BRAND_COLOUR=#1e1e2e      # optional
# HF_REPORT_ACCENT_COLOUR=#94e2d5     # optional (teal pond accent)
# HF_REPORT_PREPARED_BY=Your Name
# HF_REPORT_CLIENT_NAME=Client Corp
# HF_REPORT_LOGO_PATH=./assets/client_logo.png
```

**Signature colours:** frog green `#a6e3a1`, brand base `#1e1e2e`, accent teal `#94e2d5`. Font CDN (mocha HTML only): Google Fonts JetBrains Mono — see `src/hype_frog/reporter/mocha_theme.py`.

---

## Test sitemap seeds

```
https://africanmarketingconfederation.org/page-sitemap.xml
https://ticonafrica.org/page-sitemap.xml
```

---

## Multi-scenario workbook QA (local)

```powershell
uv run python scripts/crawl_matrix_audit.py
```

Writes `reports/matrix_test/matrix_*.xlsx` + `matrix_audit_summary.json`.

---

## Delta / previous run comparison

```powershell
uv run hype-frog --previous-run reports/latest/audit_20240601.xlsx
uv run hype-frog --previous-run reports/latest/audit_20240601_delta_summary.json
```

Populates `DeltaFromPreviousRun` and `ResolvedIssues` sheets with new/resolved issue rows, KPI deltas, and up to three SEO Health trend points per URL. Each full-suite run auto-writes `{basename}_delta_summary.json` for use as the next run's `--previous-run` input.

---

## Report-only regeneration (crawl replay)

Re-export workbook/HTML/PDF from a **stored crawl snapshot** — no HTTP, PSI, or GSC. Use after reporter or rules changes to avoid a full re-crawl.

**Always activate the venv first** (see [Session bootstrap](#session-bootstrap-every-new-terminal)):

```powershell
.\.venv\Scripts\Activate.ps1

# Latest snapshot for the configured target domain (interactive target prompt):
hype-frog --regen-report

# Non-interactive regen test harness (AMC page-sitemap target baked in):
python scripts\_run_regen_report_test.py
python scripts\_run_regen_report_test.py <snapshot-uuid>

# Full crawl + regen validation (long — PSI enabled):
.\scripts\run_full_crawl_and_regen_test.ps1

# Regen tests only (after a completed crawl saved a snapshot):
.\scripts\run_regen_test.ps1
```

| Flag / env | Effect |
|------------|--------|
| `--regen-report` | Skip crawl + enrichment; replay stored rows through `export_flow` |
| `HF_REGEN_REPORT=1` | Env equivalent of `--regen-report` |
| `--snapshot-id <uuid>` | Load that snapshot instead of latest for domain |
| `HF_SNAPSHOT_ID=<uuid>` | Env equivalent of `--snapshot-id` |
| `HF_SNAPSHOT_RETENTION_PER_DOMAIN` | Snapshots kept per domain (default **10**) |
| `HF_SNAPSHOTS_DB_PATH` | Override `.cache/crawl_snapshots.sqlite` |

**Live runs** auto-save a snapshot after enrichment (before export). Output path: `.cache/crawl_snapshots.sqlite`. Replay writes a **new** file under `reports/latest/` with `_regen_{id}_{timestamp}` in the name — it never overwrites the original crawl workbook.

List stored snapshots (PowerShell):

```powershell
sqlite3 .cache/crawl_snapshots.sqlite "SELECT snapshot_id, domain, run_timestamp, row_count FROM crawl_snapshots ORDER BY created_at DESC LIMIT 10;"
```

Mutually exclusive with `--quick-test`, `--full-smoke-test`, and `--validate`.

**Manual regression workflow:** crawl once → change reporter/rules → `--regen-report` → diff xlsx outputs or point `--previous-run` at an earlier regen workbook for delta sheets.

---

## Nuclear reset (local env artefacts)

**PowerShell:**

```powershell
Remove-Item -Recurse -Force .venv, .pytest_cache, .ruff_cache, uv.lock, test_dashboard_fix.xlsx -ErrorAction SilentlyContinue
```

**Bash / Git Bash:**

```bash
rm -rf .venv .pytest_cache .ruff_cache uv.lock test_dashboard_fix.xlsx
```

Then re-run **Fresh clone / full toolchain** above.

Delete PSI/crawl caches (required after breaking cache schema changes):

```powershell
Remove-Item -Recurse -Force .cache\ -ErrorAction SilentlyContinue
```

---

## Build the exe (distribution)

```powershell
uv sync --extra dev --extra semantic --extra render
uv run python build_exe.py
```

One-time dist setup (from repo root):

```powershell
copy .env dist\
copy secrets\client_secrets.json dist\
copy secrets\token.json dist\
mkdir dist\assets
copy assets\client_logo.png dist\assets\   # optional branding
```

```powershell
cd dist
.\hype-frog.exe --install-playwright   # one-time Chromium download (~150 MB)
.\hype-frog.exe --validate             # all checks should PASS
.\hype-frog.exe                        # interactive audit
```




Set-Location c:\Users\Dr0sera\Github\hype-frog
.\.venv\Scripts\Activate.ps1

# Optional: confirm a snapshot exists
python scripts\_check_snapshot_state.py


hype-frog --regen-report



https://africanmarketingconfederation.org/page-sitemap.xml
https://ticonafrica.org/page-sitemap.xml





https://africanmarketingconfederation.org/page-sitemap.xml
https://ticonafrica.org/page-sitemap.xml