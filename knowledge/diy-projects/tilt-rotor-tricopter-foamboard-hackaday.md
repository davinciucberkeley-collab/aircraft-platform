---
id: tilt-rotor-tricopter-foamboard-hackaday
title: "Tilt Rotor VTOL RC aircraft"
source_url: https://hackaday.io/project/163509-tilt-rotor-vtol-rc-aircraft
source_type: hackaday
creator: "Nick (hackaday.io user nstiesi); Asif Kareem is also listed on the team"
date: 2019-01
retrieved: 2026-11-11
configuration: tiltrotor
morphology:
  lift: flying-wing
  vtol_method: tiltrotor
  propulsion_count: 3
  tail: none
manufacturing_methods: [foamboard, 3d-print-fdm, other]
materials: [paper-lined foam board, polyurethane sealant, bamboo skewers, heat-shrink tubing, PLA, aluminum, zip ties, Velcro, hot glue, KK2 flight controller]
cost_usd: unknown
cost_source: unknown
wingspan_mm: unknown
mass_g: unknown
outcome: flew-with-issues
outcome_evidence: "Project log shows hover testing and PID tuning completed on one date; the forward transition was not yet demonstrated."
verified: true
---

## What's novel
A tailless tri-rotor whose two front rotors tilt 90 degrees between hover and forward flight. The airframe is built mostly from dollar-store foam board and bundled bamboo booms, with printed gears for the tilt mechanism. The log lists airframe materials at about $2; total build cost is not stated.

## How it was built
- The airframe is paper-lined foam project board, sealed with polyurethane for dew protection.
- The booms are seven bamboo skewers bundled and held with heat-shrink tubing, with no adhesive.
- Tilt gears are printed slowly with a 0.2 mm nozzle on a clone printer, and the tilt ratio is 1:1.
- Stated cost: airframe materials about $2. Total cost not stated.

## Problems and fixes
- Earlier prints came out with misshapen gear teeth. Printing very slowly with a 0.2 mm nozzle fixed it.
- The author worried a high gear ratio would pass damaging torque to the servo in a hard landing, so a 1:1 ratio was used.
- Boom rigidity was acceptable for now. Future designs may add adhesive inside the bundle or use a carbon tube.
- The FrSky receiver needed a home-built signal inverter for serial output.
- Outdoor testing waited for a low-wind day.

## Lessons for us
- A 1:1 tilt ratio gave enough servo travel and avoided the torque concern the author raised.
- Serial receiver outputs can need a simple inverter, so check the protocol before wiring.
