# hype-frog

Python 3.12 asyncio SEO/AEO pipeline → Excel workbook + optional HTML/PDF.

# NB | CRITICAL: NEVER git commit, push, add, or rebase.

## Verify
```
uv run pytest tests/<layer>/
uv run hype-frog --quick-test-fast
uv run hype-frog --regen-report   # reporter-only, no crawl
uv run hype-frog --validate
```

## Before editing
1. Identify owning layer — `docs/system_architecture.md`
2. Read scoped `CLAUDE.md` + `.cursor/rules/<layer>.mdc` for that package
3. >3 files → ask human first
4. Vibe check (one sentence) before non-trivial logic

## Contracts
- Additive row keys only (`core/models.py`). Extraction State: `complete` | `partial` | `skipped`
- `print()` prohibited in `pipeline/` and `orchestration/` — use `core/` logging
- Toolchain: `uv` only. Env: `core/env_vars.py` → `config_loader.py` (never `os.environ` elsewhere)
- LLM/PSI HTTP: short timeout, instant `Unknown` fallback, no blocking retries

## Canonical docs
`docs/system_architecture.md` · `docs/data_contracts.md` · `docs/excel_reporting_standards.md` · `commands.md` · `.env.example`
