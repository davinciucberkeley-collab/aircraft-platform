---
id: show-hn-3d-printed-lift-cruise-drone
title: "I made a 3D printed VTOL drone"
source_url: https://hn.svelte.dev/item/44241278
source_type: other
creator: tsungxu
date: unknown
retrieved: 2026-11-11
configuration: lift-plus-cruise
morphology:
  lift: fixed-wing
  vtol_method: lift-plus-cruise
  propulsion_count: 5
  tail: unknown
manufacturing_methods: [3d-print-fdm, other]
materials: [foaming PLA, PETG, carbon fiber tube, carbon spar, cyanoacrylate glue]
cost_usd: 700
cost_source: stated
wingspan_mm: 1200
mass_g: 2550
outcome: flew-with-issues
outcome_evidence: "Post says the airframe has crashed and been rebuilt at least once; the range and endurance claims come with no test data shown."
verified: true
---

## What's novel
A 1.2 m printed VTOL with four lift motors for hover and a separate cruise motor for forward flight, built by one person on a consumer printer. The author claims long range and endurance, but the post shows no test data for either. The original write-up on the author's blog is linked from the post; I did not open it.

## How it was built
- Structural parts printed in foaming PLA and PETG on a consumer printer; the wings were printed in four sections.
- Wing sections were joined with carbon spars and cyanoacrylate glue rather than printed as one piece.
- Booms and spars are carbon fiber, which keeps the structure stiff at low mass.
- Stated cost is about $700 excluding the battery. The post gives the battery price as a range of roughly $700 to $1,350, so the total is not a single figure.

## Problems and fixes
- Foaming PLA is brittle and has weak impact resistance. The author suggests dovetails or clips for printed sections in future builds.
- Weight was the priority, so tougher materials such as ASA were avoided. The printer also struggles with ASA.
- The airframe has crashed and been rebuilt at least once.
- Commenters found the ArduPilot setup hard to use and suggested an alternative configuration tool.

## Lessons for us
- Splitting large printed wings into joinable sections keeps each print within a small printer's bed.
- The range and endurance claims are unverified in the source; treat them as the author's claims.
