# C0-A3: aligned, faired stopped lift rotors (derived from C0 v0.4.0)

The team's alternative concept A3 as a platform design: C0 (`designs/c0-lift-cruise`) with only the A3 differences applied. Status `concept`, schema 0.3 (motor-bay cavities in the nacelles). Nothing printed, bench-tested or flown. The source's verdict is: build the fairing and detent in phase 1, decide the reed/Lua phase after a scripting check, run a car-top drag test before flight (`concepts/variants/a3/design.md` section 12).

- **Sources** (read-only, `/home/claude/davinciucberkeley-collab/dbf-combined` at `1244ebc`): `concepts/concepts.json` (id a3), `concepts/variants/a3/{design.md, geometry.json, metrics.json, inventory.json, analysis/final_runs.json}`, `fusion/variants/build_a3_fusion.py`, `DECISIONS.md`. Frame transform: same as C0 (`designs/c0-lift-cruise/README.md`).
- **Question it answers:** four stopped rotors are 35.8 % of C0's cruise drag in the team's estimate. Does fairing them and parking the blades fore-aft pay for its 250 g, and what does it do to the platform's geometry checks?

## What A3 changes and why

Literature (Marepally, Baeder et al., VFS 2025, via `concepts.json`): a stopped rotor with blades aligned to the flow and a faired hub has the least drag. C0's CAD already draws the props parked fore-aft, but its BLHeli_S ESCs cannot park them. A3 adds, per rotor (four in total):

1. A **printed PETG nacelle** (NACA 0022 plan section, chord 260 mm, 179.4 mm long after truncation, 62.5 mm tall, 0.8 mm wall) around the motor mount and bell, bolted to the mount.
2. A **rotating hub cap** over bell top, adapter and hub, carrying two detent magnets; a fixed magnet in the nacelle lid attracts them so the two-blade prop parks along the flow. Capture is 36-56 % per stop (Monte Carlo), so the source expects only about half the alignment benefit without phase 2.
3. **Phase 2:** a reed switch per rotor and a Lua script that nudges the motor until parked (mass 22 g total, included here because the source headline numbers include it).
4. No ESC change, no airframe change, wing not re-sized.

## Diff table vs C0 (v0.4.0)

| Item | C0 | C0-A3 | Source key |
|---|---|---|---|
| Nacelle per rotor (x4) | none | box hull [179.4, 57.2, 62.5] at rotor x + 23.3, z -17.2, 47.6 g, with a motor-bay cavity (radius 25.75, z -11.94..28.06, open top). Front pair: [133.4, 57.2, 62.5] at x 192.573 (tail cut, see below) | `a3/geometry.json` add Lift_Nacelle_L*; 37.5 g + glue 1 + 6 M3x10 2.7 + 6 inserts 0.9 + phase-2 5.5 |
| Cap per rotor (x4) | none | cylinder r 26.5 x 11.84 at z 33.98 (above the prop disc), 14.85 g | `a3/geometry.json` add Lift_Cap_L*; 9.4 g + 3 magnets 2.25 + 4 net M3x16 3.2 |
| Mass added per rotor | 0 | 62.45 g | `a3/design.md` section 5: 56.9 g phase 1 + 22/4 phase 2 |
| Total mass (bottom-up) | 7415.9 g | 7665.7 g (+249.8 g) | source +250 g (6.432 - 6.182 kg, v0.3.1) |
| `mtow_g` | 7438 | 7688 | C0 7438 + 250 |
| CG x | 689.65 mm | 689.99 mm | source: shift -3.4e-5 mm; the 0.26 mm forward move is the hollowed nacelle centroid |
| New joints | none | `mount-nacelle_*` (bolted), `boom-nacelle_*` (slip fit), `prop-cap_*` (bolted) per rotor | `a3/design.md` section 4 |

Everything else is C0 unchanged (motors, ESCs, props, tail, wing, pusher, battery, all other masses).

## Baseline notes (which numbers come from where)

`concepts/variants/a3` is on the **v0.3.1** baseline (6.182 kg, 20 m/s, rotors at X +0.37092 and -0.50458); C0 here is **v0.4.0 rev G** (7.438 kg, 18 m/s, rotors at X +0.407727 and -0.588233, boom axis 2.9 mm lower). Consequences:

