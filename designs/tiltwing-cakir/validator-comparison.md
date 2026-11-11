# TiltWing validator comparison

`plane validate designs/tiltwing-cakir --tier all` exits **1**. Tiers: T0 PASS, T1 FAIL (8 findings), T2 FAIL (10 FAIL rows plus 1 WARN), T3 FAIL (1), T4 FAIL (3 FAIL, 6 SKIP), T5 PASS. Run 2026-11-11 against the working tree; the run takes about 3 s.

Source files (TiltWing @ `1488f8f`): `M` = `model.js` (formula ids G/M/P/A/S), `V` = `data/verify.json`, `AE` = `data/aero.json`, `CAD` = `tools/cad_export.py`, `STL` = `cad/cruise_tilt0` and `cad/hover_tilt90`, `R` = the design report linked from the source README (BOM and build sequence).

## 1. Quantity comparison

| Quantity | Our validator | Their value (file, key) | Difference | Likely reason |
|---|---|---|---|---|
| Total mass | 9152.686 g | 9152.686 g (`M` M1; `V` "M1 takeoff mass"); paper 9500 g (`M` `PAPER.out.mass`) | 0.000 g | Not independent: input is their own buckets (mFus, mWing, mTail, mMisc, elec, payload, mBatt, mMotors). It only checks the conversion. Spars and props are 1 g placeholders carved out of those buckets. |
| CG x | 789.45 mm (30.0 % MAC from `xLEmac`) | 789.457 mm (`M` `size()` `xcg` = `xLEmac` + 30 % MAC, input slider `hcg`) | 0.01 mm | **By construction**: the source places no component in the fuselage, so the battery x (454.635) was solved to hit their CG. Not a test. At the hover pose our CG moves to x 787.11, z 15.7 mm (z 21.6 at cruise); the source has no hover CG. |
| Neutral point | x 844.2 mm | x 822.9 mm = `xLEmac` 702.23 + `hn` 0.41514 x `MAC` 290.757 (`M` A7 `stability()`: `hn = hcg/100 + SM`) | +21.3 mm (+7.3 pts MAC) | Ours is lift-slope-weighted AC of wing and tail with downwash on the tail and no fuselage; theirs is a finite-difference of their 2-D aero including the fuselage Munk moment (A5) and cross-flow. |
| Static margin | **18.8 % MAC, FAIL** (cap 15 %) | 11.51 % (`M` A7 `stability()` SM 0.11514; `V` "Static margin positive in cruise" 0.11514) | +7.3 pts | Fuselage destabilisation not modelled by the validator (message says so). Their model passes the 5-15 % band; ours fails by 3.8 pts. Our value is also affected by the tail-span source (ARh 4.1 span 689 mm). `AE` AeroBuildup tilt-0 sweep (no props): we computed dCm/dCL = -0.42 (alpha 0..4 fit), i.e. SM about 42 %, which agrees with neither; I do not trust that fit (CL 1.16 at alpha 0 suggests a large camber offset), so it is listed, not used. |
| Stall speed (`flight.cl_max` 2.0142) | 11.24 m/s | 11.243 m/s (`M` P4 `Vs`) | -0.003 m/s | Same formula and same S (0.57554 m2), CLmax, rho. Not independent. The CLmax itself (0.9 x 2.238 from NeuralFoil S1223 at Re 3.98e5) is their input. No stall requirement exists in the source or paper, so T3.stall carries no limit. |
| Wing loading | 159.0 g/dm^2 (155.9 N/m^2) | W/S = 89.757 N / 0.57554 m2 = 155.9 N/m^2 (`M` `size()` `W`, `S`) | 0.0 % | Same inputs. |
| Wing area / MAC / AR | S 0.57554 m2 (slab), MAC 290.76 mm | `V` G1 0.57554, G3 0.29076 | 0 | Direct inputs: a full-span trapezoid slab reproduces the source planform exactly, which is why one mirrored slab was kept (two root-offset halves would halve the wing area the validator sees). |
| Hover T/W | 1.581 (at pose hover: only the up-pointing thrust counts) | 1.581 = `tMax` 141.94 N / W 89.757 N (`M` `tMax()`; installed T/W slider 1.5 on the wing rotors plus the tail reserve) | 0.000 | Same 4 x 32.408 + 2 x 6.156 N. Not independent. The platform minimum is 1.5 (`source: pending`). |
| Hover moment | **WARN**: 6.67 N*m at pose hover, 94 % of a 5 cm reference lever | Zero by design: hover trim `P1` T_rear = W (xcg - xw)/(xt - xw) = 3.337 N total, T_front 86.42 N (`M` P1) | n/a | The validator applies every motor's `max_thrust_n` (32.4 N front, 6.16 N rear), not the trim split. Re-run in scratch with their trim thrusts (21.605 N per wing rotor, 1.668 N per tail rotor, `size()` `Tf1`, `Tr1`): 0.21 N*m, 5 %, PASS. So the geometry agrees with their trim; the check design assumes equal thrust. |
| Tilt geometry | Wing and tail rotated +90 deg about +y through (756,0,84) and (1656,0,24) | `STL` hover_tilt90 parts | 0.000 mm bounding-box difference for 5 parts tested | Direct check of the articulation convention (README). |
| Clipping at 0 deg | `T1.interference`: fuselage and wing 581,376 mm^3; fuselage and tail 573,436 mm^3 | CAD wing halves start at y = +-110 and tail halves at y = +-50 (`CAD` `y_in`), designed not to touch the fuselage; no interference report in the source | not comparable | Modelling artefact, see section 2 and the variant below. |
| Clipping at hover pose (90 deg) | fuselage and wing 1,576,518 mm^3; fuselage and tail 479,781 mm^3 | the source's hover STLs show the wing vertical through the fuselage station only for y < 110 (the CAD cut-out) | not comparable | Same artefact; at 90 deg the root strip passes through the whole fuselage section. |
| Other | T1 range max (95 deg) of the wing: fuselage and wing 1,582,541 mm^3 and tail 573,436; of the tail: wing 581,376 and tail 481,163 mm^3 | n/a | | Same artefact in the extra configurations the spec requires (each joint swept alone). |
| Power, energy, endurance | not covered | hover 1501.6 W electrical (`M` S2), cruise 323.2 W (P6), cruise-only endurance 40.77 min (P7, `V`), L/D 9.33, C_D 0.0682, Euse 219.7 Wh | n/a | No power or drag model in the validator. Paper goal 60 min is in `requirements.endurance_min` and unchecked. |
| Structure | not covered | F-section beam FE: hover spar root moment 32.0 N*m (`V` "F1 hover spar root moment") | n/a | T2 has no member bending check (same gap as C0). |

