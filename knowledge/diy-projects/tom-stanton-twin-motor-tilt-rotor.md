---
id: tom-stanton-twin-motor-tilt-rotor
title: "Optimising a RC Tilt Rotor VTOL"
source_url: https://hackaday.com/2022/08/22/optimising-a-rc-tilt-rotor-vtol/
source_type: hackaday
creator: Tom Stanton
date: 2022-08
retrieved: 2026-11-11
configuration: tiltrotor
morphology:
  lift: fixed-wing
  vtol_method: tiltrotor
  propulsion_count: 2
  tail: unknown
manufacturing_methods: [3d-print-fdm, other]
materials: [carbon fiber tube, lightweight foaming PLA, fiberglass-reinforced plastic sheet, PLA brackets, Teensy flight controller]
cost_usd: unknown
cost_source: unknown
wingspan_mm: unknown
mass_g: unknown
outcome: flew-with-issues
outcome_evidence: "Article reports flight in hover and forward flight on the first attempt, with trouble slowing down during transition back to hover and no fix stated."
verified: true
---

## What's novel
A twin-motor tilt-rotor in which the tilting motors also provide yaw and roll control in forward flight, so there is no separate yaw control in cruise. A high-torque servo drives the motor mounts through a printed gear mechanism. The wing is a NACA 4412 section printed in foaming PLA.

## How it was built
- The wing is printed in lightweight foaming PLA using vase mode, with the surface and ribs printed as one continuous line.
- Carbon fiber tubes form the wing spars and tail boom.
- The fuselage uses printed brackets and a 1 mm fiberglass-reinforced plastic sheet.
- A Teensy flight controller runs dRehmFlight firmware.

## Problems and fixes
- Matte black wings warped in sunlight. Fixed by reprinting them in white.
- Lightweight PLA oozed when extrusion stopped. Fixed by printing the wing surface and ribs as one continuous path.
- Trouble slowing down during transition back to hover. The article does not state a fix.

## Lessons for us
- Print color affected warping in sunlight for this foam PLA wing.
- The article credits the tilting motors with providing yaw and roll control in forward flight.
