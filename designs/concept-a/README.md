# concept-a: scaled quad tailsitter flying wing (D-182)

Imported from the DBF-Combined team's own CAD by `plane import dbf --dbf-root <path>` (importer: `core/aircraft_platform/importers/`).
**Generated: do not edit `plane.yaml` or `meshes/`; change the importer and re-run.** The import is deterministic (two runs, `diff -r` empty).
`import-report.json` holds per-part conversion statistics and every joint rating with its source text. This README and
`validator-comparison.md` are hand-written and are not touched by the importer.

## Provenance

| Item | Source (read only) |
|---|---|
| Repo, commit | `davinciucberkeley-collab/dbf-combined` @ `171ec426`, folder `redesign/` (its `git status` is clean after the import) |
| Geometry | `redesign/qp/A/cad/model/` stub-backend CAD (`a_model.py`, `amodel/`), built headless in a `python3 -I` subprocess (`_dbf_dump.py`) |
| Masses, CG, materials, make-or-buy | `PARTS` in the same model (sum 1261.24 g = `params-A.json` `mass.basic_cad_kg` 1.26124) |
| Joints, attachments | `EDGES` and joint records of the same model |
| Requirements, cl_max | `redesign/qp/A/params-A.json` (`req.mass_gate_kg`, `mission.cruise_ms`, `req.cruise_ratio`, `req.budget_usd`, `mission.clmax`, `env.rho_kgm3`); sources are in the YAML comments |
| Process text, BOM ids | `redesign/qp/A/cad/out/parts-a.csv` |
| Cross-check mesh | `redesign/site/assets/concept-a.glb` (used for bounds checks and as the fallback) |

Frame: the source's own (metres, x aft from the wing leading edge, y right, z up in cruise), scaled by 1000. The origin is the wing LE at
the centre, not a nose datum. A tailsitter hovers nose-up, so hover "up" is -x; no `hover_pose` is set.

## What was converted

- 104 solids, **all 104 rebuilt exactly** from the source's prism / revolve / loft bodies and cuts (`dbf_geometry.py`), written as one STL
  per part (`meshes/`, 4.5 MB). **0 GLB fallbacks.** Rebuilt volumes match the analytic body volumes within 0.987 to 1.011 (`import-report.json`),
  and the part bounds match the GLB to 0.003 mm. The fallback path exists (`_glb_fallback`) and was not exercised.
- 2 mass proxies (`hrd-001` 26.08 g hardware, `hrn-001` 18.4 g harness) as schema v0.4 `point_mass`, at the source's declared CG.
- 121 attachments from the source's 141 edges. Not emitted: 14 wire edges (centre lines, no solid; their mass sits in `hrn-001`) and 6 edges
  that bridge the elevon subtree (E-WNG-6R/6L, E-MEC-04, E-MEC-09, E-MEC-PIN-R3/L3: closing a loop around the hinge makes the articulated
  child side ambiguous). The downstream set of each elevon joint is asserted equal to the source's moving group (WNG-006, WNG-007, WNG-010,
  MEC-004, MEC-005 per side).
- Elevons: revolute, range +-21 deg (`ELEV_STOP`), pivot from the source joint origin, axis -Y because the source's positive angle is
  trailing edge DOWN and the platform's positive pose is up. Poses neutral 0, up +21, down -21.
- Motors: `propulsion` block with the real thrust direction (component matrix applied to the motor-local -x, 17 deg cant).
  `max_thrust_n` 8.81 is Dillon's 898 gf at duty 0.90 (see the YAML comment for the file).
- Component types, manufacturing methods (machine ids only from `standards/manufacturing.yaml`; the source's printer is a Prusa, the platform's
  `jacobs-fdm` is used) and connection methods are mapped by rules in `importers/dbf.py`; nearest-enum choices are noted in the YAML.

## Joint ratings (read this before trusting tier 2)

Convention: `rated_load_n` is an **ultimate** capacity (standards: joint ratings are ultimate), K factors 1.725 (CF/metal) and 2.15625
(printed/bonded) from `structures_a.py`. Counts: 33 from rows of the team's structures docs, 66 derived (allowable x measured contact patch
or fastener count x stress area; the source's own EST allowables, no tests exist), **22 placeholders** (foam tape, gel pad, velcro strap, tie,
tape hinge: the source publishes no capacity). A placeholder is set to the platform's own tier-2 demand rounded up, so its static check is
vacuous and the YAML says so. M2 and M5 stress areas are ISO values the importer did not open: marked placeholder in `dbf_ratings.py`.
The bonded area is measured on our meshes at the source's modelled glue-line clearance (0.02 to 0.5 mm), a conversion estimate.

## Known gaps

- Pushrods (MEC-003) and balance-horn linkage follow the elevon in reality (four-bar path); the source also holds them out of its pose sweep.
  Here they stay at the neutral pose, which clips at +21 deg (see the comparison).
- The wing core (`wng-001`) is a mesh, so it has no `lifting_surface`. It carries a schema 0.4 `planform` (rectangular 900 x 245 mm, from
  `amodel/common.py`) that tier 3 uses for stall, SM and NP. The planform is not geometry: collision, mass and export still use the mesh.
- Motor to propeller goes through an adapter (PRP-004); the platform wants a propeller attached directly to the motor.
- Nothing here is built, weighed or flown: every Dillon number is a CAD or EST value.
