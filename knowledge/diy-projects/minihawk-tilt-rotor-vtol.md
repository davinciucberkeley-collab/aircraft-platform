---
id: minihawk-tilt-rotor-vtol
title: "MiniHawk-VTOL"
source_url: https://hackaday.io/project/175286-minihawk-vtol
source_type: hackaday
creator: Steve Carlson
date: 2020-10
retrieved: 2026-11-11
configuration: tiltrotor
morphology:
  lift: fixed-wing
  vtol_method: tiltrotor
  propulsion_count: 3
  tail: other
manufacturing_methods: [3d-print-fdm, other]
materials: [3D-printed plastic, carbon fiber spar, cyanoacrylate glue, epoxy, flexible solar cells (optional)]
cost_usd: unknown
cost_source: unknown
wingspan_mm: 800
mass_g: unknown
outcome: flew-with-issues
outcome_evidence: "Project page reports flight in hover and forward flight but calls transitions temperamental, and lists several fixes made to the design."
verified: true
---

## What's novel
An 800 mm printed tilt-rotor that combines a plank wing with a tricopter layout: two front motors tilt on nacelles and one fixed motor sits at the tail. The design files are shared, and the page documents the transition problems and the redesigned nacelle that replaced the original.

## How it was built
- The airframe is printed on a Creality CR-10 with a carbon fiber spar integrated into the wing.
- Parts are bonded with cyanoacrylate or epoxy.
- Tilt nacelles are driven by servos, and the design files are shared.
- Flexible solar cells are an optional addition.

## Problems and fixes
- Transitions failed because the original four-bar tilt linkage put static torque on the servos, which could stall them. Soft fix: reduce thrust or drop the nose during transition. Permanent fix: a redesigned zero-torque nacelle, now in the repo.
- Hinge pins worked loose from vibration. Fix: glue or knurl them.
- Props struck the nacelles, so tilt servo endpoints had to be adjusted.
- Servos stalled at hard stops, so forward-flight endpoints must be set carefully.
- The tail prop brushed the fins when the structure flexed. A few millimeters of clearance fixed it.
- Vibration at the flight controller produced gyro spikes that caused spontaneous flips. Fix: vibration damping.
- An earlier center-of-gravity diagram was wrong. The corrected CG is 26 to 28 mm from the leading edge.

## Lessons for us
- Static torque in a tilt linkage can stall servos; a zero-torque mechanism removes that load.
- The author reports that a commercial seller reused the design files in violation of the license.
