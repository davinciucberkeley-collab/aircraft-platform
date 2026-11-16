# Brief B6c: validator limitation (b): parts linked to an articulated child (Haiku builder, after the conductor accepts the spec)

Decision needed first (conductor): see the conductor decisions in the T8 report. This brief is only for the option "skip interference between a linked part and the moved subtree".

Exact output: edit `core/aircraft_platform/checks.py` and `schema/plane.schema.json` so an attachment may carry `kinematic_link: true`; the pose and range-sweep interference test then skips pairs where one part is a child of a `kinematic_link` attachment and the other is in the articulated subtree. Add `tests/test_kinematic_link.py`.

Exact inputs: `designs/concept-a/validator-comparison.md` rows "Interference (elevon limits)"; source `redesign/qp/A/cad/out/REPORT.md` lines "Not checked against the moved parts (linkage path not modelled)".

Pass check: `python3 -m pytest -q` green and `plane validate designs/example-tailsitter-wing` exits 0.

Stop rule: if the schema change needs a version bump decision, stop and report; do not choose the version.
