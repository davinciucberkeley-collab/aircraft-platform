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

## Re-review (191d951)

Reviewer: same Opus instance (R1), continued. Inputs: commit 191d951, the 17 cases in `/tmp/ap-review/`, and new attack copies in `/tmp/ap-review2/` (made with `/tmp/ap-review2/mk.py`; each folder has `plane.yaml` and `out.md`). Nothing under `designs/` was touched.

### Automated

- `python3 -m pytest -q`: `29 passed, 22 warnings in 9.78s` (13 new tests in tests/test_review_regressions.py; warnings are still the trimesh divide warning).
- `plane validate designs/example-tailsitter-wing --tier all`: exit 0, **Accepted: yes**. Non-PASS rows: 2 WARN, `T4.fits_machine` for mount_l and mount_r ("jacobs-fdm has no build_volume_mm, fit not checked").
- `--tier all` works: same output as the default and runs tiers 0-5 (JSON `tiers: [0..5]`). On b13 it gives exit 1, Accepted: no.
- Criteria resolve: I ran `--tier all --format json` on the example, the 17 old cases and the 9 new ones (1445 rows, 21 distinct criteria). Every row has a criterion, and each one resolves to a leaf key of design-standards.yaml, a machine id in manufacturing.yaml, `manufacturing.yaml`, `schema/plane.schema.json`, or a `requirements.<field>` in the schema. None is unresolved.

### Original cases (all 17 now exit 1; the reason was checked for each)

| # | Exit | Reason now given | Right reason? |
|---|---|---|---|
| b1 | 1 | T1.attachment_contact "motor-l: parts are 5.0 mm apart" | yes |
| b2 | 1 | T1.connectivity "['camera']" + T1.attachment_overlap 100% (+ sim build crash) | yes |
| b3 | 1 | T1.connectivity "['cam_a', 'cam_b']" + overlap 25% | yes |
| b4 | 1 | T1.attachment_overlap "fin-l: embed_ok joint overlaps 46% of the child fin_l (limit 35%)" | yes |
| b5 | 1 | T1.attachment_overlap 46% (glued limit) | yes |
| b6 | 1 | T1.interference "prop strike: center_body and prop_l 102 mm^3" (+ wing 4390 mm^3, mount-l embed 87%) | yes |
| b8 | 1 | T0.schema "mass_g: 0 is less than or equal to the minimum of 0" | yes (was a sim crash before) |
| b9 | 1 | T1.attachment_overlap "prop-l: a propeller can never be an embed_ok joint" | yes |
| b10 | 1 | T1.attachment_overlap "fc-wing: embed_ok joint overlaps 100% of the child flight_controller" | yes |
| b11 | 1 | T2.sim_rest "tipped over ... 90 deg" (+ SM 17.4% now FAIL) | yes |
| b12 | 1 | T2.sim_rest tipped over (+ fins 47% embed) | yes |
| b13 | 1 | T3.static_margin FAIL "2.3% MAC ... target 5%-15%" | yes |
| b13b | 1 | T3.static_margin FAIL -2.9% | yes |
| b14 | 1 | T4.fits_machine "wing: [30, 332, 1000] mm does not fit jacobs-laser bed [457, 813]" | yes |
| b15 | 1 | T4.machine "machine 'no-such-printer' is not in standards/manufacturing.yaml" | yes |
| b16 | 1 | T2.hover_moment FAIL 193%, criterion `hover_moment_pass_ratio` | yes |
| b17 | 1 | T0.schema "'location' / 'rated_load_n' is a required property" for every joint | yes |

### Original blockers

