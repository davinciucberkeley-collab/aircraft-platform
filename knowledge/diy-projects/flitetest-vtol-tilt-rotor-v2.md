---
id: flitetest-vtol-tilt-rotor-v2
title: "VTOL Tilt-rotor V2"
source_url: https://flitetest.com/articles/vtol-tilt-rotor-v2
source_type: blog
creator: "Flite Test"
date: unknown
retrieved: 2026-11-18
configuration: tiltrotor
morphology:
  lift: fixed-wing
  vtol_method: tiltrotor
  propulsion_count: 2
  tail: unknown
manufacturing_methods: [other]
materials: [EPP foam, foam sheet, aluminium spar, fibreglass dihedral section, SunnySky x2216-8 1250kv motors, BMS-630MG tilt servos, TGY-9018MG servos, KK2.1 flight controller, Openaero2 VTOL firmware]
cost_usd: unknown
cost_source: unknown
wingspan_mm: 900
mass_g: 1285
outcome: flew-successfully
outcome_evidence: "Page lists hover tests, a maiden flight, forward flight, aerobatics and a stall test, and says no crash is reported."
verified: true
---

## What's novel
A tilt-rotor hobby build where the motors sit on the wingtips and tilt in a V-22 style layout. The article, written by a builder named tomstanton, is a second attempt that follows an earlier proof of concept and aims for better hover and forward flight.

## How it was built
- The fuselage is EPP foam profile, made from 2 cm sheets glued into a 4 cm-wide body.
- The wing uses outer halves from a commercial flying wing, with an aluminium spar and a fibreglass dihedral section.
- Tilt servos are separate from the rest of the control servos, and the flight controller runs VTOL firmware on a KK2.1 board.

## Problems and fixes
- The EPP fuselage is flexible and needs reinforcing, which gives spongy control.
- High gains cause servo shaking in hover.
- Yaw control is hard in turns, and the motors point downward in forward flight.
- The article's body text gives an airframe weight of 870 g without the battery, which does not match the spec sheet. The 1285 g total above comes from the spec sheet.
- The page gives no overall cost, and a reader's question about cost went unanswered.

## Lessons for us
- A lightweight EPP fuselage flexes, so a tilt-rotor build needs a stiffer spine or spar before tuning gains.
- Tilt-rotor hover and forward flight both ran on a single VTOL-capable flight controller, which is one way to avoid a second controller.
