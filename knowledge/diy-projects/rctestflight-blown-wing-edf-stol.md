---
id: rctestflight-blown-wing-edf-stol
title: "Blown wing RC plane (rctestflight)"
source_url: https://hackaday.com/2025/08/02/this-plane-flies-slow-because-its-wings-really-blow
source_type: hackaday
creator: rctestflight (Daniel Riley); article by Tyler August
date: 2025-08
retrieved: 2026-11-18
configuration: other
morphology:
  lift: fixed-wing
  vtol_method: none
  propulsion_count: 2
  tail: unknown
manufacturing_methods: [cnc, other]
materials: [pink XPS foam, foamboard, carbon fiber, Depron foam, packing tape]
cost_usd: unknown
cost_source: unknown
wingspan_mm: unknown
mass_g: unknown
outcome: flew-with-issues
outcome_evidence: "Article says it flew with a very short takeoff distance; it also reports that the fan-only control scheme was not trusted and ailerons were added."
verified: true
---

## What's novel
A radio-controlled fixed wing in which two electric ducted fans blow air into a plenum cut into the foam wing. The air leaves through a carbon-reinforced slot on each wing's upper surface, adding lift, thrust and control. It is a short-takeoff design, not a vertical takeoff aircraft.

## How it was built
- Wings are CNC-routed pink foam, per a separate TechEBlog write-up of the same build (techeblog.com/custom-blown-wing-airplane/).
- A carbon fiber plate covers the air slot and is epoxied and vacuum-bagged.
- The fuselage is Depron foam reinforced with packing tape to survive crashes.

## Problems and fixes
- Fans draw a lot of power. A 6-cell 2200 mAh pack lasts only a few minutes.
- Much of the thrust goes into lift rather than forward motion, and the builder is concerned about motor burnout.
- The builder first relied on differential fan speed alone for control, then added ailerons for stability.
- The builder wonders whether a conventional wing with tilted fans would need less power.

## Lessons for us
- Blown-wing lift is a short-takeoff option, but the power budget is high; size the battery for minutes, not endurance.
- Keep conventional control surfaces as a backup to differential thrust.
