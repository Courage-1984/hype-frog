# Session modes (Plan vs acceptEdits / auto) — always loaded

These instruction surfaces apply in **every** permission mode. Mode only changes what may write to disk.

## Surfaces (always available)
- **Rules** — `.claude/rules/` (path-gated; this file + `baseline.md` always on)
- **Skills** — invoke with the Skill tool or `/skill-name` (auto skills: quick-verify, reporter-change, add-row-field, doc-sync)
- **Commands** — `/validate`, `/quick-test`, `/smoke-test`, `/regen-report`, `/layer-test`, `/reporter-test`, `/preflight`, `/new-issue`, `/new-sheet`
- **Agents** — prefer project agents over ad-hoc search: `explore-layer`, `reporter-reviewer`, `rules-auditor`, `contract-guardian`, `test-triager`, `doc-drift-checker`
- **Workflows** — `/layer-boundary-audit`, `/reporter-sheet-lock-audit` (read-only audits)

## Plan mode (`plan` / Shift+Tab / `/plan`)
- Research and draft a plan only — **no Edit/Write** to product code
- Do use Read/Grep/Glob, Skill tool, slash commands that only advise, and **read-only agents** (all project agents except do not ask test-triager to apply fixes)
- Prefer `explore-layer` then domain reviewers before proposing file lists
- When proposing changes: cite owning layer + matching `.claude/rules/<name>.md` + verify command
- After plan approval the user switches to acceptEdits/auto — carry the same checklists forward

## Accept edits / Auto (`acceptEdits` or `auto`)
- Edit/Write allowed in-repo; **git mutate still denied** (settings + hook + baseline)
- Invoke skills before finishing domain work (reporter-change, add-row-field, doc-sync, quick-verify)
- After reporter/rules/contracts edits, delegate the matching reviewer agent
- In `auto` mode, broad `Agent` allow rules may be dropped by the runtime — still spawn named project agents; they are expected and safe for this repo
- Verify with `uv run pytest tests/<layer>/` or `/regen-report` as appropriate

## Do not
- Disable or ignore project skills/agents because of permission mode
- Use ultracode by default (expensive); prefer named workflows for audits only
