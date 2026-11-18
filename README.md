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

## Plane Studio: the point-and-click app

After the one-time setup below, run this (in Miniforge Prompt on Windows, with the environment active):

```bash
plane studio
```

Your browser opens on the app (it runs only on your computer, at http://127.0.0.1:8765). Keep the terminal window open while you use it.

| To... | Click |
|---|---|
| See every design in 3D with its scorecard | a design in the list; click a part to highlight it, or a failing check to show the parts involved |
| Compare two designs | **Compare** at the top |
| Try a change without touching the original | **Make a copy** (copies the file and its 3D parts) |
| Change masses, positions, materials, joint methods or strengths | **Edit design** › Parts / Joints (the Joints tab lists failing joints first) |
| Change anything else | **Edit design** › File (advanced) |
| Re-check a design | happens on every save; **Check again** or **Check all** to force it |
| Bring in Dillon's latest CAD | **Import** (paste the dbf-combined folder path) |
| Get files out | **Download** › 3D model, STL parts for printing, scorecard report, MuJoCo model |

Every button calls the same core library as the CLI and CI, so the app's verdict is the one a pull request gets.
Saves keep a backup in `.studio/backups/`; results are cached in `.studio/` so the app restarts quickly.

## Quick start

Needs Python 3.11 or newer (3.12 is what CI uses) and git. Use a fresh environment, for example
`conda create -n aircraft -c conda-forge python=3.12 -y` then `conda activate aircraft`.

```bash
git clone https://github.com/davinciucberkeley-collab/aircraft-platform
cd aircraft-platform
pip install -e ".[mcp,dev]"
plane --version                                     # plane, version 0.1.0
plane list
plane validate designs/example-tailsitter-wing     # scorecard; exit 0 = accepted
plane new my-concept --from example-tailsitter-wing
plane export designs/my-concept --format glb --out build/my-concept.glb   # also stl, json, mjcf
plane build-index --out viewer/data
python -m http.server -d viewer                    # open localhost:8000 (python3 on macOS/Linux)
pytest -q
```

On Windows, run these in Miniforge Prompt (or any terminal with the environment active) and write paths with `\`
if you like: `plane validate designs\concept-a` works the same.

### Re-import Dillon's concept A from DBF-Combined

```bash
git clone https://github.com/davinciucberkeley-collab/dbf-combined ../dbf-combined
plane import dbf --dbf-root ../dbf-combined      # rewrites designs/concept-a/ (add --id my-name to save a separate copy)
plane validate designs/concept-a --out concept-a-score.md
```

The importer runs DBF-Combined's own CAD script with this environment's Python, so nothing else needs installing.
A fresh import should differ from the committed `designs/concept-a/` only in the source commit id in its header.

Claude Code: `claude mcp add aircraft-platform -- plane-mcp` (see docs/mcp.md).

## The bar (validation tiers)

| Tier | Checks |
|---|---|
| 0 Schema | file matches `schema/plane.schema.json`; ids and references valid |
| 1 Geometry | every part connects to the root; attached parts touch; no clipping or prop strikes between unattached parts. Articulated joints (schema 0.2, e.g. a tilting wing): the contact, overlap and interference checks repeat in every named pose, at both range endpoints and in 15° sweep steps, results name the pose; `T1.articulation` checks poses lie in range and the pivot sits on both parts |
| 2 Physics | static joint loads (limit × ultimate factor); hover moment balance (at `flight.hover_pose` if the design names one); MuJoCo drop test (0° configuration): joint forces vs ratings, comes to rest upright, numerically stable; OpenCAE stress check of printed parts (`T2.fea_strength`, from stored `plane fea` results) |
| 3 Aero | mass vs MTOW, wing loading, stall speed, static margin (at `flight.cruise_pose`), lateral CG, hover thrust-to-weight (thrust axes turned to `flight.hover_pose`) |
| 4 Manufacturing | every part's method exists at Jacobs; parts fit the machine |
| 5 Standards | FAA Part 107 mass, registration threshold |

Thresholds live only in `standards/design-standards.yaml`, each with a source (or `pending`). Change a number there, never in code or skills.

## Stress check in OpenCAE (printed parts)

`plane fea`, the **Stress check** button in Plane Studio and the MCP tool `structural_check` mesh a printed part and
solve it in [OpenCAE Studio](https://github.com/davinciucberkeley-collab/OpenCAEModel) (CalculiX), with loads taken
from the design itself:

| | |
|---|---|
| Supports | joints whose other part is nearer the root through structure (clamped where the parts actually touch) |
| Landing case | joint forces and moments from the tier-2 drop test, each joint at its largest force (an envelope), × `ultimate_factor` |
| Thrust case | hover at full thrust held at the root (every motor at `max_thrust_n`, plus gravity): joint forces and moments from a static solve where every joint has the same stiffness, × `ultimate_factor` |
| Pass | peak von Mises away from the clamps ≤ `fea_allowable_printed_petg_mpa` (12.6 MPa: PETG interlayer strength, UltiMaker TDS) |

Results go to `designs/<id>/fea/<part>.json` (commit them: tier 2 reads them, and marks them out of date when the
design changes). OpenCAE's own route is used where it can mesh the part; parts with many curved facets go straight
to Gmsh, then fTetWild, and are solved with OpenCAE's material database, CalculiX deck and result reader. The
check was verified on a cantilever against beam theory (`tests/test_fea.py`: 1.003 mm vs 1.000 mm, 135 MPa).

One-time setup on Windows (Miniforge Prompt), with OpenCAE's GUI environment `qt_test` already working:

```bat
conda activate qt_test
pip install pytetwild
conda activate aircraft
plane fea --setup --opencae-python %USERPROFILE%\.conda\envs\qt_test\python.exe --opencae-root %USERPROFILE%\Documents\OpenCAE-Studio-0.1.0
plane fea designs\concept-a --all
```

Material: OpenCAE's own PETG record when it has one; otherwise the platform sends `structure.fea_material_printed_petg` from the standards, so any OpenCAE 0.2 works (tested against the GitHub version).

Limits: printed PETG only so far (CFRP and foam have no sourced material record yet); solid walls assumed; each
joint's drop-test peak is applied at once (conservative envelope); where joints form loops, the split between them
follows equal joint stiffness, not the real parts' stiffness; the motor's reaction torque and the part's own
inertia are left out; loads go in as statically equivalent force and moment on the touching faces, so stresses right
at a joint's faces are approximate (the report gives the location of the peak).

## CI and baselines

CI fails only on regressions. Each design's `designs/<id>/baseline.json` lists its known FAIL and SKIP results. A new failure, or a result that went from SKIP to FAIL, fails the build; fixing a known failure does not. To record a fix, run `plane baseline update designs/<id>` and commit the smaller file. Accepted designs need no baseline. Entries added to a baseline in a pull request are listed under "Known failures ADDED" and raised as a warning, so reviewers confirm each one. `plane baseline check --all` runs the same check locally.

## How we use agents

See `standards/agents.md`: conductor (Opus) plans, tactician (Sonnet) writes exact instructions, builders and scouts (Haiku) execute, one reviewer (Opus) scores against named criteria. The clearer the goal, the cheaper the model.

Claude Code hooks in `tools/agent_hooks.py` enforce the plan table, the edit limits and the agent log in Claude Code sessions opened in this repo. The "How this is enforced" section of `standards/agents.md` describes them, and `skills/agent-roles/SKILL.md` gives the steps.

## Known limits (v0.4)

The validator checks that a design is self-consistent and buildable. It can't tell real geometry or mass from plausible-looking fake entries, so a human reviewer still confirms the model matches the aircraft. Accepted residual holes (found in review rounds 5–7, `reviews/2026-11-11-bootstrap.md`):
- Distributed point masses (type `other`, with a reason) may sit anywhere inside the aircraft's envelope; the risk is bounded by the 3 % each / 5 % total mass caps.
- Mesh-wing chord: a thin rod across a strip centre bridges it; any part attached to a wing by a hinged (articulated) joint is counted as control surface, bridged across gaps up to 15 % of local chord, so a fake hinged piece can pad the chord; span is the geometry's extent; small leading-edge slivers are ignored as detached.

- Aero is first-order: neutral point ignores the fuselage; no VLM yet (AeroSandbox is the planned upgrade).
- Lifting surfaces are tapered slabs, not real airfoils, for collision purposes.
- Several thresholds are `source: pending` — see `knowledge/sources/std-SUMMARY.md`.
- Mesh wings: planform is measured from the modelled geometry in 41 equal spanwise midpoint strips (body-x chord, span from the geometry extent), bridging gaps up to 15% of local chord (control-surface hinges and balance pockets) and other gaps up to 3 mm, ignoring and reporting detached material; the declared planform is only cross-checked, so fake parts placed to fill a gap would still count and a reviewer must confirm control surfaces are real.
- Articulation is revolute only, and mass properties, the drop test and tiers 2–3 use the 0° configuration unless `flight.hover_pose` / `flight.cruise_pose` name a pose.
