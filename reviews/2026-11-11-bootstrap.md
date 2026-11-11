# Review: repo bootstrap (/home/claude/aircraft-platform) @ afc17c1

Reviewer: Opus (R1 in plans/2026-11-11-bootstrap.md). Format: standards/review-scorecard.md, adapted to a repo review.
**Verdict: NOT ACCEPTED.** 8 blocking issues. The validator can be fooled into accepting clipping, prop strikes and unenforced standards.

## A. Automated

`pytest -q`: `16 passed, 12 warnings in 5.41s` (warnings: trimesh `invalid value encountered in divide`, harmless).

`plane validate designs/example-tailsitter-wing`: exit 0, **Accepted: yes**. Summary of the pasted scorecard (61 rows, all PASS):

| Tier | Result | Details |
|---|---|---|
| 0 Schema | PASS | matches schema v0.1 |
| 1 Geometry | PASS | watertight; 12/12 connect to `center_body`; 11 joints OK; no interference |
| 2 Physics | PASS | static joint loads OK; hover moment 0.16 N*m (17%); drop-test peaks within ratings (mount-l 18.0 <= 20 N); rest tilt 0.3 deg; 2000 steps stable |
| 3 Aero | PASS | 759 g vs 900 g MTOW; stall 7.8 m/s; SM 14.0% MAC; lateral CG 0.0%; hover T/W 2.42 |
| 4 Manufacturing | PASS | 12/12 methods known (no machine-fit row was produced, see B) |
| 5 Standards | PASS | Part 107 mass; above the 250 g registration mass |

