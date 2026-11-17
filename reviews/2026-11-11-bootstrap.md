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

## Round 3 (5a86f3e)

Reviewer: same Opus instance (R1). Commits reviewed: 72fda53 (loophole fixes), b8c0e9a (schema v0.2 articulation), f7e3456, 645ef30, 9265042 (converted designs), 5a86f3e (agents.md). Attack copies are in `/tmp/ap-review2/` (re-generated from the current example with `mk.py`) and `/tmp/ap-review3/` (`mk3.py`; each folder has `plane.yaml` and `out.md`). Nothing under `designs/` was edited.

### Automated

- `python3 -m pytest -q`: `48 passed, 34 warnings in 15.06s`.
- `plane validate <d> --tier all`: example-tailsitter-wing exit 0, **Accepted: yes**, no non-PASS rows. c0-lift-cruise, c0-a1, c0-a2, c0-a3 and tiltwing-cakir exit 1. Their non-PASS rows match the lists in each `validator-comparison.md` (tiltwing has 29, matching its tier counts).

### 1. Re-review blockers

| # | Re-review blocker | Status | Evidence (current example, `/tmp/ap-review2`) |
|---|---|---|---|
| 1 | embed/prop rules trust `type` | CLOSED | Embed now uses geometric containment (`containment_min_fraction` 0.99, `type` not read) plus `T1.motor_has_prop`. n1b (prop relabelled `payload`): exit 1, "motor_l: has a propulsion block but no attached component of type propeller". n1 (FC 36x400x10 inside the wing, wing labelled `pod`): exit 0. The FC is now 100% inside the wing (144000/144000 mm^3), so it is a bay, not a clip. I accept that. |
| 2 | fit uses the rotated AABB | CLOSED | n2 (900x100x3 strip tilted 60 deg): "oriented extents [3.0, 100.0, 900.0] mm do not fit jacobs-laser bed [457, 813]". Sheet thickness is still not limited, but the PASS message now says so ("lists no thickness limit"). |
| 3 | unchecked fit still accepted | CLOSED | n2c (no `machine`): T4.machine FAIL "in-house method laser-cut needs a `machine`". n4 (1 m wing on jacobs-fdm): T4.fits_machine **SKIP**, not accepted. n4b: T4.method FAIL "no manufacturing method". The example's mounts moved to laser-cut ply to stay accepted, which is documented in the commit. |
| 4 | partial run says "Accepted: yes" | CLOSED | `--tier 1` prints "**Partial run (tiers 0-1):** ..." and JSON has `accepted: false, partial: true`. A clean partial run exits 0, which is fine because it never claims acceptance. |

n3 (machine without the method) is still CAUGHT.

### 2. Articulation attacks (/tmp/ap-review3/)

Base: the current example plus a hinged 80x20x4 ply hatch on the fuselage top (pivot (200,0,40), axis [0,-1,0], range [0,90]). Where needed, a post and arm sit behind it.

| # | Attack | Result | Detail |
|---|---|---|---|
| r1 | Hatch clips the arm **only mid-swing**. Poses closed 0 / open 90; 0, 90 and both range ends are clear | **MISSED (design gap)**: exit 0, Accepted: yes | `_configurations` checks only 0 deg, named poses and range endpoints. Control r1b adds a pose at 45: "pose half (45°): clipping: hatch and arm overlap 1129 mm^3". So the per-pose check works, but nothing in between is ever looked at. |
| r2 | Pivot 100 mm above the fuselage, off both parts | CAUGHT | T1.articulation "pivot is 100.0 mm from center_body and 96.0 mm from hatch at 0°", plus contact FAIL at 90 deg |
| r2b | Pivot on the parent only (60 mm from the hatch) | CAUGHT | T1.articulation "0.0 mm from center_body and 60.0 mm from hatch" |
| r3 | Tilting motor mounts (poses cruise 0 / hover 90), `flight.hover_pose: vertical`, which doesn't exist | CAUGHT | T1.articulation "flight.hover_pose 'vertical' is not a pose of any articulated joint"; T3.hover_tw 0.00. Cosmetic: T2.hover_moment still PASSes "at pose vertical", computed at 0 deg. |
| r3b | Hover pose 90 deg outside range [0, 60] | CAUGHT | T1.articulation "pose hover (90°) is outside range [0°, 60°]". T3.hover_tw alone would PASS (2.42 at 90 deg), so only the range rule stops it. |
| r3c | `hover` pose exists only on the unrelated hatch hinge; motors never tilt | CAUGHT | T3.hover_tw "0.00 at pose hover" (only the +z component of thrust counts) |
| r3d | `vtol_method: tiltrotor` with no articulation and no `hover_pose`: thrust points forward (-x) forever | **MISSED**: exit 0, Accepted: yes | Without `hover_pose`, T3.hover_tw adds up `max_thrust_n` whatever the axis points to (2.42). That is right only for a tailsitter. |
| r3e | `lift-plus-cruise`, both lift motors with axis [0,0,-1] (thrust pushes the aircraft down), no pose | **T3 MISSED**, caught by accident | T3.hover_tw PASS 2.42 on downward thrust. Exit 1 only because T2.hover_moment happens to see a 132% moment from the x offset of the motors. With motors over the CG it would pass. |

### 3. Provenance spot-check (12 numbers; every source file opened, TiltWing model.js run with node)

| Design: value in plane.yaml / comparison | Cited source | Source value | Result |
|---|---|---|---|
| c0: lift motor `max_thrust_n` 30.695 | dbf-combined `analysis/results.json` C0.struct.Tmax | 30.694814 (params.Tmax_g 3130) | match |
| c0: Lift_Motor 660/4 = 165 g | `analysis/mass/mass_budget.json` | Lift_Motor qty 4, 660.0 g | match |
| c0: spar 478.3 + joiner 197.1 = 675.4 g | mass_budget.json; results.json base.m_spar | 478.3, 197.1; 0.67524 kg | match |
| c0: pusher disc lump 37.0+11.1+4.3+8.1 g | mass_budget.json | 37.0, 11.1, 4.3, 8.1 | match |
| c0: pusher `max_thrust_n` 8.376 (stated as cruise drag, not a max) | results.json C0.sized.D_cruise | 8.3761566 | match (honestly labelled) |
| c0 comparison: total 7415.9 / sized 7438.0 g; CG xLEtoCG -0.0903 m; SM with pod 10.4% | mass_budget total_kg; results.json; aero_results.json | 7.4159; 7.4379985; -0.090253; static_margin_pct CG_28pct 10.404 | match |
| c0: servo protrusion uses lower surface yL55 -13.9 mm | `cad/params.txt` | yL55=-0.013910 | match |
| tiltwing: `cl_max` 2.0142386 | TiltWing `model.js` size() CLmax | 2.014238599 | match |
| tiltwing: TfMax 32.407694 / TrMax 6.156 / tMax 141.94 N | model.js l.174, 327 | 32.40769, 6.15619, 141.94317 | match |
| tiltwing: S 0.57554 m^2, MAC 290.757 mm, m 9152.686 g, SM 0.11514, spar root moment 32.0 N*m | `data/verify.json` G1, G3, M1, A7 row, F1 | 0.5755396, 0.2907570, 9.152686, 0.1151391, 32.00176 | match |
| tiltwing: pivots x 756 / 1656, z 84 / 24 | `cad/params.json` xw, xt; `tools/cad_export.py` zw = 0.42 df, zt = 0.12 df | 0.756, 1.656; 0.084, 0.024 | match |
| tiltwing: nacelle 1 bounds x 565.608-913.412, wing z 78.8-128.3, tail z 15.8-32.2, tail-cylinder "real radius 45 mm" | `cad/cruise_tilt0/*.stl`, Fuselage.stl | 565.608-913.412; 78.818-128.285; 15.844-32.156; section radius 45.3 at x 1656 | match |

