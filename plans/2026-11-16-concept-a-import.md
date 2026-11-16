# Plan: import concept A (quad tailsitter) from DBF-Combined (2026-11-16)

Conductor: Opus. Follows `standards/agents.md`. User approved the conductor's recommendations on 2026-11-16.

## Decisions (conductor, user-approved)
- **Role:** the platform is an independent second check on concept A, alongside Dillon's pipeline (Blender interference check, claims graph, SITL). It does not replace it. Long term the team's CAD kit (fusionkit/k09kit) is the CAD standard and `plane.yaml` is a generated summary for comparing concepts.
- **Source of truth:** DBF-Combined. The importer only reads it, never writes to it.
- **Geometry:** exact solids rebuilt from the model's own shape data (prism / revolve / loft + cuts), built headless with `StubBackend`, following the conventions of `redesign/collision/collide_blender.py`. Fall back to the published GLB only for a part that can't be rebuilt, and say so.
- **Joint ratings:** from `redesign/qp/A/structures/` where a joint is covered; otherwise derived from the fastener/adhesive spec with the ultimate factor, each with a cited source.
- **Mass-only items** (HRD-001, HRN-001 are skipped as "mass proxy" by Dillon's checker): schema v0.4 adds geometry `point_mass: {}`. Counted in mass and CG, never in collision or contact checks.
- **Wires (14):** out of scope for v1; Dillon's checker covers wire terminations. Listed as a gap.

## Agent table

| Step | Role | Model | Input | Output | Pass criterion |
|---|---|---|---|---|---|
| T8 | Tactician | Sonnet | DBF-Combined `redesign/` @ 171ec426 | importer + `plane import dbf`, schema v0.4 `point_mass`, `designs/concept-a/` | tier 0 PASS; every FAIL classified in `validator-comparison.md`; `pytest -q` green |
| B6+ | Builder | Haiku | briefs written by T8 (briefing mode) or the conductor | fixes for classified validator limitations | named check behaves as specified |
| R1 | Reviewer | Opus (reused) | the import | review round 5 | scorecard; spot-check 10 numbers against source |
