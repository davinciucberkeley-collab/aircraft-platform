# Plan: enforce the agent standard with tools (2026-11-18)

Conductor: Opus. User approved 2026-11-18 ("yes build this").

## Why
`standards/agents.md` was only a document. Misses in this project: the conductor wrote builder-ready code itself; agents were launched that no plan table listed; tacticians couldn't launch builders; an agent cited a page it never opened; misses were only noticed afterwards.

## Decisions (conductor)
1. **Agent definitions** in `.claude/agents/`: `builder` (haiku), `scout` (haiku, may write only under `knowledge/` and `standards/proposals/`), `tactician` (sonnet; writes briefs, doesn't build), `reviewer` (opus; read-only except `reviews/`). The model lives in the definition, not in the conductor's choice.
2. **Plan gate (hook before every agent launch):** the launch's description must begin with a step id (e.g. `B12`) that appears in the agent table of a plan in `plans/` modified in the last 14 days, and the agent type/model must match that row. Otherwise the launch is blocked with a message saying which table to update.
3. **Conductor code gate (hook before Edit/Write):** the main session may not edit `core/`, `tests/`, `designs/`, `schema/` or `.github/`; subagents may. If hooks can't tell the main session from a subagent, fall back to: the main session's edits there are blocked unless the file `plans/<task>/conductor-edits.md` lists the file with a reason (visible in review).
4. **Citation check (CI):** for every URL a change adds under `knowledge/` or `standards/`, fetch it and compare the page title with the cited title/claim keywords; mismatch → FAIL, unreachable → WARN. Runs in `validate.yml`.
5. **Agent log (hook on agent stop):** append role, model, step id, plan, timestamps and tokens if available to `plans/<plan-name>/agent-log.jsonl`. `standards/review-scorecard.md` gains a "Process" section scored against `agents.md` using that log.
6. `standards/agents.md` updated to describe these mechanisms; a short skill `skills/agent-roles/SKILL.md` points to them (board item #14).

## Agent table

| Step | Role | Model | Output | Pass criterion |
|---|---|---|---|---|
| S9 | Scout (claude-code-guide) | its own | facts on hook inputs: can a hook tell main session vs subagent; Agent-tool input fields; SubagentStop payload; agent definition frontmatter (model, tools) | answers with doc links |
| B15 | Builder | haiku | `.claude/agents/*.md`, `.claude/settings.json` hooks, `tools/agent_hooks.py`, tests | each rule blocks a deliberate violation in a test |
| B16 | Builder | haiku | `core/aircraft_platform/citations.py`, `plane check-citations`, CI step, tests | catches the 1987 law-review mismatch in a test |
| B17 | Builder | haiku | agents.md, review-scorecard.md, skills/agent-roles | docs match the mechanisms |
| R1 | Reviewer | opus (reused) | review round 13 | tries to break each rule |

## Round 13 fixes (conductor decisions)
| Step | Role | Model | Output | Pass criterion |
|---|---|---|---|---|
| B18 | Builder | haiku | hooks: python3/python fallback + block on failure; worktree paths gated; tools/agent_hooks.py and .claude/ protected; general-purpose can't fill role rows; Bash writes detected after the fact | each round-13 attack now caught or logged |
| B19 | Builder | haiku | citations: 404 and homepage-redirect FAIL; stronger title match; `source_url:` extraction fixed | round-13 citation attacks FAIL |
