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
uv run pytest --cov --cov-report=term-missing   # with coverage (no fail_under threshold yet)
```

## Duplicate test filenames across packages

`tests/core/test_quick_test.py` / `tests/diagnostics/test_quick_test.py` and
`tests/core/test_full_smoke_test.py` / `tests/diagnostics/test_full_smoke_test.py` are
**not duplicates** despite matching names: the `tests/core/` versions test
`core/run_config.py`'s preset constants (`quick_test_run_config()` etc.), while the
`tests/diagnostics/` versions test the `diagnostics/quick_test.py` /
`diagnostics/full_smoke_test.py` gate modules themselves. Search by full path, not
bare filename, when looking for "the quick-test tests."

## Registered-but-unused markers

`slow` and `network` are registered in `pytest.ini` alongside `integration`, but no test
currently uses either — same as `integration` (see above), these are reserved for future
use, not dead configuration.
