---
name: hype-frog-quick-verify
description: Run layer-appropriate pytest and suggest the right hype-frog verification gate.
---

# Quick verify

1. Identify the layer touched (`reporter`, `crawler`, `orchestration`, etc.).
2. Run: `uv run pytest tests/<layer>/ -q --tb=short`
3. Suggest gate:
   - Reporter/export only → `HF_REGEN_REPORT=1 uv run hype-frog --regen-report`
   - General smoke → `uv run hype-frog --quick-test-fast`
   - Pre-export → `uv run hype-frog --full-smoke-test-fast`

Never run git commands.
