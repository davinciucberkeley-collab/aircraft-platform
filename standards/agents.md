# Agent Standard v0.1

How Claude (and any other model) is used to make things in this repo. Load this before any multi-agent task. It replaces "use whatever agent happens to be selected."

## Core rule

**The clearer the goal, the cheaper the agent.** If a task can be written as exact, checkable instructions, it goes to Haiku. If you can't write it that way yet, the task isn't ready to delegate — break it down further first.

## Roles

| Role | Model | Does | Never does |
|---|---|---|---|
| **Conductor** | Opus | Owns the goal. Breaks it into steps, declares which roles run each step, writes the plan to the task list. | Grinds through bulk work itself. |
| **Tactician** | Sonnet | Turns one fuzzy plan step into exact, checkable builder/scout instructions. Launches builders and scouts. Collects their results. | Makes design decisions that belong to the conductor. |
| **Builder** | Haiku | Executes one narrowly specified task: write this file to this schema, run this command, fix this named failure. | Interprets vague goals. If instructions are ambiguous, it stops and reports instead of guessing. |
| **Scout** | Haiku | Gathers information into a fixed template (see `knowledge/TEMPLATE-*.md`). | Writes free-form prose or opinions outside the template. |
| **Reviewer** | Opus — **one per task, reused** | Runs the validators, then judges only what validators can't check, against the named criteria in `standards/`. Returns a scorecard. | Says "looks good." Every judgment cites a criterion. |

### Who can launch whom

- Conductor → tactician, builder, scout, reviewer.
  - Conductor launches builders/scouts **directly** only when its instructions already meet the builder-ready bar below. Otherwise it goes through a tactician.
- Tactician → builder, scout.
- Builder, scout, reviewer → nobody.

**Nesting.** Claude Code allows subagents to launch subagents, up to 3 levels deep. The tactician definition includes the Agent tool, so a tactician launches its builders and scouts directly. (The 2026-11-11 A-series tactician ran with no launch tool; that setup is gone.)

**Briefing mode** is only the fallback where nesting is disabled: the tactician writes the builder briefs to `plans/<task>/briefs/*.md` and returns; the conductor launches one Haiku builder per brief, then hands the results back to the same tactician (SendMessage) to check. A tactician that does the builder work itself must report it as a process miss.

## Declaring agents up front

Before any agent is launched, the conductor writes a plan with an **agent table**:

```
| Step | Role | Model | Input | Output | Pass criterion |
```

No agent is launched that isn't in the table. Adding one mid-task means updating the table first.

## Builder-ready bar

Instructions can go to Haiku only if they include all of:

1. **Exact output** — file path(s) and format (schema version, template name).
2. **Exact inputs** — the files/URLs to use; nothing to "find."
3. **A mechanical pass check** — a command to run (`plane validate`, `pytest`) or template fields that must all be filled.
4. **Stop rule** — what to do when stuck: report the blocker, don't improvise.

## Reviews

- One reviewer instance per task, kept alive (`SendMessage`) for every review in that task. Don't spawn a new reviewer per item.
- Reviewer always runs the automated validators first (`plane validate --tier all`) and pastes the scorecard.
- Human-judgment items are scored against named criteria from `standards/` (e.g. `design-standards.yaml#static_margin`), each as PASS / FAIL / N/A with a one-line reason.
- Output format: see `standards/review-scorecard.md`.

## Cost check

At the end of a task the conductor reports how many agents of each role ran. If Opus or Sonnet did work that met the builder-ready bar, note it as a process miss.

## How this is enforced

Four agent definitions live in `.claude/agents/`:

| Agent (`subagent_type`) | Model | May edit |
|---|---|---|
| builder | haiku | files its brief names |
| scout | haiku | `knowledge/`, `standards/proposals/` only |
| tactician | sonnet | briefs and plan files; launches builders and scouts |
| reviewer | opus | `reviews/` only |

Hooks in `.claude/settings.json` call `tools/agent_hooks.py`:

- **Plan gate** (before every Agent launch): the description must start with a step id (e.g. `B15`) from an agent table in a `plans/` file changed in the last 14 days. The role must match `subagent_type`, and the model must match the agent definition. Otherwise the launch is blocked.
- **Edit gate** (before Edit, Write, NotebookEdit): the conductor may not edit `core/`, `tests/`, `designs/`, `schema/` or `.github/` unless `plans/conductor-edits.md` has a row dated today (UTC) for that file with a reason. Scouts edit only `knowledge/` and `standards/proposals/`. Reviewers edit only `reviews/`. No agent edits `standards/design-standards.yaml` or `.claude/`.
- **Agent log** (after each launch and on subagent stop): one line per event is appended to `plans/agent-log.jsonl`, with role, model, step, plan, description and token usage where reported.
- **CI citation check** (`plane check-citations`, in `validate.yml`): each URL a change adds under `knowledge/` or `standards/` is fetched. A title that does not match its citation fails; an unreachable URL warns.

**Limit:** the hooks apply only to Claude Code sessions started inside this repo. Chat sessions, other tools and other clones are not covered. CI is the only check that runs everywhere.

**Round 13 limits:** each gate runs `python3` and falls back to `python`, and the gate hooks set `onFailure: block`, so a gate that cannot start blocks the call instead of passing it. `tools/agent_hooks.py` and `.claude/` can be edited only by the main session with a dated `plans/conductor-edits.md` row, and never by a subagent. Bash writes are detected only after the fact: a post-Bash hook blocks the next step and logs any file a shell command changed that its caller may not edit, but it cannot undo the write and can also flag a concurrent agent's change.
Plans are dated by filename (`plans/YYYY-MM-DD-*.md`, 14 days), table rows inside code fences or HTML comments do not count, and only the conductor edits `plans/*.md` and `plans/conductor-edits.md`; tacticians write briefs under `plans/<plan-name>/briefs/`.
