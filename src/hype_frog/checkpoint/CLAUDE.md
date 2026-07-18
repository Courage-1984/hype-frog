# checkpoint/ — scoped context

Inherits root [`CLAUDE.md`](../../../CLAUDE.md).

**Source of truth:** [`.cursor/rules/checkpoint.mdc`](../../../.cursor/rules/checkpoint.mdc).

Read it before editing this layer: `store.py` (durable crawl-progress persistence for `orchestration/crawl_runner_bfs.py` resume), `cache.py` (general-purpose crawl-scoped cache), `link_inventory_cache.py`. Writes must be idempotent and resumable — prefer atomic write-to-temp-then-replace over in-place mutation.