- **Positions:** nacelle and cap dimensions are given relative to each rotor axis and transfer unchanged. Heights were shifted -2.938 mm (v0.4.0 boom axis -32.938 vs v0.3.1 -30.000) so the nacelle keeps its position relative to the mount and boom.
- **Source absolute numbers** (cruise 365 -> 280 W, endurance 11.9 -> 15.0 min, hover 832 -> 890 W, SM 19.6 %, cost $1,943.92, reserve $56.08) are v0.3.1 and appear in `validator-comparison.md` as source values only. The drag-case numbers (CdA per rotor 0.0034 -> 0.0011 m^2, 35.8 % of drag) come from C0 v0.3.1 aero; the validator cannot test them.
- **Mass is baseline-independent** (parts, not sizing), so +250 g transfers exactly. The percentage effects do not: 250 g is 3.4 % of C0 v0.4.0 mass against 4.0 % of the v0.3.1 mass.
- **Gear clamp conflict is geometry from the source:** see the next section.

## Source inconsistency found while converting

`design.md` section 4 says the front gear clamp "needs the tail cut at x/c 0.75 (6 mm clearance)". The source's own envelope for the front nacelle is X 0.2579..0.4373 (`geometry.json` Lift_Nacelle_L1 `envelope_m`), and the front gear clamp is X 0.2639..0.2979, which lies **inside** that range, not 6 mm clear of it. At the clamp's station the nacelle is about 39 mm wide against the clamp's 46 mm. The same arithmetic holds on v0.4.0 (clamp x 265..299, nacelle x 126..305). The rear pair is clear by 6.6 mm as the source says.

**Design change (not a source fact):** the front nacelles (`nacelle_fl`, `nacelle_fr`) are cut 6 mm short of the front gear clamp, so the tail is at x 259.273 against the clamp's start at 265.273. Size 133.4 mm, position x 192.573, mass unchanged at 47.6 g (conservative). This follows the source's stated intent (`design.md` section 4, "6 mm clearance"), not its envelope. The team still needs to check the cut in CAD. With the cut, the front clamp and leg no longer overlap the nacelle.

## Unknowns left at C0's value (variant source silent)

Wing, tail, boom, pusher, battery, avionics, wiring and fasteners values; joint ratings other than the new ones. The 6 M3x10 and 6 inserts are inside the 47.6 g nacelle mass. The reed switch, ladder resistors and 10 m of 26 AWG wire (22 g in total) are spread over the four nacelle masses rather than modelled. The lid magnets and the lid pocket boss are inside the cap mass (the 14.85 g cap mass includes the fixed lid magnet, 0.75 g, which is on the nacelle in the real part).

## Modelling choices that are mine, not the source's

- **Nacelle is a solid box hull** of the source's envelope (width at its maximum thickness, so it overstates the tapered NACA section), with a **motor-bay cavity** (schema 0.3). The cavity is radius 25.75 around the 24 mm bell (1.75 mm radial clearance), its floor at the motor bottom (z -11.94) and its top open. The real part is a 0.8 mm shell open at the bottom; the 0.8 mm wall is not modelled, so the solid box outside the cavity sets the nacelle's centroid and the CG.
- **Cavity offsets:** front pair dx = -0.3 (motor x 192.273 minus nacelle x 192.573); rear pair dx = -23.3 (motor x 1188.233 minus nacelle x 1211.533). All four use dz 25.262 (motor z 4.062 and nacelle z -17.2 for all four).
- **Cap is only modelled above the swept prop disc** (z 28.06..39.9), because the schema forbids a propeller disc passing into a part. The skirt below the disc (z 15.6..28.06) and the blade slots are not modelled.
- **Props and caps are static** like C0's swept discs. The source's `cap_L*` revolutes are the motor spinning; no moving part is needed, schema 0.3 kept for cavities only. The parked azimuth (blades fore-aft) is not representable, since the prop is a disc.
- The cap/prop joint is `embed_ok: false` (contact), the nacelle/mount and nacelle/boom joints are `embed_ok: true`.
- Placeholders: all new joint ratings are `placeholder — not from source` (50 N per M3, 20 N for the slip fit), C0's rule. The source has no joint capacities.

## Result

`plane validate designs/c0-a3 --tier all`: T0 PASS, T1 FAIL (3 rows, all inherited: `servo-ail_l`/`servo-ail_r` overlap, `pusher-prop` gap), T2 FAIL (inherited placeholders), T3 FAIL (static margin 15.2 %, inherited), T4 PASS (see `validator-comparison.md` for why), T5 PASS. The eight nacelle-related interference rows of the earlier run are resolved. Every FAIL is classified in `validator-comparison.md`.