**No mismatches.** Minor: tiltwing comparison row "Power" gives "hover 1501.6 W electrical (`M` S2)". In verify.json S2, 1501.58 is the *independent* (90 deg momentum-theory) column, and the model column is 1531.4 W (sim at 79 deg). The value exists, but the column should be named.

### 4. Are the FAILs in the converted designs' validator-comparison.md honestly classified?

Mostly yes. The tables list every FAIL/SKIP/WARN the validator emits today (checked against my runs). Placeholder ratings are labelled (c), not blamed on the design. Real findings are kept as (a): the c0 aileron-servo protrusion, the A1 stall at 12.3 m/s, the A3 front gear clamp. The tiltwing (b) clipping claim is backed by a scratch variant, and the 45 mm radius checks out. Corrections needed:

1. **`T1.attachment_contact pusher-prop` 5 mm gap (c0, a2, a3) is labelled (b) "no hub in the schema". It should be (c).** The schema can model the M6 adapter as its own cylinder component between motor and disc (a3 models caps and c0 models `pusher_cup` the same way). The conversion folded the adapter mass into the disc instead (plane.yaml comment "M6 adapter, washer and bullet nut lumped in").
2. **a3 `T1.interference lift_motor_* vs nacelle_*` labelled (b) "the schema has only solid boxes".** That isn't accurate: `mesh` geometry exists, and a closed two-skin shell mesh is watertight and would not overlap the motor. Call it (b)/(c): primitive-only modelling was a conversion choice. A schema `shell_thickness_mm` would still be a good addition.
3. c0-a1 section 3 "Thrust axis sign ... A1 copies C0's value [1,0,0]" is stale. 645ef30 set C0 and all three variants to [-1,0,0]. Update or delete the paragraph.
4. tiltwing S2 power column (above).

None of these change a verdict on a design. Items 1-2 matter because "(b)" tells the conductor the platform is at fault when the fix is in the conversion.

### Verdict

**NOT ACCEPTED.** All 4 re-review blockers are closed and provenance is clean (12/12). Two articulation and thrust gaps remain, and each lets a broken design get Accepted: yes.

### Remaining blockers

1. **Clipping between poses is never checked** (r1). checks.py `_configurations`. Fix: sweep each articulated joint across `range_deg` in steps of a new `geometry.articulation_sweep_step_deg` key (e.g. 5 deg, `source: internal convention`), or check interference against the union of the child subtree's swept meshes. Add r1 as a test. A coupled joint group (tiltwing gap 4, `articulation.group`) would make the sweep cheaper and stop unflown wing-only configurations from being checked.
2. **Hover thrust direction is ignored when no `hover_pose` is given** (r3d accepted, r3e T3 PASS on downward thrust). checks.py tier3 hover_tw and tier2 hover_moment. Fix: always count only the component of each lift thrust that points up in the hover attitude. For `vtol_method: tailsitter`, that is the nose-up attitude (reuse sim.py `_landing_rotation`); for everything else, the body frame at `hover_pose` (0 deg if none). Require `flight.hover_pose` when `vtol_method` is tiltrotor or tiltwing. Add r3d and r3e as tests.

### Non-blocking (new)

1. T2.hover_moment runs and PASSes "at pose <name>" even when the pose doesn't exist (r3). Skip it, or mark it blocked when T1 reports an unknown pose.
2. The T3.hover_tw result at a pose outside `range_deg` is still computed and PASSes (r3b). Only T1 stops the design. Clamp it, or report "blocked".
3. Make the classification corrections in section 4.

## Round 5 — concept A import (9c31992)

Reviewer: same Opus instance (R1). Scope: branch `concept-a-import`, commits 57eb666..9c31992; plan `plans/2026-11-16-concept-a-import.md`. Source: `dbf-combined` @ 171ec426, read only. `git status --short` there is empty before and after everything below, including a full re-import. Throwaway designs and outputs are in `/tmp/ap-review5/` (`mk5.py`, one folder per case with `plane.yaml` and `out.md`). Nothing under `designs/` was edited.

### 6. Automated and determinism

- `python3 -m pytest -q`: `77 passed, 39 warnings in 22.46s`.
- `plane validate designs/example-tailsitter-wing`: exit 0, Accepted: yes.
- `plane validate designs/concept-a --tier all`: exit 1, 24.6 s. T1 has 10 WARN (kinematic_link), T2 has 23 FAIL (22 sim_drop_loads, 1 sim_rest), T3 has 1 FAIL (static_margin). This matches the counts in `validator-comparison.md`.
- Determinism: `plane import dbf --dbf-root … --out /tmp/ap-review5/reimport` ran in 5 min 4 s with rc 0. `diff -r` against `designs/concept-a` shows only the two hand-written files (README.md, validator-comparison.md). plane.yaml, all 104 meshes and import-report.json are byte-identical. **Deterministic.**

### 1. Provenance (14 items; each source file opened, `prop_a.py` run from a scratch copy)

| plane.yaml value | Cited source | Source | Result |
|---|---|---|---|
| `mtow_g` 1470 | params-A.json `req.mass_gate_kg` | 1.47 kg | match |
| `cl_max` 0.75, rho 1.2 | params-A.json `mission.clmax`, `env.rho_kgm3` | 0.75 (EST, UNVERIFIED), 1.2 | match |
| planform 900 x 245, rectangular | amodel/common.py "line 32 `C, B = 0.245, 0.90`" | L32 `C, B = 0.245, 0.90` | match |
| `max_thrust_n` 8.81 | prop_a.py output "898 gf x0.93" | "fresh 16.8 V duty 0.90 … thrust 966 gf table / 898 gf x0.93"; 0.898 x 9.807 = 8.807 | match |
| thrust cant 17 deg | common.py CANT | L45 `CANT = 17.0` | match |
| avn-001 8 g, avn-002 17 g | PARTS | amodel/electrical.py L478-479 | match |
| point masses hrd-001 26.08 g @ (100,0,0), hrn-001 18.4 g @ (30,0,20) | PARTS, `cg_declared` | electrical.py L507-512 cg [0.100,0,0], [0.030,0,0.020]; masses set at runtime; total 1261.24 g = sitl/cad_mass.json 1.26124 | match |
| E-FIN-01 2009.8 N | iter2_margins.md 'Fin root block on fin tube' 130 N, MS +6.17; K 2.1562 | L25 130 N, +6.17; structures_a.py L11-12 1.5 x 1.15 x 1.25 = 2.15625; 130 x 2.15625 x 7.17 = 2009.8 | match |
| E-CGE-01 944.6 N | iter2_margins.md 'Arm 12x10 in socket' 296 N, +0.48 | L17 296 N, +0.48; 944.6 | match |
| E-WNG-01 1296.8 N | foam_103.md, 86 kPa x pi x 12 mm x 0.40 m | L4 "0.40 m of bond", L12 "shear 86 (EST)"; 1296.8 | match |
| E-PRP-10 4527 N, E-PRP-03 744 N | M3 5.03 mm2 structures_a.py L228; 450 MPa and PETG bearing 20 MPa x 9.3 mm2 arm_cup_checks.md | L228 `A_s = 5.03e-6`; arm_cup_checks.md L15/L17; M2.5 3.39 at arm_cup_checks.py L82 | match |
| strap note | structures_run.md L225 | L225 "strap: 2 x 20 mm Velcro, 32 N each side, `-` not tested" | match |
| **E-WNG-30R/31R/30L/31L 88.6 N, `[doc]`** | foam_103.md 'Stop reaction at stall (30 N) peeling the lens cap off the skin', MS +0.37 | L10: the numbers are right (30 x 2.15625 x 1.37 = 88.6), but the same row ends "**peel of the tape skin is not covered by a foam value: pull coupon required**" | **MISMATCH**: the source says this is not a valid capacity, yet it is labelled `[doc]`. It should be `[placeholder]`, or `[derived, source disclaims]`. |
| **23 ratings "x structures_a.py L19 BOND_TAU 2.0 MPa"** | structures_a.py L19 | `BOND_TAU = 2.0e6` is on **L17**; L19 is `def rating(m)` | **MISMATCH** (citation; value right). The line is hard-coded in importers/dbf_ratings.py L25 and L120. |

