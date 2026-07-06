Checklist for adding a new IssueRule:

1. Add `IssueRule` to `src/hype_frog/rules/registry.py` (stable ID, correct `scope`: `url` | `site` | `server`)
2. Add playbook entry in `src/hype_frog/rules/playbook_entries.py`
3. Add test in `tests/rules/` mirroring scope behaviour
4. If new row fields needed: additive keys in `core/models.py` defaults
5. Update `docs/data_contracts.md` if contract changes

Verify: `uv run pytest tests/rules/ -q --tb=short`
