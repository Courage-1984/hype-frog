Bash / Git Bash:
rm -rf .venv .pytest_cache .ruff_cache uv.lock test_dashboard_fix.xlsx
PowerShell:
Remove-Item -Recurse -Force .venv, .pytest_cache, .ruff_cache, uv.lock, test_dashboard_fix.xlsx

.\.venv\Scripts\activate

# Accurate/rendered mode needs the `render` extra (plain `uv sync` does NOT install Playwright).
uv sync --extra render

# Required for accurate mode: downloads Chromium (~300MB) into %LOCALAPPDATA%\ms-playwright — not installed by `uv sync`.
uv run playwright install chromium

uv run hype-frog --quick-test

uv run hype-frog

# Trigger GSC OAuth only (creates/refreshes src/hype_frog/token.json)
uv run hype-frog --gsc-auth

git rm -r --cached .
git add .
git commit -m "Cleanup: Untrack files listed in .gitignore"
git push -u origin main

