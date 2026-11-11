# C0 lift+cruise quadplane (UC Berkeley DBF capstone, v0.4.0)

The team's real aircraft, converted into schema v0.1 so the platform validator can be checked against a design that has independent numbers (their sizing, AVL, CAD and structural results).

- **Source:** `/home/claude/davinciucberkeley-collab/dbf-combined` at commit `1244ebc`, read-only. Root v0.4.0 baseline, resized 2026-11-02, CAD rev G.
- **What it is:** 4 lift rotors (SunnySky X4110S 400KV, 17 in props, stopped in cruise) on two 6061 booms, a pusher (same motor, APC 14x8.5EP), a 2.4 m NACA 2415 XPS-foam wing, an H-tail with two fins on the booms. MTOW 7.438 kg by the sizing, 7.416 kg bottom-up. 5 motors in total (4 lift + 1 pusher), as the source README says. Nothing has been built or flown.
- **What it is for:** the question "can we trust `plane validate`?". The answer, with numbers, is in `validator-comparison.md`, including the schema gaps. The YAML was not tuned to pass; real disagreements are the finding.
- **Rule of the source repo kept:** every number cites its origin (YAML comments name the file and key); unknowns are left out or marked `placeholder — not from source`.

51 components, 54 attachments, mass 7415.94 g (source bottom-up 7415.93 g).

## Frame transform

The source CAD (SOLIDWORKS, metres) is built from `cad/params.txt`; `cad/hardware.json` `meta.frame` states "X forward, Y up, Z right". I checked this against the placements (`comp=` lines in `cad/params.txt`):

| Evidence | What it shows |
|---|---|
| `comp=Fuselage_Pod` at X +0.600, pod mesh x spans -1.0..0 m, `fusL` 1.000 | the nose is at X +0.600 and the tail at X -0.400, so X is forward |
| `comp=Pusher_Motor` X -0.400, tail clamps X -0.888, `xStub0` -1.074 | everything aft has negative X |
| wing section `foil=` runs x -0.322..0, `sparX` -0.0967 = 30 % chord | the wing leading edge is at X 0 |
| `comp=Landing_Leg` Y -0.2526, `yGround` -0.2526, lift props at Y +0.020 | Y is up; CAD Y 0 is the wing chord line, not the pod axis (pod axis Y -0.030) |
| `Wing_Panel_R` Z +0.08, `Aileron_R` Z +0.586, pitot at Z -1.000 on the left wing (`docs/build/print-list.csv` P19) | Z +ve is starboard |

Transform (right-handed to right-handed, no mirroring, metres to millimetres):

```
body x (aft)       = 600 - 1000 * X_cad      nose datum = pod nose, X_cad +0.600
body y (starboard) = 1000 * Z_cad
body z (up)        = 1000 * Y_cad            z = 0 is the CAD wing chord line
```

Consequences: wing LE at x 600, spar at x 696.7, rear boom clamps at x 857.9, lift motors at x 192.3 (front) and 1188.2 (rear), booms at y +-433.7, boom axis at z -32.9, pusher disc at x 1041. Cross-checks that the transform is right: the source CG (28 % MAC, `analysis/results.json` `C0.cg.xLEtoCG` -0.0903 m) maps to x 690.25 mm and the model's CG is 689.65 mm; the lift-motor centroid (x 690.25) coincides with the source's "thrust centroid = CG" (`C0.cg.pct.thrust`).

Meshes were **not** used. `cad/mesh/*.STL` are in metres in part-local frames with an extra per-instance rotation matrix, 75 files, and the pod mesh has pockets (risk to `T1.watertight`). The transform above is clear enough to bake them, but the schema's `mesh` geometry has no unit or transform field (see Schema gaps in `validator-comparison.md`). Primitives were used instead. The mesh bounding boxes were used to size boxes (servos with trays, clamps, fin shoes) and to read the fin sweep.

## Provenance

`MB` = `analysis/mass/mass_budget.json`, `R` = `analysis/results.json`, `AR` = `analysis/aero/aero_results.json`, `P` = `cad/params.txt`, `M` = `cad/mesh/<part>.STL` bounds. Line-level citations are in comments above each component in `plane.yaml`.

