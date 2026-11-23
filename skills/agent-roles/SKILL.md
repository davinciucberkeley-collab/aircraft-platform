---
name: agent-roles
description: Use when any multi-agent task in this repo needs planning, launching or checking agents against standards/agents.md.
---

# Running agents by role

## Goal
A plan in `plans/` with an agent table written before any launch, every launch made under a step id from that table, and a cost check at the end. Done means the agent log and the plan agree.

## Agents
| Step | Role | Model |
|---|---|---|
| Plan, launch and check (this skill) | Conductor (main session) | Opus |
| Builder-ready step (exact output, inputs, pass check, stop rule) | Builder | Haiku |
| Fuzzy step that is not yet builder-ready | Tactician | Sonnet |
| Gather facts into a `knowledge/` template | Scout | Haiku |
| Review against `standards/` (one per task, reused) | Reviewer | Opus |

Definitions are in `.claude/agents/`. The model comes from the definition, not from the conductor's choice.

## Steps
1. Write `plans/<date>-<task>.md` with an agent table: `| Step | Role | Model | Input | Output | Pass criterion |`. Give each step a short id (for example `B15`).
2. Check each row against the builder-ready bar in `standards/agents.md#builder-ready-bar`. A row that fails it goes to a tactician, not a builder.
3. Launch with the Agent tool. Set `subagent_type` to `builder`, `scout`, `tactician` or `reviewer`, and start `description` with the step id, for example `B15 write hooks`. The role must match the row.
4. If the plan gate blocks a launch, its message names the table to fix. Update the plan, then relaunch. Do not work around the gate.
5. Conductor edits to `core/`, `tests/`, `designs/`, `schema/` or `.github/` go to a builder. If one cannot be avoided, add a dated row with a reason to `plans/conductor-edits.md` first.
6. At the end, read `plans/agent-log.jsonl`. Count `agent_done` lines by `subagent_type` and `model`, and list any whose `plan` is null (a launch not in a table).
7. Report the cost check: agents per role and model, plus any Opus or Sonnet run that did builder-ready work (a process miss). If a review ran, put the same facts in the Process section of `reviews/` per `standards/review-scorecard.md`.

## Pass check
- [ ] `python -m pytest -q tests/test_agent_hooks.py; echo $?` prints `0`
- [ ] `python -c "import json,os; p='plans/agent-log.jsonl'; rows=[json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []; bad=[r for r in rows if r.get('event')=='agent_done' and not r.get('plan')]; print(len(bad)); raise SystemExit(1 if bad else 0)"; echo $?` prints `0`, so every logged launch has a plan row
- [ ] The cost check from step 7 is written in the final report

## Stop rules
- A step is not builder-ready and no tactician can make it so: stop and ask the human what to decide.
- A hook fails closed (its message says "failed closed"): stop and report the message. Do not edit `tools/agent_hooks.py` or `.claude/` to get past it without the human's approval.
- A launch is blocked for a reason the plan cannot fix without a design decision: stop and ask.