| # | Blocker | Status | Evidence |
|---|---|---|---|
| 1 | embed_ok hides clipping and prop strikes | **FIXED as filed, but bypassed** | b4/b9/b10 fail for the right reason. Both new rules depend on the component `type` the author picks, so n1 and n1b below get around them. Fix (c) from the first review (embed_ok only for insertion methods) was not done: the example still has `glued` + embed_ok (mount-l, mount-r). |
| 2 | static margin outside 5-15% accepted | FIXED | checks.py: `PASS if lo <= sm <= hi else FAIL`; b13 and b11 (17.4%) now FAIL |
| 3 | joints without location/rating accepted | FIXED | schema `attachment.required` has both; checks.py also FAILs (T1.attachment_location, T2.joint_load, T2.sim_drop_loads) |
| 4 | tier 4 never checks fit or machine ids | **FIXED as filed, partly bypassed** | b14/b15 fail; a machine named for a method it doesn't do also fails (n3). Fit is still not checked when the part is rotated (n2), when `machine` is left out (n2c), or when the machine has no volume (n4). |
| 5 | drop test SKIPped without mujoco, and SKIP accepted | FIXED | pyproject: `mujoco>=3` is a core dependency; `Scorecard.accepted` rejects any FAIL or SKIP row; schema `mass_g` has `exclusiveMinimum: 0`; pages.yml `pip install -e .` now includes mujoco |
| 6 | `--tier all` fails | FIXED | cli.py accepts `all`; see Automated |
| 7 | criterion links don't resolve | FIXED | 1445/1445 rows resolve (see Automated); agents.md and review-scorecard.md use `design-standards.yaml#static_margin` |
| 8 | thresholds in code | FIXED | hover-moment lever and bands, `aft_surface_efficiency`, the 250 g literal and the sim.py fallbacks are now read from the yaml. The method allowlist moved to `manufacturing.yaml#machine_optional_methods`. New lists in code: `EMBED_PARENTS`/`EMBED_CHILDREN` (checks.py:31-32) and `SHEET_METHODS` (see suggestions) |

### New attacks (/tmp/ap-review2/)

