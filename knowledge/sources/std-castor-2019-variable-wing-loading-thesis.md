---
id: std-castor-2019-variable-wing-loading-thesis
title: Design and Development of a Controllable Wing Loading Unmanned Aerial System
authors: Garret Oakley Castor (Oklahoma State University, master's thesis)
year: 2019
url: https://core.ac.uk/download/304590919.pdf
type: paper
retrieved: 2026-11-18
verified: true
---

## Summary
Master's thesis on a VTOL-capable UAS with controllable wing loading and jet-thrust lift. Chapter I ("V/STOL Requirements") gives a minimum acceptable thrust-to-weight ratio and a more desirable margin, both attributed to Raymer's Aircraft Design (cited as ref. [12]). The thesis does not open Raymer's text, so the 1.05 figure is secondhand.

## Usable rules / numbers
- [hover_thrust_to_weight_min] Chapter I, "V/STOL Requirements" (p. 9): minimum acceptable thrust-to-weight ratio of 1.05, citing [12] (Raymer).
- [hover_thrust_to_weight_min] Same passage (p. 9): a ratio of about 1.3 is desirable, giving cushion for an emergency and leaving thrust available for control.
- [hover_thrust_to_weight_min] The author's own prototypes are 1.03 (Locust, pp. 38-39) and 1.14 (Grasshopper, p. 36). These are the author's calculations, not design rules.
- [landing_load_factor] None. The landing gear section (pp. 64-69) describes nose and main gear weight shares and a drop test of a main strut. It gives no load factor, sink speed or g value.

## How we could use it
- Gives 1.05 as the lowest minimum found, attributed to Raymer, and 1.3 as the desirable margin. Use as evidence for a 1.2-1.3 range, not as a primary number.
- Does not support a landing load factor.
