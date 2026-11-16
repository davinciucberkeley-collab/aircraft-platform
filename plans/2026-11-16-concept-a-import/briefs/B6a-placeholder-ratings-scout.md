# Brief B6a: scout the 22 placeholder joint ratings (Haiku scout, briefing mode)

Role: scout. Fixed template only; no opinions. Not blocking: designs/concept-a already validates tier 0.

Exact output: `knowledge/sources/dbf-concept-a-joint-capacities.md` (new file), one table, columns
`edge | via | what the source says (quote, <= 25 words) | file:line | value N or "none found"`.

Exact inputs (read only, do not write there):
- edge ids: the 22 rows with `"kind": "placeholder"` in `designs/concept-a/import-report.json` (key `ratings`).
- search only these files under `/home/claude/davinciucberkeley-collab/dbf-combined/redesign/qp/A/`:
  `structures/structures_run.md`, `structures/iter2_margins.md`, `structures/foam_103.md`, `structures/qp5_checks.md`,
  `structures/arm_cup_checks.md`, `cad/amodel/*.py` (the EDGES notes), `cad/out/BOM-A.csv`.

Rules: quote only text you opened; if a file has no capacity for the edge, write `none found` (do not estimate, do not look elsewhere).

Pass check: `grep -c '^| E-' knowledge/sources/dbf-concept-a-joint-capacities.md` prints 22.

Stop rule: if a listed file does not exist, stop and report the path; do not substitute another file.
