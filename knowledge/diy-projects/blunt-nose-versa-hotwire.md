---
id: blunt-nose-versa-hotwire
title: "Hot Wire build of the Blunt Nose Versa Wing"
source_url: https://flitetest.com/articles/hot-wire-build-of-the-blunt-nose-versa-wing
source_type: blog
creator: jimmyp39
date: 2016-03
retrieved: 2026-11-11
configuration: flying-wing
morphology:
  lift: flying-wing
  vtol_method: none
  propulsion_count: unknown
  tail: none
manufacturing_methods: [hotwire-foam, other]
materials: [solid foam block, monocoat covering, spars, 1/2 in plywood for the cutter bow, paper templates, reused elevons, fins and electronics from a crashed balsa wing]
cost_usd: unknown
cost_source: unknown
wingspan_mm: unknown
mass_g: 2000   # article says "at 2 kg"; approximate
outcome: flew-with-issues
outcome_evidence: "Wing flew; during an endurance test the elevon control horns pulled out of the foam and the wing dove into the ground."
verified: true
---

## What's novel
A flying wing cut from one solid foam block with a homemade battery-powered hot wire, reusing the servos, elevons, and electronics from a crashed balsa wing. The article is an honest account of a foam wing failing at a control-horn joint.

## How it was built
- Paper templates are screwed to each end of the foam block.
- Hot wire: a 12 V battery with a light switch, a spring to keep the wire taut; heat set by the spacing of the power wires (about 30 in apart was best).
- Vertical cuts use a clamped straight edge as a guide; the narrow end needs about twice the cutting speed.
- Parts are glued up, then spars are installed, then the wing is covered in monocoat.

## Problems and fixes
- Sluggish roll before the crash: cause not stated.
- Elevon control horns pulled out of the foam: reinforced the foam and fitted stronger horns.
- Limited battery room: a new nose about one inch longer was cut.
- Return-to-home failsafe: moved the low-throttle failsafe into the flight controller instead of setting it through the radio link.
- Later flight of 33 minutes; author estimates 40 to 45 minutes total and recommends a 40-minute limit.

## Lessons for us
- The failure was at the control-horn anchor in foam, so the anchor point is the first thing to reinforce in a foam wing.
- The author says hot-wire cutting takes practice; no time or cost figure is given.
