# Validator comparison: platform vs the DBF team's own numbers

Platform run: `plane validate designs/concept-a --tier all` (JSON: `/tmp/ca5.json`), wall time about **25 s** (tier 1 broad phase + pair cache; the budget was 5 min).
The importer itself takes about 5.6 min (measuring bonded areas on large meshes); it is not part of validate.
The team's interference run took 103 s for 3 poses (`redesign/qp/A/cad/out/report.json` key `seconds` 103.1).
Dillon's numbers are CAD or EST values from his files; nothing here is measured. "Dillon" means the source repo, path under `redesign/qp/A/`.

**Verdict: NOT ACCEPTED** (`accepted: false`, exit 1). Not ready to merge.

Status by tier: **T0 PASS (1 row); T1 SKIP (142 rows: 132 PASS, 10 SKIP kinematic_link, no FAIL); T2 FAIL (245 rows: 190 PASS, 52 SKIP placeholder ratings, 3 FAIL); T3 FAIL (6 rows: 5 PASS, 1 FAIL); T4 PASS (106); T5 PASS (2).** 502 rows, 66 not PASS, all classified below.

## Key rows

| Topic | Ours | Dillon | Match |
|---|---|---|---|
| Mass | 1261.24 g (`plane mass`) | 1.26124 kg (`params-A.json` `mass.basic_cad_kg`, the CAD basic mass; predicted take-off 1.456 kg adds growth and overrun, `proofs/out/CHAIN.md` CL-A-MASS-PRED) | exact |
| CG x, y | 20.46, 2.38 mm (z 6.68) | 20.510, 2.396 mm (`params-A.json` `mass.cg_x_mm`, `mass.cg_y_mm`; CL-A-CG 20.51) | 0.05 mm in x |
| Interference, static | PASS, no clipping between unattached parts (limit 1 mm3) | PASS; 6 pairs below tolerance, deepest 0.034 mm (`cad/out/REPORT.md` static) | agree |
| Interference, elevons -21 deg | PASS | No overlaps (REPORT.md, lower limit) | agree |
| Interference, elevons +21 deg and sweep | SKIP per pose for the pairs behind kinematic_link (T1.kinematic_link, 10 rows, see below); no FAIL; overlap up to 9 mm3 before the flag | PASS, 2 pairs below tolerance; MEC-003 and WNG-009 "not checked against the moved parts (linkage path not modelled)" | agree the pose is not clean; ours is reported as SKIP |
| Static margin and NP (T3, from the `planform` on wng-001) | NP **61 mm** at the quarter chord of the MAC (CG 20.5 mm), SM **16.6%** vs 5-15% target: FAIL. No prop, fin, body or viscous term | NP **40.7 mm** aft of LE (`params-A.json` `cg.np_mm`, EST; MASS-GATE.md L59: "SIZING-A 44.0 inviscid, -3.3 viscous"), SM **8.24%** (CL-A-SM) | differ, class (b). Direction: ours is **aft** of his, so our margin is **larger** than his (16.6% vs 8.24%). Shifts that move NP forward (prop normal force, fin and body lift, viscous effect) would reduce our margin; his inviscid 44.0 mm is still 17 mm forward of ours |
| Stall and wing loading (T3, planform) | 11.2 m/s at 1261 g, wing loading 57.2 g/dm^2, CLmax 0.75, rho 1.2; T3.stall PASS | CLmax 0.75 EST (`params-A.json` `mission.clmax`, UNVERIFIED). A-P6 (1.3 Vs below cruise 17 m/s) margin +8%. Own arithmetic from his inputs at 1.456 kg: Vs 12.0 m/s, 1.3 Vs 15.6 m/s | consistent |
| Planform vs geometry (T3.planform_matches_geometry) | wng-001 planform LE/TE within 4.9 mm, span within 18.0 mm of the geometry of wng-001, wng-006-r, wng-006-l: PASS | Rectangular 900 x 245 mm (`amodel/common.py` L32) | agree |
| Point masses (T1.point_mass_location) | hrd-001 at (100, 0, 0) mm and hrn-001 at (30, 0, 20) mm: inside the envelope, outside every prop disc: PASS (both `distributed: true`) | Declared CG of the two proxies (PARTS, `cg_declared`) | agree |
| Hover T/W | 2.72 at 1261 g (33.7 N up of 35.2 N rated); same thrust at the 1.47 kg gate gives 2.34 (own arithmetic) | 2.338 fresh at the gate (CL-A-TW-FRESH-GATE) | agree |
| Drop and tip | Static T2: joint loads 95 PASS, hover moment PASS, sim stable PASS. Dynamic: drop loads 93 PASS, 2 FAIL (E-WNG-20/21), 26 SKIP (placeholders). Rigid 0.3 m drop tipped to 79 deg (T2.sim_rest FAIL) | Static tip-over narrow axis **33.2 deg, limit 30** (`structures/structures_run.md` L184; requirement A-P9 "static tip-over >= 30 deg (33.2 deg EST)", `REQUIREMENTS-A.md` L42). Landing sim with 20 mm crushable feet: "No tip-over in any case (end tilt <= 3 deg)" (`structures_run.md` L199) | see the tip-over row below |
| Manufacturing | T4 PASS for all 106 (printed parts fit `jacobs-fdm`) | parts-a.csv "Made / bought" text, mapped by rule | agree |
| Articulation | +-21 deg, pivot on both parts, poses PASS | joint limits +-21 (`ELEV_STOP`) | agree |

