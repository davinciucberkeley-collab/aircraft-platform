# Plan: CI fails only on regressions (2026-11-17)

Conductor: Opus. Follows `standards/agents.md`. User approved 2026-11-17 ("yes lets do the next step").

## Problem
`validate.yml` fails whenever any design isn't accepted. No real design is accepted yet (C0 family 15–19 FAILs, tilt-wing 37, concept A 4 FAIL + 64 SKIP), so `main` is permanently red and the signal is lost.

## Decisions (conductor)
- Each design has `designs/<id>/baseline.json`: its known non-PASS results (FAIL and SKIP; WARN ignored).
- A result's key = `check_id` + message with standalone numbers replaced by `#` (ids like `wng-006-l` or `E-WNG-20` keep their digits). Values may move without counting as a change; status changes count.
- CI fails on a **regression**: a FAIL/SKIP whose key isn't in the baseline; a FAIL whose key the baseline has as SKIP; or a non-accepted design with no baseline.
- **Improvements** (baseline keys no longer present, or FAIL→SKIP) never fail CI; the summary asks for `plane baseline update` to lock them in.
- **Baseline growth is visible:** on a PR, keys added to a baseline relative to the base branch are listed and raise a GitHub `::warning` annotation, so nobody quietly hides a new failure.
- Accepted designs need no baseline.

## Agent table

| Step | Role | Model | Input | Output | Pass criterion |
|---|---|---|---|---|---|
| B10 | Builder | Haiku | this plan + brief | `core/aircraft_platform/baseline.py`, `plane baseline update/check`, tests, `validate.yml`, baselines for all designs, docs | pytest green; `plane baseline check --all` exits 0 on main; a mutated design exits 1 |
| R1 | Reviewer | Opus (reused) | the change | review round 9 | scorecard; tries to sneak a regression past CI |
