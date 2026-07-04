# tests/ — scoped Claude Code context

Inherits root `CLAUDE.md`. Additional invariants for this layer only.

## Layout mirrors src/

Test packages mirror `src/hype_frog/` paths exactly:
`tests/crawler/` → `src/hype_frog/crawler/`, `tests/reporter/` → `src/hype_frog/reporter/`, etc.
New test files go in the matching package. Do not create top-level test files outside a package directory.

## No live network in unit tests

Mock `aiohttp` sessions and Playwright interactions with `unittest.mock`. Async tests use `pytest-asyncio`.
`tests/integration/` is for offline, multi-module smoke tests that exercise real code paths (no internals mocked out) against local fixtures — it does not by itself mean "live network." Today every file in `tests/integration/` is offline and runs as part of the default `uv run pytest`. If a test genuinely needs live network/credentials, mark it `@pytest.mark.integration` (registered in `pytest.ini`) so it can be deselected with `-m "not integration"`; no such test exists yet.

## Extraction state must be asserted explicitly

Tests covering crawl or fetch outcomes must assert `Extraction State` against one of the three lowercase literals: `complete`, `partial`, `skipped`. Never leave the three-way contract ambiguous or unasserted.

## Common patterns

- **Env var tests:** use `monkeypatch.setenv` / `monkeypatch.delenv` — see `tests/orchestration/test_run_setup.py` for the established pattern
- **Fixtures:** shared HTML/JSON test data lives in `tests/fixtures/` — reuse before creating new files
- **Async tests:** annotate with `@pytest.mark.asyncio`; import async helpers from `pytest_asyncio` where needed
- **Integration tests:** live-network/credential tests are marked `@pytest.mark.integration` and excluded via `-m "not integration"`; offline multi-module tests in `tests/integration/` are unmarked and run by default

## Run the suite

```powershell
uv run pytest                          # full suite
uv run pytest tests/reporter/          # reporter layer only
uv run pytest tests/crawler/           # crawler layer only
uv run pytest -k "test_extraction"     # filter by name
```
