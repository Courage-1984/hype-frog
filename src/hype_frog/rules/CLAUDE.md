# rules/ — scoped context

Inherits root [`CLAUDE.md`](../../../CLAUDE.md).

**Source of truth:** [`.cursor/rules/rules_engine.mdc`](../../../.cursor/rules/rules_engine.mdc).

Read it before editing this layer: `IssueRule` definitions in `registry.py` (`severity`, `name`, `fn`, `scope`), stable snake_case identifiers that are **never renamed**, frozen severity levels, pure scoring functions returning 0–100 or `None`. Follow the new-rule checklist before adding one.
