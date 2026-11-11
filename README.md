# Aircraft Design Platform

One shared place, format and toolset for our aircraft designs, so everything we make can plug into everything else and be checked against the same bar.

**One schema; every tool reads and writes it.**

```
schema/        plane.schema.json — the design language (v0.1)
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
| 1 Geometry | every part connects to the root; attached parts touch; no clipping or prop strikes between unattached parts |
| 2 Physics | static joint loads (limit × ultimate factor); MuJoCo drop test: joint forces vs ratings, comes to rest upright, numerically stable |
| 3 Aero | mass vs MTOW, wing loading, stall speed, static margin, lateral CG, hover thrust-to-weight |
| 4 Manufacturing | every part's method exists at Jacobs; parts fit the machine |
| 5 Standards | FAA Part 107 mass, registration threshold |

Thresholds live only in `standards/design-standards.yaml`, each with a source (or `pending`). Change a number there, never in code or skills.

## How we use agents

See `standards/agents.md`: conductor (Opus) plans, tactician (Sonnet) writes exact instructions, builders and scouts (Haiku) execute, one reviewer (Opus) scores against named criteria. The clearer the goal, the cheaper the model.

## Known limits (v0.1)

- Aero is first-order: neutral point ignores the fuselage; no VLM yet (AeroSandbox is the planned upgrade).
- Lifting surfaces are tapered slabs, not real airfoils, for collision purposes.
- Several thresholds are `source: pending` — see `knowledge/sources/std-SUMMARY.md`.
