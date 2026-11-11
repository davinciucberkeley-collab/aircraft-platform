---
id: rc-vtol-f35-parkjet
title: "RC VTOL F-35 Parkjet"
source_url: https://hackaday.io/project/180603-rc-vtol-f-35-parkjet
source_type: hackaday
creator: Nick Rehm
date: 2021-07
retrieved: 2026-11-11
configuration: other
morphology:
  lift: fixed-wing
  vtol_method: other
  propulsion_count: unknown
  tail: unknown
manufacturing_methods: [foamboard, laser-cut, 3d-print-fdm]
materials: [foam board, Dollar Tree foam board, 3 mm plywood, 3D-printed plastic hinges and flaperons, glue]
cost_usd: unknown
cost_source: unknown
wingspan_mm: unknown
mass_g: unknown
outcome: flew-successfully
outcome_evidence: "Builder comments on the project page report stable hover and flight without issues; the author posts flight footage, and the author's speed claim is not independently checked."
verified: true
---

## What's novel
A foam-board jet-style VTOL that hovers on a central lift fan plus motors mounted on the ailerons, which the page describes as thrust vectoring. The plans are laser-cut and the page collects builder reports from several people. The author claims speeds over 80 mph, which the page does not verify.

## How it was built
- Parts are laser-cut from foam board using the author's plans, and a no-grid version was added for laser cutters.
- Wing motor mounts are laser-cut from 3 mm plywood.
- Ailerons and flaperons are 3D printed with integrated hinges.
- One builder reported using Dollar Tree foam board for the build.
- The page lists no cost; it links only to parts sources without prices.

## Problems and fixes
- Motors did not arm reliably. The fix was longer delays in setup and extra motor commands with short delays.
- One motor spun faster than the others. Calibration checks were suggested, and the outcome is not confirmed.
- The specified 4-in-1 ESC was unavailable, so builders used single ESCs with a separate BEC.
- Roll oscillation of about 10 Hz in hover. Suggested fix: lower roll P gain by about 10 percent; outcome not stated.
- Paper lifted off the foam when glued. Builders switched to 3D-printed parts.
- An arming failure and a channel that cut motor output were reported with no fix stated.

## Lessons for us
- Plans printed with grid lines interfered with laser cutting, so a version without grid lines was provided.
- Builders reported arming and oscillation problems with the motor-mounted thrust setup, which needed firmware-level fixes.
