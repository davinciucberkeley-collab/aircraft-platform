"""Schema 0.4 point_mass: mass at a point, counted in mass and CG, absent from every geometry check."""
from __future__ import annotations

import copy

import numpy as np

from aircraft_platform.checks import tier0_schema, validate
from aircraft_platform.design import FAIL, PASS, Design
from aircraft_platform.export import to_scene
from aircraft_platform.geometry import component_parts, is_point_mass
from aircraft_platform.mass import mass_properties

from conftest import statuses


def _mfg():
    return {"method": "hand-cut"}


def pm_design(pm_position=(0, 0, 0), version="0.4", attach=True) -> dict:
    """A 100 mm cube (100 g) with a 50 g point mass. By default the point mass sits INSIDE the cube, where a
    solid would clip; as a point mass it must not."""
    data = {
        "schema_version": version, "id": "pm-test", "name": "point mass test", "status": "concept",
        "morphology": {"lift": "other", "vtol_method": "none"},
        "root": "block",
        "components": [
            {"id": "block", "type": "structure", "geometry": {"box": {"size": [100, 100, 100]}},
             "position": [0, 0, 0], "mass_g": 100, "manufacturing": _mfg()},
            {"id": "lump", "type": "other", "geometry": {"point_mass": {}},
             "position": list(pm_position), "mass_g": 50, "manufacturing": _mfg()},
        ],
        "attachments": [],
    }
    if attach:
        data["attachments"].append({"id": "lump-tie", "parent": "block", "child": "lump", "method": "tape",
                                    "location": [0, 0, 0], "rated_load_n": 50})
    return data


def run(data, tier=5):
    return validate(Design(data=data, path=None), max_tier=tier)


def test_schema_accepts_point_mass_at_v04():
    rep = tier0_schema(Design(data=pm_design(), path=None))
    assert rep.status == PASS


def test_point_mass_needs_v04():
    rep = tier0_schema(Design(data=pm_design(version="0.3"), path=None))
    assert any(r.check_id == "T0.version" and r.status == FAIL for r in rep.results)


def test_point_mass_rejects_extent():
    d = pm_design()
    d["components"][1]["geometry"] = {"point_mass": {"size": [1, 1, 1]}}
    assert tier0_schema(Design(data=d, path=None)).status == FAIL


def test_no_mesh():
    c = pm_design()["components"][1]
    assert is_point_mass(c)
    assert component_parts(c) == []


def test_mass_and_cg_count_the_point():
    d = pm_design(pm_position=(30, -20, 10))
    mp = mass_properties(Design(data=d, path=None))
    assert mp["mass_g"] == 150
    # block CG at the origin (100 g), point at (30, -20, 10) (50 g)
    assert np.allclose(mp["cg_mm"], [10.0, -6.67, 3.33], atol=0.01)


def test_cg_offset_applies_to_point_mass():
    d = pm_design(pm_position=(30, 0, 0))
    d["components"][1]["cg_offset"] = [-30, 0, 0]
    mp = mass_properties(Design(data=d, path=None))
    assert np.allclose(mp["cg_mm"], [0, 0, 0], atol=0.01)


def test_inside_a_solid_is_not_a_clash_and_attachment_skips_contact():
    sc = run(d := pm_design(), tier=1)
    assert statuses(sc, "T1.interference") == [PASS]
    assert statuses(sc, "T1.connectivity") == [PASS]
    assert "T1.attachment_contact" not in {r.check_id for t in sc.tiers for r in t.results}
    msgs = [r.message for t in sc.tiers for r in t.results if r.check_id == "T1.attachment"]
    assert any("point mass" in m for m in msgs)


def test_far_from_parent_still_passes_contact_check():
    """A solid 500 mm away would FAIL attachment contact; a point mass has no extent so the check is skipped."""
    sc = run(pm_design(pm_position=(500, 0, 0)), tier=1)
    assert statuses(sc, "T1.attachment_contact") == []
    assert FAIL not in statuses(sc, "T1.attachment") + statuses(sc, "T1.attachment_location")


def test_unattached_point_mass_fails_connectivity():
    sc = run(pm_design(attach=False), tier=1)
    assert statuses(sc, "T1.connectivity") == [FAIL]


def test_full_run_has_no_crash_and_sim_holds_the_point_mass():
    sc = run(pm_design())
    errs = [r for t in sc.tiers for r in t.results if r.check_id.endswith(".error")]
    assert errs == []
    assert statuses(sc, "T2.sim_stable") == [PASS]
    assert statuses(sc, "T4.method") == [PASS, PASS]  # block fits; the point mass has no extent to fit


def test_export_skips_point_mass():
    scene = to_scene(Design(data=pm_design(), path=None))
    assert set(scene.geometry) == {"block"}
