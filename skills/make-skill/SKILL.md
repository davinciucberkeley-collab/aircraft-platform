---
name: make-skill
description: Use when creating or revising any skill in this repo's skills/ folder, so every skill has the same shape, uses the CLI/MCP instead of its own logic, and has a mechanical pass check.
---

# Making a skill

Every skill in `skills/` follows this shape. A skill is instructions for using the platform (`plane` CLI / `aircraft-platform` MCP), not a second implementation of it. If a skill needs logic the platform lacks, add it to `core/` first.

## Required sections (in this order)

1. **Frontmatter** — `name` (kebab-case, matches folder) and `description`: one sentence starting "Use when…", naming the trigger.
2. **Goal** — one or two sentences: what "done" looks like.
3. **Agents** — the agent table from `standards/agents.md` for this skill: which roles run, which model, what each produces. Default to the cheapest role that can meet the builder-ready bar.
4. **Steps** — numbered. Each step names the exact command or MCP tool and its output path.
5. **Pass check** — a command or checklist that decides done/not done mechanically (e.g. `plane validate … ; echo $?` → 0).
6. **Stop rules** — when to stop and ask a human instead of improvising.

## Rules

- Under ~120 lines. If longer, split it or move reference material into a sibling file the skill links to.
- No numbers or thresholds inside skills: link to `standards/design-standards.yaml#key` so one edit updates everything.
- Every output lands in the repo (designs/, knowledge/, reviews/), never only in a chat or a temporary artifact.

## Pass check for a new skill

- [ ] All six sections present
- [ ] Every step names a command, MCP tool or file path
- [ ] Pass check is mechanical
- [ ] Tried once end-to-end on a real input; result committed
