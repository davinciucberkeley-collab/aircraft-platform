# C0-A2 validator comparison

`plane validate designs/c0-a2 --tier all` exits **1**. Tiers: T0 PASS, T1 FAIL, T2 FAIL, **T3 PASS**, T4 FAIL, T5 PASS. Run 2026-11-11 against the working tree. C0 for reference: T0 PASS, T1 FAIL, T2 FAIL, T3 FAIL, T4 FAIL, T5 PASS (`designs/c0-lift-cruise/validator-comparison.md`; re-run today, identical rows).

Source files in `dbf-combined` @ `1244ebc`: `A2G` = `concepts/variants/a2/geometry.json`, `A2M` = `.../a2/metrics.json` (rev 2), `A2D` = `.../a2/design.md` (text partly rev 1). Source numbers are **v0.3.1**; the design is on **v0.4.0**.

## 1. Quantity comparison

| Quantity | C0 (validator) | C0-A2 (validator) | Source A2 value (v0.3.1) and file#key | Comment |
|---|---|---|---|---|
| Mass | 7415.9 g | 7474.9 g (+59.0 g) | 6241 g vs 6182 g, +59 g (`A2M#mass_kg`) | Input is the source delta, so this only checks the conversion. |
| CG x | 689.65 mm | 695.78 mm (+6.1 mm) | held at -0.0668 m (28 % MAC) by sliding the pod 16.7 mm forward; 30.8 % MAC before the fix (`A2M#cg_x_m`) | Fix not applied (README). Direction and size agree with the source's unfixed CG (+2.8 % MAC vs +1.9 % here). |
| Static margin | 15.3 % (FAIL) | 13.4 % (PASS) | 19.1 % (18.8-19.3) vs C0 19.6 % (`A2M#static_margin_pct`) | **Artifact.** Validator SM moves with CG only; the aft CG buys 1.9 pts. With the source's slide (CG back to 689.65) the validator would give C0's 15.3 % again. The source's own effect of A2 is -0.5 pt (tail volume and prop normal force). |
| Stall speed | 11.73 m/s | 11.8 m/s | not stated | Mass only (+0.8 %). |
| Hover T/W | 1.69 | 1.67 | 1.99 vs C0 2.03 (`A2D` performance table) | Same direction and size (-1.2 % vs -2 %; v0.3.1 mass base differs). |
| Hover moment | 0.47 N*m | 0.82 N*m (PASS, 13 %) | CG fixed to the thrust centroid by the slide | Shows what the un-applied fix would remove. |
| Interference | PASS | PASS | prop tip to H-tail LE 0.249 m; pusher disc to lift disc 0.04 m (`A2G#checks`) | Agrees: the pusher disc (y +-178) clears the rear lift disc (y from 218) by 40 mm, and the elevator servo and H-tail are well aft of the disc plane x 1141. |
| Cruise power, endurance, BLI saving, boundary-layer and separation analysis, tail-strike angle | not covered | not covered | 366 W vs 365 W, 11.82 vs 11.94 min, +0.07 pt BLI, theta 7.2 mm, tail strike 18.6 vs 56.7 deg (`A2M`, `A2D`) | No drag, power, boundary-layer or ground-geometry model in v0.1. |

## 2. Every FAIL, classified

No FAIL is new. (a) variant issue, (b) validator or standards limitation, (c) placeholder or conversion input.

| Check | Result | Origin | Class | Explanation |
|---|---|---|---|---|
| T1.attachment_overlap `servo-ail_l/r` | 89 % overlap | inherited | (a), team to confirm | Aileron servo envelope protrudes below the wing; A2 does not touch it. |
| T1.attachment_contact `pusher-prop` | 5.0 mm gap > 2 mm | inherited | (b) | Disc sits on the M6 adapter 5 mm aft of the motor; no hub in the schema. Moves with the parts, gap unchanged. |
| T2.sim_drop_loads (12 joints: `gear-leg-*` 93-126 N, `wing-clampr-*`/`clampr-boom-*` 146-151 N, `pod-battery` 217 N, `pod-avionics` 119 N, `pod-wiring` 33 N, `pod-fasteners` 25 N) | exceed placeholder ratings | inherited, same 12 joints as C0 | (c) | Placeholders (50 N per M3). Peaks are within 10 % of C0's. |
| T4.method `pod`, `wing`, `fin_l`, `fin_r`, `h_tail` | no machine does hotwire-foam | inherited | (b) | Same as C0. The A2 cone would be 3D printed, but the validator sees one pod cylinder with the C0 `hotwire-foam` method. |
| T4.fits_machine (SKIP) | build volume unknown | inherited | (b) | Same as C0. The 3-segment printed cone would add checks if modelled separately. |

T3.static_margin **passes** at 13.4 %; see the artifact note above.

## 3. Validator limitations found while building A2

- **Separable joints and a swappable module** (the spigot joint and the cone's slide-off breakdown) cannot be expressed in schema 0.1 (C0 comparison gap 5), and the module cannot be a component without overlapping the pod cylinder.
- **Static margin ignores fuselage and propeller aerodynamics**, so an aft CG shift reads as a stability gain.
- **No moving part is needed for A2.** The slide motion is breakdown only, so schema 0.1 was kept.

## 4. For the conductor

- Decide whether to apply a CG correction (pod slide about 22 mm on v0.4.0, or battery shift) so the T3 result is comparable with C0.
- Whether the A-series should be re-based on v0.4.0 (`DECISIONS.md` D1).
