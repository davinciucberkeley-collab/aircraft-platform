# Aircraft Design Platform

One shared place, format and toolset for our aircraft designs, so everything we make can plug into everything else and be checked against the same bar.

**One schema; every tool reads and writes it.**

```
schema/        plane.schema.json — the design language (v0.3: articulated joints, hollow-part cavities; v0.1–v0.2 files still validate)
core/          Python library: load, validate (tiers 0–5), mass properties, export, sim
               + the `plane` CLI and `plane-mcp` MCP server (thin wrappers over core)
designs/       one folder per design: designs/<id>/plane.yaml
standards/     agents.md, review-scorecard.md, design-standards.yaml, manufacturing.yaml
knowledge/     DIY projects, sources, concept evidence, morphological chart
skills/        Claude skills that drive the CLI/MCP
viewer/        static web viewer (GitHub Pages) — reads generated data, no per-design HTML
plans/ reviews/  agent plans and review scorecards
```

## Quick start

```bash
pip install -e ".[mcp,dev]"
plane list
plane validate designs/example-tailsitter-wing     # scorecard; exit 0 = accepted
plane new my-concept --from example-tailsitter-wing
plane export designs/my-concept --format glb --out build/my-concept.glb   # also stl, json, mjcf
plane build-index --out viewer/data && python3 -m http.server -d viewer   # open localhost:8000
pytest -q
```

Claude Code: `claude mcp add aircraft-platform -- plane-mcp` (see docs/mcp.md).

## The bar (validation tiers)

| Tier | Checks |
|---|---|
| 0 Schema | file matches `schema/plane.schema.json`; ids and references valid |
| 1 Geometry | every part connects to the root; attached parts touch; no clipping or prop strikes between unattached parts. Articulated joints (schema 0.2, e.g. a tilting wing): the contact, overlap and interference checks repeat in every named pose, at both range endpoints and in 15° sweep steps, results name the pose; `T1.articulation` checks poses lie in range and the pivot sits on both parts |
| 2 Physics | static joint loads (limit × ultimate factor); hover moment balance (at `flight.hover_pose` if the design names one); MuJoCo drop test (0° configuration): joint forces vs ratings, comes to rest upright, numerically stable |
| 3 Aero | mass vs MTOW, wing loading, stall speed, static margin (at `flight.cruise_pose`), lateral CG, hover thrust-to-weight (thrust axes turned to `flight.hover_pose`) |
| 4 Manufacturing | every part's method exists at Jacobs; parts fit the machine |
| 5 Standards | FAA Part 107 mass, registration threshold |

Thresholds live only in `standards/design-standards.yaml`, each with a source (or `pending`). Change a number there, never in code or skills.

## How we use agents

See `standards/agents.md`: conductor (Opus) plans, tactician (Sonnet) writes exact instructions, builders and scouts (Haiku) execute, one reviewer (Opus) scores against named criteria. The clearer the goal, the cheaper the model.

## Known limits (v0.3)

- Aero is first-order: neutral point ignores the fuselage; no VLM yet (AeroSandbox is the planned upgrade).
- Lifting surfaces are tapered slabs, not real airfoils, for collision purposes.
- Several thresholds are `source: pending` — see `knowledge/sources/std-SUMMARY.md`.
- Articulation is revolute only, and mass properties, the drop test and tiers 2–3 use the 0° configuration unless `flight.hover_pose` / `flight.cruise_pose` name a pose.
