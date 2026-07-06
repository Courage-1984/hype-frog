---
paths:
  - tests/**
---

# Testing invariants

Source of truth: `.cursor/rules/auto_documentation.mdc` and `tests/CLAUDE.md`.

## Layout
Mirror `src/hype_frog/` paths under `tests/`.

## No live network in unit tests
Mock `aiohttp` and Playwright. `@pytest.mark.integration` for live-network tests (none exist yet).

## Extraction State
Assert `complete` | `partial` | `skipped` in crawl/fetch tests.

## Run
```powershell
uv run pytest tests/<layer>/ -q --tb=short
```