Other notes, not blocking: E-FIN-03 borrows the 'Rib saddle on 12 mm spar' row for a different joint (rib-in-saddle socket) and says so. The 17 ratings tagged `[derived] … (placeholder stress area)` (M2, M5 ISO values never opened) are counted under "66 derived" in the README; that count would be clearer as 49 + 17.

### 2. Geometry fidelity (8 parts, every body kind; our STL vs the team's `redesign/site/assets/concept-a.glb`)

The GLB is Y-up. The axis map ours = (x, -z_glb, y_glb) x 1000 makes the bounds of every tested part identical (max difference 0.000 mm).

| Part | Body kinds (bodies / cuts) | Our volume mm3 | / GLB | Bounds diff |
|---|---|---|---|---|
| avn-001 plate | prism (1 / 12) | 18978.5 | 1.0000 | 0.000 |
| cge-002-ur arm | revolve (1 / 0) | 8442.4 | 1.0000 | 0.000 |
| wng-001 core | loft (1 / 83) | 2600446.9 | 1.0001 | 0.000 |
| prp-002-ur prop | loft + revolve (4 / 0) | 6543.6 | 0.9980 | 0.000 |
| fin-003-r root block | prism + revolve (2 / 2) | 18508.1 | 1.0007 | 0.000 |
| cge-001 hub | loft + prism + revolve (18 / 20) | 13225.4 | 0.9963 | 0.000 |
| wng-009-r horn | revolve (3 / 0) | 1117.2 | 1.0000 | 0.000 |
| cge-003-ur cup | prism + revolve (4 / 18) | 9436.1 | 1.0000 | 0.000 |

Over all 104 parts the largest volume deviation from the GLB is 0.37% (cge-001). **No part deviates more than 1% from the GLB.** Against the source's *analytic* body volumes (before cuts, from `volume_centroid()`), every revolved body is 1.14% low (0.9886 = 24-segment faceting, which the GLB shares) and the prop lofts are -1.3%/+1.06%. That is about 0.9% of radius (0.05 mm on a 12 mm tube): not a conversion error, but worth knowing for 1 mm3 interference calls. Not blocking.

### 3. Independence

| Quantity | Computed or echoed? |
|---|---|
| Mass 1261.24 g | Echo by design: sum of his part masses. |
| CG (20.46, 2.38, 6.68) mm | **Computed** from our mesh centroids. No `cg_offset` anywhere in plane.yaml. It matches his cad_mass.json to 0.05 mm, a real cross-check. |
| NP / static margin | **Computed** (MAC quarter chord of the `planform`); disagrees with his 40.7 mm. |
| Interference | **Computed** (our own booleans, broad phase plus exact); agrees with his REPORT.md. |
| Hover T/W | Our sum and directions; thrust per motor is his input (898 gf). |
| **kinematic_link list** | **Echo**: `KINEMATIC_LINK_CHILDS` in importers/dbf.py L34 is hard-coded from REPORT.md. The dump already carries the source's own `poses[].linked` (same 4 parts), so read it from there and the import can't go stale. Copying his *blind spot* is acceptable as a declared modelling limit, because the four-bar is not in the schema. It is not acceptable that the result is a WARN, which still allows Accepted: yes (attack k1). |
| **22 placeholder ratings** | **Self-echo**: each is set to *our own* tier-2 demand rounded up, so T2.joint_load shows **PASS by construction** on 22 rows. The README and YAML comments say so, but the scorecard doesn't. A check that cannot fail must not print PASS. |

### 4. Attacks on the new rules (/tmp/ap-review5/)

| # | Attack | Result | Detail |
|---|---|---|---|
| p3 | Example + two 15 g "camera" **point masses floating 60 mm above the wing** at x = CG, plus two 2 g point masses **inside the prop discs** | **MISSED**: exit 0, Accepted: yes | Rows say "glued joint to a point mass: no contact or location check". As boxes (control p2b) the same parts FAIL "parts are 49.5 mm apart" and "prop strike … 16000 mm^3". |
| p1 | 250 g battery as a point mass 170 mm below the fuselage | Caught by accident | Geometry is silent; only the CG shift trips T2.hover_moment and sim_rest. |
| k1 | Round-3 hatch that clips an arm at the 45 deg sweep step; the ordinary glued `arm-post` joint marked `kinematic_link: true` | **MISSED**: exit 0, Accepted: yes | One WARN "sweep hatch-hinge 45°: 1 pair(s) not checked — linkage path not modelled: arm, hatch". Control k0 (no flag): T1.interference FAIL 1129 mm^3. The flag is visible but doesn't block, and any joint may carry it. |
| ca-f3 | concept-a copy, `planform.origin` moved 5 mm forward of the mesh LE | **MISSED**: T3.static_margin FAIL 16.6% becomes **PASS 14.6%** | Nothing ties the planform to the mesh. |
| f2 | Example + a 300 x 100 planform on the *battery* at x 500 (an invented tail) | **MISSED** (shifts NP +16 mm) | The planform is accepted on any component type and anywhere. Here it pushed SM to 21.6% (FAIL), but it can be moved either way. |
| f1 | Wing planform duplicated on the fuselage box | Accepted, no numeric effect | T0 rejects planform + lifting_surface on *one* component only. A second copy elsewhere is accepted. Area and stall use the largest surface, so no double count here; an offset copy behaves like f2. |
| ca-m1 | concept-a copy, motor→adapter E-PRP-10 changed to `glued` | CAUGHT | "prp-001-ur: … no propeller attached directly or through up to 2 bolted or press-fit other/structure parts" |
| m2 | Example, prop press-fit to the motor *mount* (structure) instead of the motor | Rule MISSED, geometry caught | T1.motor_has_prop PASS "motor_l -> mount_l -> prop_l: drives its propeller through an adapter chain". Only the 29.5 mm contact gap fails. The chain may run *up* the mount toward the root. |

### 5. Are the classifications in designs/concept-a/validator-comparison.md honest?

