"""Concept A validator rules: motor-to-propeller through an adapter (T1.motor_has_prop) and kinematic_link
(T1.kinematic_link: linked child not checked against parts moved by a pose, reported as WARN)."""
from __future__ import annotations

import pytest

from aircraft_platform.checks import validate
from aircraft_platform.design import FAIL, PASS, WARN, Design

from conftest import statuses


def _mfg():
    return {"method": "hand-cut"}


def _box(cid, ctype, size, pos, mass=10, **extra):
    return {"id": cid, "type": ctype, "geometry": {"box": {"size": size}}, "position": pos,
            "mass_g": mass, "manufacturing": _mfg(), **extra}


def motor_design(first_method="bolted", second_method="bolted", adapter_type="structure", extra_chain=()) -> dict:
    """body (root) -> motor (propulsion) -> adapter -> prop, stacked along z. `extra_chain` inserts more parts
    (type other, bolted joints) between the adapter and the prop."""
    comps = [
        _box("body", "structure", [100, 100, 100], [0, 0, 0], 100),
        _box("motor", "motor", [20, 20, 20], [0, 0, 60], 50,
             propulsion={"max_thrust_n": 8.8, "axis": [0, 0, 1], "role": "both"}),
        _box("adapter", adapter_type, [20, 20, 10], [0, 0, 75], 4),
        _box("prop", "propeller", [60, 10, 2], [0, 0, 81], 10),
    ]
    chain = ["adapter"] + [c for c in extra_chain]
    # stack the extras above the adapter so every joint sits on a shared face
    z = 80.0
    atts = [{"id": "m-body", "parent": "body", "child": "motor", "method": "glued",
             "location": [0, 0, 50], "rated_load_n": 20},
            {"id": "m-adapter", "parent": "motor", "child": "adapter", "method": first_method,
             "location": [0, 0, 70], "rated_load_n": 20}]
    prev = "adapter"
    for n, cid in enumerate(extra_chain):
        comps.insert(3 + n, _box(cid, "other", [20, 20, 5], [0, 0, z + 2.5], 2))
        atts.append({"id": f"x-{n}", "parent": prev, "child": cid, "method": "bolted",
                     "location": [0, 0, z], "rated_load_n": 20})
        prev = cid
        z += 5.0
    # propeller sits on top of the last part of the chain
    comps[-1]["position"] = [0, 0, z + 1]
    atts.append({"id": "p-last", "parent": prev, "child": "prop", "method": second_method,
                 "location": [0, 0, z], "rated_load_n": 20})
    return {"schema_version": "0.4", "id": "motor-test", "name": "motor test", "status": "concept",
            "morphology": {"lift": "other", "vtol_method": "none"}, "root": "body",
            "components": comps, "attachments": atts}


def run(data: dict):
    return validate(Design(data=data, path=None), max_tier=1)


def fails(sc, check_id=None):
    return [r for t in sc.tiers for r in t.results if r.status == FAIL and (check_id is None or r.check_id == check_id)]


# ---------------------------------------------------------------- T1.motor_has_prop (B6d)

def test_motor_through_bolted_adapter_passes_and_names_chain():
    sc = run(motor_design())
    assert not fails(sc), [r.message for r in fails(sc)]
    rows = [r for t in sc.tiers for r in t.results if r.check_id == "T1.motor_has_prop"]
    assert [r.status for r in rows] == [PASS]
    assert "motor -> adapter -> prop" in rows[0].message


def test_motor_through_glued_adapter_fails():
    sc = run(motor_design(first_method="glued"))
    assert statuses(sc, "T1.motor_has_prop") == [FAIL]


def test_motor_through_three_intermediates_fails():
    sc = run(motor_design(extra_chain=("spacer-a", "spacer-b")))  # adapter + 2 spacers = 3 intermediates
    assert statuses(sc, "T1.motor_has_prop") == [FAIL]


def test_motor_through_two_intermediates_passes():
    sc = run(motor_design(extra_chain=("spacer-a",)))  # adapter + 1 spacer = 2 intermediates
    assert statuses(sc, "T1.motor_has_prop") == [PASS]


# ---------------------------------------------------------------- T1.kinematic_link (B6c)

