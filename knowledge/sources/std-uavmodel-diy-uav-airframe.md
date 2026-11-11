---
id: std-uavmodel-diy-uav-airframe
title: DIY UAV Airframe Design: Wing Loading, Aspect Ratio, and Stability Calculations
authors: uavmodel.com (blog, author not stated on page)
year: unknown
url: https://blog.uavmodel.com/diy-uav-airframe-design-wing-loading-aspect-ratio-and-stability-calculations/
type: website
retrieved: 2026-11-11
verified: true
---

## Summary
Hobbyist design blog for DIY UAVs covering wing loading, aspect ratio and static stability. Its stability section gives a practical static-margin window for small UAVs and frames it as a rule of thumb. It also notes a worked flying-wing example.

## Usable rules / numbers
- [static_margin] Recommended static margin for a DIY UAV is 5 to 15 percent (section "Static Stability: Designing an Aircraft That Flies Itself", under "Longitudinal Static Stability").
- [static_margin] Margin below 5 percent is described as twitchy; above 20 percent as sluggish (same section).
- [static_margin] Worked flying-wing example: a 10 percent static margin puts the CG at 0.424 MAC, about 42 percent back from the leading edge of the MAC (section "Finding the Neutral Point"). The neutral point used is 0.524 MAC.

## How we could use it
- Supports keeping static_margin at 0.05 to 0.15 for small UAV / flying-wing cruise checks, as a non-authoritative blog.
- The 42 percent example shows the relation between margin and CG position; usable as a test case for the validator.
