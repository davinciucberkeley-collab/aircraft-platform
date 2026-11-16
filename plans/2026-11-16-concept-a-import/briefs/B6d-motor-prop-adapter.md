# Brief B6d: validator limitation (b): motor to prop through an adapter (Haiku builder, after the conductor accepts the spec)

Decision first (conductor): `T1.motor_has_prop` accepts only a propeller attached directly to the motor. Concept A has motor -> adapter (PRP-004) -> prop (E-PRP-10, E-PRP-02).

Exact output: change `T1.motor_has_prop` in `core/aircraft_platform/checks.py` to also accept a propeller reached through components of type `other` or `structure` that are attached to the motor with `method: bolted`, and add the cases to `tests/test_checks_motor_prop.py` (new).

Pass check: `python3 -m pytest -q` green; `plane validate designs/concept-a --tier 1` has no `T1.motor_has_prop` FAIL.

Stop rule: do not change `standards/`; if an existing test contradicts the change, stop and report the test id.
