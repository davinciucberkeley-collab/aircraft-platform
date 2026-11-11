---
id: morph-box-wing-barua-scholz-2013
title: Systematic Approach to Analyze, Evaluate and Select Box Wing Aircraft Configurations from Modified Morphological Matrices
authors: Priyanka Barua, Dieter Scholz
year: 2013
url: https://www.fzt.haw-hamburg.de/pers/Scholz/Airport2030/Airport2030_TN_BoxWingSystematic_13-06-14.pdf
type: paper
retrieved: 2026-11-11
verified: true
---

## Summary
A technical note from the Airport2030 project (Hamburg University of Applied Sciences) on generating box-wing aircraft configurations with a modified morphological matrix derived from General Morphological Analysis. It lists six configuration parameters, then prunes the 162 combinations stepwise by removing pairs that are illogical or infeasible. Engine position and tail type are deferred to later stages. The note is for large transport aircraft, so only the method carries over.

## Usable rules / numbers
- Six chart rows (Table 3.7), with options: stagger (3: unstaggered, positive, negative); sweep (3: backward, forward, backward/forward); box-wing vertical position (2: low-high, low-super-high); horizontal stabilizer position (3: canard, none, aft); vertical stabilizer position (1: aft); engine position (3: fuselage aft, fuselage middle, wing). Full chart = 3 × 3 × 2 × 3 × 1 × 3 = 162 combinations.
- Before any option is dropped, the count is 2,268. Pre-pruning exclusions: no-sweep, super-low wing positions, unsuitable vertical tail types (inverted V, Y, ring), and engines at the fuselage front. (Section on option pruning.)
- Stepwise pruning: step 1 combines stagger and sweep and drops pairings with long winglets or illogical stagger, leaving 4. Step 2 adds vertical position, giving 8. Step 3 combines the two stabilizer positions, giving 3 empennage outcomes. Step 4 merges them into 24 basic configurations. Step 5 removes configurations with both wings forward-swept, leaving 18. (Pruning section.)
- Cross-consistency checking is mentioned but not carried out in the note.

## How we could use it
- Shows the stepwise pruning sequence: group rows, combine pairs, merge, then remove infeasible sets. Use the same sequence for the VTOL chart's compatibility pass.
- Rows for wing position, stabilizer position and engine position map onto the VTOL chart's tail and propulsion rows.
