---
id: std-ardupilot-quadplane-building
title: Building a QuadPlane (ArduPilot documentation)
authors: ArduPilot development team
year: unknown
url: https://ardupilot.org/plane/docs/quadplane-building.html
type: website
retrieved: 2026-11-11
verified: true
---

## Summary
Official ArduPilot guide to building a quadplane (hybrid VTOL). It discusses lift motor power and the effect of wing downforce on lift needs. It gives no numeric thrust-to-weight ratio.

## Usable rules / numbers
- [hover_thrust_to_weight_min] None. The "General Rules" section says lift motors need enough power for the airframe weight plus extra load from wing downforce, and recommends eCalc for component choice. No ratio is stated.

## How we could use it
- Confirms that the hover-thrust requirement should include downforce margin, but gives no value. Does not support or change the 1.5 default.
