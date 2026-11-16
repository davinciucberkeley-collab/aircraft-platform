# Validator comparison: platform vs the DBF team's own numbers

Platform run: `plane validate designs/concept-a --tier all`, wall time **25 s** (tier 1 broad phase + pair cache; the budget was 5 min).
The importer itself takes about 5.6 min (measuring bonded areas on large meshes); it is not part of validate.
The team's interference run took 103 s for 3 poses (`redesign/qp/A/cad/out/report.json` key `seconds` 103.1).
Dillon's numbers are CAD or EST values from his files; nothing here is measured. "Dillon" means the source repo, path under `redesign/qp/A/`.

Status by tier: **T0 PASS, T1 no FAIL (10 WARN rows, linkage not modelled; the 14 earlier FAIL rows are resolved, see below), T2 FAIL (23 rows), T3 FAIL (1 row), T4 PASS (106), T5 PASS.**

## Key rows

| Topic | Ours | Dillon | Match |
|---|---|---|---|
| Mass | 1261.24 g (`plane mass`) | 1.26124 kg (`params-A.json` `mass.basic_cad_kg`, the CAD basic mass; predicted take-off 1.456 kg adds growth and overrun, `proofs/out/CHAIN.md` CL-A-MASS-PRED) | exact |
| CG x, y | 20.46, 2.38 mm (z 6.68) | 20.510, 2.396 mm (`params-A.json` `mass.cg_x_mm`, `mass.cg_y_mm`; CL-A-CG 20.51) | 0.05 mm in x |
| Interference, static | PASS, no clipping between unattached parts (limit 1 mm3) | PASS; 6 pairs below tolerance, deepest 0.034 mm (`cad/out/REPORT.md` static) | agree |
| Interference, elevons -21 deg | PASS | No overlaps (REPORT.md, lower limit) | agree |
| Interference, elevons +21 deg and sweep | WARN, no FAIL: mec-003 pairs with mec-004/005 are not checked (kinematic_link), overlap up to 9 mm3 before the flag | PASS, 2 pairs below tolerance; MEC-003 and WNG-009 "not checked against the moved parts (linkage path not modelled)" | agree the pose is not clean; ours is reported as WARN |
| NP and SM (planform variant) | NP 61 mm, SM 15.5% MAC (variant CG 23 mm; 16.6% at Dillon's CG, own arithmetic) | NP 40.7 mm (`cg.np_mm`), SM 8.241% (CL-A-SM) | differ: row (b) |
| Stall (planform variant) | 11.2 m/s at 1261 g, CLmax 0.75, rho 1.2 | A-P6 (1.3 Vs below cruise 17 m/s) margin +8%. Own arithmetic from his inputs at 1.456 kg: Vs 12.0 m/s, 1.3 Vs 15.6 m/s | consistent |
| Hover T/W | 2.72 at 1261 g (33.7 N up of 35.2 N rated); same thrust at the 1.47 kg gate gives 2.34 (own arithmetic) | 2.338 fresh at the gate (CL-A-TW-FRESH-GATE) | agree |
| Drop test | static T2 joint loads all PASS; dynamic: 22 peak-load FAILs, tipped to 79 deg | tip-over is a documented damage case (`structures/arm_cup_checks.md` "Tip-over damage case ... CG drop 95 mm, E 1.36 J"); foot foam 30 N per foot, stroke 20 mm (`structures_run.md` L185) | see rows below |
| Manufacturing | T4 PASS for all 106 (printed parts fit `jacobs-fdm`) | parts-a.csv "Made / bought" text, mapped by rule | agree |
| Articulation | +-21 deg, pivot on both parts, poses PASS | joint limits +-21 (`ELEV_STOP`) | agree |

## Every non-PASS row, classified

(a) real concept A issue, (b) validator limitation, (c) conversion error.

| Rows | Check | Class | Why |
|---|---|---|---|
| 4 (prp-001-ll/lr/ul/ur) | T1.motor_has_prop | (b), resolved | Source chain is motor -> adapter PRP-004 (E-PRP-10) -> propeller (E-PRP-02). The check used to accept only a propeller attached directly to the motor. Brief B6d: a propeller reached through at most 2 other/structure parts, every joint bolted or press-fit, now PASSes (e.g. prp-001-ul -> prp-004-ul -> prp-002-ul). |
| 10 (up pose, range max, sweep -6 and 9 deg) | T1.kinematic_link (was T1.interference mec-003 vs mec-004/005) | (b), reported as WARN | The pushrods MEC-003-L/R (E-MEC-08, E-MEC-03) are marked kinematic_link: true, so their pairs with the moved horns and pins are not checked in those poses. Each pose gets one WARN that names the unchecked parts; it is not a PASS, because the linkage path is still not modelled (the source leaves these out too, REPORT.md 'Not checked against the moved parts'). Overlap was 1 to 9 mm3 at the pin ends. Brief B6c. |
| 1 | T3.stall (and no T3 SM, NP) | (b) | Mesh wing has no `lifting_surface`. Planform variant runs, rows above. |
| (variant) SM 15.5% over the 15% target | T3.static_margin | (b) | The platform takes NP at the wing quarter-chord (61 mm) with no body, fin or reflex effect; Dillon's NP 40.7 mm is from his aero model (EST). Not a concept A defect on this evidence. |
| 20 | T2.sim_drop_loads on E-WNG-10/11, E-PRP-09, E-PWR-02/03, E-AVN-02..06/08, E-GER-02/04/06/08, E-HRN-20/21/32/33, E-ASM-01 | (a) with (b) | Each has a placeholder rating: the source gives no capacity for tape, gel pad, strap, tie or tape hinge (a real documentation gap in concept A). The peaks are also inflated: the sim uses rigid convex-hull contacts with no foot crush (source: 20 mm foam stroke), so deceleration is about 80 g. |
| 2 | T2.sim_drop_loads on E-WNG-20/21 (peak 2.1 to 2.2 N vs 1.4 N) | (c) risk | Rating is derived from a 16 mm2 contact patch measured on our meshes, not a source number; the bond may be larger than the clearance-based estimate. |
| 1 | T2.sim_rest: tipped, landing axis 79 deg | (a) with (b) | The nose-up footprint is 354 mm in z with the CG 317 mm above the feet: tip-over margin about 29 deg, the same case the source treats as accepted damage. The rigid sim also adds bounce (no foot crush). |

Static tier 2 (121 joint-load rows, hover moment, sim stable) all PASS. Placeholder joints pass the static check by construction (vacuous).
Open numbers I did not invent: ratings for M2 and M5 stress areas are flagged placeholder in `importers/dbf_ratings.py`.
