"""Round 3 review: articulation sweep between named poses, and hover thrust that must point up."""
from __future__ import annotations

import copy

from aircraft_platform.checks import validate
from aircraft_platform.design import FAIL, PASS, Design, load_design

from conftest import EXAMPLE_PATH, statuses


def _example() -> dict:
    return copy.deepcopy(load_design(EXAMPLE_PATH).data)


def _validate(data: dict, max_tier: int = 3):
    return validate(Design(data=data, path=EXAMPLE_PATH), max_tier=max_tier)


def _fails(sc, check_id=None):
    return [r for t in sc.tiers for r in t.results if r.status == FAIL and (check_id is None or r.check_id == check_id)]


LC = {"method": "laser-cut", "machine": "jacobs-laser"}


def _hatch_with_arm() -> dict:
    """Review attack r1: a hatch on the fuselage top with an arm behind it. Poses 0 and 90 and both range
    ends are clear; the hatch swings through the arm only around 45 deg."""
    d = _example()
    d["schema_version"] = "0.2"
    d["components"].append({"id": "hatch", "type": "structure", "geometry": {"box": {"size": [80, 20, 4]}},
                            "position": [240, 0, 42], "mass_g": 5, "manufacturing": dict(LC)})
    d["attachments"].append({"id": "hatch-hinge", "parent": "center_body", "child": "hatch", "method": "hinge",
                             "location": [200, 0, 40], "rated_load_n": 20,
                             "articulation": {"type": "revolute", "pivot": [200, 0, 40], "axis": [0, -1, 0],
                                              "range_deg": [0, 90], "poses": {"closed": 0, "open": 90}}})
    d["components"].append({"id": "post", "type": "structure", "geometry": {"box": {"size": [4, 20, 70]}},
                            "position": [292, 0, 75], "mass_g": 2, "manufacturing": dict(LC)})
    d["components"].append({"id": "arm", "type": "structure", "geometry": {"box": {"size": [50, 20, 12]}},
                            "position": [265, 0, 94], "mass_g": 2, "manufacturing": dict(LC)})
    d["attachments"].append({"id": "post-body", "parent": "center_body", "child": "post", "method": "glued",
                             "location": [292, 0, 40], "rated_load_n": 20})
    d["attachments"].append({"id": "arm-post", "parent": "post", "child": "arm", "method": "glued",
                             "location": [290, 0, 94], "rated_load_n": 20})
    return d


def test_sweep_catches_clipping_only_between_named_poses():
    sc = _validate(_hatch_with_arm(), max_tier=1)
    clips = _fails(sc, "T1.interference")
    assert clips, "hatch swinging through the arm mid-travel must be caught"
    assert all(r.message.startswith("sweep hatch-hinge ") for r in clips), [r.message for r in clips]
    assert any(r.message.startswith("sweep hatch-hinge 45°") for r in clips), [r.message for r in clips]
    assert not any("pose " in r.message for r in clips)


def test_tiltrotor_with_no_hover_pose_has_no_upward_thrust():
    d = _example()
    d["morphology"]["vtol_method"] = "tiltrotor"  # motors still point along -x, so no thrust is upward
    sc = _validate(d)
    assert statuses(sc, "T3.hover_tw") == [FAIL]


def test_lift_thrust_pointing_down_fails_hover_tw():
    d = _example()
    d["morphology"]["vtol_method"] = "lift-plus-cruise"
    for m in d["components"]:
        if m["id"] in ("motor_l", "motor_r"):
            m["propulsion"]["axis"] = [0, 0, -1]
            m["propulsion"]["role"] = "lift"
    sc = _validate(d)
    assert statuses(sc, "T3.hover_tw") == [FAIL]


def test_example_tailsitter_still_passes_hover_tw():
    sc = _validate(_example())
    assert statuses(sc, "T3.hover_tw") == [PASS]
    msg = next(r.message for t in sc.tiers for r in t.results if r.check_id == "T3.hover_tw")
    assert "upward thrust 18.0 N of 18.0 N rated" in msg, msg
