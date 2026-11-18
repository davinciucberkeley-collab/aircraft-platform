---
id: rocketman1092-f35b-hover-frame
title: "The Road to a VTOL R/C F-35B"
source_url: https://flitetest.com/articles/the-road-to-a-vtol-r-c-f-35b
source_type: blog
creator: Rocketman1092
date: 2020-06
retrieved: 2026-11-18
configuration: lift-plus-cruise
morphology:
  lift: fixed-wing
  vtol_method: lift-plus-cruise
  propulsion_count: unknown
  tail: other
manufacturing_methods: [3d-print-fdm, other]
materials: [wood dowels, printed plastic, foam]
cost_usd: unknown
cost_source: unknown
wingspan_mm: unknown
mass_g: unknown
outcome: flew-with-issues
outcome_evidence: "Article reports the hover frame hovered, first on a KK2 and later on ArduPilot, and that the test airframe made a first fixed-wing flight; transitions were still planned."
verified: true
---

## What's novel
An R/C F-35B-style VTOL built around a main fan and a lift fan, with roll control from two small thrusters. Yaw comes from tricopter-style thrust vectoring rather than differential motor torque. The project was shelved for years and restarted once ArduPilot had VTOL support.

## How it was built
- The hover test frame is wood dowels with printed plastic parts.
- The forward-flight airframe began as a scaled foam F-35 and became a test airframe with non-scale wings and a boom-mounted tail, bolted to the hover frame.
- A printed three-bearing swivel module (3BSM) was redesigned to be lighter and lower friction.

## Problems and fixes
- Thrust was too low: two 90 mm fans only hovered near full power. Fixed by upgrading to larger fans and stronger motors.
- Roll authority was too low: valves and ducts could not handle wind. Replaced by small dedicated motors and later larger fan units.
- ArduPilot did not default to this frame class, so the author modified the firmware for the F-35B layout.
- The KK2 controller was replaced with a Matek F765-Wing running ArduPilot.

## Lessons for us
- Roll control built from ducts and valves failed outdoors; use dedicated thrust for roll.
- Lift-fan layouts need custom ArduPilot frame setup, so budget time for firmware work.