### Clipping with the CAD geometry (scratch variant, not in the repo)

A copy of the design in the scratchpad replaced each mirrored slab by two non-mirrored halves starting at the CAD offsets (wing y = +-110, tail y = +-50), pivots moved to y = +-115 / +-55 so they lie in both parts, the fuselage split into a R100 front and a R52 tail cylinder, and the payload and one gear lump kept inside the front cylinder. Tier 1 then reports **no clipping of the wing at 0, 90 or 95 deg**, and only 551-553 mm^3 between the tail halves and the R52 tail cylinder at the hover pose (0.06 % of the tail; the real radius there is 45 mm, less than the R52 cylinder). So the CAD geometry does not clip at either pose, and the large FAILs below come from the schema, not from the TiltWing layout.

## 2. Every FAIL, SKIP and WARN, classified

(a) real TiltWing issue, (b) validator, schema or standards limitation, (c) conversion error or unresolved input.

| Check | Result | Class | Explanation |
|---|---|---|---|
| T1.interference (0 deg): `fuselage`/`wing` 581,376 mm^3, `fuselage`/`tail` 573,436 mm^3 | clipping | (b) | The schema's lifting surface has no root offset, so the slab fills y = 0..110 (wing) and 0..50 (tail) where the CAD has a cut-out. A wing slab at z 104 +- 25 mm passes through the top of the R100 cylinder; the tail slab through the tail section. Not a TiltWing finding (variant above). |
| T1.interference (pose hover 90 deg): wing 1,576,518 and tail 479,781 mm^3 | clipping | (b) | Same root-strip artefact, larger because a vertical wing slab cuts the full fuselage cross-section. The pose label proves the per-pose machinery works: the 0 deg message and the hover message differ. |
| T1.interference (range max of wing-tilt, 95 deg): wing 1,582,541, tail 573,436 | clipping | (b) | Same. These configurations (wing tilted, tail not) are not flown; the spec sweeps each joint alone. |
| T1.interference (range max of tail-tilt, 95 deg): wing 581,376, tail 481,163 | clipping | (b) | Same. |
| T2.joint_load `wing-shaft-fuselage` (314.5 N vs 200 N) | exceeds rating | (c) | Placeholder rating (the source has no joint capacities). Load is the mass on the child (fuselage) side of the shaft at 4.5 g. |
| T2.joint_load `tail-shaft-fuselage` (371.9 N vs 50 N) | exceeds rating | (c) / (b) | Placeholder rating; also an artefact of the declared direction (tail_spar parent, fuselage child, chosen so the shaft embeds in the fuselage), which makes the "load beyond the joint" nearly the whole aircraft. The real tail shaft carries only the tail. |
| T2.joint_load `payload-bay` (110.3 N vs 100 N) | exceeds rating | (c) | Placeholder rating. |
| T2.sim_drop_loads `wing-motor-1..4` (91.0, 53.5, 53.7, 90.7 N vs 50 N) | exceeds rating | (c) | Placeholder rating of 50 N. The outer nacelles carry the most (91 N) in the rigid-body drop; I did not inspect the contact order. Numbers are what a real nacelle joint must exceed. |
| T2.sim_drop_loads `battery-bay` 365.9 N, `electronics-bay` 203.6 N, `payload-bay` 499.7 N vs 100 N | exceeds rating | (c) | Placeholder ratings; heavy lumps in a rigid-contact drop. Same class as the C0 battery joint. |
| T2.hover_moment | WARN, 6.67 N*m (94 %) | (b) | Validator applies max thrust per motor, not the trim split; 0.21 N*m with their trim thrusts (section 1). |
| T3.static_margin | 18.8 % vs 5-15 % | (b) | Fuselage effect not modelled: their own model gives 11.5 % mid-band (section 1). |
| T4.method `wing`, `tail` | no machine does hotwire-foam | (b) | `hotwire-foam` is a schema method but `standards/manufacturing.yaml` has no hot-wire machine and it is not in `machine_optional_methods` (same finding as C0). The build sequence cuts S1223 and NACA 0009 cores with a hot wire. |
| T4.method `fuselage` | no machine does composite-layup | (b) | Same: the 1 mm glass/epoxy shell has no machine entry. No machine was invented. |
| T4.fits_machine `*_motor_*` (6 SKIP) | fit not verified | (b) | `jacobs-fdm-fortus` lists no `build_volume_mm`. The nacelles are 297 mm (wing) and 169 mm (tail) long. |

