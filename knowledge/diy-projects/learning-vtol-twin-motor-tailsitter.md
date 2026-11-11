---
id: learning-vtol-twin-motor-tailsitter
title: "Learning VTOL Tailsitter"
source_url: https://discuss.ardupilot.org/t/learning-vtol-tailsitter/126754
source_type: other
creator: dpapworth (forum username; real name not stated)
date: 2024-11
retrieved: 2026-11-11
configuration: tailsitter
morphology:
  lift: flying-wing
  vtol_method: tailsitter
  propulsion_count: 2
  tail: unknown
manufacturing_methods: [foamboard, other]
materials: [foam board, carbon rod, flat foam sheet with KFM airfoil, parts-bin electronics]
cost_usd: unknown
cost_source: unknown
wingspan_mm: unknown
mass_g: 315
outcome: flew-with-issues
outcome_evidence: "Thread shows quad-style hovers, a first forward transition with oscillation, a tumble on descent, and a v2 airframe that still struggled to hover in breezy conditions."
verified: true
---

## What's novel
A small twin-motor tailsitter with fixed motors and no tilt mechanism, built from carbon-rod-reinforced foam board and parts-bin components. The thread is an open log of the builder working through oscillation, center-of-gravity and descent problems. The all-up weight is about 315 g on a 4S 650 mAh battery.

## How it was built
- Carbon rod reinforces a foam board wing with a flat foam sheet and a KFM airfoil.
- The builder used parts-bin components and chose not to 3D print.
- Early hovers used 2400kv motors from another project.
- Propellers changed from 4023 to 5-inch 3-blade to help center of gravity and hover.

## Problems and fixes
- Log dropouts appeared early and were absent on a later flight; the cause is unknown.
- Compass calibration was forgotten before flights; the builder planned to calibrate before each flight.
- Pitch oscillation improved after lowering the pitch rate limit, first to 130 and then to 125.
- The center of gravity was off-center. A small battery pod on the nose and the larger props helped.
- The aircraft tumbled during low-throttle descent in VTOL mode. Switching to QHOVER did not help. The v2 airframe with larger elevons had mixed results.
- An expert said the aircraft was extremely underpowered and was running into motor saturation.

## Lessons for us
- An expert advised tuning the VTOL modes before running the fixed-wing autotune.
- Thrust margin and motor saturation were the main constraints the thread identifies.