| # | Attack | Result | Detail |
|---|---|---|---|
| n1 | Containment abuse: b10 (flight controller 36x400x10 mm running through the wing, `fc-wing` embed_ok), with the **wing relabelled `type: pod`** and FC joints rated 20 N | **MISSED**: exit 0, Accepted: yes | The overlap is 144000 mm^3, 100% of the FC. `ptype in EMBED_PARENTS and ctype in EMBED_CHILDREN` skips every overlap check, and `type` is free text that no other check reads (lifting surfaces are found by geometry). With the original 5 N ratings it failed only by accident (drop-load peaks 5.7/8.2 N). |
| n1b | b9 (prop disc moved into the wing, embed_ok to the wing), with the **prop relabelled `type: payload`** (wing also `pod`) | **MISSED**: exit 0, Accepted: yes | The disc overlaps 60553 mm^3 (12% of the disc) of the wing. The "propeller never embed_ok" rule and the "prop strike" label only look at `type == "propeller"`. The disc is under the 35% limit, so the wing relabel isn't even needed. The left motor no longer drives a prop, and nothing checks that. |
| n2 | Laser-cut strip 900x100x3 mm (it can't fit an 813x457 bed even on the diagonal), **tilted 60 deg about y**, glued under the fuselage | **MISSED**: exit 0, Accepted: yes, "skid: laser-cut on jacobs-laser, fits" | `_fits` uses the world-frame AABB after rotation (453 x 100 x 781). For a 2-value bed it never checks the smallest extent, so the tilt moves the length into the "thickness" axis. Control n2b (same strip, no tilt): T4.fits_machine FAIL "[3, 100, 900] mm does not fit". The same gap means any solid block passes as laser-cut sheet. |
| n2c | b14 (1000 mm wing, laser-cut) with the `machine` field **left out** | **MISSED**: exit 0, Accepted: yes | With no machine, checks.py only checks that some machine does the method. Fit is never computed. |
| n3 | `mount_l: {method: 3d-print-fdm, machine: jacobs-laser}` | CAUGHT | T4.method "jacobs-laser does not do 3d-print-fdm (it does ['laser-cut'])" |
| n4 | 1000 mm wing `3d-print-fdm` on `jacobs-fdm` | **MISSED** (WARN only): exit 0, Accepted: yes | "wing: jacobs-fdm has no build_volume_mm, fit not checked" is a WARN, and WARN is accepted. No FDM printer at Jacobs prints 1 m. All six FDM/SLA/mill machines lack a volume, so every printed or milled part passes unchecked. |
| n4b | `manufacturing` removed from the wing | **MISSED** (WARN only): exit 0, Accepted: yes | "wing: no manufacturing method" is a WARN. |
| n6 | b13 (SM 2.3%) run with `--tier 1` | **MISSED**: exit 0, "**Accepted:** yes" | A partial run prints Accepted: yes. An agent can run a low tier and report acceptance. |

The remaining WARN rows in any scorecard are the three T4 rows above and T2.hover_moment between 20% and 100% (b6: 68%, accepted). The last is a WARN by design per `design-standards.yaml#hover_moment_fail_ratio` (internal convention, no source), so I don't count it as blocking.

### Verdict

**NOT ACCEPTED.** 6 of 8 original blockers are fixed outright. 1 and 4 are fixed as filed but still bypassed. 6 of the 9 new attacks are accepted (n1, n1b, n2, n2c, n4, n4b), and so is a partial run (n6). Clipping and a prop disc inside the wing can still pass by relabelling `type`, and tier 4 still accepts parts that can't be made on the machine named.

### Remaining blockers

1. **Embed and prop rules trust the author's `type` label** (n1, n1b). checks.py:139-159, 196. Fix: (a) identify propellers by structure, not label: add `propulsion.prop: <component id>` (required) to each motor in the schema, treat that component as a prop disc everywhere (never embed_ok, may overlap only its own motor, interference always checked even when attached), and FAIL a motor with no prop; (b) a component with `lifting_surface` geometry may never be an `EMBED_PARENTS` parent, and `fuselage`/`pod` require box/cylinder/mesh geometry (schema `if/then` or tier 0); (c) for the containment exemption, require the child to really be inside the parent (overlap >= ~0.98 of the child) and add an exemption volume limit relative to the parent. Add n1 and n1b as tests.
2. **Fit uses the rotated world AABB and ignores sheet thickness** (n2). checks.py `_fits` / tier4. Fix: compute extents in the component's own frame (before `rotation_deg`), or use `trimesh.bounds.oriented_bounds`. For sheet methods, also FAIL if the smallest extent is above a `max_sheet_thickness_mm` per machine (add it as `pending` with a FAIL until sourced, or source it). Add n2 as a test.
3. **Fit is skipped and still accepted** (n2c, n4, n4b). Fix: require `machine` for every method not in `machine_optional_methods` (FAIL otherwise). Make "no build_volume_mm, fit not checked" and "no manufacturing method" FAIL, and add sourced build volumes for the Jacobs printers and mills (Prusa model, TAZ 6, Fortus 380mc, Form 3 from the manufacturers' spec pages). The example will fail on mount_l/mount_r until jacobs-fdm has a volume, which is the honest result.
4. **Partial runs print "Accepted: yes"** (n6). design.py `Scorecard.accepted` / cli.py. Fix: accepted only when tiers 0-5 all ran. Otherwise print "Not accepted: partial run (tiers 0-N)" with a non-zero exit, or a separate exit code.

### Non-blocking suggestions (new)

1. Some criteria resolve but cite the wrong rule: T1.watertight -> `interference_max_mm3`, T1.connectivity -> `attach_tolerance_mm`, T2.sim_stable/sim_rest SKIP -> `drop_height_m`. Add keys such as `geometry.watertight_required`, `geometry.connectivity_required` and `sim.stable_required`.
2. tests/test_review_regressions.py `test_every_criterion_resolves` checks only the all-PASS example. `_std_keys` collects every key at any depth, so a section anchor like `#geometry`, or even `#value`, would pass. Restrict it to leaf rule keys and run it over the failing fixtures too.
3. `EMBED_PARENTS`, `EMBED_CHILDREN` and `SHEET_METHODS` are written in checks.py, and the embed lists are repeated in the yaml rule text. Read them from design-standards.yaml/manufacturing.yaml (e.g. `sheet: true` per machine).
4. `embed_max_fraction_of_child: 0.35` (internal convention) still lets a fin sink 34% into a wing or a non-prop part clip 35% through another. Justify the number or tie it to joint method (slot-tab depth).
5. The MuJoCo error in T2.sim_stable (b2) contains a newline, which breaks the markdown table row. Collapse whitespace in messages.
