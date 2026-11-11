# C0 validator comparison

`plane validate designs/c0-lift-cruise --tier all` exits **1**. Tiers: T0 PASS, T1 FAIL, T2 FAIL, T3 FAIL, T4 FAIL, T5 PASS. Run 2026-11-11 against the working tree while another agent was editing `core/`; re-run once, results identical.

Source files: `AR` = `analysis/aero/aero_results.json`, `R` = `analysis/results.json`, `MB` = `analysis/mass/mass_budget.json`, `CV` = `cad/verification.txt`, all in `dbf-combined` @ `1244ebc`.

## 1. Quantity comparison

| Quantity | Our validator | Their value (file#key) | Difference | Likely reason |
|---|---|---|---|---|
| Total mass | 7415.9 g | 7415.9 g (`MB#total_kg`); 7438.0 g (`R#concepts.C0.sized.m`) | 0.0 g vs bottom-up; -22 g (-0.30 %) vs sizing | Input is their own group masses, so this only checks the conversion. The -22 g is their own budget delta (`MB#groups`). The CAD-only roll-up is 6.683 kg (`CV`), without wiring, ESCs, skins, avionics. |
| CG x | 689.65 mm = 27.8 % MAC | 690.25 mm = 28.0 % MAC (`R#concepts.C0.cg.xLEtoCG` -0.0903 m, `cg.pct.target`; `AR#geometry.CG_target_pct_MAC`) | -0.60 mm (-0.19 % MAC) | Their CG is the design target (battery position solved for it; battery +-30 mm gives 26.97-29.03 %, `AR#geometry.CG_range_pct_MAC`). Ours is a roll-up of lumps with derived wing-foam CG and lump stations (avionics 15 mm off). |
| Neutral point | 738.9 mm = 43.09 % MAC | 38.404 % with pod (`AR#neutral_point.AVL_pod_pct_MAC`); 43.34 % AVL no pod; 43.69 % repo VLM; 39.90 % AeroSandbox VLM; 38.24 % sizing (`AR#neutral_point.*`) | -0.25 pts vs AVL no pod; +4.7 pts vs AVL with pod | Ours ignores the fuselage ("fuselage effect not modelled" in the message). Their pod shift is -4.93 pts (`AR#neutral_point.pod_shift_pct_MAC`). Ours also uses the CAD H-tail span 917.4 mm (+5.8 % tail area vs 867.4 mm in the sizing). |
| Static margin | **15.3 % MAC, FAIL** (cap 15 %) | 10.40 % AVL with pod at 28 % CG (`AR#neutral_point.static_margin_pct.CG_28pct`); 10.24 % sizing (`AR#neutral_point.static_margin_sizing_pct`) | +4.9 pts | Pod effect not modelled (above). Knife-edge: with the sizing H-tail span 867.4 mm the same validator gives 14.1 % PASS (mutation H below). |
| Stall speed (cl_max 1.115 via `flight.cl_max`) | 11.73 m/s | 11.7501 m/s (`AR#stall.V_stall_mps`; `R#base.Vs` 11.75) | -0.02 m/s (-0.17 %) | Same formula (W, S 0.7736 m^2, CLmax 1.115, rho 1.225); the difference is the -0.30 % mass. Not independent. Requirement 12 m/s met by both. |
| Wing loading | 95.86 g/dm^2 (= 94.0 N/m^2) | 94.289 N/m^2 (`AR#geometry.wing_loading_N_m2`; `R#sized.wingLoading`) | -0.29 % | Mass difference. Wing area 0.7736 m^2, AR 7.446, MAC 322.3 mm match their `S_ref_m2`, `AR`, chord exactly (direct inputs). |
| Hover T/W | 1.688 | 1.683 (`R#sized.TW`); 1.688 on the CAD bottom-up mass (`docs/validation/proofs/AERO-18.md`) | +0.005 (+0.3 %) | Same 4 x 3130 gf. Source requirement R13 is 1.6 (cites T-Motor, 1.6 min / 2.0 recommended; link not opened by us); our threshold is 1.5 with `source: pending`. C0 passes either. |
| Hover moment | 0.47 N*m, PASS (8 % of reference) | Thrust centroid = CG by design (`R#concepts.C0.cg.pct.thrust` 28 = target); no lateral CG stated | n/a | Our CG y is -3.7 mm: the 27.7 g pitot on the port wing only (y = -1.0 m). The source sizing is laterally symmetric. A small real observation. |
| Drop test (0.3 m) | battery joint peak 220 N = 27 g; legs 93-126 N; wing-pod 275 N | `R#concepts.C0.struct.strokes`: n = 1 + h/stroke with h = 0.30 m: 16 g at 20 mm stroke, 7 g at 50 mm | not comparable | Ours is a rigid-contact MuJoCo drop; theirs assumes a stroked gear. Same drop height, order-of-magnitude consistent. |
| Interference / clipping | T1.interference PASS (no overlap > 1 mm^3 between the 51 unattached solids) | `CV`: 263 interferences = 189 insert press fits + 74 model artefacts (244 mm^3), **0 unexplained**; 31 unexplained (393 mm^3) found 2026-11-02, fixed 2026-11-03 (`cad/README.md`) | not comparable | Agree in sign. Ours works on part envelopes without fasteners, so it cannot see the clash classes their CAD found (canopy x pod, clevis x horn, spar tube x foam, clamp x spar collar). It did report 2 other conditions (section 2, T1). |
| Mass limits | 7.416 kg < 24.947 kg (T5 PASS) | hard cap < 25 kg (`CLAUDE.md` of source); R2 8-15 kg target not met by any version (`DECISIONS.md` D3) | consistent | The platform has no working-target check. |
| Not covered by the validator | n/a | CD0 0.0425, L/D 8.71, cruise 296 W / 258 W, hover 1132 W, endurance 12.0 min, tail volumes 0.35 / 0.03, CL_max 1.115 derivation, joiner RF 1.41 | n/a | No power, energy, drag or tail-volume model in v0.1. |

## 2. Every FAIL, classified

(a) real C0 issue, (b) validator or standards limitation, (c) conversion error or unresolved input.

| Check | Result | Class | Explanation |
|---|---|---|---|
| T1.attachment_overlap `servo-ail_l/r` | embed_ok overlaps 89 % of the servo | (a), needs team confirmation | The servo+tray envelope from the CAD meshes spans z -21.9..+12.0 mm at x 750-804 (55-63 % chord). The real lower surface there is at z -13.9 (`cad/params.txt` `yL55`), so the servo body protrudes about 8 mm below the wing; the model's slab hull is thicker (bottom -18.1) and still sees 11 % outside. The CAD interference check does not flag protrusion, only overlap. Caveat: the envelope includes the tray tabs and a horn arm may be in it. Not tuned away. |
| T1.attachment_contact `pusher-prop` | 5.0 mm gap > 2 mm | (c) | The pusher disc plane (x 1037-1045) sits on the M6 adapter 5 mm aft of the motor body face (x 1032). The conversion folded the adapter's mass into the disc and did not model it as a part, so the disc cannot meet the motor face. The schema can model the adapter as its own cylinder component between motor and disc, as `pusher_cup` already does for the motor cup. Lift props touch their motors (no adapter). |
| T2.sim_drop_loads `gear-leg-*` (93, 126 N vs 50 N), `wing-clampr-*` and `clampr-boom-*` (134-138 N vs 100 N), `pod-battery` (220 N vs 50 N), `pod-avionics` (122 N vs 50 N), `pod-wiring` (31 N vs 20 N), `pod-fasteners` (26 N vs 20 N) | peak exceeds rating | (c) | All are placeholder ratings (50 N per M3 screw rule, see README): the source has no joint capacities. The failures say only that the placeholders are low; they are not a verdict on C0. Joints with source-derived ratings pass (wing-pod 275 of 536 N). Useful by-product: the numbers are what the team's real joint ratings must exceed in a 0.3 m rigid drop. |
| T3.static_margin | 15.3 % vs 5-15 % | (b) | Pod destabilisation (-4.9 pts in AVL) is not modelled; with it the margin is about 10.4 %, mid-band. Also sensitive to the H-tail span source (15.3 % with CAD 917.4 mm, 14.1 % with sizing 867.4 mm). |
| T4.method `pod`, `wing`, `fin_l`, `fin_r`, `h_tail` | no machine does hotwire-foam | (b) | `hotwire-foam` is a schema method but `standards/manufacturing.yaml` has no hot-wire machine and it is not in `machine_optional_methods`. The team cuts XPS with its own bow (BOM "Hot-wire cutter", `docs/build/BUILD-MANUAL.md` K13). |
| T4.fits_machine (SKIP, 18 printed parts) | build volume unknown | (b) | `jacobs-fdm` has no `build_volume_mm`. The source notes the saddle plate P13 (322 mm) needs a bed of at least 324 x 200 mm and is not in this model. |

T0 and T5 pass. T1 connectivity, watertight, motor-has-prop (5 motors) and interference pass.

## 3. Does the validator behave? Perturbation tests

Copies of the design in the scratchpad, one change each, core API called as is.

| Change | Result | Verdict |
|---|---|---|
| Rear-left lift prop moved 288 mm forward into the wing | `T1.interference` "prop strike: wing and lift_prop_rl overlap 658751 mm^3", plus joint contact FAIL | caught |
| Battery 150 mm aft | SM 10.1 % (CG x 706), hover moment WARN 2.02 N*m, joint-location FAIL | correct direction |
| `flight.cl_max` 0.9 | stall 13.1 m/s > 12 FAIL | caught |
| One lift motor + prop removed | T/W 1.30 FAIL, hover moment 18.75 N*m FAIL, SM FAIL | caught |
| H-tail span 917.4 -> 867.4 mm | SM 14.1 % PASS (NP x 735) | sensible; shows the knife edge |
| H-tail span halved | SM 4.6 % FAIL, joints 131-181 mm apart FAIL | caught |
| Wing 100 mm forward, CG fixed | SM -8.7 % FAIL, hover moment WARN | caught |
| +2 kg in the pod | mass 9416 > 7438 FAIL, stall 13.2 FAIL, T/W 1.33 FAIL | caught |

Conclusion: the checks respond correctly to every perturbation and agree with the source wherever the formula is shared (mass, wing loading, stall, T/W, wing geometry). Where physics differs (static margin, pod effect) the validator is wrong by a known, stated amount, and the verdict is knife-edge. Its T2 joint-load check is too weak to rely on (below). It can be trusted as a regression and sanity gate, not as an independent stability or structure check.

Validator limitations found while converting:

- **T2.joint_load counts only mass below the joint, and in a loop uses the child alone.** Wing-boom, tail and clamp joints sit in loops (boom held by two clamps), so they were "loaded" with 1-14 N, and motor thrust (30.7 N per lift motor) never loads any joint. The drop test is the only real load.
- **Parent/child direction changes the embed verdict.** A tail clamp as child of the boom overlaps 35.8 % of its own volume (limit 35 %); as parent it passes (boom overlap 3 %). Clamps were therefore parented to the booms they grip. Solid cylinders stand in for tubes (boom in clamp, joiner in socket) so every nesting needs an `embed_ok` workaround.
- **Wing slab is a box**, thicker than the real section at the rear (rear clamp tops sit 11 mm inside it), and wing mass distribution needs a `cg_offset` calculated by hand.
- **MuJoCo prints "only got N/400 samples!"** to stderr during the drop test; results still came out.

## 4. Schema gaps

Everything in C0 the schema could not express cleanly, with a proposed addition (no schema change made).

| # | Gap in C0 | How it was worked around | Proposed addition |
|---|---|---|---|
| 1 | Control surfaces: ailerons (26 % chord, outer 55 % span), elevator and rudders (30 % chord), 2 % hinge gap, servo-to-surface links | Mass folded into wing/tail/fin; no geometry | `lifting_surface.control_surfaces: [{name, kind, span_frac: [a,b], chord_frac, hinge_gap_mm, servo: <component id>}]` |
| 2 | Airfoil: NACA 2415 / 0009 and the coordinates (`cad/params.txt` `foil=`), polars behind CL_max 1.115 | Name string; slab hull | `airfoil: {name, coordinates_file, polar_file}` and a hull option that follows the section |
| 3 | Fuselage profile (ellipse nose, parallel, smoothstep taper to R30); pod effect is -4.9 pts of static margin | R80 x 1000 cylinder | `fuselage` geometry `profile: [{x, radius}]` (body of revolution) plus a pod term in the neutral-point estimate |
| 4 | Twin-boom H-tail; booms as tubes with OD/ID (25.4 x 23.6), joiner in socket, clamps with bores, pod with slots, bays and pockets | `tail: other`; solid cylinders; `embed_ok` and parent/child tricks | `tail: h-tail-twin-boom`; `cylinder.inner_radius`; geometry `cavities: [...]` or boolean subtraction so overlap checks respect bores and pockets |
| 5 | Breakdown for transport (R4: largest piece <= 1.5 x 0.5 x 0.4 m): panels slide off the joiner, booms, tail, legs | none | `attachments[].separable: true` and `requirements.transport_envelope_mm`, tier check on the largest connected group after cutting separable joints |
| 6 | Materials: 6061-T6 yield 275 MPa, E 69 GPa, PETG, PA6-CF20, XPS 32 kg/m^3; tube wall thickness | density and notes only | `materials.<id>.yield_mpa`, `e_gpa`, `source`; tube `wall_mm` |
| 7 | Structural results that are not joints: joiner RF 1.41 at 4.5 g (Schrenk root moment 91.0 N*m), boom RF 7.44 (14.99 N*m) | Converted to equivalent loads in `rated_load_n` | `members: [{component, check: bending_moment_nm, applied, allowable, load_case, source}]` and tier-2 beam check |
| 8 | Link to their claims and proofs (79 claims in `analysis/validation/validation_matrix.json`, proofs under `docs/validation/proofs/`) and per-number sources | YAML comments only, invisible to tools | `source` string and `evidence: [{claim_id, file, key, status}]` on components, attachments, requirements, flight; `bom_ref` into the BOM |
| 9 | Joint ratings are moments and directional (N*m), set by fastener patterns | One scalar `rated_load_n`, mostly placeholders | `rated_moment_nm`, per-axis loads, `load_case`, `fastener_count` |
| 10 | Thrust: lift motor table (1250 g / 135 W ... 3130 g / 615 W), pusher max thrust unknown | `max_thrust_n` is required, so cruise drag was entered for the pusher (flagged) | `propulsion.thrust_basis: static / cruise / estimate`, optional `thrust_curve`, `power_w`, `current_a` |
| 11 | Energy: 6S 6500 mAh 144.3 Wh, hover 1132 W, 12.0 min cruise; endurance requirement | `endurance_min` unchecked | `battery: {capacity_wh, cells, max_discharge_a}` and a power / endurance tier |
| 12 | Propeller hub and stand-off (pusher disc 5 mm off the motor) | adapter lumped into the disc (conversion choice, not a schema limit); contact FAIL | Model the adapter as its own cylinder component, as `pusher_cup` does. Optional convenience: `propeller: {hub_offset_mm}`, measured from the hub |
| 13 | Landing gear stroke, compliance, fairings, dome feet | rigid legs, mass lumped | `landing_gear: {stroke_mm, stiffness_n_per_mm}` feeding the drop test |
| 14 | Mass-only items (wiring 370 g, 139 screws + 67 inserts 221 g, avionics lump 378 g) | placeholder boxes with invented sizes | `mass_only: true` component with a point position and no geometry |
| 15 | Movable CG (battery +-30 mm) and a CG target (28 % MAC) | single CG | `movable: {component, range_mm}` and `requirements.cg_range_pct_mac` checked at both ends |
| 16 | Meshes: STLs in metres, part-local frames, per-instance rotation | not used | `mesh: {file, units, scale, transform}` |
| 17 | Repeated units (4 lift units, 2 booms, mirrored tail parts) | 51 hand-written components | `pattern` / `mirror_of` so one definition yields all instances |
| 18 | Requirement targets that are ranges or sourced (R13 T/W >= 1.6, R11 stall, R21 25 C ambient) | scalars only | `requirements.<key>: {value, source}` |

## 5. For the conductor

- Add a hot-wire bow to `standards/manufacturing.yaml` (the team owns one) or accept 5 T4 fails for any foam design.
- Decide whether the static-margin check should model the fuselage; as is it fails a design the source AVL puts at 10.4 %.
- T2 needs thrust loads and loop handling before its joint results mean much; real ratings from the team would replace the placeholders.
- The platform's pending hover T/W minimum (1.5) can cite the source's R13 pointer (T-Motor 1.6 min / 2.0 recommended); I did not open that URL.
- Confirm with the team that the aileron servo envelope really protrudes below the lower surface.
