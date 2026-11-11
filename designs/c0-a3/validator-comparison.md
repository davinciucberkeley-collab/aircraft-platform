# C0-A3 validator comparison

`plane validate designs/c0-a3 --tier all` exits **1**. Tiers: T0 PASS, T1 FAIL, T2 FAIL, T3 FAIL, T4 FAIL, T5 PASS. Run 2026-11-11 against the working tree. C0 for reference: T0 PASS, T1 FAIL, T2 FAIL, T3 FAIL, T4 FAIL, T5 PASS (`designs/c0-lift-cruise/validator-comparison.md`; re-run today, identical rows).

Source files in `dbf-combined` @ `1244ebc`: `A3G` = `concepts/variants/a3/geometry.json`, `A3M` = `.../a3/metrics.json`, `A3D` = `.../a3/design.md`. Source numbers are **v0.3.1**; the design is on **v0.4.0**.

## 1. Quantity comparison

| Quantity | C0 (validator) | C0-A3 (validator) | Source A3 value (v0.3.1) and file#key | Comment |
|---|---|---|---|---|
| Mass | 7415.9 g | 7665.7 g (+249.8 g) | 6432 g vs 6182 g, +250 g (`A3M#mass_kg`) | Input is the source delta (phase 1 + 2). Conversion check only. |
| CG x | 689.65 mm | 690.25 mm | -0.06683 m, shift -3.4e-5 mm (`A3M#cg_x_m`) | Agrees: equal masses on the front and rear pairs. |
| Static margin | 15.3 % | 15.1 % (FAIL, cap 15 %) | 19.6 %, unchanged (`A3M#static_margin_pct`) | Both nearly the same; the 0.2 pt change is the 0.6 mm CG shift. Nacelle weathercock effect is not modelled by either. |
| Stall speed | 11.73 m/s | 11.9 m/s (PASS) | stall rises 12.0 -> 12.24 m/s from mass (`A3D` section 5) | Same direction (+1.5 % here, +2 % there). |
| Hover T/W | 1.69 | 1.63 | 2.03 -> about 1.95 (4 x 3130 gf over 6.432 kg, calc) | Same formula; baseline mass differs. |
| Hover moment | 0.47 N*m | 0.44 N*m (PASS) | none | |
| Interference | PASS | **FAIL** (8 rows) | front gear clamp "6 mm clear", rear nose "6.6 mm clear" (`A3G` Lift_Nacelle clearances_checked) | Validator sees: nacelle hull overlaps the motor (all four, 46,725 mm^3) and the front gear clamp (50,380 mm^3) and leg (409 mm^3). Rear gear clamp clear, as the source says. See section 2. |
| Cruise power, endurance, hover power, rotor CdA, windmilling brake risk, capture probability | not covered | not covered | 280 W (265-303), 15.0 min (13.9-15.9), 890 W, CdA 0.0011 m^2, windmill 797 W, capture 36-56 % (`A3M`, `A3D` sections 2-3) | No drag, power or rotor-park model in v0.1. The check that decides whether A3 pays (T-A3-8, car-top drag) is physical. |

## 2. Every FAIL, classified

(a) variant issue, (b) validator or standards limitation, (c) placeholder or conversion input. "Inherited" = same as C0.

| Check | Result | Origin | Class | Explanation |
|---|---|---|---|---|
| T1.interference `lift_motor_{fl,fr,rl,rr}` vs `nacelle_*` | 46,725 mm^3 each | **new** | (b) | The real nacelle is a 0.8 mm shell with the motor inside (1.75 mm radial clearance to the lid hole); the schema has only solid boxes. |
| T1.interference `gear_clamp_{fl,fr}` vs `nacelle_*` | 50,380 mm^3 | **new** | (a), needs team confirmation | Not a validator artefact: the source's own envelope contains the front gear clamp (README, "Source inconsistency"). The clamp is 46 mm wide, the nacelle 35-43 mm there. Rear clamps are clear (6.6 mm). |
| T1.interference `leg_{fl,fr}` vs `nacelle_*` | 409 mm^3 each | **new** | (a)/(b) | Leg top (z -47.6) is 0.8 mm into the box bottom (z -48.4). The real nacelle is open at the bottom, so likely harmless; follows from the front gear clamp conflict and the 2.9 mm height shift. |
| T1.attachment_overlap `servo-ail_l/r` | 89 % overlap | inherited | (a), team to confirm | Aileron servo protrusion; A3 does not touch it. |
| T1.attachment_contact `pusher-prop` | 5.0 mm gap | inherited | (b) | No hub in schema. |
| T2.sim_drop_loads (12 joints: `gear-leg-*` 104-135 N vs 50, `wing-clampr-*`/`clampr-boom-*` 134-138 N vs 100, `pod-battery` 220 N, `pod-avionics` 122 N, `pod-wiring` 31 N, `pod-fasteners` 26 N) | exceed placeholder ratings | inherited, same 12 joints | (c) | Placeholders. Gear-leg peaks rise 93 -> 104 N (front) and 126 -> 135 N (rear) with the extra 63 g per rotor. |
| T3.static_margin | 15.1 % vs 5-15 % | inherited (C0 15.3 %) | (b) | Pod effect not modelled (AVL with pod 10.4 %); knife edge at the 15 % cap. |
| T4.method `pod`, `wing`, `fin_l`, `fin_r`, `h_tail` | no machine does hotwire-foam | inherited | (b) | Same as C0. |
| T4.fits_machine (SKIP) | build volume unknown | inherited | (b) | The 4 printed nacelles (179 mm) and caps add to the unverified printed parts (source: print 2 clamshell halves per nacelle). |

New joints (`mount-nacelle_*`, `boom-nacelle_*`, `prop-cap_*`) raise no T2 rows.

## 3. Validator limitations found while building A3

- **No hollow bodies**, so a fairing or nacelle that encloses a motor always reads as clipping.
- **A propeller cannot be an embed joint**, so a cap that covers a prop hub had to be modelled above the disc only.
- **No rotating or parked-position representation**: A3's whole concept is the parked azimuth, and a disc has none. This is not an articulation request (the prop already spins in C0); schema 0.1 was kept.
- **No drag model**, so the thing A3 is for (35.8 % of cruise drag from stopped rotors, 23 % cruise power cut) is invisible.

## 4. For the conductor

- Decide whether the solid-hull interference FAILs are acceptable for a fairing, or whether the schema should get a `hollow`/`shell_thickness_mm` field or an `envelope` flag that is exempt from interference.
- The front gear clamp conflict needs a CAD check by the team (source claim not reproducible).
- A3 is the only A-variant with no mass or CG problem on v0.4.0; its payoff is outside what the validator can see.