T0 and T5 pass. T1 watertight, connectivity (22 of 22), motor-has-prop (6 motors), `T1.articulation` (both joints: poses in range, pivots on both parts) all pass, and T3 mass, stall, lateral CG and hover T/W pass.

## 3. Does the new articulation machinery behave? Perturbations

Scratchpad copies, one change each, core API as is (T1 only unless stated).

| Change | Result | Verdict |
|---|---|---|
| Joint pose out of range (hover 120 deg, range 0..95) | `T1.articulation` FAIL "pose hover (120 deg) is outside range" | caught (also in tests) |
| CAD-offset wing and tail halves (variant above) | wing clear at 0/90/95 deg; only 551 mm^3 tail clip at hover | correct and matches the CAD intent |
| Hover thrust trim instead of max thrust (T2) | hover moment 0.21 N*m PASS | consistent with `P1` |

Conclusion: the pose labels, range endpoints and per-pose contact check work on a real design with two joints and 12 downstream parts, and T3 / T2 follow `hover_pose` / `cruise_pose`. The TiltWing result is dominated by one schema gap (root offset).

## 4. Schema gaps

| # | Gap in TiltWing | How it was worked around | Proposed addition |
|---|---|---|---|
| 1 | Lifting-surface root offset: CAD halves start at y_in (110 mm wing, 50 mm tail) so the surface clears the fuselage and can tilt; a joint pivot on the fuselage centreline then lies outside both halves | One full-span slab from y = 0 (keeps S, MAC, AR exact), so T1 FAILs in every pose | `lifting_surface.root_offset_mm` (planform area still counted from the full trapezoid, or a `reference_area_mm2`); `articulation.pivot` allowed on the axis away from the parts (pivot check = axis within tolerance of both) |
| 2 | Fuselage body of revolution (ellipse nose, parallel section, taper to 28 % radius) | R100 x 1800 cylinder | `fuselage` geometry `profile: [{x, radius}]` and a body term in the neutral-point estimate (same as C0 gap 3) |
| 3 | Airfoil camber (S1223 is 12.1 % thick with +13.5 % camber; the section sits above the chord line) | Slab of camber-envelope height 0.1511 centred at the envelope middle | `airfoil: {name, coordinates_file}` and a hull that follows the section |
| 4 | Tilt actuation is shared: wing and tail tilt together by one command (`tailTilt = d`); stop at 95 deg; poses are per joint | two independent joints, each with poses `cruise`/`hover`; range endpoint sweeps also check unflown wing-only and tail-only configurations | `articulation.group` (joints that move together) so tier 1 sweeps the group once; `actuator` with torque for a tilt-drive check (report: 15 N*m static load) |
| 5 | Thrust at trim vs maximum: hover trim splits 86.4 N front / 3.3 N rear (`P1`), installed maximum differs per rotor | `max_thrust_n` from `TfMax`, `TrMax`; hover-moment check uses the maxima and WARNs | `propulsion.trim_thrust_n` (or a trim solve) so the hover moment uses the balanced thrust |
| 6 | Unplaced mass (battery, electronics, payload, gear, fasteners) and an equal split of the propulsion kit | placeholder boxes; CG solved by moving the battery | `mass_only` component with a point position (C0 gap 14), `movable` battery with a CG target (C0 gap 15), `propulsion.kit_mass_g` split |
| 7 | Tilt-dependent aero: slipstream, tilt 0-90 sweeps (A1-A7), transition corridor, tilt schedule | tier 3 uses one pose | `flight.poses: {name: {tilt, V, ...}}` and per-pose stall / margin; a transition check |
| 8 | Power, energy, endurance (hover 1.5 kW, cruise 323 W, 40.8 min) | unchecked | `battery: {capacity_wh}` and a power tier (C0 gap 11) |
| 9 | Landing in the hover pose with no gear geometry (the CAD has none; BOM names gear points at 0.30 L and 0.82 L) | tier-2 drop test runs in the 0 deg configuration; gear lumps inside the fuselage | `flight.landing_pose` for the drop test and a `landing_gear` geometry |
| 10 | Propeller identity: 14 in model vs 15 in BOM, hub and spinner offset | swept disc at the model diameter, motor cylinder reaching the disc | `propeller: {diameter_mm, pitch_in, hub_offset_mm}` (C0 gap 12) |
| 11 | Structural results (spar root moment 32.0 N*m, bearing plate FE, margins) and moments as joint ratings | placeholder `rated_load_n` | `rated_moment_nm`, `members` beam check (C0 gaps 7, 9) |
| 12 | Manufacturing: hot-wire foam, composite layup (shell over foam plug), PA6-CF printing | method used anyway, T4 FAILs | machine entries for a hot-wire bow and a layup bench (conductor), build volume for `jacobs-fdm-fortus` |
| 13 | Source evidence fields (verify.json rows, per-number provenance) | YAML comments only | `source` / `evidence` on components and requirements (C0 gap 8) |
| 14 | Meshes: the source STLs are already in our frame and mm, but `Fuselage.stl` is not watertight and a mesh component gives tier 3 no lifting-surface data | primitives only | `mesh` with `lifting_surface` metadata for T3, units and transform (C0 gap 16) |

