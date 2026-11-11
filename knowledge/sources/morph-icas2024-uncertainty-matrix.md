---
id: morph-icas2024-uncertainty-matrix
title: A Morphological Analysis of Methods for Conceptual Aircraft Design under Uncertainties
authors: V.T. Todorov, D. Rakov, A. Bardenhagen
year: 2024
url: https://www.icas.org/icas_archive/icas2024/data/papers/icas2024_1169_paper.pdf
type: paper
retrieved: 2026-11-11
verified: true
---

## Summary
A morphological matrix used to choose a method for conceptual aircraft design under uncertainty, rather than to choose an aircraft configuration. The matrix's rows describe how the design process is set up: data sources, modelling method, elicitation, aggregation and solution-space generation. The paper also reports how the full combination space was reduced by sampling and by removing infeasible pairs.

## Usable rules / numbers
- 14 attribute rows in three groups. Group 1 (system decomposition and modelling): data source (4 options), system modelling (AHP, Bayesian networks, linear regression, neural networks, expert rules), model definition (2), decomposition (3). Group 2 (elicitation): protocol (4), format (3), uncertainty modelling (4: none, intervals, fuzzy numbers, probability distributions), technology evaluation (2), attribute interaction (3). Group 3 (aggregation): aggregation type (4), mathematical aggregation (3), evaluation weighting (3), re-evaluation (2), solution-space generation (3). (Tables 1–3, treated as one matrix.)
- Full combination count is about 16.6 million (product of option counts). (Solution-space section.)
- Pruning: randomly sample 100,000 combinations, keep the 50,000 with the highest total score, then remove impossible option pairs, leaving 5,403 rational solutions. The paper is inconsistent here: the Figure 6 caption gives 11,045. Record both if used.

## How we could use it
- The matrix is about the design process, not the vehicle. Do not copy its rows into the aircraft chart. Its sampling-then-filter step is a reusable method if our chart grows past a few thousand combinations.
- Feeds the process-level notes for the chart (how options are scored and combinations are filtered).
