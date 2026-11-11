---
id: eclipson-e-vtol-dual-motor-tailsitter
title: "Eclipson E-VTOL, 3D printable dual motor tailsitter"
source_url: https://discuss.ardupilot.org/t/eclipson-e-vtol-3d-printable-dual-motor-tailsitter
source_type: other
creator: Satoru Sasaki
date: 2022-01
retrieved: 2026-11-11
configuration: tailsitter
morphology:
  lift: flying-wing
  vtol_method: tailsitter
  propulsion_count: 2
  tail: none
manufacturing_methods: [3d-print-fdm]
materials: [ColorFabb lightweight foaming PLA, TPU]
cost_usd: unknown
cost_source: unknown
wingspan_mm: 1065
mass_g: 800
outcome: flew-with-issues
outcome_evidence: "Thread reports hover and transition testing, several crashes and a broken prop, and a yaw drift after transition that was still unresolved at the last post."
verified: true
---

## What's novel
A tailless dual-motor tailsitter printed in foaming PLA that hovers and transitions using ArduPilot quadplane modes. The author's test build is about 800 g with a 3S battery. The thread is a long tuning log rather than a finished design.

## How it was built
- Printed in lightweight foaming PLA, with TPU used for tires, wing bands and motor mounts.
- Assembly is print-and-glue with no sanding, according to the author.
- Parts were printed one at a time because the foaming material strings badly when several print together.
- Two motors with 8x4.3 props; control is by elevons on a flying wing.

## Problems and fixes
- Elevons saturated during hover moves. Fixes tried: a longer servo arm, faster servos (one was suggested), and a higher servo rate. A servo lock during one flight caused a crash, so the settings were backed off.
- Fast descent in QHover was unstable. The fix was a lower descent velocity limit.
- Roll and yaw in wind were addressed by changing thrust mix limits and yaw gain. The author reported no unexpected yaw in wind after that.
- Yaw drift after the switch from QHover to forward flight was still unresolved at the last post. The author suspected differential thrust compensation.
- Several crashes and a broken prop during tuning, and several airframes were rebuilt.

## Lessons for us
- Hover tuning drove most of the parameter and hardware changes before transition was attempted.
- Printing parts one at a time avoided a stringing problem with the foaming material.
