---
name: quick-verify
description: After editing hype-frog, pick layer pytest and the right gate (regen/quick/smoke). Use when finishing a change or asking how to verify.
---

# Quick verify

1. Map edited path → layer under `tests/<layer>/`.
2. Run:
```powershell
uv run pytest tests/<layer>/ -q --tb=short
```
3. Suggest the lightest sufficient gate:

| Change type | Gate |
|-------------|------|
| Reporter/sheets only | `--regen-report` then `tests/reporter/` |
| Rules/scoring | `tests/rules/` |
| Pipeline/analysis | matching layer pytest |
| Cross-layer / crawl | `--quick-test-fast` |
| Pre-release | `--full-smoke-test-fast` or `/smoke-test` |

Never git commit. Prefer `/layer-pytest` skill for the exact recipe.
