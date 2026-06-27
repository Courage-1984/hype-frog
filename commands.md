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

```powershell
uv run hype-frog                              # interactive prompts
uv run hype-frog --quick-test                 # preflight + pytest + 10-URL crawl + workbook audit
uv run hype-frog --quick-test-fast            # crawl + workbook audit only (~5 min)
```

Quick-test flags (combine with `--quick-test`):

| Flag | Effect |
|------|--------|
| `--quick-test-skip-preflight` | Skip GSC/PSI preflight |
| `--quick-test-skip-pytest` | Skip pytest subset |
| `--quick-test-skip-audit` | Skip workbook audit |

Override preset BFS depth: `HF_MAX_DEPTH=1 uv run hype-frog --quick-test-fast`

Useful crawl flags (see `uv run hype-frog --help`):

`--check-images` · `--check-og-images` · `--gsc-url-inspection` · `--gsc-url-inspection-full` · `--competitors domain.com` · `--previous-run path.xlsx` · `--streaming` · `--export-pdf` · `--psi-delay 2.5`

Output defaults to `reports/latest/` unless `HF_OUTPUT_FILENAME` is set.

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

---

## Git: re-sync index with `.gitignore` (use with care)

```bash
git rm -r --cached .
git add .
git commit -m "Cleanup: Untrack files listed in .gitignore"
git push -u origin main
```

---

## Still TODO

| # | Item | Notes |
|---|------|--------|
| 13 | D2 — LLM as post-crawl pass | Cost and reliability improvement |
