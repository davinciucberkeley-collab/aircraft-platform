"""Tier-3 neutral point from a vortex lattice (AeroSandbox): unit checks and the fallback path."""
from __future__ import annotations

import copy

import pytest

from aircraft_platform import aero
from aircraft_platform.checks import validate
from aircraft_platform.design import Design, load_design

pytest.importorskip("aerosandbox")


def _surface(span, chord, x_le, z=0.0, per_semi=8):
    ls = {"span": span, "root_chord": chord, "tip_chord": chord}
    return aero.lifting_surface_sections({"geometry": {"lifting_surface": ls}, "position": [x_le, 0, z]}, None, per_semi)


def test_rectangular_wing_alone_np_is_quarter_mac():
    chord, span = 150.0, 900.0  # AR 6
    r = aero.vlm_neutral_point([_surface(span, chord, 100.0)], 100.0 + 0.25 * chord, chord, span * chord)
    assert abs((r["x_np_mm"] - 100.0) / chord - 0.25) < 0.02
    assert r["panels"] > 50 and r["cl_alpha"] > 0


def test_np_is_independent_of_reference_point():
    chord, span = 150.0, 900.0
    a = aero.vlm_neutral_point([_surface(span, chord, 0.0)], 20.0, chord, span * chord)
    b = aero.vlm_neutral_point([_surface(span, chord, 0.0)], 120.0, chord, span * chord)
    assert abs(a["x_np_mm"] - b["x_np_mm"]) < 0.5


def test_aft_tail_moves_np_aft():
    chord, span = 150.0, 900.0
    wing = aero.vlm_neutral_point([_surface(span, chord, 0.0)], 37.5, chord, span * chord)["x_np_mm"]
    both = aero.vlm_neutral_point([_surface(span, chord, 0.0), _surface(400.0, 80.0, 600.0)], 37.5, chord,
                                  span * chord)["x_np_mm"]
    assert both > wing + 20.0


def test_vertical_fin_adds_no_pitch_lift_slope_of_its_own():
    chord, span = 150.0, 900.0
    fin = aero.lifting_surface_sections({"geometry": {"lifting_surface": {"span": 200, "root_chord": 100, "tip_chord": 60,
                                                                       "mirrored": False}},
                                         "position": [500, 0, 0], "rotation_deg": [90, 0, 0]}, None, 4)
    assert all(abs(p[1]) < 1e-6 for p, _c, _t in fin) and fin[-1][0][2] > 190  # fin stands up along z
    base = aero.vlm_neutral_point([_surface(span, chord, 0.0)], 37.5, chord, span * chord)
    with_fin = aero.vlm_neutral_point([_surface(span, chord, 0.0), fin], 37.5, chord, span * chord)
    assert abs(with_fin["cl_alpha"] / base["cl_alpha"] - 1) < 0.03


def _static_margin_row(design: Design):
    for t in validate(design).tiers:
        for r in t.results:
            if r.check_id == "T3.static_margin":
                return r
    raise AssertionError("no static margin row")


def test_tier3_message_names_vlm_and_what_is_not_modelled(example):
    row = _static_margin_row(load_design(example))
    assert "VLM," in row.message and "panels" in row.message and "wings and tails only" in row.message


def test_fallback_when_aerosandbox_import_fails(example, monkeypatch):
    def boom():
        raise ImportError("No module named 'aerosandbox'")
    monkeypatch.setattr(aero, "_import_asb", boom)
    assert not aero.available()
    row = _static_margin_row(load_design(example))
    assert "quarter-chord estimate because AeroSandbox is not installed" in row.message
    assert "VLM," not in row.message
    assert row.data["x_np_mm"] > 0
