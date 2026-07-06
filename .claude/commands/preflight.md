Run hype-frog preflight: credential/env validation, then targeted pytest for the layer being worked on.

**Step 1 — validate (no crawl):**
```powershell
uv run hype-frog --validate
```

**Step 2 — layer tests** (ask which layer if unclear; map `src/hype_frog/<layer>/` → `tests/<layer>/`):

```powershell
uv run pytest tests/<layer>/ -q --tb=short --maxfail=5
```

Common layers: `reporter`, `crawler`, `orchestration`, `rules`, `analysis`, `pipeline`, `core`, `extractors`, `diagnostics`.

**Default** when no layer is specified (quick smoke):
```powershell
uv run pytest tests/core/ tests/rules/ -q --tb=short --maxfail=5
```

Report validate exit code first, then pytest summary only — do not paste full logs.
