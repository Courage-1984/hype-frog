
Bash / Git Bash:
rm -rf .venv .pytest_cache .ruff_cache uv.lock test_dashboard_fix.xlsx
PowerShell:
Remove-Item -Recurse -Force .venv, .pytest_cache, .ruff_cache, uv.lock, test_dashboard_fix.xlsx

git rm -r --cached .
git add .
git commit -m "Cleanup: Untrack files listed in .gitignore"
git push -u origin main

==============================

$env:Path += ";$HOME\.local\bin"

.\.venv\Scripts\activate

uv run playwright install chromium

# Semantic / AEO entity columns (spaCy NER — optional; keyword fallback works without this)
uv sync --extra semantic
uv run hype-frog --install-semantic

uv sync --extra render --extra semantic

uv run hype-frog --gsc-auth

uv run hype-frog --validate
uv run hype-frog --validate --validate-url "https://africanmarketingconfederation.org/"

==============================

$env:Path += ";$HOME\.local\bin"

.\.venv\Scripts\activate

uv run hype-frog --quick-test          # full gate: preflight + pytest + 10-URL crawl + workbook audit
uv run hype-frog --quick-test-fast     # crawl + workbook audit only (~5 min)

uv run hype-frog

==============================

https://africanmarketingconfederation.org/page-sitemap.xml

https://ticonafrica.org/page-sitemap.xml

========================================================================


$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

# Check everything (no crawl)
uv run hype-frog --validate

# Also confirm a crawl target matches a Search Console property
uv run hype-frog --validate --validate-url "https://africanmarketingconfederation.org/"


uv sync --extra semantic

uv run hype-frog --install-semantic
uv run hype-frog --validate

uv sync --extra semantic --extra render --extra dev
uv run playwright install chromium
uv run hype-frog --install-semantic
