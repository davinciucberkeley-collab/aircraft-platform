---
id: std-kamal-ramirez-serrano-2018-hybrid-vtol-design
title: Design methodology for hybrid (VTOL + Fixed Wing) unmanned aerial vehicles
authors: Ashraf M. Kamal, Alex Ramirez-Serrano
year: 2018
url: http://medcraveonline.com/AAOAJ/AAOAJ-02-00047.pdf
type: paper
retrieved: 2026-11-18
verified: true
---

## Summary
Open-access design methodology paper (Aeron Aero Open Access J. 2018;2(3):165-176) for hybrid VTOL and fixed-wing UAVs. It reports a thrust-to-weight range from the literature for VTOL and names its source. It also mentions a tail-sitter design that used the range.

## Usable rules / numbers
- [hover_thrust_to_weight_min] Page 166: some references suggest a thrust-to-weight ratio between 1.2 and 1.5 for VTOL, with good results. The cited source is ref. 16, Raymer, Aircraft Design: A Conceptual Approach, 5th ed. (2012). This is a secondhand citation; Raymer was not opened.
- [hover_thrust_to_weight_min] Page 166: the 1.2-1.5 approach has been used in developing tail-sitter UAVs, citing ref. 19 (Wang et al., 2016).
- [hover_thrust_to_weight_min] Page 169: hover and vertical climb are modeled with rotor thrust equal to weight (T = W). No margin is stated.
- [landing_load_factor] None.

## How we could use it
- Supports a 1.2-1.5 range for VTOL thrust-to-weight, which is the same range the ArduPilot forum quotes. The 1.5 upper end in our rule is at the edge of this range.
- Shows that the 1.2-1.5 range traces to Raymer. Opening Raymer's own text would be needed to confirm it.
