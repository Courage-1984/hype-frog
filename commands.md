
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
uv run python -m spacy download en_core_web_sm

uv sync --extra render

uv run hype-frog --gsc-auth

==============================

$env:Path += ";$HOME\.local\bin"

.\.venv\Scripts\activate

uv run hype-frog --quick-test

uv run hype-frog

==============================

https://africanmarketingconfederation.org/page-sitemap.xml

https://ticonafrica.org/page-sitemap.xml

========================================================================

