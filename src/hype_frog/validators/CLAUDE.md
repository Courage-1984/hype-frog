# validators/ — scoped context

Inherits root [`CLAUDE.md`](../../../CLAUDE.md).

**Source of truth:** [`.cursor/rules/validators.mdc`](../../../.cursor/rules/validators.mdc).

Read it before editing this layer: `schema_validator.py` owns JSON-LD validation, invoked during HTML assembly (not from reporters). No workbook I/O; read-only enrichment; never raise on malformed JSON-LD — degrade gracefully.
