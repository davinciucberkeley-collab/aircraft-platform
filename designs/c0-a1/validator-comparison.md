# C0-A1 validator comparison

`plane validate designs/c0-a1 --tier all` exits **1**. Tiers: T0 PASS, T1 FAIL, T2 FAIL, T3 FAIL, T4 FAIL, T5 PASS. Run 2026-11-11 against the working tree. C0's own result for reference (`designs/c0-lift-cruise/validator-comparison.md`): T0 PASS, T1 FAIL, T2 FAIL, T3 FAIL, T4 FAIL, T5 PASS, re-run today with identical rows.

Source files are in `dbf-combined` @ `1244ebc`: `A1G` = `concepts/variants/a1/geometry.json`, `A1M` = `.../a1/metrics.json`, `A1D` = `.../a1/design.md`. Their numbers are **v0.3.1** (6.182 kg C0 base, S 0.573 m^2); the platform design is on **v0.4.0** (7.416 kg bottom-up, S 0.774 m^2), so absolute numbers do not compare, only deltas and directions.

## 1. Quantity comparison

| Quantity | C0 (validator) | C0-A1 (validator) | Source A1 value (v0.3.1) and file#key | Comment |
|---|---|---|---|---|
| Mass | 7415.9 g | 8185.1 g (+769.1 g, +10.4 %) | 6910.4 g vs C0 6182.2 g, +728 g (`A1M#mass_kg`) | 41 g more than the source delta: pusher-side parts differ between baselines (README). Direction agrees. |
| CG x | 689.65 mm | 686.46 mm | held at 28 % MAC by the 174.2 mm battery move (`A1M#cg_x_m`, `A1G` modify Battery) | Source shift was solved on the v0.3.1 CG. On v0.4.0 it leaves the CG 3.8 mm forward of the 690.25 mm lift centroid. About 38 mm more shift would fix it. |
| Static margin | 15.3 % | 16.3 % | 17.7 % (range 16.7-18.7), C0 19.6 % (`A1M#static_margin_pct`) | Validator moves with the CG only. The source's -2.0 pt from tip-prop normal force is not modelled (no prop aero in v0.1). |
| Stall speed | 11.73 m/s | 12.3 m/s (**FAIL**, limit 12) | not stated for A1 | Same formula as the source (W, S, CLmax 1.115). V rises with sqrt(W): +4.8 %. |
| Hover T/W | 1.69 | 1.53 (minimum 1.5) | 1.81 vs C0 2.03 (`A1M#hover_TW`) | Same 4 x 3130 gf. The source's own requirement R13 is 1.6 (C0 README), which 1.53 would miss. |
| Hover moment | 0.47 N*m | 0.60 N*m (PASS) | tip mass moves CG 21 mm forward, "about 1.4 N*m bias" unless the battery moves (`A1D` section 2) | Consistent: the battery move was needed. |
| Width over discs | 2.4 m span | not checked by any tier | 2.812 m, 0.188 m under 3 m (`A1M#width_m`) | No width requirement in v0.1. Geometry gives the same: discs span y +-1406 mm. |
| Interference | PASS | PASS (tip props clear of wing LE and pitot) | prop disc to wing LE 77 mm, pitot at y 0.90 vs disc edge 1.05 (`A1G#checks`) | Agrees. |
| Cruise power, endurance, roll inertia, one-motor-out yaw, tip deflection, wing mode 9 Hz | not covered | not covered | 378 W, 10.3 min, x2.07, 11.8 N*m, 2.25 mm, 9.0 Hz (`A1M`, `A1D` sections 2, 3, 5) | No power, drag, inertia-response, yaw or modal model in v0.1. The mass-properties tool does report the inertia (Ixx 2.48e9 vs 1.32e9 g*mm^2, x1.88; mass and tip placement only, not the source's lumped model). |

## 2. Every FAIL, classified

(a) variant issue, (b) validator or standards limitation, (c) placeholder or conversion input. "Inherited" means C0 fails the same check for the same reason.

| Check | Result | Origin | Class | Explanation |
|---|---|---|---|---|
| T1.attachment_overlap `servo-ail_l/r` | embed_ok overlaps 89 % of the servo | inherited from C0 | (a), team to confirm | Unchanged by A1: aileron servo protrusion below the wing (C0 comparison section 2). |
| T2.sim_drop_loads `gear-leg-fl/rl/fr/rr` (93, 126 N vs 50 N) | peak exceeds rating | inherited | (c) | Placeholder 50 N ratings, unchanged parts. |
| T2.sim_drop_loads `wing-clampr-*`, `clampr-boom-*` (147-154 N vs 100 N) | exceeds | inherited, higher | (c) | C0 134-138 N; 10 % more mass raises the peak. Placeholder ratings. |
| T2.sim_drop_loads `pod-battery` 151 N, `pod-avionics` 142 N, `pod-wiring` 45 N, `pod-fasteners` 27 N | exceeds | inherited | (c) | Placeholders. `pod-battery` is lower than C0's 220 N (battery moved aft; cause not investigated). |
| T2.joint_load `pod-wiring` | 26.3 N at 4.5 g vs 20 N | **new** | (c) | The wiring lump grew to 596 g (tip wiring and harness) on the same 20 N tape placeholder. Not a verdict on the wiring. |
| T2.joint_load `wing-tip_r/l` | 50.0 N vs 50 N | **new** | (c) | Placeholder 50 N foam bond. The real load path to the spar is `spar-tip_*` (197 N, passes), so the foam bond is not load carrying; the check counts only mass below a joint (C0 limitation). |
| T3.stall | 12.3 m/s vs 12 m/s | **new**, variant issue | (a) | +769 g at the same 0.774 m^2 wing. At v0.3.1 the source reported no stall figure for A1. On v0.4.0 A1 needs more wing, a higher CLmax, or a weight cut. |
| T3.static_margin | 16.3 % vs 5-15 % | inherited (C0 15.3 %), 1.0 pt worse | (b) | Same pod-effect gap as C0 (AVL with pod is 10.4 %, validator ignores the fuselage). The extra point comes from the CG sitting 3.8 mm forward; the source's tip-prop term would pull it back about 2 pts. |
| T4.method `pod`, `wing`, `fin_l`, `fin_r`, `h_tail` | no machine does hotwire-foam | inherited | (b) | Same as C0. |
| T4.fits_machine (SKIP, printed parts) | build volume unknown | inherited | (b) | 2 new printed mounts join the list. |

C0's `T1.attachment_contact pusher-prop` (5 mm gap) and the `T2` rows for `pusher` parts no longer exist because the pusher is removed. The new tip motor-to-prop gap is 2.0 mm (limit 2.0), which passes; it relies on the schema having no hub, like C0.

## 3. Validator limitations found while building A1

- **Propeller cannot be in an embed joint, protruding tubes trip the embed limit.** The tip tube sticks out 22 mm beyond the wing tip, so as the child of the wing it was 94 % inside (limit 35 % unless >= 99 %). Swapped to tube = parent (C0's README documents the same direction effect).
- **No hollow bodies**, so the nacelle shell has no geometry (mass lumped into the mount).
- **Thrust axis sign (resolved 2026-11-11).** `axis` is the thrust direction in body coordinates, with body x aft, so forward thrust is [-1, 0, 0]. The tip motors use [-1, 0, 0]; an earlier copy of [1, 0, 0] (which points aft) was wrong and is fixed. The role is `cruise`, which no tier reads.
- **No power, drag or yaw checks**, so A1's one-motor-out yaw hazard (half the required balancing thrust, `A1D` section 5) and 21 % higher hover power are invisible to the validator.

## 4. For the conductor

- A1 on v0.4.0 fails stall and sits at 1.53 hover T/W; a decision on whether the A-series should be re-based on v0.4.0 (`DECISIONS.md` D1) changes all of this.
- Decide whether CG should be re-solved per baseline (A1 needs about 38 mm more battery shift) or kept as the documented number.
