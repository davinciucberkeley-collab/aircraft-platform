# TiltWing tilt-wing VTOL (Cakir & Kurtulus 2022 study)

A second real design converted into schema 0.2, and the first with articulated joints: the wing and the horizontal tail tilt about their spars (0 deg cruise, 90 deg hover). It checks `plane validate` against a design that has its own independent numbers (the source's sizing model, CAD STLs at 0 and 90 deg, an AeroBuildup sweep, a verification table). The YAML was not tuned to pass; real disagreements are the finding, see `validator-comparison.md`.

- **Source:** `/home/claude/davinciucberkeley-collab/TiltWing` at commit `1488f8f`, read-only. Files used: `README.md`, `model.js` (header formulas, `PAPER`, `INPUTS`, `size()`), `cad/params.json`, `cad/manifest.json`, `tools/cad_export.py`, `data/verify.json`, `data/airfoils.json`, `data/aero.json`, and the STLs in `cad/cruise_tilt0/` and `cad/hover_tilt90/`. The "fabrication BOM" is in the design report linked from the source README (Claude Docs doc `b23ddeab-180c-40f5-969b-97d22813868d`, section "Fabrication: components and build plan"), which I read.
- **What it is:** model after Cakir and Kurtulus, Turk J Elec Eng & Comp Sci 30 (2022) 767-784. Tilting 2.0 m S1223 wing with 4 tractor rotors (14 in), tilting NACA 0009 horizontal tail with 2 rotors (8 in), no vertical tail, 1.8 m x 0.2 m fuselage. Mass 9.153 kg by the sizing (M1). Nothing has been built.
- **Values:** the model's DEFAULT slider values, which are the paper's (`model.js` `PAPER`, `INPUTS`). `cad/params.json` equals the defaults, so `size()` run at the defaults (node, nothing written to the source) gives every derived number.
- **Rule of the source repo kept:** every number cites its origin (file + key or formula id, in the YAML comments); unknowns are left out or marked `placeholder - not from source`.

22 components, 21 attachments (2 of them articulated), mass 9152.686 g (source M1: 9152.686 g).

## Frame

No transform needed. `tools/cad_export.py` states "CAD axes: X aft from the nose, Y to starboard, Z up. Units mm", which is the platform body frame. Checked against the STLs: the wing LE root at x 654.43 (`xLEroot`), the tilt shaft at (756, 0, 84), the tail shaft at (1656, 0, 24) all match `Wing_Tilt_Spar.stl` / `Tail_Tilt_Spar.stl` bounds.

## Tilt joint: sign and axis (checked against the STLs)

Rotating each part of `cad/cruise_tilt0/` by +90 deg about +y through the pivot reproduces the same part in `cad/hover_tilt90/` with a maximum bounding-box difference of 0.000 mm (Wing_S1223, H_Tail_NACA0009, Wing_Nacelle_2, Wing_Prop_2, Tail_Nacelle_1); -90 deg is off by 78-407 mm. So: axis `[0, 1, 0]`, pivot `[756, 0, 84]` (wing, `xw` and `zw = 0.42*df`) and `[1656, 0, 24]` (tail, `xt`, `zt = 0.12*df`), +90 = leading edge up, thrust axis `[-1, 0, 0]` turns to `[0, 0, 1]`. The motors and their prop discs are downstream of the tilt joint, so they turn with the wing or tail.

Both surfaces tilt together in the source (`cad_export.py` applies one `tilt_deg` to both; `model.js` `flightForces` sets `tailTilt = d`), so the hover pose sets both joints to 90. Range `[0, 95]` is from the design report's build sequence ("hard stop at 0 and 95 deg", stated for the wing; the tail is assumed to match).

## Provenance

`M` = `model.js` (formula id), `CAD` = `tools/cad_export.py`, `P` = `cad/params.json`, `R` = the design report BOM. Line-level citations are in the comments above each component in `plane.yaml`.

| Component | Mass from | Geometry from |
|---|---|---|
| `fuselage` 990 g | M M1 `mFus` = 0.55 kg/m x Lf x df/0.2 | CAD `fuselage()` (profile) simplified to a R100 x 1800 cylinder; `Lf` 1.8, `df` 0.2 |
| `wing` 804.755 g | M M1 `mWing` = 1.40 kg/m2 x S = 805.755 g (includes the tilt mechanism) less 1 g | M G1-G4: S 0.57554 m2, cr 338.553, ct 236.987, sweep 5.7994 deg; `xLEroot` 654.434; slab thickness 0.1511 from `data/airfoils.json` s1223 |
| `tail` 114.856 g | M M1 `mTail` = 1.0 kg/m2 x S_h = 115.856 g less 1 g | M G5: S_h 0.115856 m2, ARh 4.1, span 689.21, crh 186.78, cth 149.42; sweep 5 deg (CAD) |
| `wing_spar`, `tail_spar` | placeholder 1 g each, carved out of the wing / tail bucket | CAD `spar`, `tspar`: radius 12 / 8 mm, length 240 / 120 mm along y |
| `wing_motor_1..4`, `tail_motor_1..2` 304.09 g | M M1 `mMotors` = f_prop x (1 - f_batt) x m = 1830.537 g, equal split over 6 (placeholder), less 1 g prop | CAD `rotor()`: nacelle R28 x 286.2 (wing), R20 x 162.7 (tail); y = +-400, +-1000 (wing), +-344.6 (tail) |
| `*_prop_*` 1 g | placeholder carved out of the motor kit | M `PAPER.Dfront` 14 in, `Drear` 8 in -> disc R177.8, R101.6; thickness 6 mm (CAD) |
| `battery` 1830.537 g | M M2 `mBatt` = f_batt x f_prop x m | box and x are placeholders (below) |
| `electronics` 1000 g, `payload` 2500 g | M `PAPER.elec`, `PAPER.payload` | placeholders (below) |
| `gear_lump_1/2` 40 g each | M M1 `mMisc` = 0.08 kg split in two | x at 0.30 L and 0.82 L (R build sequence); box placeholder |
| `max_thrust_n` | M `size()` `TfMax` 32.4077 N (wing), `TrMax` 6.1562 N (tail) | |
| `requirements`, `flight` | M `PAPER`, M1, P4 `CLmax` 2.0142 | |
| Manufacturing | R BOM and build sequence | see below |

### Manufacturing map (BOM to methods and machines)

| Part | BOM entry (R) | `method` / `machine` | T4 result |
|---|---|---|---|
| `wing`, `tail` | FOAMULAR NGX F-250 cores, "Hot-wire S1223 cores ... skin them" | `hotwire-foam`, no machine | FAIL (manufacturing.yaml has no hot-wire machine) |
| `fuselage` | 1 mm glass/epoxy shell over a foam plug | `composite-layup`, no machine | FAIL (no layup machine; the foam plug would be a second hot-wire item) |
| nacelles (`*_motor_*`) | Polymaker PA6-CF20 mounts | `3d-print-fdm` on `jacobs-fdm-fortus` (engineering-grade thermoplastics; `jacobs-fdm` lists PLA only) | SKIP (no build volume listed; nacelles are 297 mm and 169 mm long) |
| motors, props, spars, battery, electronics, gear hardware | SunnySky X3515S KV400, APC 15 x 5.5, Mars 2807, Rock West 45002, Ovonic 6S, CoreWing F405... | `purchased` | PASS |

Not modelled because the CAD has no geometry: tilt bearings (6804-2RS), 6061 bearing plates, tilt servos, control servos.

## Where the source conflicts with itself

- **Rotor diameter:** the model (and the paper, Table 2) use 14 in wing / 8 in tail props; the BOM buys APC 15 x 5.5 for the wing "instead of the paper's 14 in" and a 7 in tail prop. Geometry uses the model's 14 / 8 in.
- **Spar:** the CAD tilt shaft is 24 mm OD (240 mm long); the BOM buys 26.8 / 25.0 mm Rock West tubes, one per half (about 0.89 m). CAD used.
- **Tail span:** the model derives it from S_h and ARh = 4.1 (689 mm); the `PAPER.out.tailSpan` comparison value is 0.74 m. Model used.
- **Payload and mass:** the model gives 9.153 kg; the paper's 9.5 kg is only a comparison value.

## Placeholders (values not from the source)

1. Every `rated_load_n`: the source has no joint capacities (its F-section reports moments and margins, not joint forces). Values are low guesses: 200 N / 50 N tilt and shaft joints, 50 N nacelles, 30 N props, 100 N bays, 50 N gear lumps.
2. Battery, electronics and payload positions and box sizes: the source places no component in the fuselage. Electronics at x 250, payload at x 960, **battery x 454.635 mm solved so the whole-aircraft CG equals the model's input CG** (`xcg` 789.457 mm = `xLEmac` + 30 % MAC). The CG comparison is therefore not independent.
3. Equal mass split of the propulsion kit over 6 rotors (the 4 wing and 2 tail rotors are different sizes; `size()` gives shaft power 313 W vs 11.8 W per rotor); 1 g placeholder prop masses and spar masses (carved out of their buckets so the total stays the source mass).
4. Gear lump boxes (30 mm cubes) and z (-80 mm). The CAD has no landing gear.
5. Joint points of the nacelle attachments (a point inside both motor and surface).

## Modelling simplifications

- Wing and tail are single mirrored slabs from y = 0 (the CAD halves start at y = +-110 and +-50 so they clear the fuselage and can tilt). This is the largest effect on tier 1 and is analysed in `validator-comparison.md`.
- Slab thickness for the wing is the camber-envelope height (0.1511 c) with the slab centre at the envelope mid (z 104.2 mm at the root), not the 0.1211 c section; the tail uses 0.09 c about z 24.
- Fuselage is a cylinder; the CAD profile has an ellipse nose and a taper to 28 % of the radius.
- Each nacelle and motor is one cylinder from the prop-disc rear face to the nacelle end (the spinner cone is omitted).

## Validation result

`plane validate designs/tiltwing-cakir --tier all` exits 1. T0 PASS, T1 FAIL (root-strip clipping in every configuration), T2 FAIL (placeholder ratings vs joint loads and drop test; hover moment WARN), T3 FAIL (static margin 18.8 % vs the 15 % cap), T4 FAIL (no hot-wire or layup machine; Fortus fit SKIP), T5 PASS. Every failure is classified in `validator-comparison.md`.
