---
id: std-multirotor-design-compendium
title: Multirotor / Drone Aerodynamics & Control (Robotics Reference)
authors: Robotics reference compendium (author not stated in fetched text)
year: unknown
url: https://compendium-01j.pages.dev/Engineering-and-Robotics/Robotics/multirotor-design
type: website
retrieved: 2026-11-11
verified: true
---

## Summary
Online robotics reference page on multirotor design, with first-principles notes and design heuristics. It gives thrust-to-weight regimes and a minimum design heuristic for drones that must hover with control authority. It gives no landing-load or static-margin values.

## Usable rules / numbers
- [hover_thrust_to_weight_min] Design heuristic (section "Design heuristics"): static thrust of at least 2 times weight per motor, i.e. thrust-to-weight minimum 2.0, for any drone expected to hover with control authority.
- [hover_thrust_to_weight_min] Regimes (section "First principles"): a thrust-to-weight of 1.0 barely hovers with no control margin; 2.0 is described as a typical consumer drone with acceptable agility.
- [landing_load_factor] None. Landing appears only in failsafe context (descent rate limit 3 to 5 m/s), with no load factor.
- [static_margin] None. Center of gravity is discussed qualitatively only.

## How we could use it
- Supports a higher hover thrust-to-weight floor (2.0) than our current 1.5, for multirotor control authority. Source is a non-authoritative web page; confirm with a textbook or paper.
