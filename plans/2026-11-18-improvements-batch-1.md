# Plan: improvements batch 1 + creator research (2026-11-18)

Conductor: Opus. Follows `standards/agents.md`. User asked (2026-11-18): research creators' own sites (Peter Sripol, Project Air, Flite Test, others) since YouTube itself isn't reachable, and "get started on the other stuff" (the board's improvement list).

## Decisions (conductor)
- Base branch: `ci-baselines` (PR #1, not merged yet). Every task gets its own branch and git worktree under `/home/claude/wt/<task>`, so agents can't collide; each becomes its own PR once #1 is merged.
- In a worktree, agents run code with `export PYTHONPATH=<worktree>/core` so `plane` and `pytest` use the worktree's code, not the main checkout.
- Batch 1 = items that are well specified and don't need team input: #2, #3, #4, #7, #9–#11, plus creator research. Batch 2 (after this): #15, #16, #17, #6, #12–#14. #5 (joint strengths) needs the team's measurements.

## Agent table

| Step | Role | Model | Branch / output | Pass criterion |
|---|---|---|---|---|
| S7a | Scout | Haiku | `research-creators`: Flite Test articles + plans | template filled, sources opened |
| S7b | Scout | Haiku | same branch: Peter Sripol, Project Air | same |
| S7c | Scout | Haiku | same branch: rctestflight, Tom Stanton, Eclipson, others | same |
| B12 | Builder | Haiku | `results-summary` (#2) | md scorecard leads with summary + failures; tests green |
| B13 | Builder | Haiku | `import-id` (#3) | `plane import dbf --concept X --id Y`; tests green |
| S8 | Scout | Haiku | `threshold-sources` (#7) | each pending threshold has ≥1 opened source or "none found" |
| B14 | Builder | Haiku | `setup-and-windows` (#9–#11) | environment.yml, Windows CI job, live viewer link |
| T9 | Tactician | Sonnet | `aero-vlm` (#4) | AeroSandbox neutral point; concept A vs Dillon's 40.7 mm explained |
| R1 | Reviewer | Opus (reused) | each branch | scorecard before merge |