## Every non-PASS row, classified

(a) real concept A issue, (b) validator limitation, (c) conversion or input gap. Counts are rows in `/tmp/ca5.json`.

| Rows | Check | Class | Why |
|---|---|---|---|
| 10 | T1.kinematic_link SKIP, one per pose: pose up (21°); pose down (-21°); range min and max of E-WNG-10 and E-WNG-11 (±21°); sweep E-WNG-10 and E-WNG-11 at -6° and 9° | (b) | Reported as SKIP, not PASS and not WARN: the pushrods MEC-003-L/R (E-MEC-08, E-MEC-03) are `kinematic_link: true`, so their pairs with the moved horns and pins are not checked in those poses. The four-bar linkage is not modelled (the source also holds these out, REPORT.md "Not checked against the moved parts"). Overlap was 1 to 9 mm3 at the pin ends. A design with any SKIP is not accepted until the linkage is modelled. |
| 52 (26 + 26) | T2.joint_load SKIP (26) and T2.sim_drop_loads SKIP (26), on the same 26 placeholder joints: E-WNG-10, E-WNG-11, E-WNG-30R, E-WNG-31R, E-WNG-30L, E-WNG-31L, E-PRP-09, E-PWR-01 to E-PWR-04, E-AVN-02 to E-AVN-06, E-AVN-08, E-GER-02, -04, -06, -08, E-HRN-20, -21, -32, -33, E-ASM-01 | (c) conversion / input gap | Each rating is a placeholder: the source publishes no capacity for tape, gel pad, strap, tie, tape hinge, or the lens-cap peel (`foam_103.md` L10: "peel of the tape skin is not covered by a foam value: pull coupon required"). The check is SKIP, not PASS: before, these joints printed PASS by construction (our own demand as the rating). E-ASM-01 and E-HRN-20 are lumps for hardware and harness, not joints, so they can never be a concept A joint issue. The four lens caps (E-WNG-30R/31R/30L/31L) were `[doc]` before; they are now placeholder because no peel allowable exists. |
| 2 | T2.sim_drop_loads FAIL on E-WNG-20 (peak 2.2 N vs rating 1.4 N) and E-WNG-21 (peak 2.1 N vs 1.4 N) | (c) risk | Rating is derived from a 16 mm2 contact patch measured on our meshes, not a source number. The real bond may be larger than the clearance-based estimate. |
| 1 | T2.sim_rest FAIL: tipped, landing axis 79 deg (limit 30) | (a) static tip angle; (b) the drop | **(a), pending team confirmation of the foot geometry.** The static narrow-axis tip angle is the real finding. The source requires >= 30 deg (A-P9, `REQUIREMENTS-A.md` L42; team's own value 33.2 deg, `structures_run.md` L184). The review (Round 5) puts ours on the current CAD at **29.1 deg** (pads at x 307.5-337.5 mm, z ±183 mm; CG 317 mm above the feet), but does not show its calculation. Two checks with the figures in this doc: 29.2 deg (354 mm footprint, CG 317 mm) and 30.0 deg (pads at z ±183 mm). Either way it sits at or just under the 30 deg limit, so the exact value depends on the foot geometry, which the team must confirm. Our validator does not compute a static tip angle; this number is not a validator result. **(b) for the drop:** the rigid 0.3 m drop (about 2.4 m/s, no foot crush, rigid convex-hull contacts) tipped. The source's landing sim has crushable feet and reports no tip-over. The earlier claim that the source "treats this as accepted damage" was wrong: `arm_cup_checks.md` "Tip-over damage case" is a strength case (arm bending if it tips), not an acceptance. |
| 1 | T3.static_margin FAIL: 16.6% MAC vs 5-15% target | (b) | The platform takes NP at the quarter chord of the MAC (61 mm) with no prop, fin, body or viscous effect (validator message: "fuselage effect not modelled"). With the planform matching the mesh (T3.planform_matches_geometry PASS), the remaining gap is those terms. Direction: our NP is aft of Dillon's 40.7 mm, so our margin is larger; see key rows. |

Coverage: 10 + 52 + 2 + 1 + 1 = **66**, equal to the 66 non-PASS rows in `/tmp/ca5.json`. Every row is in one of the five entries above.

## Open numbers I did not invent

- The tip angle of 29.1 deg is the review's figure. It is not reproduced exactly by this file's numbers (29.2 or 30.0 deg, depending on the pad extent used). The team should confirm the foot geometry before this is called a defect.
- Ratings for the M2 and M5 stress areas are placeholders in `importers/dbf_ratings.py` (ISO values not opened in the source).
- Every Dillon number is a CAD or EST value; no coupon or flight test exists for any of them.
