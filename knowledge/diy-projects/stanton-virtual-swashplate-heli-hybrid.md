---
id: stanton-virtual-swashplate-heli-hybrid
title: "Tom Stanton Built a Drone-Helicopter Hybrid with a Virtual Swashplate"
source_url: https://www.hackster.io/news/tom-stanton-built-a-drone-helicopter-hybrid-with-a-virtual-swashplate-0c5d574fd2af
source_type: blog
creator: Tom Stanton (article by Cameron Coward)
date: unknown
retrieved: 2026-11-18
configuration: other
morphology:
  lift: other
  vtol_method: other
  propulsion_count: 2
  tail: other
manufacturing_methods: [3d-print-fdm]
materials: [3D-printed hinges]
cost_usd: unknown
cost_source: unknown
wingspan_mm: unknown
mass_g: unknown
outcome: unknown
outcome_evidence: "Article says the aircraft is a practical way to fly and is fun to watch, but does not state a flight test or result."
verified: true
---

## What's novel
A drone-helicopter hybrid with one main rotor and one tail rotor, each driven by its own motor. Blade pitch changes come from 3D-printed hinges instead of a conventional swashplate and servos. The idea was inspired by a virtual swashplate concept from University of Pennsylvania researchers.

## How it was built
- The main rotor motor carries a sensor that reports its position twice per revolution, so the controller can time speed changes precisely.
- Only the 3D-printed hinges are named as custom hardware in the article.

## Problems and fixes
- None reported in the article.

## Lessons for us
- Motor-driven pitch control with printed hinges removes the swashplate and its servos, which cuts parts for a rotor-based VTOL.
- Position feedback from the main motor is what makes the timing work; plan for that sensor in any similar design.
