---
name: layer-pytest
description: Run uv pytest for one hype-frog layer. Use when told to test a specific package or after /layer-test.
disable-model-invocation: true
---

# Layer pytest

```powershell
uv run pytest tests/$ARGUMENTS/ -q --tb=short
```

If `$ARGUMENTS` empty, ask which layer: `core`, `crawler`, `extractors`, `pipeline`, `analysis`, `rules`, `reporter`, `orchestration`, `checkpoint`, `snapshots`, `validators`, `diagnostics`, `config`.

Hook `HF_CLAUDE_HOOK_TEST=0` disables post-edit auto pytest.
