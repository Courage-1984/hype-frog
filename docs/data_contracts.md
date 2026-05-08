# Data contracts

## Crawl result envelope

Each processed URL contributes:

- **`main`** — `dict[str, Any]` aligned with `MainRowPayload` contracts in `src/hype_frog/core/models.py` plus additive pipeline fields (scores, badges, extraction metadata, etc.).
- **`extra`** — `dict[str, Any]` for extended signals (`ExtraRow` patterns: links, hreflang, snippets, etc.).

Typed payload models in `src/hype_frog/core/models.py` document intent; runtime rows may carry additional additive keys where models permit `extra="allow"`.

## Additive key policy

Established keys consumed by reporters, scoring, or checkpoints **must not be renamed or removed** without an explicit migration and human approval. New analytics should add **new keys** or clearly versioned side structures.

## Extraction observability

`Extraction State` and `Extraction Source` are part of the contract between `crawler/fetcher.py` outcomes and downstream scoring. Values must stay aligned with the lowercase literals documented in [crawler_engine.md](./crawler_engine.md).

## Serialization and checkpoints

Checkpoint payloads store completed URL lists and serialized crawl results. Any change to on-disk checkpoint schema must remain backward compatible or be version-guarded.
