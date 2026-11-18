---
id: nzge-sova-tilt-rotor-drone
title: "Tilt-rotor drone (Sova-inspired)"
source_url: https://nzge.github.io/projects/drone.html
source_type: other
creator: Nathan Ge
date: unknown
retrieved: 2026-11-18
configuration: tiltrotor
morphology:
  lift: multirotor
  vtol_method: tiltrotor
  propulsion_count: unknown
  tail: unknown
manufacturing_methods: [unknown]
materials: [unknown]
cost_usd: unknown
cost_source: unknown
wingspan_mm: unknown
mass_g: unknown
outcome: unknown
outcome_evidence: "Build log has one entry (2-25-25) reporting the IMU works but the gyro drifts; the page does not say whether the drone flew."
verified: true
---

## What's novel
A tilt-rotor drone in which servos tilt the brushless motors for thrust vectoring. Motor selection came from rough thrust calculations. The control stack splits duties across a Teensy 4.0 for low-level stabilisation, a Raspberry Pi Pico as a relay, and a Raspberry Pi 5 running a web GUI.

## How it was built
- Thrust calculations are kept in a Google Colab notebook in the project's GitHub repo.
- A wiring schematic is provided as an SVG in the repo.
- Power is from a LiPo battery with a UBEC stepping down for the controllers.

## Problems and fixes
- Gyro drift on the MPU6050 IMU is the one documented problem. The page describes calibration, a low-pass filter and sensor-fusion options, but does not confirm the drift was resolved.

## Lessons for us
- Split stabilisation from the telemetry and GUI computer so a GUI crash does not affect the flight loop.
- Keep thrust calculations and wiring in the repo next to the firmware so the design can be re-checked.