def linked_design(kinematic: bool, version: str = "0.4") -> dict:
    """base (root) with a hinged flap that swings to +90 deg down the +x face of the base, and a rod glued to that
    face. The rod sits in the flap's swept region: it is clear at 0 deg and clipped only at the hover pose."""
    att_rod = {"id": "rod-tie", "parent": "base", "child": "rod", "method": "glued",
               "location": [50, 0, -35], "rated_load_n": 20}
    if kinematic:
        att_rod["kinematic_link"] = True
    return {
        "schema_version": version, "id": "link-test", "name": "link test", "status": "concept",
        "morphology": {"lift": "other", "vtol_method": "none"},
        "root": "base",
        "components": [
            _box("base", "fuselage", [100, 100, 100], [0, 0, 0], 100),
            _box("flap", "structure", [100, 100, 10], [100, 0, 55], 20),
            _box("rod", "structure", [10, 20, 10], [55, 0, -35], 5),
        ],
        "attachments": [
            {"id": "flap-hinge", "parent": "base", "child": "flap", "method": "hinge",
             "location": [50, 0, 50], "rated_load_n": 20,
             "articulation": {"type": "revolute", "pivot": [50, 0, 50], "axis": [0, 1, 0],
                              "range_deg": [0, 90], "poses": {"cruise": 0, "hover": 90}}},
            att_rod,
        ],
    }


def test_linked_part_clipping_only_at_pose_warns_not_fails():
    sc = run(linked_design(kinematic=True))
    assert sc.tiers[0].status == PASS
    assert not fails(sc), [r.message for r in fails(sc)]
    warns = [r for t in sc.tiers for r in t.results if r.check_id == "T1.kinematic_link"]
    assert warns and all(r.status == WARN for r in warns)
    hover = [r for r in warns if "pose hover (90°)" in r.message]
    assert len(hover) == 1, [r.message for r in warns]
    assert "linkage path not modelled" in hover[0].message and "rod" in hover[0].message
    assert statuses(sc, "T1.articulation") == [PASS]


def test_same_clip_without_kinematic_link_fails():
    sc = run(linked_design(kinematic=False))
    clips = fails(sc, "T1.interference")
    assert any("pose hover (90°)" in r.message and "rod" in r.message for r in clips), [r.message for r in clips]
    assert not any(r.check_id == "T1.kinematic_link" for t in sc.tiers for r in t.results)


def test_kinematic_link_needs_schema_040():
    sc = run(linked_design(kinematic=True, version="0.3"))
    assert any(r.check_id == "T0.version" and r.status == FAIL for r in sc.tiers[0].results)


def _wing(planform: bool, version: str = "0.4") -> dict:
    """One flying-wing component, 900 x 245 mm rectangular. As a lifting_surface, or as a box with a schema 0.4 planform
    (tier 3 only; the box gives the geometry)."""
    ls = {"span": 900, "root_chord": 245, "tip_chord": 245, "mirrored": True}
    if planform:
        wing = {"id": "wng", "type": "wing", "geometry": {"box": {"size": [245, 900, 10]}}, "position": [0, 0, 0],
                "mass_g": 1000, "manufacturing": _mfg(),
                "planform": {"lifting_surface": dict(ls), "origin": [0, 0, 0]}}
    else:
        wing = {"id": "wng", "type": "wing", "geometry": {"lifting_surface": dict(ls)}, "position": [0, 0, 0],
                "mass_g": 1000, "manufacturing": _mfg()}
    return {"schema_version": version, "id": "wing-test", "name": "wing test", "status": "concept",
            "morphology": {"lift": "flying-wing", "vtol_method": "none"}, "root": "wng",
            "components": [wing], "attachments": []}


def _tier3(data: dict) -> dict:
    sc = validate(Design(data=data, path=None), max_tier=3)
    return {r.check_id: r for t in sc.tiers for r in t.results}


def test_planform_wing_gets_stall_and_matches_lifting_surface():
    with_planform = _tier3(_wing(planform=True))
    as_surface = _tier3(_wing(planform=False))
    assert "no lifting surface" not in with_planform["T3.stall"].message
    assert with_planform["T3.stall"].status == as_surface["T3.stall"].status
    assert with_planform["T3.stall"].data["stall_mps"] == pytest.approx(as_surface["T3.stall"].data["stall_mps"])
    assert with_planform["T3.static_margin"].message.endswith("(planform declared; mesh wing)")
    assert not as_surface["T3.static_margin"].message.endswith("(planform declared; mesh wing)")


def test_planform_needs_schema_040():
    sc = run(_wing(planform=True, version="0.3"))
    assert any(r.check_id == "T0.version" and r.status == FAIL for r in sc.tiers[0].results)
