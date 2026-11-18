---
id: std-pollet-2022-common-framework-vtol-uav
title: A common framework for the design optimization of fixed-wing, multicopter and VTOL UAV configurations
authors: Félix Pollet, Scott Delbecq, Marc Budinger, Jean-Marc Moschetta, Jonathan Liscouët
year: 2022
url: https://www.icas.org/icas_archive/ICAS2022/data/papers/ICAS2022_0383_paper.pdf
type: paper
retrieved: 2026-11-18
verified: true
---

## Summary
ICAS 2022 conference paper that defines one sizing framework for fixed-wing, multicopter and VTOL UAV configurations. Its propulsion sizing uses two thrust-to-weight equations (hover and takeoff) and a table of mission parameters. The text gives a hover ratio with no margin, and a takeoff acceleration for the fixed-wing VTOL case.

## Usable rules / numbers
- [hover_thrust_to_weight_min] Eq. 4a (p. 4): hover thrust-to-weight for multirotor equals 1. No margin is included.
- [hover_thrust_to_weight_min] Eq. 4b (p. 4): takeoff thrust-to-weight equals 1 plus a_to/g, where a_to is the vertical takeoff acceleration. Table 4 gives 0.3 g for FW-VTOL (p. 15). Using Eq. 4b, this implies about 1.3 for that case. The 1.3 is this scout's arithmetic, not a value the paper states.
- [landing_load_factor] None.
- Note: the text extraction garbles some subscripts in Eq. 4a and 4b. Check against the original PDF before quoting.

## How we could use it
- Gives an explicit physical link between takeoff acceleration and thrust-to-weight (T/W = 1 + a/g). If the team adopts a takeoff acceleration target, this gives the matching thrust-to-weight.
- Supports the 1.2-1.3 range only as derived arithmetic. Does not support a landing load factor.
