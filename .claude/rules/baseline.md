# Git sovereignty and toolchain (always loaded)

- NEVER run mutating git commands (`add`, `commit`, `push`, `rebase`, `reset`, `restore`, `checkout --`). Read-only `git status` / `log` / `diff` / `branch` / `rev-parse` only.
- Toolchain: `uv` only (`uv sync`, `uv run`, `uv add`). No pip or ad-hoc venvs.
- >3 file changes require explicit user approval unless already approved in-thread.
- Ignore `archive/`, `archive_legacy/`, `.old/` for scans and refactors — not live product code.
- User-facing copy: British English (e.g. Optimisation, colour).
- Prefer small, reviewable diffs. Do not delete repo files to “clean up”.
- Plan mode and acceptEdits/auto both use project skills, agents, commands, and workflows — see `session-modes.md`. Mode only changes whether Edit/Write is allowed.