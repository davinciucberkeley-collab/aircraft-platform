# C0-A1: wingtip cruise propellers (derived from C0 v0.4.0)

The team's alternative concept A1 as a platform design. It is C0 (`designs/c0-lift-cruise`) with only the A1 differences applied. Status `concept`, schema 0.1. Nothing has been built or flown, and the source's own verdict is "do not build A1 first, revisit after C0 has flown" (`concepts/variants/a1/design.md` section 12).

- **Sources** (read-only, `/home/claude/davinciucberkeley-collab/dbf-combined` at `1244ebc`): `concepts/concepts.json` (id a1), `concepts/variants/a1/{design.md, geometry.json, metrics.json, calc.py, calc_out.json}`, `fusion/variants/build_a1_fusion.py`, `DECISIONS.md`. Frame transform: same as C0, see `designs/c0-lift-cruise/README.md`.
- **Question it answers:** can the platform express and check a layout where the cruise thrust moves from one pod pusher to two wingtip tractor props, and what does that do to mass, CG, stall and hover T/W on the current v0.4.0 airframe?

## What A1 changes and why

The idea (Sinnige et al., J. Aircraft 2019, via `concepts.json`): a propeller at each wingtip, turning so the inboard blade rises against the tip vortex, can cut induced drag. The team worked it through for C0 and found the benefit is about 0.9 % of drag at this aircraft's thrust coefficient (CT 0.028, a quarter of the tunnel value), against 1.5 % extra drag from the nacelles and 2.8 % from the added mass.

To make it work they changed:

1. **Cruise thrust:** pusher motor, prop, cup and firewall removed. Two X4110S motors with 14 in APC props (right 14x8.5E, left 14x8.5EP) on nacelles at y +-1228 mm, prop plane 77 mm ahead of the wing leading edge (`geometry.json` add Tip_Motor, Tip_Prop_R/L). Width over discs 2.812 m (limit 3 m).
2. **Structure:** a 25.4 mm aluminium tube (342 mm, cut from a boom offcut) bonded into each spar socket end, through a 25.6 mm bore in the wing tip foam, carrying a printed nacelle mount (`geometry.json` add Tip_Tube_Ext, Tip_Splice_Sleeve, Nacelle_Mount).
3. **Battery** moved 174.2 mm aft (extended tray rails, belly hatch) to hold the CG, because the tip nacelles sit ahead of it.
4. **Left pitot** moved 0.10 m inboard, out of the left prop's induction field.
5. **Wiring:** two power/signal runs from the wing-root junction box to each tip ESC, plus a harness extension for the moved battery.

## Diff table vs C0 (v0.4.0)

| Item | C0 | C0-A1 | Source key |
|---|---|---|---|
| Cruise propulsion | 1 pusher on the pod, x 1016 | 2 tip motors, x 545, y +-1228, z 12 | `a1/geometry.json` add Tip_Motor |
| Cruise prop(s) | APC 14x8.5EP, 60.5 g lump | 2 x APC 14x8.5E/EP, 59.1 g lump (prop 37.1 + adapter 12 + spinner 8 + screws 2), disc x 523 | `a1/design.md` "Mass (est)", `geometry.json` Tip_Prop_R/L |
| Pusher cup (56.39 g incl. 5th ESC) | present | removed (pusher set removed) | `a1/geometry.json` remove Pusher_Prop_Set, ESC_P |
| Tip tube + sleeve | none | 2 x 82.4 g, y 880..1222 on the spar axis | `a1/geometry.json` add Tip_Tube_Ext 63.2, Tip_Splice_Sleeve 19.2 |
| Nacelle mount, ESC, cap, shell | none | 2 x 100 g lump (mount 45 + epoxy 8 + ESC 15 + cap 4 + shell 28) | `a1/geometry.json`, `a1/design.md` "Mass (est)" |
| Battery x | 345 | 519.2 (174.2 mm aft) | `a1/geometry.json` modify Battery_6S_LiPo shift_m -0.1742 |
| Left pitot y | -1000 | -900 | `a1/geometry.json` modify Pitot_Tube |
| Pod mass | 539.5 g | 551.5 g (+12 g tray rails) | `a1/geometry.json` add Battery_Tray_Ext |
| Wiring lump | 370 g | 596 g (+2 x 105 tip wiring, +16 W02_ext) | `a1/design.md`, `geometry.json` W02_ext |
| Motor count | 5 | 6 (4 lift + 2 tip) | `a1/metrics.json` motors |
| Total mass (bottom-up) | 7415.9 g | 8185.1 g (+769.1 g) | source delta +728 g (6.9104 - 6.1822 kg, v0.3.1) |
| `mtow_g` | 7438 | 8207 | C0 7438 + 769 + C0's own 22 g margin |