| Component id(s) | Mass from | Geometry / position from |
|---|---|---|
| `pod` (539.5 g) | MB rows Fuselage_Pod, Canopy, Battery_Tray, FC_Tray, Pod frames (group "Fuselage pod" less pitot) | P `fusL` 1.0, `fusR` 0.08, `comp=Fuselage_Pod`; CG MB `calibration.stations.pod_from_nose` 0.4359 |
| `wing` (1133.97 g) | MB group "Wing" less spar and joiner | P `chord`, `panelLen`, `tc`, `foilWing`, `sparY`; CG R `C0.cg.items` Wing |
| `spar` (675.4 g) | MB Spar_Tube + Wing_Joiner (= R `base.m_spar`) | P `sparX`, `sparOD`, `sparLen`, `joinLen` |
| `boom_l/r` (307.6 g each) | MB Boom_Front, Boom_Rear_Stub, Splice_Plug | P `xFront`, `xStub0`, `yIn`, `boomOD`; R `C0.geo.booms` |
| `boom_clamp_f_*`, `boom_clamp_r_*` | MB Boom_Clamp_F/R_Upper/Lower | M Boom_Clamp_*; P `comp=` X -0.0967 / -0.2579 |
| `lift_mount_{f,r}{l,r}` (108.7 g) | MB Motor_Mount_Upper/Cap + ESC (EST 25 g each) | M Motor_Mount_Upper/Cap; P `comp=Motor_Mount_*` |
| `lift_motor_*` (165 g) | MB Lift_Motor | P `motorD`, `motorH`; thrust R `C0.struct.Tmax` 30.695 N |
| `lift_prop_*` (37.6 g) | MB Lift_Prop (32 g EST) + Prop_Plate | P `liftProp` 0.4318, `propT` 0.008 |
| `gear_clamp_*`, `leg_*` | MB Gear_Clamp_*, Landing_Leg, Gear_Fairing, Dome feet | P `legLen`, `legOD`, `comp=Landing_Leg`; M Gear_Clamp_* |
| `tail_clamp_*`, `fin_shoe_*`, `fin_*`, `h_tail` | MB Tail_Clamp_*, Crush_Sleeve, Fin_Shoe, Fin, Rudder, H_Tail, Elevator | P `hSpan`, `hC`, `vH`, `vC`, `foilTail`; M Fin (tip chord, sweep), Fin_Shoe |
| `servo_ail_l/r`, `servo_elev`, `servo_rud_l/r` | MB "Servos (5)" group split per servo (servo + tray + horn + pushrod) | M Servo + Servo_Tray bounds at P `comp=` placements |
| `pitot_clamp`, `pitot_tube` | MB Pitot_Clamp, Pitot_Tube | P `pitotX`, `pitotZ`, `pitotL`; M Pitot_* |
| `battery` (820 g) | MB Battery_6S_LiPo | P `battX`, `battY`, `battL/H/W` (EST dims) |
| `flight_controller` (40 g) | MB Flight_Controller | M Flight_Controller, P `comp=` X 0.4075 |
| `avionics_other` (378 g), `wiring` (370 g), `fasteners` (221 g) | MB "Avionics not modelled" + GPS pad, Wiring, group "Fasteners and inserts" (all EST) | station from R `C0.cg.items` / MB `calibration.stations`; **box size is a placeholder** |
| `pusher_cup`, `pusher_motor`, `pusher_prop` | MB Pusher_Cup + 5th ESC, Pusher_Motor, Pusher_Prop_14in + adapter + washer + nut | P `pushMotorL`, `pushProp`, `comp=Pusher_*`; M Pusher_Cup |
| `requirements`, `flight` | R `C0.sized.m`, `base.Vc`, `base.CLmax`, `base.rho`; AR `stall.V_stall_req_mps`, `mission.R10_req_min` | |
| Joint ratings marked "from source" | R `C0.struct.MS_J` 1.4126, `feaWingForce` (P), `struct.MS_B` 7.4367, `struct.Tmax` | see below |