## 5. For the conductor

- Decide on the lifting-surface root offset (gap 1). It turns this design's T1 from 8 findings to about 2 small ones and is the first thing a tilt-wing needs.
- Add a hot-wire bow and a layup method or machine to `standards/manufacturing.yaml` (or `machine_optional_methods`); add `build_volume_mm` to `jacobs-fdm-fortus`.
- Decide whether T3 should model the fuselage; here it changes SM from 11.5 % (source) to 18.8 % (ours) and fails a design the source puts mid-band.
- The hover-moment check needs trim thrust to be meaningful for any design with unequal motors.
- Confirm the payload, electronics and battery layout and joint ratings with whoever owns TiltWing; the CG here is solved, not designed.
- Articulation semantics worth confirming: range endpoints are swept per joint, so a coupled tilt wing gets two unflown extra configurations (gap 4).

## Update 2026-11-11 (sweep checks)

Tier 1 now also sweeps each articulated joint in 15° steps (`design-standards.yaml#articulation_sweep_step_deg`). TiltWing gains `sweep wing-tilt 15°…60°` interference rows. They are the same root-strip clipping as the pose rows above, class (b) validator/schema limitation: the schema has no lifting-surface root offset, so the wing slab starts inside the fuselage at every angle. The scratch variant with the CAD root offsets was clear at 0°, 90° and 95°; re-check it across the sweep once the schema gains `root_offset`.
