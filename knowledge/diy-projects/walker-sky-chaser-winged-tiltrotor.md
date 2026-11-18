---
id: walker-sky-chaser-winged-tiltrotor
title: "New full scale unmanned winged tiltrotor VTOL (Sky Chaser)"
source_url: https://discuss.ardupilot.org/t/new-full-scale-unmanned-winged-tiltrotor-vtol/78146
source_type: other
creator: William Walker
date: 2021-11
retrieved: 2026-11-18
configuration: tiltrotor
morphology:
  lift: fixed-wing
  vtol_method: tiltrotor
  propulsion_count: 4
  tail: unknown
manufacturing_methods: [foamboard, other]
materials: [foam board, hot glue]
cost_usd: unknown
cost_source: unknown
wingspan_mm: unknown
mass_g: unknown
outcome: flew-with-issues
outcome_evidence: "Thread reports the 1/6 scale model and full-scale vehicle hovered indoors in February 2022 after tuning, with later pitch oscillations reported in March 2022."
verified: true
---

## What's novel
An unmanned, full-scale winged tiltrotor where the body is the wing. Two front motors tilt for forward flight, and two coaxial counter-rotating motors behind the cockpit push thrust through a hole in the body. The vehicle is also meant to be amphibious and has four large wheels with steerable front wheels. The forum post describes the full-scale vehicle as roughly 150 lb; no measured mass is given.

## How it was built
- A 1/6 scale model was built from foam board and hot glue to test lift and tail behaviour.
- Four large batteries (about 60 lb total) power the vehicle, with a 28S 300A ESC mentioned.
- Flight controller is a Pixhawk Cube Orange running ArduPilot Plane/Quadplane firmware.

## Problems and fixes
- November 2021: would not lift off in VTOL mode because the rear coaxial pair could not lift the tail.
- January 2022: the real cause was a vacuum under the side panels. Taping foam sheeting inside the panels confirmed it; the vehicle then hovered at about 60% throttle.
- Roll was unstable with heavier batteries; Roll P was already at its maximum.
- Tilting the front motors in hover was unstable in QLOITER; Stabilize worked but throttle then controlled tilt.
- February 2022: after pivoting on the CG to tune it, the vehicle hovered stably indoors; 90% charged batteries used because a rear ESC had caught fire earlier.
- March 2022: after moving from Plane 4.0.9 to 4.2 beta, pitch oscillations grew with elevator pulses during hover; motors briefly cut out at 80% battery.

## Lessons for us
- Check for suction under the body before assuming a control-tuning fault; it can block takeoff.
- Battery and ESC power levels can cause thermal and cut-out faults; keep a conservative charge limit during tuning.
- Forum logs from the author show a longer tuning path than the vehicle's first hover suggests.
