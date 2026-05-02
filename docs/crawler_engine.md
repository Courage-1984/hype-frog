# Crawler engine

## Modes

- **HTTP (fast)** — Default path using `aiohttp` and HTML parsers. Suitable when DOM execution is not required.
- **Rendered (accurate)** — Uses `playwright.async_api` to load the page and snapshot HTML. If Playwright or Chromium is unavailable, or the event loop cannot spawn subprocesses, the implementation **falls back** to HTTP and marks extraction accordingly.

## Extraction contract

Row data includes observability fields used by scoring (see `rules/scoring.py` for consumption examples):

| Field | Allowed values (conceptual) |
|-------|------------------------------|
| Extraction State | `complete`, `partial`, `skipped` |
| Extraction Source | `raw_http`, `rendered_browser` |

Fetch code sets `partial` when rendering is incomplete or degraded, and may return `skipped`-compatible outcomes when upstream assigns that default in merge logic.

## Retries and backoff

Network configuration (`config.py`) supplies maximum attempts, base delay, max delay, backoff factor, jitter, and retryable HTTP status codes. Fetch logic must remain **bounded**: after exhausting retries, failures surface as structured row state rather than infinite loops.

## Session and connector limits

`create_session` wires `aiohttp.TCPConnector` with global and per-host limits and keepalive timeout from configuration. Do not remove these limits without an explicit replacement strategy.

## Playwright constraints

- Import and use **`playwright.async_api`** only in crawler runtime code.
- Browser launch, navigation, waits, and `page.content()` run inside async context managers; semaphore acquisition limits parallel browser count.

## URL identity

Normalization helpers (`utils`, `core`) ensure deduplication, checkpoint resume, and join keys stay consistent across crawl, enrichment, and reporting.
