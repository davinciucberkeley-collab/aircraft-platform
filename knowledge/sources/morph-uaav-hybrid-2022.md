---
id: morph-uaav-hybrid-2022
title: Design Conception and Evaluation of an Unmanned Amphibious Aerial Vehicle Using Systematic Approach
authors: Surendar Ganesan, Balasubramanian Esakki, Silambarasan Mathiyazhagan, Vikram Pandimuthu
year: 2022
url: https://bme.vgtu.lt/index.php/Aviation/article/download/16519/11044
type: paper
retrieved: 2026-11-11
verified: true
---

## Summary
Concept design of a hybrid unmanned amphibious aerial vehicle that combines a multirotor with a hovercraft-style skirt. A morphological chart (Figure 4) generates configurations from four design variables. Pairs of options are scored for compatibility, the compatible combinations are grouped into concept models, and the models are then ranked with weighted decision methods and checked with CFD and FEA.

## Usable rules / numbers
- Four chart rows, with options: hull type (5: ellipse, square, box, rectangular, circular; Table A1); skirt type (5: open, bag, finger, segmented, pericell); lifting system (2: axial, centrifugal); multirotor frame (4: quad-plus, quad-X, quad-H, quad-V). Up to 5 × 5 × 2 × 4 = 200 combinations. (Figure 4 and Table A1.)
- Compatibility: every option pair is scored by the team as 1.0 (consistent), 0.5 (partly consistent) or 0.0 (inconsistent). (Table A1.)
- Concept models are built from compatible combinations. Each model's score is the sum of its pair scores, ranging 3.0 to 4.0. Thirteen models (CM 1–13) were kept. (Table A2.)
- Screening: an expert committee reviewed the models, then Pugh's method with criteria weighted 1–10 and models scored 1–5. Only models above a 75% design-requirement satisfaction threshold passed (CM 11: 86.7%, CM 12: 82.0%, CM 13: 86.3%). TOPSIS broke ties. (Sections on concept selection.)
- Final: CFD and FEA on the three finalists; CM 11 chosen as baseline.

## How we could use it
- Shows a full pruning loop: pairwise compatibility matrix, then combine into models, then weighted screening. Use this as the template for the chart's compatibility step.
- Its rows are shape and frame options for a hybrid UAV, so only the frame and lifting-system rows transfer directly to a small electric VTOL chart.
