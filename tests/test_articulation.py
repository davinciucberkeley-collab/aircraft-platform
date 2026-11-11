"""Schema v0.2 articulated joints: tier-1 checks run once per configuration and name the pose."""
from __future__ import annotations

import copy

import numpy as np
import pytest

from aircraft_platform.checks import validate
from aircraft_platform.design import FAIL, PASS, Design, load_design
from aircraft_platform.geometry import posed_component_parts
from aircraft_platform.mass import mass_properties

from conftest import statuses


def _mfg():
    return {"method": "hand-cut"}


def tilt_design(hover_deg: float = 90.0, range_deg=(0.0, 90.0)) -> dict:
    """Fuselage box, a hinge block on top, and a 100 x 200 x 10 flap hinged at the block's centre.
    The flap lies on top at 0 deg. Rotating +90 deg about +y swings its aft end DOWN through the fuselage;
    -90 deg swings it UP, clear of everything."""
    return {
        "schema_version": "0.2", "id": "tilt-test", "name": "Tilt test", "status": "concept",
        "morphology": {"lift": "other", "vtol_method": "none"},
        "root": "fuselage",
        "components": [
            {"id": "fuselage", "type": "fuselage", "geometry": {"box": {"size": [400, 200, 100]}},
             "position": [200, 0, 0], "mass_g": 100, "manufacturing": _mfg()},
            {"id": "hinge", "type": "structure", "geometry": {"box": {"size": [10, 20, 10]}},
             "position": [200, 0, 55], "mass_g": 5, "manufacturing": _mfg()},
            {"id": "flap", "type": "structure", "geometry": {"box": {"size": [100, 200, 10]}},
             "position": [250, 0, 55], "mass_g": 20, "manufacturing": _mfg()},
        ],
        "attachments": [
            {"id": "hinge-body", "parent": "fuselage", "child": "hinge", "method": "glued",
             "location": [200, 0, 50], "rated_load_n": 20},
            {"id": "flap-hinge", "parent": "hinge", "child": "flap", "method": "hinge",
             "location": [200, 0, 55], "embed_ok": True, "rated_load_n": 20,
             "articulation": {"type": "revolute", "pivot": [200, 0, 55], "axis": [0, 1, 0],
                              "range_deg": list(range_deg), "poses": {"cruise": 0, "hover": hover_deg}}},
        ],
    }


def run(data: dict):
    return validate(Design(data=data, path=None), max_tier=1)


def fails(sc, check_id=None):
    return [r for t in sc.tiers for r in t.results if r.status == FAIL and (check_id is None or r.check_id == check_id)]


def test_flap_clipping_only_at_90_fails_and_names_pose():
    sc = run(tilt_design())
    assert sc.tiers[0].status == PASS
    clips = fails(sc, "T1.interference")
    assert clips, "flap swinging through the fuselage must be caught"
    assert any("pose hover (90°)" in r.message and "fuselage and flap overlap" in r.message for r in clips), [r.message for r in clips]
    # the 0 deg configuration itself is clean, so no un-prefixed failure exists
    assert all(r.message.startswith(("pose ", "range ", "sweep ")) for r in fails(sc))
    assert statuses(sc, "T1.articulation") == [PASS]


def test_same_hardware_with_clearance_passes():
    sc = run(tilt_design(hover_deg=-90, range_deg=(-90, 0)))
    assert not fails(sc), [r.message for r in fails(sc)]
    assert statuses(sc, "T1.articulation") == [PASS]
    assert PASS in statuses(sc, "T1.pose")


def test_pose_outside_range_fails():
    sc = run(tilt_design(hover_deg=120, range_deg=(0, 90)))
    msgs = [r.message for r in fails(sc, "T1.articulation")]
    assert msgs and "pose hover (120°) is outside range" in msgs[0]


def test_pivot_away_from_parts_fails():
    d = tilt_design(hover_deg=-90, range_deg=(-90, 0))
    d["attachments"][1]["articulation"]["pivot"] = [200, 0, 300]
    assert fails(run(d), "T1.articulation")


def test_articulation_needs_schema_0_2():
    d = tilt_design(hover_deg=-90, range_deg=(-90, 0))
    d["schema_version"] = "0.1"
    sc = run(d)
    assert [t.tier for t in sc.tiers] == [0] or fails(sc, "T0.version")
    assert fails(sc, "T0.version")


def test_v01_example_still_valid(example):
    data = load_design(example).data
    assert data["schema_version"] == "0.1"
    assert validate(load_design(example)).accepted


def test_posed_geometry_and_mass_properties_follow_the_joint():
    d = Design(data=tilt_design(hover_deg=-90, range_deg=(-90, 0)), path=None)
    up = posed_component_parts(d, {"flap-hinge": -90})
    flat = posed_component_parts(d, None)
    c0 = flat["flap"][0].bounds.mean(axis=0)
    c1 = up["flap"][0].bounds.mean(axis=0)
    assert np.allclose(c0, [250, 0, 55])
    assert np.allclose(c1, [200, 0, 105], atol=1e-6)        # x offset 50 swings to z offset +50
    assert np.allclose(up["fuselage"][0].bounds, flat["fuselage"][0].bounds)   # upstream part untouched
    m0, m1 = mass_properties(d), mass_properties(d, {"flap-hinge": -90})
    assert m1["mass_g"] == pytest.approx(m0["mass_g"])
    assert m1["cg_mm"][2] > m0["cg_mm"][2]
