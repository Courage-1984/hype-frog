# tests/ — scoped Claude Code context

Inherits root `CLAUDE.md`. Additional invariants for this layer only.

## Layout mirrors src/

Test packages mirror `src/hype_frog/` paths exactly:
`tests/crawler/` → `src/hype_frog/crawler/`, `tests/reporter/` → `src/hype_frog/reporter/`, etc.
New test files go in the matching package. Do not create top-level test files outside a package directory.

## No live network in unit tests

Mock `aiohttp` sessions and Playwright interactions with `unittest.mock`. Async tests use `pytest-asyncio`.
Real network calls are only permitted in `tests/integration/` and must be marked `@pytest.mark.integration` — they are excluded from the default `uv run pytest` run.

## Extraction state must be asserted explicitly

Tests covering crawl or fetch outcomes must assert `Extraction State` against one of the three lowercase literals: `complete`, `partial`, `skipped`. Never leave the three-way contract ambiguous or unasserted.

## Common patterns

- **Env var tests:** use `monkeypatch.setenv` / `monkeypatch.delenv` — see `tests/orchestration/test_run_setup.py` for the established pattern
- **Fixtures:** shared HTML/JSON test data lives in `tests/fixtures/` — reuse before creating new files
- **Async tests:** annotate with `@pytest.mark.asyncio`; import async helpers from `pytest_asyncio` where needed
- **Integration tests:** marked `@pytest.mark.integration` and excluded from the default run

## Run the suite

```powershell
uv run pytest                          # full suite
uv run pytest tests/reporter/          # reporter layer only
uv run pytest tests/crawler/           # crawler layer only
uv run pytest -k "test_extraction"     # filter by name
```
