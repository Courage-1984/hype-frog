#!/usr/bin/env bash
set -euo pipefail

uv venv
uv sync --extra dev --extra render --extra llm
echo "Installing Playwright Chromium browsers (uv run playwright install chromium)..."
uv run playwright install chromium
