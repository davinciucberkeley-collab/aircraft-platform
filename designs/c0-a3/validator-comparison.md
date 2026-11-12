# C0-A3 validator comparison

`plane validate designs/c0-a3 --tier all` exits **1**. Tiers: T0 PASS, T1 FAIL (3 rows, all inherited), T2 FAIL, T3 FAIL, T4 PASS, T5 PASS. Run 2026-11-11 after the schema 0.3 cavity change (working tree). C0 for reference: T0 PASS, T1 FAIL, T2 FAIL, T3 FAIL, T4 FAIL, T5 PASS as recorded in `designs/c0-lift-cruise/validator-comparison.md` (not re-run here).

T4 moved from FAIL to PASS because `standards/manufacturing.yaml` changed (conductor edit, 17:21 today; not part of this build). Hot-wire parts now pass, and jacobs-fdm has a build volume, so the printed nacelles and caps fit.

Source files in `dbf-combined` @ `1244ebc`: `A3G` = `concepts/variants/a3/geometry.json`, `A3M` = `.../a3/metrics.json`, `A3D` = `.../a3/design.md`. Source numbers are **v0.3.1**; the design is on **v0.4.0**.

## 1. Quantity comparison

| Quantity | C0 (validator) | C0-A3 (validator) | Source A3 value (v0.3.1) and file#key | Comment |
|---|---|---|---|---|
| Mass | 7415.9 g | 7665.7 g (+249.8 g) | 6432 g vs 6182 g, +250 g (`A3M#mass_kg`) | Input is the source delta (phase 1 + 2). Conversion check only. |
| CG x | 689.65 mm | 689.99 mm (was 690.25 mm before the motor-bay cavities) | -0.06683 m, shift -3.4e-5 mm (`A3M#cg_x_m`) | Source shift is about zero. The 0.26 mm forward move comes from the hollowed nacelle centroid, not from mass. |
| Static margin | 15.3 % | 15.2 % (FAIL, cap 15 %) | 19.6 %, unchanged (`A3M#static_margin_pct`) | Both nearly the same. The forward CG move adds 0.1 pt. Nacelle weathercock effect is not modelled by either. |
| Stall speed | 11.73 m/s | 11.9 m/s (PASS) | stall rises 12.0 -> 12.24 m/s from mass (`A3D` section 5) | Same direction (+1.5 % here, +2 % there). |
| Hover T/W | 1.69 | 1.63 | 2.03 -> about 1.95 (4 x 3130 gf over 6.432 kg, calc) | Same formula; baseline mass differs. |
| Hover moment | 0.47 N*m | 0.45 N*m (PASS) | none | |
| Interference | PASS | **PASS** (0 rows) | front gear clamp "6 mm clear", rear nose "6.6 mm clear" (`A3G` Lift_Nacelle clearances_checked) | Schema 0.3 motor-bay cavities clear all four motors. The front nacelles were cut 6 mm short of the front gear clamp, which is a design change (section 2). |
| Cruise power, endurance, hover power, rotor CdA, windmilling brake risk, capture probability | not covered | not covered | 280 W (265-303), 15.0 min (13.9-15.9), 890 W, CdA 0.0011 m^2, windmill 797 W, capture 36-56 % (`A3M`, `A3D` sections 2-3) | No drag, power or rotor-park model in v0.1. The check that decides whether A3 pays (T-A3-8, car-top drag) is physical. |

## 2. Every FAIL, classified

(a) variant issue, (b) validator or standards limitation, (c) placeholder or conversion input. "Inherited" = same as C0.

Rows from the pre-cavity run that are now resolved are kept for the record.

| Check | Result | Origin | Class | Explanation |
|---|---|---|---|---|
| T1.interference `lift_motor_{fl,fr,rl,rr}` vs `nacelle_*` | was 46,725 mm^3 each | new, **resolved** | (b), fixed by schema 0.3 | Each nacelle has a motor-bay cavity (radius 25.75 around the 24 mm bell, open top). The motor no longer overlaps the nacelle. |
| T1.interference `gear_clamp_{fl,fr}` vs `nacelle_*` | was 50,380 mm^3 | new, **resolved by design change** | (a) | The front nacelles are cut 6 mm short of the clamp (tail x 259.273 vs clamp x 265.273). This is a design change, not a source fact. The source's own envelope still contradicts the 6 mm claim (README, "Source inconsistency"). Not checked in CAD. |
| T1.interference `leg_{fl,fr}` vs `nacelle_*` | was 409 mm^3 each | new, **resolved** | (a) | The leg (x 269.6..294.9) is clear of the shortened nacelle (tail x 259.3). |
| T1.attachment_overlap `servo-ail_l/r` | 89 % overlap | inherited | (a), team to confirm | Aileron servo protrusion; A3 does not touch it. |
| T1.attachment_contact `pusher-prop` | 5.0 mm gap | inherited | (b) | No hub in schema. |
| T2.sim_drop_loads (12 joints: `gear-leg-*` 102-135 N vs 50, `wing-clampr-*`/`clampr-boom-*` 134-138 N vs 100, `pod-battery` 220 N, `pod-avionics` 122 N, `pod-wiring` 31 N, `pod-fasteners` 26 N) | exceed placeholder ratings | inherited, same 12 joints | (c) | Placeholders. Gear-leg peaks rise 93 -> 102.5 N (front) and 126 -> 135 N (rear) with the extra 63 g per rotor. |
| T3.static_margin | 15.2 % vs 5-15 % | inherited (C0 15.3 %) | (b) | Pod effect not modelled (AVL with pod 10.4 %); knife edge at the 15 % cap. |
| T4 | no FAIL | was inherited (`pod`, `wing`, `fin_*`, `h_tail` hot-wire; nacelles unverified) | (b), now passing | Passes because of the `standards/manufacturing.yaml` change in section header, not this build. |

New joints (`mount-nacelle_*`, `boom-nacelle_*`, `prop-cap_*`) raise no T2 rows.

## 3. Validator limitations found while building A3

- **Hollow bodies: resolved in schema 0.3.** `cavities` subtract box or cylinder shapes from a part before its transform. A cavity may open the surface. Still not modelled: the tapered NACA section (the nacelle is a box).
- **A propeller cannot be an embed joint**, so a cap that covers a prop hub had to be modelled above the disc only.
- **No rotating or parked-position representation**: A3's whole concept is the parked azimuth, and a disc has none. This is not an articulation request (the prop already spins in C0); schema 0.1 was kept.
- **No drag model**, so the thing A3 is for (35.8 % of cruise drag from stopped rotors, 23 % cruise power cut) is invisible.

## 4. For the conductor

- The solid-hull interference FAILs are resolved by cavities. The nacelle is still a solid box outside the cavity, so its centroid (and the 0.26 mm CG move) reflects the box, not the 0.8 mm shell. Decide whether that is acceptable or whether a shell-thickness field is needed.
- The front gear clamp conflict is resolved in the design by the 6 mm cut. The team still needs a CAD check of the source's claim (the source's own envelope is not reproducible).
- A3 is the only A-variant with no mass or CG problem on v0.4.0; its payoff is outside what the validator can see.
