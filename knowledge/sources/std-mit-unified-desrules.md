---
id: std-mit-unified-desrules
title: Design Rules lab notes (MIT 16.01 Unified Engineering)
authors: MIT 16.01 Unified Engineering course staff
year: unknown
url: https://web.mit.edu/16.unified/www/SPRING/systems/Lab_Notes/desrules.pdf
type: website
retrieved: 2026-11-11
verified: true
---

## Summary
Short course lab note on airplane design rules. It is aimed at full-scale teaching aircraft rather than RC or UAV models. It gives a static-margin window and explains why a small positive margin is preferred over a large one.

## Usable rules / numbers
- [static_margin] Recommended static margin is a small positive window of 0.05 to 0.15, defined as (neutral point minus CG) divided by chord c, i.e. a fraction of chord, not explicitly of MAC (section "Center of Gravity Position", p. 3, eq. 2).
- [static_margin] The note calls the small positive margin the ideal case and warns that a large positive margin causes large elevator trim changes with airspeed (p. 3).
- [static_margin] A negative margin means pitch instability; the neutral point is treated as the practical aft CG limit (p. 2).

## How we could use it
- Supports keeping static_margin 0.05 to 0.15 for the fixed-wing cruise tier. Reviewer should confirm whether "c" here means MAC for a wing.
- Not a source for hover thrust, landing loads or CLmax.