Everything else is C0 unchanged.

## Baseline notes (which numbers come from where)

Per `DECISIONS.md`, `concepts/variants/a1-a3` sit on the **v0.3.1** baseline (6.182 kg, 20 m/s, S 0.573 m^2, chord 238.7 mm, AR 10.06, T/W 2.03), while C0 here is **v0.4.0 rev G** (7.438 kg, 18 m/s, S 0.774 m^2, chord 322.3 mm, AR 7.45, T/W 1.68). Self-inconsistency 5 in `DECISIONS.md` is exactly this. Consequences:

- **Source numbers kept as deltas only.** The A1 absolute results (6.910 kg, hover 1,009 W, cruise 378 W, 10.3 min, SM 17.7 %, T/W 1.81, roll inertia x2.07) are v0.3.1 and appear in `validator-comparison.md` as source values, not as inputs.
- **Positions in the wing frame** (X of the tip nacelle, prop plane, motor) are relative to the wing leading edge and identical in both baselines, so they transfer directly. The tip tube is placed on the **v0.4.0 spar axis** (x 696.7, 30 % of 322.3 mm) instead of the source's v0.3.1 axis (30 % of 238.7 mm).
- **Battery shift 174.2 mm was computed for the v0.3.1 CG** (-0.0668 m) and is applied as documented. On v0.4.0 the CG target is -0.0903 m, and the model's CG lands at x 686.5 mm, 3.8 mm forward of C0's 690.25 mm target. About 38 mm more aft shift (battery x about 557) would restore it. Not done: the shift is a documented number and the difference is reported, not tuned.
- **Pusher removal mass differs by 41 g.** The source removes 323 g (v0.3.1 parts: pusher set 227 g plus adapter, spinner, firewall, wires, cap, screws). C0 v0.4.0's pusher items (motor, prop and hardware, cup plus ESC) sum to 281.9 g; firewall, pusher wires and cap are not itemised in the C0 lumps, so the rest stays inside the `wiring` and `fasteners` lumps. Bottom-up delta is therefore +769 g rather than +728 g.
- **No spare motor in v0.4.0.** In v0.3.1 the pusher motor and the spare became the two tip motors. C0 v0.4.0 dropped the spare (`DECISIONS.md` D9), so A1 on this baseline needs one more X4110S (+$46.99, listed in the component).

## Unknowns left at C0's value (variant source silent)

Lift-motor, lift-prop, boom, tail, fin, servo, spar and wing values; joint ratings other than the new ones; fasteners lump (the 70 added/36 removed hardware pieces are not itemised by mass in the source); `avionics_other`; wiring and fasteners stations; flight, cl_max, cruise speed (C0's 18 m/s kept even though A1's drag work uses 20 m/s).

## Modelling choices that are mine, not the source's

- Nacelle shell (28 g) is **not geometry**: a solid cylinder would swallow the mount and clip the wing tip (schema has no hollow bodies). Its mass is lumped into the mount.
- Nacelle mount is an estimated box [155, 40, 40] (source gives ring OD 57 x 6 mm and barrel OD 38.6 mm only).
- Tip motor `max_thrust_n` 4.9 N is the cruise thrust per prop from `design.md` section 2, **not a maximum** (same convention as C0's pusher). Thrust axis is [-1, 0, 0] (force forward, body x aft; corrected 2026-11-11 from [1, 0, 0], see `validator-comparison.md`).
- `wing-tip_*` is parented tip_tube -> wing (the tube protrudes 22 mm past the wing tip, so the other direction trips the 35 % embed limit; same workaround class as C0's clamps).
- Placeholders: all new joint ratings except `spar-tip_*` are `placeholder — not from source` using C0's rule (50 N per M3, per grub screw). `spar-tip_*` = 14.3 N nacelle load at 4.5 g x tube reserve factor 13.8 = 197 N (tube yield equivalent, not a joint rating).

## Result

`plane validate designs/c0-a1 --tier all`: T0 PASS, T1 FAIL (2, both inherited), T2 FAIL, T3 FAIL (stall and static margin), T4 FAIL (inherited). Every FAIL is classified in `validator-comparison.md`. The new FAILs are stall speed (12.3 m/s, mass at fixed wing area) and three placeholder-rating joint-load rows.