| Row | Claimed | Verdict |
|---|---|---|
| T2.sim_rest tipped 79 deg: "(a) with (b) … tip-over margin about 29 deg, the same case the source treats as accepted damage" | (a)+(b) | **Misreads the source.** arm_cup_checks.md L37 "Tip-over damage case" is a *strength* case (arm bending if it tips), not acceptance that it tips. The source's landing sim (structures_run.md L186-199) says "**No tip-over in any case (end tilt <= 3 deg)**", with crushable feet and touchdown up to 1.2 m/s. Our 0.3 m rigid drop (about 2.4 m/s, no crush) tipping is **(b)**. There is a separate **real (a) finding** the doc doesn't state: on the current CAD (pads x 307.5-337.5, z +-183; our CG) the static narrow-axis tip angle is **29.1 deg**, below the source's own **30 deg limit** (structures_run.md L184 "33.2 deg (limit 30)", computed for the older geometry: feet x 0.300, CG 0.275 m above them, versus 0.317 m now). Send that to the team. |
| T3.static_margin 16.6%: (b) | (b) | Class honest: our NP is the bare MAC quarter chord with no prop, fin or body terms. **But the text is wrong in direction**: "Dillon's NP 40.7 mm … is 20 mm aft of ours". With x aft, 40.7 is 20 mm **forward** of our 61 mm. That is why ours reads more stable. |
| 20 placeholder drop-load FAILs: "(a) with (b) … a real documentation gap" | (a)+(b) | **Should be (c)**, the convention in all earlier comparisons. The FAIL compares the drop peak with a number *we* set. The missing capacity is a real gap, so note it, but the row is no evidence about the joint. Also E-ASM-01 (hardware lump) and E-HRN-20 (harness lump) are fictitious zip-tie joints created for point masses; they can never be a concept A issue. |
| E-WNG-20/21: (c) risk | (c) | Honest. |
| 10 kinematic_link WARN: (b) | (b) | Honest about the cause, but see blocker 3: today a WARN lets a design be accepted with unchecked pairs. |
| T1.motor_has_prop resolved | n/a | Honest. The chain check works on concept A, with the hole shown in m2. |

### Verdict

**NOT ACCEPTED** (branch not ready to merge). The import itself is good: deterministic, the source is untouched, geometry is exact to the team's GLB, CG is independently reproduced, and 12 of 14 spot-checked numbers match. But the three new schema escape hatches each let a broken design get Accepted: yes (p3, k1, ca-f3), placeholder ratings print PASS, and the comparison doc misreads the source on tip-over.

### Remaining blockers

1. **Provenance**: (a) relabel E-WNG-30R/31R/30L/31L from `[doc]` to placeholder: foam_103.md L10 says the peel case has no valid allowable. (b) Fix `structures_a.py L19` to **L17** in importers/dbf_ratings.py (23 citations), and re-import.
2. **point_mass has no placement check** (p3). Fix: T1 FAIL unless the point lies inside its attached parent's mesh (or within `attach_tolerance_mm` of it). Optionally require a `proxy_reason` and cap the mass fraction in design-standards.yaml. Concept A passes this: hrd-001 is inside wng-001, and hrn-001 is 0.9 mm from avn-008.
3. **kinematic_link makes unchecked pairs a WARN, so the design is accepted** (k1). Fix: report the unchecked pairs as **SKIP** (not accepted, the same rule as "fit not verified"). Allow the flag only on hinge or linkage joints, with a required `reason`. Have the importer read `poses[].linked` from the dump instead of hard-coding it.
4. **planform isn't tied to geometry** (ca-f3, f2, f1). Fix: allow `planform` only on wing/tail_surface components, at most one per lifting system. Check its LE, span and root location against the bounds of the component plus its articulated children (concept A: core x 0-183.8 plus elevons to 245) within `attach_tolerance_mm`. Add ca-f3 and f2 as tests.
5. **Placeholder ratings print PASS** (22 rows). Fix: add `rated_load_basis: placeholder|derived|doc` to the attachment schema, and have T2.joint_load and sim_drop_loads emit **SKIP** for placeholders. A placeholder set from our own demand must never be a PASS.
6. **validator-comparison.md corrections**: tip-over → (b), with the 29.1 deg vs 30 deg static finding added as (a). Fix the NP direction sentence. Placeholder FAILs → (c), noting that E-ASM-01/E-HRN-20 are lumps, not joints.

### Non-blocking

1. Motor→prop chain (m2): require each intermediate to be on the child side of the motor, away from the root, so a prop on the motor mount doesn't count.
2. Revolved bodies are 24-segment facets (-1.14% volume against analytic). Consider 48 segments in `dbf_geometry` for tight-clearance pairs.
3. README: split "66 derived" into 49 + 17 placeholder-stress-area.

## Round 6 (b757287)

Reviewer: same Opus instance (R1). Commits reviewed: 0887923, 106eae6, 7070357, b757287 on `concept-a-import`. Round-5 cases were re-run in `/tmp/ap-review5/` (`out-r6.md` in each folder; example and concept-a copies regenerated with `mk5.py` from the current files). New attacks are in `/tmp/ap-review6/` (`mk6.py`, one folder per case with `out.md`). Nothing under `designs/` was edited.

### 5. Automated

- `python3 -m pytest -q`: `95 passed, 42 warnings in 25.06s`.
- `plane validate designs/example-tailsitter-wing`: exit 0.
- `plane validate designs/concept-a --tier all`: exit 1, Accepted: no. 66 non-PASS rows: T1 10 SKIP (kinematic_link); T2 26 joint_load SKIP, 26 sim_drop_loads SKIP, 2 sim_drop_loads FAIL (E-WNG-20 2.2 N and E-WNG-21 2.1 N vs 1.4 N), 1 sim_rest FAIL (79 deg); T3 1 static_margin FAIL (16.6%). T4 and T5 PASS. This matches the conductor's summary.

### 1. Round-5 blockers

| # | Round-5 blocker | Status | Evidence |
|---|---|---|---|
| 1 | Provenance: lens caps `[doc]`; BOND_TAU at L19 | **FIXED** | E-WNG-30R/31R/30L/31L are `rating_basis: placeholder` and quote the foam_103.md L10 disclaimer. plane.yaml now has 0 "L19" and 27 "structures_a.py L17" citations. |
| 2 | point_mass placement | **FIXED for ordinary point masses; reopened by `distributed`** | New T1.point_mass_location. p1: "battery … is 170.0 mm from every part it is attached to". p2 and p3: off-host FAIL plus "lies inside the prop disc of prop_l". But see d1/d2: the conductor's `distributed: true` relaxation lets the same cases through. |
| 3 | kinematic_link WARN, so accepted | **FIXED** | T1.kinematic_link is now SKIP. k1 (ordinary glued joint flagged) exits 1, Accepted: no. The flag is still allowed on any joint, with no reason field. That is fine now, because it can only block acceptance. |
| 4 | planform not tied to geometry | **FIXED as filed, but bypassed** | New T3.planform_matches_geometry: ca-f3 (5 mm shift) FAIL "LE off by +5.0 mm (limit 4.9 mm)"; f1 (planform copied onto fuselage) FAIL; f2 (tail planform on the battery) FAIL. But c1 and c2 below get through. |
| 5 | placeholder ratings print PASS | **FIXED** | Schema `rating_basis` (sourced 29, derived 66, placeholder 26; all 121 joints carry it). Placeholders give SKIP in both T2.joint_load and T2.sim_drop_loads, so none PASS by construction. `rating_basis` is optional in the schema, so a hand-written design can leave it off; suggestion 1. |
| 6 | comparison doc: tip-over, NP direction, placeholder class | **FIXED** | Tip-over: (b) for the rigid drop, and (a) pending team confirmation for the static angle against A-P9 (REQUIREMENTS-A.md L42, ">= 30 deg"); the "accepted damage" claim is withdrawn. NP direction: "ours is aft of his, so our margin is larger". Placeholders: (c), with E-ASM-01/E-HRN-20 named as lumps. The doc rightly asks for my 29.1 deg calculation: CG (20.46, 2.38, 6.68) mm from `mass_properties`; pads x 307.5-337.5, z -183..+183. The narrow-side half-footprint from the CG is 183 - 6.68 = 176.3 mm, the height is 337.5 - 20.46 = 317.0 mm, and atan(176.3/317.0) = **29.1 deg** (tipping toward +z, the side the CG leans to; 30.0 deg ignores the CG z offset). That is outer pad edges; pad centres would give less. |

