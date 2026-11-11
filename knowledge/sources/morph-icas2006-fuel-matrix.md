---
id: morph-icas2006-fuel-matrix
title: An Algorithmic Morphology Matrix for Aircraft Fuel System Conceptual Design
authors: Hampus Gavel, Johan Ölvander, Björn Johansson (Saab Aerosystems; Linköping University)
year: 2006
url: https://icas.org/ICAS_ARCHIVE/ICAS2006/PAPERS/037.PDF
type: paper
retrieved: 2026-11-11
verified: true
---

## Summary
A conceptual-design paper for a combat-aircraft fuel system (reference case: a Saab fighter). The fuel system is split into subfunctions, each with alternative solution principles laid out as a morphological matrix. Each option carries simple mathematical models (weight, cost, power, reliability), so concepts can be scored and screened in a spreadsheet rather than by judgement alone. It is a subsystem example, not a whole-aircraft chart.

## Usable rules / numbers
- Chart rows are subfunctions, columns are options. Rows for a fighter fuel system: engine feed (3 options: negative-g tank, hopper tank with jet pumps, negative-g accumulator); transfer for fuselage, wing and drop tank (5: distributed pump, inline pump, jet pump, gravity, siphoning); vent and pressurization (3: closed, ejector, non-pressurized); measurement (3: level sensor, tank probe, both); refueling (3: pressurized, gravity, air-to-air); fire protection for fuselage/wing and for drop tank (4 each: SAFOM, OBIGGS, liquid nitrogen, none). (Figure 7 of the paper.)
- Method: build the matrix with a model per option, enter top-level requirements (altitude, dive rate, load factor, fuel density), set design parameters, then pick exactly one option per row and read the summed outputs. (Section on the matrix method.)
- Trade study: rerun with a different objective (e.g. low weight vs robustness) or different requirements, then compare the concepts. (Section on the matrix method.)
- Pruning is manual screening: poor concepts are dropped by rough assessment and approximate calculations before deeper analysis. The paper gives no formal pruning algorithm; optimisation and Pareto methods are described as future work.

## How we could use it
- Pattern to copy for the chart: one row per subfunction, one option picked per row, a model per option, then screening. Use it for the subsystem rows of the VTOL chart (e.g. energy storage, landing gear), not for the airframe rows.
- Feeds the concept-screening step, before any sizing step runs.
