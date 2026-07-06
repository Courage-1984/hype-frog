# Git sovereignty and toolchain (always loaded)

- NEVER run git commands (add, commit, push, rebase, reset, restore).
- Use `uv` only: `uv sync`, `uv run`, `uv add`. No pip or python -m venv.
- >3 file changes require explicit user approval unless approved in-thread.
