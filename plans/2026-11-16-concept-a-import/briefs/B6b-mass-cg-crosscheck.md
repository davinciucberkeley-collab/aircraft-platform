# Brief B6b: mass and CG cross-check (Haiku builder)

Exact output: print to stdout, no file in the repo.

Exact inputs: `designs/concept-a/plane.yaml`, `/home/claude/davinciucberkeley-collab/dbf-combined/redesign/qp/A/params-A.json` (keys `mass.basic_cad_kg`, `mass.cg_x_mm`, `mass.cg_y_mm`), and the output of `plane mass designs/concept-a`.

Task: print four lines: sum of component `mass_g` from plane.yaml; `mass.basic_cad_kg` x 1000; CG x and y from `plane mass`; `mass.cg_x_mm` and `mass.cg_y_mm`. Use `python3 -I` with a script in the scratchpad.

Pass check: the two masses agree to 0.01 g; CG x differs by <= 0.1 mm and CG y by <= 0.05 mm (expected 20.46 vs 20.51 and 2.38 vs 2.40). Report the actual numbers.

Stop rule: if a key is missing, stop and report the key; do not substitute another number.
