---
id: morph-ceas2017-morphing-wings
title: Morphological Design and Analysis of Aircraft Wings
authors: Jakub Drzewoszewski, Cristinel Mares (Brunel University London)
year: 2017
url: https://www.fzt.haw-hamburg.de/pers/Scholz/ewade/2017/CEAS2017/289-final.pdf
type: paper
retrieved: 2026-11-11
verified: true
---

## Summary
A CEAS 2017 paper that applies Zwicky's morphological analysis to morphing wings for a subsonic UAV benchmark (RQ-21A class). It builds a five-dimension morphological box, then uses a pairwise cross-consistency assessment (CCA) to remove infeasible combinations. The remaining options are shortlisted and checked with XFOIL and XFLR5 across mission segments.

## Usable rules / numbers
- Five chart rows (Table 3), with options: fuselage count (3: none/flying wing, one, two); aerofoil morphing (4: none, leading-edge, trailing-edge, entire camber); planform span morphing (3: none, uniform, non-uniform); planform sweep morphing (4: none, forward, backward, asymmetric/oblique); out-of-plane morphing (4: none, straight dihedral, tip dihedral, gull). Box = 3 × 4 × 3 × 4 × 4 = 576 solutions.
- Cross-consistency: a pairwise matrix marks each option pair compatible (1) or not (0). This removes 264 combinations, leaving 312. (Table 4.)
- Further pruning: keep the 156 compatible with a one-fuselage type. Drop the non-morphing options, leaving 36 for one fuselage (the paper states 72 when the two-fuselage case is included). These feed a shortlist of 12 candidates.
- Shortlisted candidates are compared on non-dimensional aerodynamic metrics per mission segment.

## How we could use it
- Shows the cross-consistency step (pairwise 0/1 matrix) applied to a morphological box, which we need to prune the VTOL chart.
- Its rows are about morphing and fuselage count, so only fuselage count and wing morphing are useful as optional rows for a small electric VTOL chart.
