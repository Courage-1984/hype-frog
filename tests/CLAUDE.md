# tests/ — scoped context

Inherits root [`CLAUDE.md`](../CLAUDE.md).

**Source of truth:** [`.cursor/rules/auto_documentation.mdc`](../.cursor/rules/auto_documentation.mdc) (testing section) and [`.claude/rules/testing.md`](../.claude/rules/testing.md).

Mirror `src/hype_frog/` layout. No live network in unit tests. Assert `Extraction State` explicitly.

```powershell
uv run pytest tests/<layer>/ -q --tb=short
```
