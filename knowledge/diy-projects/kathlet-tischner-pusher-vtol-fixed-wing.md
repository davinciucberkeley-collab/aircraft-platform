---
id: kathlet-tischner-pusher-vtol-fixed-wing
title: "3D Printed VTOL Drone"
source_url: https://kathlet.github.io/portfolio/project-3-3d-printed-tail
source_type: other
creator: Kathle Tischner
date: unknown
retrieved: 2026-11-18
configuration: lift-plus-cruise
morphology:
  lift: fixed-wing
  vtol_method: lift-plus-cruise
  propulsion_count: 2
  tail: v-tail
manufacturing_methods: [3d-print-fdm]
materials: [carbon-infused PETG, Oratex covering]
cost_usd: unknown
cost_source: unknown
wingspan_mm: unknown
mass_g: unknown
outcome: unknown
outcome_evidence: "Page discusses flight-time results and design lessons but does not explicitly confirm a flight or report the endurance achieved."
verified: true
---

## What's novel
A modular fixed-wing VTOL drone with a pusher motor for cruise and a separate VTOL motor on a spar, using an inverted V-tail. The airframe is 3D-printed in carbon-infused PETG, which was chosen over PLA for stiffness.

## How it was built
- Wing and tail sections are printed, with a printed fuselage that has a removable skin for avionics access.
- The wing and tail are covered with Oratex.
- The page describes the design as modular and built from US-sourced parts, but gives no part list.

## Problems and fixes
- Wing torsion under load: the first wing needed more centre reinforcement. Proposed fixes are a larger spar or a composite skin.
- Centre of gravity moved strongly with the pusher motor position. Proposed fix is to move the motor forward in the design.
- Carbon-infused PETG was hard to print for long, thin spars and needed special settings.
- The VTOL motor mount spar should be enlarged for rigidity. This is a recommended change, not a completed one.

## Lessons for us
- A pusher motor placement changes CG enough to need a printed-design revision; check CG before printing a second wing.
- Long thin printed spars in carbon PETG need dedicated print settings and supports.
