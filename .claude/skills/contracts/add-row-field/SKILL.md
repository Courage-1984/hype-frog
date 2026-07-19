---
name: add-row-field
description: Add an additive Main/Extra row field through models defaults so it survives validate/merge. Use when introducing new row keys.
---

# Add row field (additive)

1. Add default to `MAIN_ROW_DEFAULTS` and/or `EXTRA_ROW_DEFAULTS` / `ENRICHMENT_PIPELINE_DEFAULTS` in `core/models.py`
2. Populate in the owning layer (crawler assembler, pipeline, analysis) — additive only
3. Wire reporter column only if the sheet should show it
4. Update `docs/data_contracts.md` if semantics matter to consumers
5. Test: assert field present after validate/merge; Extraction State tests unchanged unless relevant

```powershell
uv run pytest tests/core/ tests/<owning-layer>/ -q --tb=short
```

Never rename/remove existing keys without migration + approval.