Part numbers for purchased parts are from `docs/purchasing/C0_BOM.csv` (SunnySky X4110S 400KV, JeeFly 1755 amazon B0FJ21V736, APC 14x8.5EP, EMAX ES3005HV, CoreWing F405 Wing APP V2, Ovonic 6S 6500). Printed parts use `3d-print-fdm` on `jacobs-fdm` (source print list: PETG and PA6-CF20); tubes are `hand-cut` from OnlineMetals stock; foam parts are `hotwire-foam`.

### Where the source conflicts with itself (root values used)

- Static margin: 10.4 % (AVL with pod, `AR neutral_point`) vs 10.2 % (sizing, `DESIGN-BASIS`); both are in the comparison. DECISIONS self-inconsistency 2.
- H-tail span: CAD `P hSpan` 0.9174 m (used) vs sizing `R C0.geo.hSpan` 0.8674 m (boom spacing, what the aero numbers use). This alone moves our static margin by 1.2 points.
- Fin shape: `cad/README.md` says "65 % tip chord" and the sizing treats a fin as a 166.4 x 208 rectangle (`Sv` 0.0692 m^2); `Fin.STL` has tip chord 73.6 mm (44 %) and 15.6 degrees LE sweep. The mesh was used.
- Fasteners: 221.0 g bottom-up (`MB`) vs 164.1 g in the sizing; bottom-up used. `cad/verification.txt` prints different printed-part masses (e.g. Battery_Tray 46.4 g vs 35.0 g in `MB`); `MB` used as instructed.
- `MB calibration.stations.cad_chord` 0.320765 differs from `P chord` 0.322333 (stale); `P` used for geometry, the station fractions only for CG.

## Placeholders (values not from the source)

1. **Every joint rating marked `placeholder — not from source`** in `plane.yaml`. The source has no joint capacities. Rule used: 50 N per M3 screw into a printed insert (screw counts from `cad/hardware.json` fastener schedule), 20 N per M2 screw, 20 N for small bonded or taped lumps, 50 N for a strap or a single cross-bolt. These are deliberately low guesses, not engineering values.
2. Ratings that are from the source (comment says "from source"): `wing-pod`, `spar-pod`, `spar-wing` = 535.8 N (joiner yield capacity, `struct.MS_J` 1.4126 x 2 x `feaWingForce` 189.64 N, expressed as total wing lift); `clampf-boom-*` = 228.3 N (`struct.Tmax` x `struct.MS_B`, boom tube yield, not a clamp slip rating).
3. `pusher_motor` `max_thrust_n` 8.376 N is the cruise drag (`R C0.sized.D_cruise`), **not a maximum**: the source has no thrust table for the 14x8.5EP (`docs/research/pusher-battery-servo.md`). It does not enter any check (role cruise).
4. Lump geometry: `avionics_other` (30x60x30), `wiring` (100x60x40), `fasteners` (20x20x20) box sizes and z positions; `avionics_other` station 240 mm instead of the source's 225 mm so it does not overlap the FC.
5. Estimates inherited from the source and flagged EST there: lift prop 32 g, ESC 25 g each (5 in total, folded into the lift mounts and the pusher cup because the CAD does not place them), printed-part masses, battery box dimensions, PETG density 1.27.
6. Modelling simplifications: pod = R80 x 1000 cylinder (real pod tapers to R30 aft of x 650); wing, tail and fins are the schema's slab hulls (box section, not NACA 2415 or 0009); the spar is one 25.4 mm tube across the centre gap; ailerons, elevator, rudders, leg fairings, motor shaft stubs and the pusher M6 adapter are not separate geometry.
7. The extra joint `spar-pod` exists only because the cylinder pod has no wing slot, so the spar would otherwise "clip" the pod.

## Validation result

`plane validate designs/c0-lift-cruise --tier all` exits 1. T0 PASS, T1 FAIL (3 findings), T2 FAIL (placeholder ratings vs drop-test peaks), T3 FAIL (static margin 15.3 % vs the 15 % cap, fuselage not modelled), T4 FAIL (`hotwire-foam` has no machine), T5 PASS. Each failure is classified in `validator-comparison.md`.
