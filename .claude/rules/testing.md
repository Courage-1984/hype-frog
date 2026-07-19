---
paths:
  - tests/**
---

# Testing invariants

## Layout
Mirror `src/hype_frog/` under `tests/` (`tests/reporter/`, `tests/pipeline/`, …).

## Network
No live network in unit tests — mock aiohttp/Playwright. Live calls only under `tests/integration/` with `@pytest.mark.integration` (excluded from default runs).

## Extraction State
Assert `complete` | `partial` | `skipped` explicitly in crawl/fetch tests.

## Run
```powershell
uv run pytest tests/<layer>/ -q --tb=short
```

Prefer skill `.claude/skills/verification/quick-verify/` when choosing a gate after edits.