`plane validate ... --tier all` (the command in agents.md#reviews): **exit 2**, `Invalid value for '--tier': 'all' is not a valid integer.`

## B. Does the validator enforce "nothing falls apart, nothing clips, everything properly attached"?

The copies are in `/tmp/ap-review/<case>/plane.yaml`, made by mutating the example. Each was run with `plane validate`.

| # | Defect planted | Result | Check that caught it / why missed |
|---|---|---|---|
| b1 | motor_l floats 5 mm in front of its mount; joint `location` put on the mount face | CAUGHT | T1.attachment_contact "parts are 5.0 mm apart" |
| b2 | new part attached only to itself | CAUGHT | T1.connectivity (also T1.attachment_overlap; sim build crashes on self-weld) |
| b3 | two parts attached to each other in both directions, a cycle that bypasses the root | CAUGHT | T1.connectivity "not attached to 'center_body'" |
| b4 | fin_l `rotation_deg` [90,0,0] -> [0,0,0]: the fin lies flat inside the wing panel | **MISSED** | accepted. fin-l has `embed_ok: true`, so any overlap is allowed |
| b5 | same as b4 with embed_ok false | CAUGHT | T1.attachment_overlap 46% |
| b6 | motor pod moved inboard so the prop disc cuts 1 mm into the fuselage | CAUGHT | T1.interference "prop strike: center_body and prop_l 102 mm^3" |
| b8 | motor_l `mass_g: 0` (schema allows it) | CAUGHT (by accident) | T2.sim_stable is a MuJoCo build crash ("mass ... larger than mjMINVAL"), plus lateral CG. No mass check; it passes if mujoco is absent |
| b9 | prop_l disc moved into the wing (x=200) and re-attached to the wing with `embed_ok` | **MISSED** | accepted. A spinning prop disc passes through the wing |
| b10 | flight controller widened to 400 mm so it passes through the wing; extra `fc-wing` joint with embed_ok | **MISSED** | accepted. Interference is skipped for any attached pair |
| b11 | tailsitter with fins removed (can't stand) | CAUGHT | T2.sim_rest "tipped over ... 90 deg" |
| b12 | tailsitter fins shortened to 20 mm span | CAUGHT | T2.sim_rest "tipped over ... 90 deg" |
| b13 | battery moved aft: static margin 2.3% (limit 5-15%) | **MISSED** | WARN only, accepted. Also b11 had 17.4% as WARN. Only SM < 0 FAILs (b13b -2.9%: CAUGHT) |
| b14 | 1000 mm wing set to `laser-cut` on `jacobs-laser` (bed 813 x 457 mm) | **MISSED** | accepted. No machine has `build_volume_mm`, so T4.fits_machine never runs |
| b15 | `machine: no-such-printer` | **MISSED** | accepted. The machine id is never checked |
| b16 | one motor at 4 N, the other at 9 N | CAUGHT | T2.hover_moment FAIL (193%); its threshold is in code, see C |
| b17 | every joint lacks `location` and `rated_load_n` | **MISSED** | accepted with WARNs only. "Properly attached" is not shown |

Not a defect: swapping parent/child changes nothing, because connectivity is undirected (checks.py tier1). A 1 mm prop clearance case could not be isolated: moving the pod also put the disc into the wing (caught). No standard sets a prop clearance minimum, so 0 mm passes by design.

Tier score: tier 1 is sound for floating and detached parts. `embed_ok` is an unbounded escape hatch that hides clipping and prop strikes. Tiers 3 and 4 do not enforce limits they report.

## C. Standards compliance

| Criterion | Result | Reason |
|---|---|---|
| agents.md#reviews | FAIL | the prescribed `plane validate --tier all` exits 2; review-scorecard.md heading repeats it |
| review-scorecard.md#rules ("every row cites a criterion that exists in standards/") | FAIL | docs cite `design-standards.md#static-margin` and `manufacturing.md#...` (no such files); the validator emits `design-standards.yaml#static_margin`; T1.watertight, T1.attachment and T2.hover_moment have an empty criterion; `#geometry` and `#sim` are sections, not keys; `requirements.mtow_g` is not in standards/ |
| README.md#the-bar-validation-tiers + CLAUDE.md (thresholds only in design-standards.yaml) | FAIL | checks.py:226-229: hover-moment 0.05 m lever and 0.2/1.0 pass/warn/fail bands, with no criterion; checks.py:275 tail efficiency 0.9; checks.py:255 rho 1.225 default; checks.py:311 method allowlist `{"purchased","hand-cut","foamboard"}` (foamboard is not a Jacobs machine); checks.py:342 literal "250 g"; sim.py:61,155-157 fallbacks 0.3/2.0/0.05/30 duplicate the yaml |
| design-standards.yaml#static_margin | FAIL | the rule says 5-15%, but code (checks.py:280) gives WARN outside it, and WARN is accepted |
| make-skill/SKILL.md#required-sections, design-concept | PASS | all six sections in order |
| make-skill/SKILL.md#required-sections, research | FAIL | has no "Steps" section (Modes/Templates instead) |
| make-skill/SKILL.md#required-sections, review-design | FAIL | "Agents" is prose, not the required agent table |
| make-skill/SKILL.md#rules (no thresholds in skills) | PASS | skills hold only process numbers (120 lines, 20%, 3 attempts, ~20 searches); no design thresholds |
| make-skill/SKILL.md#pass-check-for-a-new-skill ("tried once end-to-end; result committed") | FAIL | no committed output: no reviews/ before this one, and no designs/example-tailsitter-wing/README.md that design-concept step 7 requires |
| agents.md#declaring-agents-up-front | PASS | the plan has the agent table with the roles and models of agents.md |
| agents.md#cost-check | N/A | the task has not ended; no role count has been reported yet |

## D. Knowledge base integrity (6 sampled, each URL fetched)

| File | Result | Facts confirmed at source |
|---|---|---|
| diy-projects/cygnet-petg-motor-only-tailsitter.md | PASS | 1249 mm span; no control surfaces; ~70% printed; ~1622 g airframe; "50% increase" PETG; landing legs + carbon rod |
| diy-projects/dollar-tree-foamboard-trainer.md | PASS | 36 in span; 1.5 lb Simple Scout; $3.75-$6.25 foam; 2205 motor; diagonal tape; iron tip |
| sources/std-mit-unified-desrules.md | PASS | S.M. = (xnp-xcg)/c = +0.05...+0.15 (p.3); trim drawback; NP is the aft CG limit. The page defines c as "average wing chord", which settles the yaml note |
| sources/std-guglielmo-selig-1997-s1223.md | PASS | S1223 Clmax ~2.2; 2.3 with Gurney flap/VGs; Table 1 values all match. Minor: the paper is Selig & Guglielmo, "High-Lift Low Reynolds Number Airfoil Design" (author order and title differ) |
| sources/morph-box-wing-barua-scholz-2013.md | PASS | 162 and 2,268 counts; 6 parameters; pruning 4/8/3/24/18; cross-consistency not performed |
| concepts/tailsitter-evidence.md (Ryan X-13 and PX4 rows) | PASS | X-13 full cycle 11 Apr 1957, retired 30 Sep 1957, no operational requirement; PX4 duo/quad, harder in wind, quad steadier, Caipiroshka linked. Minor: "source states no technical problems" overstates (the page is silent); the ax1800 link was not found |
| (extra) sources/std-ardupilot-forum-hybrid-vtol-twr.md | PASS | Feibernaut 1.05 floor / 1.2-1.5; 0x48 2-2.2; Ben_Stanton tailsitter question. Minor: Ben_Stanton, not Feibernaut, wrote the first post |

No invented URLs or unsupported numbers were found. No item here is blocking.

## E. Fit to the team's goals

| Goal | Result | Reason |
|---|---|---|
| CLI | ✓ | `plane` has list/validate/new/export (glb/stl/json/mjcf)/build-index/schema; all thin over core |
| MCP | ✓ | `plane-mcp` imports and lists 8 tools (validate, save with schema check, etc.) |
| Skills | ✓ | 4 skills that drive the CLI/MCP; 2 break the make-skill shape (see C) |
| Consistent file format | ✓ | one schema v0.1; all tools read `designs/<id>/plane.yaml` |
| Viewer needs no per-design HTML | ✓ | viewer/app.js reads only `data/index.json` + generated files |
| Review against specific criteria | ✗ | the criterion links don't resolve and several rows have none (C rows 1-2) |
| DIY knowledge base | ✓ | 16 projects + 22 sources; 6/6 sampled verified |
| Unexplored concepts | ✗ | the morphological chart exists, but `knowledge/concepts/unexplored.md` (named in research skill) does not; no recon output |
| Agent model standard | ✓ | agents.md roles/models/builder-ready bar; the plan declares its table |

## Blocking issues

1. **`embed_ok` hides clipping and prop strikes** (b4, b9, b10). core/aircraft_platform/checks.py `tier1_geometry`. Fix: (a) a propeller may overlap only its own motor and never be an embed_ok child; (b) add `geometry.embed_overlap_max_fraction` (with a source) to design-standards.yaml and FAIL above it; (c) allow embed_ok only for methods that imply insertion (slot-tab, clamp/bay, press-fit). Add b4/b9/b10 as tests.
2. **Static margin outside 5-15% is accepted** (b13). checks.py:280. Fix: FAIL outside [min, max], or add an explicit `severity` field in design-standards.yaml and honour it.
3. **Joints with no `location` or `rated_load_n` are accepted** (b17). schema/plane.schema.json `attachment` + checks.py. Fix: make both required in the schema (or FAIL), so "properly attached" is shown for every joint.
4. **Tier 4 never checks machine fit or machine ids** (b14, b15). standards/manufacturing.yaml + checks.py `tier4_manufacturing`. Fix: add `bed_mm`/`build_volume_mm` from the verified notes (e.g. jacobs-laser 813x457); FAIL on an unknown `machine`; move the hard-coded method allowlist (`purchased`, `hand-cut`, `foamboard`) into manufacturing.yaml.
5. **Drop test (stands upright, joint peaks, mass > 0) is silently SKIPped without mujoco, and SKIP is accepted.** pyproject.toml (`sim` optional), docs/mcp.md installs only `.[mcp]`, and .github/workflows/pages.yml installs without sim, so the viewer's scorecards lack tier 2 sim. Fix: make mujoco a core dependency or treat a SKIP in a claimed tier as not accepted; set `mass_g` to `exclusiveMinimum: 0` in the schema.
6. **The reviewer command in the standards fails.** standards/agents.md#reviews and standards/review-scorecard.md use `--tier all`. Fix: accept `all` in core/aircraft_platform/cli.py `--tier`, or change the docs to `plane validate <path>`.
7. **Criterion links don't resolve.** standards/agents.md, standards/review-scorecard.md (`design-standards.md#static-margin`, `manufacturing.md#...`) and checks.py rows with an empty criterion, a section-level anchor or `requirements.mtow_g`. Fix: one link form, `design-standards.yaml#<key>`. Every CheckResult gets an existing key; add a test that resolves every emitted criterion against the yaml.
8. **A pass/fail threshold lives in code.** checks.py:226-229 hover-moment lever 0.05 m and bands 0.2/1.0, with no criterion. Fix: add `aero.hover_moment_*` keys (with source or `pending`) to design-standards.yaml and read them. Also move the 0.9 tail efficiency and the "250 g" literal, and remove the duplicated sim fallbacks in sim.py.

## Non-blocking suggestions

1. skills/research/SKILL.md: add a numbered "Steps" section; skills/review-design/SKILL.md: make "Agents" a table (make-skill#required-sections).
2. Write `knowledge/concepts/unexplored.md` with a first recon pass, as the research skill describes.
3. Add `designs/example-tailsitter-wing/README.md` (design-concept step 7) so the example models the full workflow.
4. Propose a criterion `geometry.prop_clearance_min_mm` (prop flex and tip clearance); today 0 mm clearance passes.
5. design-standards.yaml#static_margin note: the MIT source defines c as average wing chord. Update the note and close it.
6. plans/2026-11-11-bootstrap.md: B1/B2 output paths (`cli/plane_cli.py`, `mcp/server.py`) and "6 tools" don't match what was built (core/…, 8 tools); the cost check (agents.md#cost-check) is still due.
7. viewer/README.md says `viewer/data/` is gitignored; .gitignore doesn't list it.
8. knowledge/morphological-chart.yaml `vtol_method` lacks the `none` option the schema has.
9. KB minor fixes: Selig & Guglielmo author order/title; X-13 "states no technical problems"; Ben_Stanton opened the T/W thread; confirm the PX4 ax1800 link.
10. T2.sim_stable reports self-attachment and zero-mass errors as "could not build simulation model". Catch both explicitly in tier 0/1 with clear messages.
11. Suppress or fix the trimesh divide-by-zero warnings seen in pytest.
