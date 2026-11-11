"""Validator behaviour on the example tailsitter, plus targeted mutations that must be caught."""
from __future__ import annotations

import pytest

from aircraft_platform.checks import validate
from aircraft_platform.design import FAIL, PASS, load_design
from aircraft_platform.mass import mass_properties

from conftest import statuses


def _comp(data: dict, cid: str) -> dict:
    return next(c for c in data["components"] if c["id"] == cid)


def _att(data: dict, aid: str) -> dict:
    return next(a for a in data["attachments"] if a["id"] == aid)


def test_example_accepted(example):
    sc = validate(load_design(example))
    assert sc.accepted
    by_tier = {t.tier: t.status for t in sc.tiers}
    for tier in (0, 1, 2, 3, 4, 5):
        assert by_tier[tier] == PASS, f"tier {tier} is {by_tier[tier]}"


def test_mass_equals_sum_of_components(example):
    design = load_design(example)
    total = sum(c["mass_g"] for c in design.components)
    assert mass_properties(design)["mass_g"] == pytest.approx(total)


def test_bad_schema_version_stops_at_tier0(mutate):
    sc = mutate(lambda d: d.__setitem__("schema_version", "9"))
    assert [t.tier for t in sc.tiers] == [0]
    assert sc.tiers[0].status == FAIL
    assert not sc.accepted


def test_detached_prop_fails_connectivity(mutate):
    def remove_prop_attachment(d):
        d["attachments"] = [a for a in d["attachments"] if a.get("id") != "prop-l"]

    sc = mutate(remove_prop_attachment)
    assert FAIL in statuses(sc, "T1.connectivity")


def test_prop_moved_into_wing_is_prop_strike(mutate):
    def move_prop(d):
        _comp(d, "prop_l")["position"] = [150, -250, 0]
        _att(d, "prop-l")["location"] = [150, -250, 0]

    sc = mutate(move_prop)
    assert FAIL in statuses(sc, "T1.interference")


def test_fin_floating_off_tip_fails_contact(mutate):
    sc = mutate(lambda d: _comp(d, "fin_l").__setitem__("position", [242, -560, 0]))
    assert FAIL in statuses(sc, "T1.attachment_contact")


def test_heavy_battery_fails_mass(mutate):
    sc = mutate(lambda d: _comp(d, "battery").__setitem__("mass_g", 2000))
    assert FAIL in statuses(sc, "T3.mass")


def test_low_thrust_fails_hover_tw(mutate):
    def weak_motors(d):
        for cid in ("motor_l", "motor_r"):
            _comp(d, cid)["propulsion"]["max_thrust_n"] = 3.0

    sc = mutate(weak_motors)
    assert FAIL in statuses(sc, "T3.hover_tw")


def test_low_joint_rating_fails_joint_load(mutate):
    sc = mutate(lambda d: _att(d, "wing-body").__setitem__("rated_load_n", 1))
    assert FAIL in statuses(sc, "T2.joint_load")


def test_battery_outboard_fails_geometry_or_lateral_cg(mutate):
    def move_battery(d):
        _comp(d, "battery")["position"] = [140, 120, -28]
        _att(d, "battery-bay")["location"] = [140, 120, -28]

    sc = mutate(move_battery)
    geometry_fail = any(
        s == FAIL
        for cid in ("T1.attachment_contact", "T1.attachment_location", "T1.attachment_overlap", "T1.connectivity")
        for s in statuses(sc, cid)
    )
    assert geometry_fail or FAIL in statuses(sc, "T3.lateral_cg")


def test_duplicate_component_id_fails_tier0(mutate):
    def duplicate_fc(d):
        d["components"].append(dict(_comp(d, "flight_controller")))

    sc = mutate(duplicate_fc)
    assert [t.tier for t in sc.tiers] == [0]
    assert FAIL in statuses(sc, "T0.unique_ids")


def test_scorecard_outputs(example):
    sc = validate(load_design(example))
    assert "Accepted" in sc.to_markdown()
    assert "tiers" in sc.to_dict()
