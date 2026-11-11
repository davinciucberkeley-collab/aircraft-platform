# C0-A2: boundary-layer-ingesting pusher on a stretched boat-tail (derived from C0 v0.4.0)

The team's alternative concept A2 as a platform design: C0 (`designs/c0-lift-cruise`) with only the A2 differences applied. Status `concept`, schema 0.1. Nothing built or flown. The source's verdict is "do not build A2 as a performance upgrade" (`concepts/variants/a2/design.md`, Verdict).

- **Sources** (read-only, `/home/claude/davinciucberkeley-collab/dbf-combined` at `1244ebc`): `concepts/concepts.json` (id a2), `concepts/variants/a2/{design.md, geometry.json, metrics.json, bli_estimate.json, bli_estimate.py}`, `fusion/variants/build_a2_fusion.py`, `DECISIONS.md`. Frame transform: same as C0 (`designs/c0-lift-cruise/README.md`).
- **Question it answers:** what does a 100 mm longer tail cone, with the pusher moved aft with it, do to mass and CG, and is it visible to the platform's checks?

## What A2 changes and why

C0 already puts the pusher at the end of a tapered pod, 38 mm behind the cone end, so it ingests some of the pod wake. The BLI literature claim (up to 21.7 % less power on a lone body, IMAV 2017) would need a much larger share of the drag ingested. A2 stretches the tail cone from 0.35 m to 0.45 m so the prop sits deeper in the wake and the cone half-angle drops (mean 8.1 to 6.3 deg, max 12.1 to 9.5 deg). The team's estimate is that this changes the BLI saving by 0.07 percentage points, about 0.3 W of 367 W.

Changes:

1. **Tail cone +100 mm**, built as a printed PETG shell in 3 segments joined to the foam forebody at a spigot joint, so the module unplugs for A/B testing (`geometry.json` add Tail_Cone, Tail_Joint_Spigot, Tail_Joint_Sleeve).
2. **Pusher motor, ESC, prop and cup move aft with the cone**, same parts (`geometry.json` modify Pusher_Motor, Pusher_Prop_Set, J-11 hardware).
3. **Wiring:** pusher phase leads extended 0.10 m, power and signal lines split at the tail joint with connector pairs (+18 g).
4. **Pod re-registered 16.7 mm forward** on the wing saddle to give the CG back. **Not applied here**, see baseline notes.

## Diff table vs C0 (v0.4.0)

| Item | C0 | C0-A2 | Source key |
|---|---|---|---|
| Pod cylinder length / centre x | 1000 / 500 | 1100 / 550 (tail end x 1000 -> 1100) | `a2/geometry.json` constants.tail_stretch_m 0.1 |
| Pod mass | 539.5 g | 598.5 g (+59.0) | `a2/metrics.json` mass_kg.formula, rev 2: +35.3 printed cone, +29.3 XPS extension, +12 rings, -35.5 old foam cone, +18 wiring |
| Pod `cg_offset` x | -64.1 | -59.6 | C0 539.5 g at 435.9 from the nose plus 59.0 g at x 988 (middle of the 877..1100 tail module), minus the new centre 550 |
| `pusher_cup` x | 985 | 1085 | `a2/geometry.json` modify J-11 (-0.100 m) |
| `pusher_motor` x | 1016 | 1116 | `a2/geometry.json` modify Pusher_Motor (-0.100 m) |
| `pusher_prop` x | 1041 | 1141 | `a2/geometry.json` modify Pusher_Prop_Set (-0.100 m) |
| Joint locations `pod-cup`, `cup-pusher`, `pusher-prop` | 985 / 1000 / 1034.5 | 1085 / 1100 / 1134.5 | follow the parts |
| Total mass (bottom-up) | 7415.9 g | 7474.9 g (+59.0 g) | source delta +59 g (6.241 - 6.182 kg, v0.3.1) |
| `mtow_g` | 7438 | 7497 | C0 7438 + 59 |
| Motor count, parts, cost | 5, same | 5, same parts (no purchase) | `a2/metrics.json` motors 5, cost delta 0 |

Everything else is C0 unchanged.

## Baseline notes (which numbers come from where)

`concepts/variants/a2` is on the **v0.3.1** baseline (6.182 kg, 20 m/s, pod 0.85 m); C0 here is **v0.4.0 rev G** (7.438 kg, 18 m/s, pod 1.0 m). The tail end of the pod is at the same CAD X (-0.400, prop at -0.437) in both baselines, because the v0.4.0 pod was lengthened 0.15 m at the nose. So the tail stretch transfers as a pure +100 mm. What does not transfer:

- **Revisions of the source.** `design.md` text still describes rev 1 (+0.100 kg, 852 W hover, 11.74 min). `geometry.json` and `metrics.json` are rev 2 (+0.059 kg, 843.9 W, 11.82 min). This design uses rev 2 (the metrics and geometry files, which agree with each other). DECISIONS.md self-inconsistency 5 covers the baseline, not this revision gap.
- **The CG fix (pod slide 16.7 mm forward)** was solved from v0.3.1 moments (pod group 2.497 kg, dM_x -35.9 g*m). On v0.4.0 the pod group and CG differ, so it is **not applied**; the added tail mass is left to move the CG. The model's CG moves from 689.65 to 695.78 mm (+6.1 mm, 1.9 % MAC), consistent in direction and size with the source's 2.8 % MAC before the fix. By the source's method a slide of about 22 mm (pod group about 2.1 kg on v0.4.0) would be needed here; not done.
- **Source absolute numbers** (MTOW 6.241 kg, hover 844 W, cruise 366 W, 11.82 min, SM 19.1 %, BLI credit 0.26 W, tail strike 18.6 deg) are v0.3.1 and appear in `validator-comparison.md` as source values only.

## Unknowns left at C0's value (variant source silent)

Everything not listed in the diff table, including: pod radius along the tail (the source's cone law r 54.7 -> 30 mm is not modelled; C0 also uses a plain R80 cylinder), joint ratings, aft joint plane hardware (3 radial screws, spigot and sleeve, 6 g each) and the tail connectors (10 g), which are inside the 59 g net rather than separate components, and the 16.7 mm pod slide (above).

## Modelling choices that are mine

- The removable tail module is modelled as part of the pod cylinder, as C0 models its own foam cone. The source's `slide_tail_cone` slider is a breakdown motion, not a flight-configuration moving part, and schema 0.1 has no separable-joint field (C0 comparison gap 5), so nothing is encoded.
- Net +59 g is placed in the pod through `cg_offset` rather than as a new component, because a separate cone cylinder would overlap the pod.

## Result

`plane validate designs/c0-a2 --tier all`: T0 PASS, T1 FAIL (3, all inherited), T2 FAIL (inherited placeholders), T3 PASS (static margin 13.4 %, see below), T4 FAIL (inherited), T5 PASS. No new FAIL. The T3 pass is an artifact of the un-applied CG fix, not an A2 advantage.
