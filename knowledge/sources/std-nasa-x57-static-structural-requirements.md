---
id: std-nasa-x57-static-structural-requirements
title: X-57 Static Structural Requirements and Airworthiness Approach
authors: Wesley W. Li, NASA Armstrong Flight Research Center
year: unknown
url: https://ntrs.nasa.gov/api/citations/20240006690/downloads/20240006690FINAL.pdf
type: paper
retrieved: 2026-11-11
verified: true
---

## Summary
NASA report on the structural airworthiness plan for the X-57 electric aircraft, a derivative of a 3000 lb Part 23 airplane. It lists the load factor and factors of safety used for new and modified structures. It is specific to X-57 and does not address small UAVs.

## Usable rules / numbers
- [landing_load_factor] Reduced design load factor Nz of 3.4 g used for new and modified structures (section V). Original Tecnam P2006T certified at 3.8 g. This is a maneuver-type design load, not a landing factor.
- [landing_load_factor] Landing and taxi inertial loads are included, but no landing load factor value is given in the text read (section V.A).
- [static_margin] None.
- [cl_max_default] None.
- Factors of safety (section IV): 2.25 for new metallic structures verified by analysis only; 1.5 kept for existing certified metal; 2.25 to 3.00 for composites; 3.0 for additive manufacturing parts; 1.8 for one composite wing with a stated justification.

## How we could use it
- Supports a 2.25 factor for analysis-only new structure as a reference, but not for small UAVs.
- Does not support the 3 g landing load factor; 3.4 g is a maneuver-type limit for a larger aircraft.
