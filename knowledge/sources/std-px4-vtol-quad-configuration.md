---
id: std-px4-vtol-quad-configuration
title: Generic Standard VTOL (QuadPlane) Configuration & Tuning (PX4 documentation)
authors: PX4 development team
year: unknown
url: https://docs.px4.io/main/en/config_vtol/vtol_quad_configuration.html
type: website
retrieved: 2026-11-11
verified: true
---

## Summary
Official PX4 guide to configuring a standard VTOL quadplane. It covers pusher and puller throttle behavior in transition. It gives no numeric hover thrust-to-weight or hover throttle guidance.

## Usable rules / numbers
- [hover_thrust_to_weight_min] None. The page gives no thrust-to-weight or hover-throttle figure for the multicopter motors.
- [hover_thrust_to_weight_min] Only throttle figure is a forward-transition slew rate default of 0.33, meaning about 3 seconds to ramp to full pusher throttle (pusher/puller section). Not relevant to hover sizing.

## How we could use it
- Does not support or change hover_thrust_to_weight_min. Confirms no official PX4 default for this value was found.