Round-5 cases still caught: ca-m1 (glued adapter, motor_has_prop FAIL) and k0. m2 (prop on the motor mount) still gets T1.motor_has_prop PASS "motor_l -> mount_l -> prop_l"; only the contact gap fails it (still non-blocking).

### 2. New attacks on the `distributed` relaxation and the planform rule (/tmp/ap-review6/)

| # | Attack | Result | Detail |
|---|---|---|---|
| d1 | Example: the **250 g battery** (33% of the aircraft) declared `point_mass: {distributed: true}` and placed **30 mm above the fuselage top, in open air** | **MISSED**: exit 0, **Accepted: yes** | "battery at (140.0, 0.0, 70.0) mm: distributed mass inside the aircraft's envelope". The convex hull of a wing with fins is mostly empty space. Only a hover-moment WARN (47%) shows. |
| d2 | Round-5 p3 cameras (15 g payloads, 48 mm off the wing, which now FAIL) relabelled `distributed: true` | **MISSED**: exit 0, **Accepted: yes** | One keyword turns the p3 FAIL into a PASS. Nothing limits `distributed` by type (these are `payload`), by mass, or by need. |
| d3 | 400 g payload declared distributed, at the battery's own position | Not accepted, but only through mass/stall/SM | The overlap with the battery is invisible by design; this case only shows that mass checks still bite. |
| c1 | concept-a copy: planform moved **4.5 mm** forward (inside the 2% = 4.9 mm tolerance) | **MISSED**: T3.planform_matches_geometry PASS; **T3.static_margin FAIL 16.6% → PASS 14.8%** | 2% of chord is 1.8 points of SM on a 245 mm MAC, so the tolerance alone can flip the verdict. |
| c2 | concept-a copy: a fake articulated "LE strip" (15 x 100 x 2 mm, 1 g, hinge range [0, 1] deg, on 100 mm of the 900 mm span) pads the LE; planform declared 260 mm chord from x -15 | **MISSED**: planform PASS "of the geometry of wng-001, wng-006-r, wng-006-l, le-strip"; **SM 11.4% PASS**; wing area +6% (stall 11.2 → 10.8 m/s) | The rule compares only the *extreme* LE/TE/span of the union, so one small articulated child anywhere moves the bound for the whole span. The strip passes every T1 check (contact, pivot, sweep) and T4. |

### 3. Where E-WNG-20/21's 1.4 N comes from

`rating_basis: derived`, comment "contact area 16 mm2 (measured on the meshes) x foam_103.md XPS shear 86 kPa (EST)". 16 x 0.086 = 1.38 N, rounded to 1.4. Import-report agrees: kind derived. The source gives no capacity for this bond. amodel/wing.py L413 only says "balance horn root bonded to the elevon nose face (D-187)", and no structures doc checks it. The part is a 16.1 g lead strip plus two PETG/CF tabs (wing.py L378). Our horn mesh is 24.6 x 106 x 1.45 mm and ends 0.14 mm short of the elevon, so the 16 mm2 is whatever our meshes put within the assumed glue-line clearance. **The label is honest but weak**: "derived" here means a measured artefact times an EST allowable, not a designed bond area. The comparison's "(c) risk" with "the real bond may be larger" is the right class. These two FAILs are no evidence about concept A, and the peaks also come from the rigid drop. Suggestion: if the source has no bond geometry, downgrade a contact patch under ~25 mm2 to placeholder. Not blocking.

### 4. Coverage of validator-comparison.md

All 66 non-PASS rows are covered: 10 + 52 + 2 + 1 + 1 = 66, matching my run row for row (26 placeholder joints listed by id; the counts match). The tier counts and the "95 static joint-load PASS" (121 - 26) are correct. **Complete.**

### Verdict

**NOT merge-ready**, but close. Round-5 blockers 1, 3, 5 and 6 are fixed; 2 and 4 are fixed for the filed cases. The conductor's `distributed` relaxation and the bounds-only planform match each let a broken design get Accepted: yes or flip the key static-margin result (d1, d2, c1, c2).

### Remaining blockers

