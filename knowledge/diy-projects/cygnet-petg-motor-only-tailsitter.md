---
id: cygnet-petg-motor-only-tailsitter
title: "3D printed Cygnet VTOL build (motor-only, no control surfaces, PETG version)"
source_url: https://discuss.ardupilot.org/t/3d-printed-cygnet-vtol-build-motor-only-no-control-surfaces-petg-version/142979
source_type: other
creator: Reb1 (display name Reb, signs as Bogdan)
date: 2026-03
retrieved: 2026-11-11
configuration: tailsitter
morphology:
  lift: fixed-wing
  vtol_method: tailsitter
  propulsion_count: 4
  tail: unknown
manufacturing_methods: [3d-print-fdm]
materials: [PETG, LW-PLA]
cost_usd: unknown
cost_source: unknown
wingspan_mm: 1249
mass_g: unknown
outcome: not-flown
outcome_evidence: "Thread shows the builder about 70 percent printed with no flight yet; the designer's own flight results are not stated."
verified: true
---

## What's novel
A copter-style tailsitter with four fixed motors that provide all control, so the design has no elevons or other control surfaces. The 1249 mm wingspan is the designer's original build; the thread follows a second builder printing a PETG version. The printed airframe alone is about 1.6 kg before electronics and battery.

## How it was built
- The entire airframe is 3D printed. The designer used lightweight PLA with two walls on the body and wings.
- The second builder is printing in PETG and reported about 70 percent of the parts printed at the time of the post.
- The design needs no servos for control surfaces, so the build is motor and prop driven.

## Problems and fixes
- PETG is heavier than the designer's material. A commenter estimated roughly 50 percent more weight, so the suggested motors and props may be too small. Suggested fix: run thrust numbers first, or reprint in LW-PLA.
- The landing legs were flagged as a weak point. Suggested fix: reinforce them with a carbon rod and stronger material.
- Rushing into forward flight can make the aircraft unstable on return to hover. Suggested fix: tune the hover modes before attempting transition.

## Lessons for us
- Changing the print material changes the all-up mass enough to affect motor and prop sizing, so check thrust margin before printing the full airframe.
- The thread's advice is to tune hover before transition on a motor-only tailsitter.
