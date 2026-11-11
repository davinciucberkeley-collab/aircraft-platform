---
name: design-concept
description: Use when asked to create or modify an aircraft design or concept; produces a designs/<id>/plane.yaml that passes the validation tiers instead of a one-off HTML page or artifact.
---

# Design a concept

## Goal
A new or changed `designs/<id>/plane.yaml` that conforms to `schema/plane.schema.json` and passes `plane validate` (tiers 0–5), plus a short `designs/<id>/README.md` saying what it is and what it's trying to learn.

## Agents
| Step | Role | Model |
|---|---|---|
| Pick morphology, set requirements | Conductor | Opus |
| Write/patch YAML to a precise spec | Builder | Haiku |
| Fix a named validator failure | Builder | Haiku (escalate to Sonnet after 3 failed attempts on the same check) |
| Final review | Reviewer | Opus (one) |

## Steps
1. Check what already exists: `plane list` (MCP: `list_designs`). Check `knowledge/morphological-chart.yaml` for the cell this concept fills, and `knowledge/diy-projects/` for prior art. Record both under `lineage`.
2. Start from the closest design: `plane new <id> --from <closest-id>`.
3. Set `morphology`, `requirements`, then components. Units: mm, g, N, deg. Body frame: +x aft from the nose, +y right, +z up. Model propellers as swept-disc cylinders so prop strikes are caught.
4. Declare every joint in `attachments`, with `location`, `method` and `rated_load_n`. Use `embed_ok: true` only when a part is meant to pass into another (spar into slot, battery in bay).
5. Run `plane validate designs/<id>` (MCP: `validate_design`). Fix FAILs in tier order — a tier-1 failure invalidates everything above it.
6. When a sim or load check fails, fix the design (stronger joint, different geometry), not the threshold. Threshold changes go through `standards/` with a source.
6b. Moving parts (tilt wing, tilt rotor): set `schema_version: "0.2"` and add `articulation` (revolute, `pivot`, `axis`, `range_deg`, named `poses`) to the joint's attachment; rotation applies to the child side. Tier 1 re-runs its contact/clipping checks in every pose and at both range ends; name `flight.hover_pose` / `flight.cruise_pose` so tiers 2–3 use them.
7. Write `designs/<id>/README.md`: one paragraph, plus the question this concept answers.

## Pass check
`plane validate designs/<id>; echo $?` prints `0`, and the scorecard has no FAIL rows.

## Stop rules
- The schema can't express the concept → stop; propose a schema change to the conductor.
- A check fails and you believe the check is wrong → stop; report with numbers.
