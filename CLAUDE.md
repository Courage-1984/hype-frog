# hype-frog

Python 3.12 asyncio SEO/AEO pipeline → Excel workbook + optional HTML/PDF.

# NB | CRITICAL: NEVER git commit, push, add, or rebase.

## Layers (dependency direction)

`core` / config → `crawler` / `extractors` → `validators` / `analysis` → `pipeline` / `rules` → `reporter`. `orchestration` coordinates only. `checkpoint` = resume; `snapshots` = `--regen-report` replay (do not conflate).

| Package | Owns |
|---------|------|
| core | Models, env accessors, logging, URL identity |
| crawler | Fetch, assemble rows, PSI/GSC |
| extractors | Parse-only HTML/schema/AEO |
| pipeline | Enrichment glue, Main merge, graph/links |
| rules | IssueRule registry, scoring, playbook |
| reporter | openpyxl workbook (read-only rows) |
| orchestration | BFS, enrichment phases, export sequence |
| diagnostics | `--validate` / `--quick-test` / `--full-smoke-test` |

## Verify
```
uv run pytest tests/<layer>/
uv run hype-frog --quick-test-fast
uv run hype-frog --regen-report   # reporter-only, no crawl
uv run hype-frog --validate
```

## Before editing
1. Identify owning layer — path-scoped rules under `.claude/rules/` load automatically
2. Read that package’s `CLAUDE.md` if present
3. >3 files → ask human first (unless approved in-thread)
4. One-sentence vibe check before non-trivial logic

## Contracts
- Additive row keys only (`core/models.py`). Extraction State: `complete` | `partial` | `skipped`
- `print()` prohibited in `pipeline/` and `orchestration/` — use `core/` logging
- Toolchain: `uv` only. Env: `core/env_vars.py` → `config_loader.py` (never `os.environ` elsewhere)
- LLM/PSI HTTP: short timeout, instant `Unknown` fallback, no blocking retries
- User-facing copy: British English

## Claude Code surfaces (Plan mode and acceptEdits/auto)
Always use these — permission mode only gates writes, not discovery:
- **Rules** — `.claude/rules/` (path-gated; `baseline.md` + `session-modes.md` always on)
- **Skills** — Skill tool or `/name` under `.claude/skills/<domain>/`
- **Commands** — `/validate`, `/quick-test`, `/smoke-test`, `/regen-report`, `/layer-test`, …
- **Agents** — `explore-layer`, `reporter-reviewer`, `rules-auditor`, `contract-guardian`, `test-triager`, `doc-drift-checker`
- **Workflows** — `/layer-boundary-audit`, `/reporter-sheet-lock-audit`

**Plan mode:** research + plan only (no product edits); prefer explore/reviewer agents and skills for checklists.
**acceptEdits / auto:** implement with the same skills/agents; git mutate still denied. See `.claude/rules/session-modes.md`.

## Canonical docs (exactly six under `docs/`)
`docs/system_architecture.md` · `docs/data_contracts.md` · `docs/excel_reporting_standards.md` · `docs/workbook_tabs.md` · `docs/logging_architecture.md` · `docs/performance_benchmarks.md` · `commands.md` · `.env.example`
