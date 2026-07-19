# core/ — scoped context

Inherits root [`CLAUDE.md`](../../../CLAUDE.md).

**Rules:** [`.claude/rules/data-contracts.md`](../../../.claude/rules/data-contracts.md), [`.claude/rules/config.md`](../../../.claude/rules/config.md), [`.claude/rules/architecture.md`](../../../.claude/rules/architecture.md).

Owns Pydantic contracts (`models.py`), `env_vars.py` (sole `os.environ` reader), logging, URL normalisation, discovery order. Additive keys only.
