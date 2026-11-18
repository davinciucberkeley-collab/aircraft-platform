---
id: std-stone-wong-tandem-wing-tailsitter-usyd
title: Preliminary Design of a Tandem-Wing Tail-Sitter UAV Using Multi-Disciplinary Design Optimisation
authors: H. Stone, K.C. Wong (Department of Aeronautical Engineering, University of Sydney)
year: unknown
url: https://web.aeromech.usyd.edu.au/uav/twing/pdfs/Pap2_v1.pdf
type: paper
retrieved: 2026-11-18
verified: true
---

## Summary
Design paper from the University of Sydney T-wing tail-sitter program. It has a "Major Design Issues" section on hover thrust and a vehicle design constraints table. The text cites a 1996 AUVSI conference paper with the same title, which suggests this is the conference version, but the document does not state its own year.

## Usable rules / numbers
- [hover_thrust_to_weight_min] Hover thrust requirement (section "Major Design Issues"): total available thrust must exceed vehicle weight by a margin, "typically 15%" (footnote 1 marks it). Equivalent to a ratio of about 1.15.
- [hover_thrust_to_weight_min] Table 3, "Vehicle Design Constraints": thrust must exceed vehicle weight by 15%.
- [hover_thrust_to_weight_min] The paper gives no ratio beyond the 15% margin and no maximum-thrust value.
- [landing_load_factor] None. Structural model treats landing as two drop cases (symmetric drop of 4.0 ft onto all four legs, unsymmetric drop of 1.0 ft onto one leg at a 25 degree tip angle). No g value is given.
- [landing_load_factor] Flight design load factors of plus and minus 6 g are stated for the airframe (structural model). These are flight loads, not landing loads.

## How we could use it
- Supports a 1.15 minimum thrust margin for tail-sitter VTOL, which sits below our current 1.5.
- Does not give a landing load factor. The drop cases could be used to design a drop test, but they do not set a g value.
