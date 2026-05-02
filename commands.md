Bash / Git Bash:
rm -rf .venv .pytest_cache .ruff_cache uv.lock test_dashboard_fix.xlsx
PowerShell:
Remove-Item -Recurse -Force .venv, .pytest_cache, .ruff_cache, uv.lock, test_dashboard_fix.xlsx

uv sync

uv run playwright install chromium

uv run hype-frog --quick-test

uv run hype-frog

