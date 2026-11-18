---
id: std-wang-2016-small-tailsitter-sizing
title: Preliminary Design of a Small Unmanned Battery Powered Tailsitter
authors: Bo Wang, Zhongxi Hou, Zhaowei Liu, Qingyang Chen, Xiongfeng Zhu
year: 2016
url: https://core.ac.uk/download/195002844.pdf
type: paper
retrieved: 2026-11-18
verified: true
---

## Summary
Peer-reviewed preliminary sizing paper (International Journal of Aerospace Engineering, article 3570581) for a small battery-powered tail-sitter UAV. Section 2.2 defines a thrust ratio K_T as maximum design thrust over takeoff weight and proposes a value for small battery-powered tail-sitters. The value is tied back to an earlier suggestion by Stone (ref. 11).

## Usable rules / numbers
- [hover_thrust_to_weight_min] Maximum design thrust T_max = K_T x takeoff weight, with K_T required to be greater than 1 (Section 2.2, Eq. 5). This ratio is maximum thrust, not hover thrust.
- [hover_thrust_to_weight_min] K_T = 1.2 is proposed for small battery-powered tail-sitters (Section 2.2, p. 3). This is the authors' proposal, not a measured requirement.
- [hover_thrust_to_weight_min] Stone (ref. 11) is cited as suggesting maximum thrust of at least 1.15 times takeoff weight (Section 2.2, p. 3).
- [landing_load_factor] None. Section 2.2.5 mentions a landing drop reference from a 4.0 ft height, given as a velocity limit, not a load factor.

## How we could use it
- Supports a minimum thrust-to-weight of about 1.2 for small battery-powered VTOL (tail-sitter) designs. This is the strongest primary number found for the hover rule so far.
- Does not give a landing load factor. Do not use it for the structure rule.
