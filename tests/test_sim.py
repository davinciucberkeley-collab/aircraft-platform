"""MuJoCo drop-test checks: the example builds, and deliberately broken copies fail."""
from __future__ import annotations

import copy

import pytest

pytest.importorskip("mujoco")

from aircraft_platform.checks import validate
from aircraft_platform.design import DESIGNS_DIR, Design, load_design
from aircraft_platform.sim import build_mjcf, export_mjcf

EXAMPLE = DESIGNS_DIR / "example-tailsitter-wing" / "plane.yaml"


def _run(fn):
    base = load_design(EXAMPLE)
    data = copy.deepcopy(base.data)
    fn(data)
    sc = validate(Design(data=data, path=EXAMPLE))
    return [r for t in sc.tiers for r in t.results if r.check_id.startswith("T2.sim")]


def _by(results, check_id):
    return [r for r in results if r.check_id == check_id]


def test_example_runs_all_sim_checks():
    res = _run(lambda d: None)
    assert _by(res, "T2.sim_drop_loads") and _by(res, "T2.sim_rest") and _by(res, "T2.sim_stable")
    assert _by(res, "T2.sim_stable")[0].status == "PASS"
    assert _by(res, "T2.sim_rest")[0].status == "PASS"


def test_mjcf_export(tmp_path):
    d = load_design(EXAMPLE)
    xml = build_mjcf(d)
    assert "<weld" in xml and "wing_m0" in xml
    assert export_mjcf(d, tmp_path / "x.xml").read_text() == xml


def test_tailsitter_without_fins_tips_over():
    def mut(d):
        gone = {"fin_l", "fin_r"}
        d["components"] = [c for c in d["components"] if c["id"] not in gone]
        d["attachments"] = [a for a in d["attachments"] if a["child"] not in gone]
    res = _run(mut)
    assert _by(res, "T2.sim_rest")[0].status == "FAIL"


def test_weak_joint_fails_drop_loads():
    def mut(d):
        for a in d["attachments"]:
            if a["id"] == "motor-l":
                a["rated_load_n"] = 0.1
    res = _run(mut)
    bad = [r for r in _by(res, "T2.sim_drop_loads") if r.status == "FAIL" and r.message.startswith("motor-l")]
    assert bad
