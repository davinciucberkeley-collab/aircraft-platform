# Plan: platform bootstrap (2026-11-11)

Conductor: Opus (main session). Follows `standards/agents.md`.

## Done by conductor (design decisions, not delegable)
- `standards/agents.md`, `standards/review-scorecard.md`
- `schema/plane.schema.json` v0.1
- `core/aircraft_platform/` design model, geometry, mass, checks tiers 0–5, GLB/STL export
- `designs/example-tailsitter-wing/plane.yaml` (passes tiers 0–3, 5)

## Agent table

| Step | Role | Model | Input | Output | Pass criterion |
|---|---|---|---|---|---|
| S1 | Scout | Haiku | web | `knowledge/diy-projects/*.md` (VTOL/tailsitter builds, 8 entries) | every template field filled, `verified` honest |
| S2 | Scout | Haiku | web | `knowledge/diy-projects/*.md` (cheap construction methods, 8 entries) | same |
| S3 | Scout | Haiku | web | `standards/manufacturing.yaml` (Jacobs Hall equipment) | parses as YAML in given format; each machine has source URL |
| S4 | Scout | Haiku | web | `knowledge/concepts/tailsitter-evidence.md` | template filled, ≥6 real examples with outcomes |
| S5 | Scout | Haiku | web | `knowledge/sources/morph-*.md` + `knowledge/morphological-chart.yaml` | ≥3 sources; chart parses |
| S6 | Scout | Haiku | web | `knowledge/sources/std-*.md` | each `pending` rule in design-standards.yaml has ≥1 source |
| B1 | Builder | Haiku | spec below | `cli/plane_cli.py` | `plane validate designs/example-tailsitter-wing` exits 0 |
| B2 | Builder | Haiku | spec below | `mcp/server.py` | server imports, lists 6 tools |
| B3 | Builder | Haiku | spec below | `tests/test_*.py` | `pytest -q` green |
| T1 | Tactician | Sonnet | core lib | `core/aircraft_platform/sim.py` (MuJoCo drop test + MJCF export) | tier 2 runs on example; deliberately broken design fails |
| T2 | Tactician | Sonnet | core lib, export | `viewer/` v0 | opens designs + scorecards with no hand-edited HTML |
| R1 | Reviewer | Opus (one) | whole repo | `reviews/2026-11-11-bootstrap.md` | scorecard per review-scorecard.md |
