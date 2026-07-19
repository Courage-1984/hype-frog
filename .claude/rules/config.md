---
paths:
  - src/hype_frog/config.py
  - src/hype_frog/config_defaults.py
  - src/hype_frog/config_loader.py
  - src/hype_frog/core/env_vars.py
  - .env.example
---

# Config and env

## Ownership
- `config_defaults.py` — pure constants only (no env reads)
- `core/env_vars.py` — **only** module that may call `os.environ`
- `config_loader.py` — merges env accessors with defaults
- `config.py` / `RunConfig` — validated, immutable after construction

## Precedence
`.env` < shell env < CLI flags

## Naming
- Product knobs: `HF_*` (booleans `1`/`0` or unset)
- Vendor keys: conventional names (`PSI_API_KEY`, etc.)
- Document every new var in `.env.example` before merge
- Never read env in crawler/pipeline/analysis/orchestration/reporter — pass `RunConfig`
