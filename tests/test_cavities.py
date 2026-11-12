"""Schema 0.3 cavities: subtracted from the local mesh before the component transform."""
from __future__ import annotations

import math

import pytest

from aircraft_platform.checks import tier0_schema, validate
from aircraft_platform.design import FAIL, PASS, Design
from aircraft_platform.geometry import component_parts

from conftest import statuses


def _box_with_cylinder_cavity() -> dict:
    return {
        "id": "blk", "type": "structure", "mass_g": 1,
        "geometry": {"box": {"size": [100, 100, 100]}},
        "position": [0, 0, 0],
        "cavities": [{"geometry": {"cylinder": {"radius": 10, "length": 50, "axis": "z"}},
                      "position": [0, 0, 0]}],
    }


def _nacelle_and_motor(cavity_radius: float | None) -> dict:
    """Solid 100 x 60 x 70 box with a motor (r 24, 32 long) whose bottom sits on the cavity floor.
    The cavity runs z -10..30 (centre z 10, length 40) and is open at the top."""
    nacelle = {
        "id": "nacelle", "type": "structure", "mass_g": 20,
        "geometry": {"box": {"size": [100, 60, 70]}},
        "position": [0, 0, 0],
    }
    if cavity_radius is not None:
        nacelle["cavities"] = [{"geometry": {"cylinder": {"radius": cavity_radius, "length": 40, "axis": "z"}},
                                "position": [0, 0, 10]}]
    motor = {
        "id": "motor", "type": "motor", "mass_g": 165,
        "geometry": {"cylinder": {"radius": 24, "length": 32, "axis": "z"}},
        "position": [0, 0, 6],
        "propulsion": {"max_thrust_n": 30, "axis": [0, 0, 1], "role": "lift"},
    }
    return {
        "schema_version": "0.3", "id": "cav-test", "name": "cavity test", "status": "concept",
        "morphology": {"lift": "other", "vtol_method": "none"},
        "root": "nacelle",
        "components": [nacelle, motor],
        "attachments": [],
    }


def test_box_with_cylindrical_cavity_loses_cylinder_volume():
    parts = component_parts(_box_with_cylinder_cavity())
    hollow = sum(p.volume for p in parts)
    assert hollow == pytest.approx(100 ** 3 - math.pi * 10 ** 2 * 50, rel=0.02)


def test_cavity_that_removes_whole_part_raises():
    comp = _box_with_cylinder_cavity()
    comp["cavities"] = [{"geometry": {"box": {"size": [200, 200, 200]}}, "position": [0, 0, 0]}]
    with pytest.raises(ValueError, match="blk"):
        component_parts(comp)


def test_motor_inside_matching_cavity_does_not_interfere():
    sc = validate(Design(data=_nacelle_and_motor(cavity_radius=25.5)), max_tier=1)
    assert statuses(sc, "T1.interference") == [PASS]


def test_motor_inside_solid_nacelle_interferes():
    sc = validate(Design(data=_nacelle_and_motor(cavity_radius=None)), max_tier=1)
    assert FAIL in statuses(sc, "T1.interference")


def test_cavities_need_schema_version_0_3():
    data = _nacelle_and_motor(cavity_radius=25.5)
    data["schema_version"] = "0.2"
    rep = tier0_schema(Design(data=data))
    assert [r.status for r in rep.results if r.check_id == "T0.version"] == [FAIL]

    data["schema_version"] = "0.3"
    rep = tier0_schema(Design(data=data))
    assert FAIL not in [r.status for r in rep.results if r.check_id == "T0.version"]