1. **`distributed: true` is an unlimited escape hatch** (d1, d2). Keep the relaxation, but bound it. Allow it only on component types `other`/`structure` with a required `items` or `reason` string (harness, hardware). Cap each distributed mass at a new `geometry.distributed_mass_max_fraction` in design-standards.yaml (e.g. 0.05 of total mass, `source: internal convention`; concept A's 26.08 g and 18.4 g are 2.1% and 1.5%). Change "inside the convex hull" to within `attach_tolerance_mm` of *some* solid part, or inside the union of solids: HRD-001 sits inside wng-001, and HRN-001 is 0.9 mm from avn-008, so concept A still passes. Add d1 and d2 as tests.
2. **The planform match is bounds-only and too loose for SM** (c1, c2). (a) Compare per spanwise station: slice the component plus its articulated children at, say, 10 stations, and require the local LE/TE to match the planform outline. A 100 mm strip then fails 9 of 10 stations. (b) Tighten `planform_match_tolerance_fraction` for LE/TE so the allowed shift is well under one SM point (≤ 0.5% chord = 1.2 mm here), or compute the NP from the *measured* LE/TE instead of the declared ones. (c) Count only articulated children that are control surfaces (an articulated part that lies within the planform's span and chord), not any articulated part. Add c1 and c2 as tests.

### Suggestions (non-blocking)

1. Make `rating_basis` required in schema 0.4 attachments, so a hand-written rating can't skip the label.
2. Motor→prop chain via the mount (m2) still passes T1.motor_has_prop; restrict intermediates to the child side of the motor.
3. E-WNG-20/21: see section 3.

## Round 7 (ca08b1e)

Reviewer: same Opus instance (R1). Commits reviewed: a8ff638, a3b2ca0, e81d45a, 19ce430, ca08b1e on `concept-a-import`. New attack copies are in `/tmp/ap-review7/` (`mk7.py`; each folder has `plane.yaml` and `out.md`). Round-6 d1/d2 were re-run in `/tmp/ap-review6/` (`out-r7.md`, plus `out-r7b.md` with a `reason` added). Nothing under `designs/` was edited.

### Automated, determinism, CI

- `python3 -m pytest -q`: `107 passed, 42 warnings in 25.19s`. The tests do not need the dbf-combined checkout: no path to it in tests/.
- `plane validate designs/example-tailsitter-wing`: exit 0.
- `plane validate designs/concept-a --tier all`: exit 1, 67 non-PASS rows. These are the 66 from round 6 plus the new T3.planform_matches_geometry WARN. T3 now reads SM 16.4% (NP 58 mm), stall 11.7 m/s, lateral CG 0.3%.
- Determinism: a re-import to `/tmp/ap-review7/reimport` took 4 min 58 s with rc 0. `diff -r -x '*.md'` against `designs/concept-a` is empty. dbf-combined `git status --short` is empty.
- `git diff main --stat`: 132 files, +6336/-102. That is core (checks, geometry, mass, sim, cli, export), the new `importers/` package, schema, standards (+4 keys), 3 new test files, `designs/concept-a/` (104 STL, about 4.5 MB), the plan and briefs, and this review. No other design on main is touched: c0-*, tiltwing-cakir and example-tailsitter-wing have no diff. Sane.
- CI: `.github/workflows/validate.yml` and `pages.yml` are unchanged from main. `plane build-index --out /tmp/ap-review7/viewer-data` (the Pages step) runs in 38 s and writes concept-a.glb, mass and scorecard. **Pre-existing, not a regression:** validate.yml's "Score every design" step exits 1 whenever any design is not accepted. On main, c0-a1/a2/a3, c0-lift-cruise and tiltwing-cakir already exit 1, so that job is already red; concept-a adds a sixth. Suggestion: gate only on `status: built|flown` designs, or make the step report-only.

### 1. Round-6 blockers

| # | Round-6 blocker | Status | Evidence |
|---|---|---|---|
| 1 | `distributed: true` unlimited | **FIXED** | Schema requires `reason`: d5 (no reason) T0 FAIL. Type: d1 (battery) and d2 (payload cameras) with a reason added both FAIL "distributed point masses are only for type other". Caps: d1 also FAILs "250.0 g is 32.9% … at most 3%" and the 5% total; d6 (four 16 g `other` lumps, 7.8%) FAILs the total. Residual, within the conductor's decision: d4 (two 16 g `other` lumps, 1.9% each, floating 48 mm above the wing) is accepted, as the 3%/5% bound allows. Concept A: HRD-001 2.07%, HRN-001 1.46%, PASS. |
| 2 | planform bounds-only and loose | **Redesign accepted; two new holes** | All tier-3 numbers now come from measured strips; the declared outline is a cross-check only (concept A: -8.4% area, WARN). Re-run: round-6 c1 (4.5 mm origin shift) and c2 (100 mm LE strip) no longer move anything that matters; the origin cancels out of x_ac. But the declared *rotation* still sets the slicing axes (s1), and a gap between pieces counts as chord (s4). |

### 2. Attacks on the measured-strip method (concept-a copies)

| # | Attack | Result | Detail |
|---|---|---|---|
| s1 | Geometry untouched; only the declared `planform.rotation_deg` set to [0, 0, 15] | **MISSED**: T3.static_margin **FAIL 16.4% becomes PASS 13.0%** (NP 58 → 51 mm), measured span 900 → 917 mm; planform check only WARNs | `strip_planform` slices in the *declared* planform frame, so a yawed declaration cuts oblique sections. This contradicts "a declared planform can't move any number". |
| s2 | 1 x 1 x 200 mm articulated "spike" ahead of the LE at y = 300 | No effect (CAUGHT in effect) | It lies between station centres, so no slice sees it: area and NP are unchanged. A narrow feature is sampled arbitrarily, but its effect is bounded by one strip (22 mm). |
| s3 | Disjoint pieces: a 50 x 600 mm plate 95 mm behind the elevon TE, joined by a 1 x 1 mm rod | CAUGHT (planform FAIL +32.4% area, plus a joint location FAIL) | The gap between the pieces is counted as chord (measured area 291952 mm^2), but the declared/measured cross-check FAILs above 15%. |
| s4 | Disjoint pieces kept under the 15% band: a 10 x 200 x 1 mm strip **60 mm ahead of the LE** (y 100-300), joined by a 1 x 1 mm rod, range [0, 0] | **MISSED**: planform WARN (-2.0%), **SM 16.4% FAIL becomes 9.0% PASS** (NP 58 → 43 mm); area 202009 → 216002 mm^2; every T1 check passes | Per station, chord = max x - min x across all pieces, so the 60 mm of air counts as wing. 2000 mm^2 of real strip becomes 14000 mm^2 of area and moves NP 15 mm. This is not the documented "padding counts" limit: real disjoint geometry (a slotted flap, a hinged canard-like part) would be mis-measured the same way. |

### 3. The strip numbers on concept A, by hand

From `amodel/common.py`: C 0.245, B 0.90, ELEV_FRAC 0.25, so XH (hinge) 183.75 mm; elevons at |y| 40-350 mm. The wing is then a 183.75 mm core over 900 mm plus 61.25 mm elevons over 2 x 310 mm. Analytic: S = 183.75 x 280 + 245 x 620 = **203350 mm^2**, MAC = (183.75^2 x 280 + 245^2 x 620) / S = **229.5 mm**, x_ac = MAC/4 = **57.4 mm** (LE at x = 0), SM at the 20.46 mm CG **16.1%**. The validator's 41 strips give S 202009 (-0.66%), MAC 228.36 (-0.5%), x_ac 57.87 mm (+0.5 mm), and SM 16.4%. With 401 strips: 202308, 228.58, 57.65. The 41-strip result is converged to 0.15%. The small differences are the hub cut-out at the centre (LE 22.5 mm aft, chord 161 mm, per the comparison doc) and the elevon ends. **Plausible and correct.** The declared rectangle (220500 mm^2) overstates the modelled wing by 8.4%, because the CAD has no trailing 25% outside the elevons. The WARN is right, and Dillon's sizing S 0.22 m^2 uses the full rectangle.

### 4. validator-comparison.md is now stale

It still says "66 not PASS" (now 67), still lists T3.static_margin as "16.6% … NP (61 mm)" (now 16.4%, 58 mm), and the SM row still says "With the planform matching the mesh (T3.planform_matches_geometry PASS)" (now WARN, -8.4%). The key-rows table *does* describe the new planform WARN (line 23), but the classified table and coverage line don't include it. One row, (b)/(c) cross-check only, plus updated numbers will fix it.

### Verdict

**NOT MERGE-READY.** Distributed masses are closed. Determinism, tests, the example, the diff and CI behaviour are all fine. The measured-strip redesign is sound and its numbers check out by hand. Two holes remain in it, each flipping concept A's static margin from FAIL to PASS without changing any real geometry (s1) or with a 1 g part (s4). The comparison doc also lags the code.

### Remaining blockers

1. **Declared rotation sets the slicing axes** (s1). In `strip_planform`, slice in the component's own frame: body y, or the component's `rotation_deg` for a rotated mesh. Ignore `planform.rotation_deg`, or require it to equal the component's rotation (T0 FAIL otherwise). Add s1 as a test.
2. **Gaps count as chord** (s4). Per station, take chord as the total length of the *union of x-intervals* of the section polygons, not max - min. Compute x_ac from the forward-most interval's LE (or per interval). Alternatively, FAIL or SKIP a station whose pieces are separated by more than a small gap (e.g. `attach_tolerance_mm` plus the hinge gap). Concept A's elevon hinge gap (core TE 183.75 to elevon LE 183.49, an overlap) is unaffected. Add s3 and s4 as tests.
3. **Update `designs/concept-a/validator-comparison.md`** to the current run: 67 rows, SM 16.4% / NP 58 mm, and the planform WARN classified.

### Non-blocking

1. validate.yml "Score every design" is red on main already (pre-existing); see CI above.
2. d4: two 1.9% `other` lumps floating in the hull are accepted by design. Consider requiring distributed masses to lie inside a solid part or within `attach_tolerance_mm` of one, which concept A's two lumps satisfy (round 5).
3. Earlier suggestions still open: `rating_basis` optional; motor→prop chain via the mount (m2).

## Round 8 (8ff06ec) — final merge sign-off

Reviewer: same Opus instance (R1). Commit reviewed: 8ff06ec on `concept-a-import` (on top of d913e22). Attacks were re-run in `/tmp/ap-review7/` (`out-r8.md` in each folder; s4b and s5 are new, built with `mk7.py`). Nothing under `designs/` was edited.

### Automated

- `python3 -m pytest -q`: `113 passed, 42 warnings in 25.21s`.
- `plane validate designs/example-tailsitter-wing`: exit 0.
- `plane validate designs/concept-a --tier all` (fresh run, md and JSON): exit 1. 502 rows, 67 not PASS: T1 10 SKIP (kinematic_link); T2 52 SKIP (placeholders) and 3 FAIL (E-WNG-20/21, sim_rest); T3 1 FAIL (static_margin 16.8%, NP 59 mm) and 1 WARN (planform -8.9%, measured 200905 mm^2).
- Code changed only in geometry.py, checks.py and standards since round 7. Determinism was verified last round, and this commit does not touch the importer or the concept-a import files (`git diff d913e22 --stat`: README, checks, geometry, standards, tests, comparison doc).

### Round-7 blockers

| # | Blocker | Status | Evidence |
|---|---|---|---|
| 1 | Declared rotation sets the slicing axes (s1) | **CLOSED** | Chord is along body x and the span axis comes from the geometry. s1 (declared yaw 15 deg) now gives T3.planform_matches_geometry **FAIL** "declared span runs 15.0 deg from the measured span … limit 5 deg", and the numbers are unchanged from baseline (SM 16.8%, NP 59 mm). |
| 2 | Gaps count as chord (s4) | **CLOSED** | Chord is the longest contiguous group. s4 (strip 60 mm ahead): the strip is ignored as detached, SM 16.8% as baseline, WARN "detached material ignored at 11 strips". s3 (plate 95 mm aft): ignored, area -6.8% (WARN), SM 17.0%. |
| 3 | Comparison doc stale | **CLOSED** | It now matches the fresh run: 502 rows, 67 not PASS (62 SKIP, 4 FAIL, 1 WARN), SM 16.8% / NP 59 mm, measured 200905 mm^2 (-8.9%), and the planform WARN classified (c). Small omission: the WARN row's "detached material ignored at 3 strips (largest 7 mm)" is not explained. My run puts these at y = 0 and y = ±197.6 mm (6-7 mm slivers ahead of notches in the core, e.g. at the hub); together under 1500 mm^2 of chord-area. Add one sentence. |

### Is the 15% bridging rule principled?

- **Mechanism**: gaps up to 15% of the local envelope are bridged *only* when one side is the root's material and the other an articulated child (or a group containing the root). Any other gap is bridged only up to 3 mm. Detached material is ignored and reported. **It can't be abused without an articulated child**: non-articulated parts never enter the measurement, s4 shows a hinged piece past 15% is ignored, and material in the root mesh beyond 3 mm is dropped as detached.
- **On concept A** the bridged gaps are exactly where the source puts the balance lead: strips 5-9 and 31-35 (|y| ≈ 241-329 mm), 23.56 mm each. That matches the WNG-007 lead strip at y 232-338 (amodel/wing.py L378; mesh bounds from round 6). So the rule reproduces a real pocket and is not a blanket fudge. By hand from common.py: S 203350 analytic vs 200905 measured (-1.2%); MAC 229.5 vs 227.5; x_ac 57.4 vs 58.6 mm (hub notch at the LE). Plausible.
- **Value**: the 0.15 is sized from concept A (9.6%) with margin, and the standards entry says so honestly ("value internal convention, sized to cover … concept A's 23.6 mm"). The principle (a wing's planform includes its control surfaces) is the standard definition. A tighter principle would bridge only where the gap contains the child's hinge line (its articulation pivot lies between the pieces), which needs no fraction at all. Suggested, not required.
- **What it allows (documented)**: s4b, a 1 g hinged 10 x 200 mm strip 40 mm *ahead of the LE* on a 1 mm hinged rod, is bridged and takes SM from 16.8% FAIL to **12.0% PASS**. s5, a hinged 30 mm "slat" 2 mm off the LE, likewise gives 12.0% PASS (that one is legitimate geometry if real). Both need deliberately added hinged components that appear by name in plane.yaml, in the scorecard ("…geometry of wng-001, …, rod3, fwdstrip3") and in the viewer. README "Known limits" lists "a fake hinged piece within 15% of a real control surface's chord is counted". s4b shows the piece need not be near a control surface (it was ahead of the LE), so reword to "any hinged (articulated) child of the wing within 15% of local chord, anywhere along the chord". Wording only; non-blocking.

### The conductor's position

I agree with it, with one condition that is already met. After rounds 5-7 every remaining hole needs a *deliberately fabricated* entry: a hinged strip, a 1 mm rod, a lump typed `other` with a written `reason` under 3%/5%. Each is visible as a named component in the design file, the scorecard and the viewer. None can be produced by an honest import or an honest modelling mistake, and none changes a result without adding something a reviewer can point at. Chasing them in code would mean deciding whether geometry is "real", which a validator can't do. The condition is that the limits are written where users will read them. README "Known limits (v0.4)" does that, and says plainly that a human reviewer must confirm the model matches the aircraft. Each limit was reproduced here (d4, s4b) and behaves as documented. The holes I treated as blockers in earlier rounds (s1, s4, the c1/c2 planform shifts, d1/d2 type disguise, placeholders printing PASS, kinematic_link accepted) needed no fake parts, and those are all closed.

### Verdict

**MERGE-READY.** No remaining blocker that is not already a documented limit.

### Non-blocking (for a follow-up)

1. README: reword the hinged-piece limit as above (s4b).
2. validator-comparison.md: one sentence on the 3 detached LE slivers.
3. Consider pivot-in-gap bridging instead of a 15% fraction; consider computing `envelope` (the base of the 15%) from the root and adjacent children only, since detached material currently enlarges it.
4. Still open from earlier rounds: `rating_basis` optional in the schema; motor→prop chain via the mount (m2); validate.yml "Score every design" red on main, which predates this branch.

## Round 9 — regression-only CI (ci-baselines)

Reviewer: same Opus instance (R1). Commit reviewed: 14f75a8 on `ci-baselines`; plan `plans/2026-11-17-ci-baselines.md`. Every attack ran in a full throwaway copy, `/tmp/ap-review9/wt` (`cp -a` of the repo, `PYTHONPATH=/tmp/ap-review9/wt/core`, so `REPO_ROOT` is the copy), using git commits in that copy for `--base-ref`. Nothing in the real repo was edited except this file.

### Automated

- `python3 -m pytest -q`: `150 passed, 3 skipped, 46 warnings`.
- `plane baseline check --all --format json`, run twice: exit 0 both times, and the outputs are **byte-identical** (deterministic). Known keys per design: c0-a1 20, c0-a2 16, c0-a3 17, c0-lift-cruise 17, concept-a 66, tiltwing-cakir 24; example accepted. Keys that merge several results: concept-a "sweep E-WNG-10/11 #°" (2 each), tiltwing "sweep wing-tilt/tail-tilt #°: clipping …" (6, 6, 4).

### Attacks

| # | Attack | Result | Evidence |
|---|---|---|---|
| A1 | **Swap inside one key.** Design `atk-a1` (the example with numeric joint ids "1".."11"); baseline has joint "4" failing its rating. The change fixes "4" and breaks "5". | **MISSED** | `#: # N at 4.5g exceeds rating # N`: "4:" and "5:" normalise to the same key, so the check says "Unchanged: 2. Regressions: 0", rc 0. The same happens wherever the subject is only in a number or past a truncated list (A1c). |
| A1b | **Regression plus a baseline edit that adds no key.** Joints "4" and "5" both fail (count 1 → 2; the control run is caught, rc 1), and the same commit sets `count: 2` in baseline.json. `--base-ref` = previous commit. | **MISSED, silently** | rc 0, and **no "ADDED" section and no `::warning`**: `growth()` compares key sets only, so raising a `count` or changing a `status` (SKIP→FAIL) in baseline.json is invisible. Also, in the control run the regression table showed "4: … exceeds rating 0.1 N" (the old joint) and not the reason "count rose from 1 to 2". The md tables drop the `reason` field, so the reviewer is pointed at the wrong joint. |
| A1c | **Truncated id lists.** kinematic_link ("…: mec-003-l, …, wng-006-r, …") and fea "out of date for # part(s) (…6 ids…)" show at most 6 ids. | **MISSED** (key level) | `normalize_message` of "6 pair(s) … wng-006-r, …" and "7 pair(s) … wng-006-r, …" is identical (checked in Python). A new unchecked pair, or a stale part past the 6th id, adds nothing to the key. |
| A2 | **Value crosses the band.** concept-a: foot pads 0.7 → 50 g each, so SM 16.8% → **-1.2% (unstable)**. | Caught only by accident | The SM key is unchanged. CI failed only because every fea result went stale (new SKIP key; the mass change alters the part hashes). |
| A2b | Same on a design without fea results. c0-lift-cruise: battery 820 → 100 g, so SM **15.3% (too stable) → 3.8% (below the 5% minimum)**; hover moment rises to a 73% WARN. | **MISSED** | "Result: pass", rc 0. The summary even lists an **Improvement** (the battery joint's drop-load FAIL went away) and tells the author to run `plane baseline update`. Static margin moving from one side of the band to the other is the classic regression, and the key `#% MAC (NP x=# mm, CG x=# mm; target #%#%; …)` can't see it (the sign is lost too: "-1.2%" becomes "#%"). WARNs are ignored by design, so the hover-moment change is also invisible. |
| A3 | Delete `requirements.stall_speed_max_mps` from c0-a1 to silence T3.stall FAIL (12.3 > 12 m/s). | **MISSED** (shown as an improvement) | rc 0; "Improvements: T3.stall … > required 12 m/s". The validator then PASSes stall with no limit. This is mainly a validator gap (a missing requirement is silent), but the summary calls it an improvement. The plane.yaml diff shows the removal. |
| A4 | Regression plus `plane baseline update` in the same change (new keys). | CAUGHT as visible, **not failing** | rc 0. "Known failures ADDED to the baseline in this change (reviewers: confirm each)" lists the 2 wing-pod rows, plus `::warning title=Baseline grew (c0-a2)::…` annotations. This is the plan's stated policy (growth is visible, not a failure). |
| A5 | Same regression plus **renaming the folder** (`designs/c0-a2` → `c0-a2-renamed`). | Visible but **buried** | `baseline_at_ref` looks up the new path at the base ref, finds nothing, and lists **all 18** keys as ADDED; the 2 real additions are among them. Every rename or move of a design hides its real growth this way. |
| A6 | Delete a non-accepted design's baseline.json. | CAUGHT | rc 1, "Missing baseline.json". All 17 rows are listed as regressions. |
| A7 | "Accepted because a tier was skipped" | Not reachable | `baseline check` always runs `validate(design)` at tier 5. A SKIP anywhere blocks acceptance (rounds 2-6), and a partial run is never accepted. |
| A8 | Numbers next to punctuation and units | No miss; some noise | `[1.0, 50.0, 600.0]`, `(SF 1.5;`, `12/41`, `sweep E-WNG-10 -6°` normalise; ids (`E-WNG-20`, `prop_2`, `M3x8`, `v2.0`) keep their digits. Numbers glued to a unit (`x=-5.0mm`, `4.5g`) or in exponent form (`1e-3`) are **not** normalised, so if such a value moved it would read as a new key: a false regression, not a miss. Current messages use spaced units ("2.2 N", "mm^3"). |

### Workflow reasoning (validate.yml)

- PR: `base = origin/<base_ref>`; `fetch-depth: 0` makes it present. Growth is measured against the base branch tip. Correct.
- Push to main: `base = github.event.before`. For a force-push whose old head is gone, or for **the first push that introduces baselines** (the merge of this branch), `git show <before>:…/baseline.json` fails. `baseline_at_ref` returns None, so every key of every design (about 160) is reported as ADDED and annotated. That is noisy but harmless (exit 0), and it happens once on merge. A new branch (`before` = 000…) skips growth. Correct.
- `shell: bash` runs with `-eo pipefail`, so the step fails on plane's exit 1 even before `exit ${PIPESTATUS[0]}`; the summary is still written by `tee`. Correct. The `::warning` lines also go through `tee` into the step summary as raw text (cosmetic).
- Growth never fails CI (by policy), so the safety of this path depends on a human reading the ADDED section. A5 shows that section can be flooded.

### Is the md summary readable?

Mostly yes: a result line, then per design the counts, regressions, improvements and ADDED keys, each as a table or list. Two defects matter for a reviewer:
1. The regression and improvement tables omit the `reason` field ("count rose from 1 to 2", "was SKIP in baseline, now FAIL"). With only one example message per key, they can name the wrong instance (A1b control).
2. "Improvements" includes things that aren't (A2b, A3). The text "run `plane baseline update` … to record the improvement" invites locking in a worse design.

### Verdict

**NOT MERGE-READY.** Determinism, missing-baseline handling and the workflow are sound, and plain baseline growth is visible as the plan intends. But three paths let a real regression through with a green check, two of them with no trace in the summary.

### Blockers

1. **Baseline edits that add no key are invisible** (A1b). Make `growth` diff whole entries `(key, status, count)` against the base ref, and list any count increase or SKIP→FAIL change under "ADDED/LOOSENED". Treat a path rename as a move: match by `design_id`, not folder (A5).
2. **The key can't see a FAIL changing side or direction** (A2b; the sign is lost). Give band checks distinct failure modes in their messages (e.g. T3.static_margin "above band" / "below band"; the same for any min/max check), or derive the key from structured data (check_id + `r.data` mode/side). Then 15.3% → 3.8% becomes a new key. Don't call a set of changes an "improvement" when another FAIL got worse in the same design.
3. **Several results collapse into one key** (A1, A1c). Build the key from the result's *subject* (`r.data` part / pair / joint / configuration, or the full untruncated id list) rather than from display text, and list every instance. Never truncate an id list in text that forms a key. Show the `reason` column in the md tables.

### Non-blocking

1. A3: emit a visible row (WARN or SKIP) when a requirement the checks use is absent (`stall_speed_max_mps`, `mtow_g`), so deleting it isn't silent.
2. Normalise numbers attached to units (`5.0mm`, `4.5g`) and exponents, to avoid false regressions.
3. The first push after merge will annotate about 160 "Baseline grew" warnings. Consider skipping growth when the base ref has no baselines at all.
