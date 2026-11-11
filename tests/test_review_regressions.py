"""One test per attack in reviews/2026-11-11-bootstrap.md that the validator originally MISSED.

Each defect is built by mutating the example in code and must now FAIL the relevant check.
"""
from __future__ import annotations

import json

import yaml
from click.testing import CliRunner

from aircraft_platform.checks import validate
from aircraft_platform.cli import cli
from aircraft_platform.design import DESIGNS_DIR, FAIL, REPO_ROOT, SKIP, CheckResult, Scorecard, TierReport, load_design

from conftest import statuses


def _comp(d: dict, cid: str) -> dict:
    return next(c for c in d["components"] if c["id"] == cid)


def _att(d: dict, aid: str) -> dict:
    return next(a for a in d["attachments"] if a.get("id") == aid)


def test_b4_embed_ok_fin_flat_inside_wing_fails(mutate):
    sc = mutate(lambda d: _comp(d, "fin_l").__setitem__("rotation_deg", [0, 0, 0]))
    assert FAIL in statuses(sc, "T1.attachment_overlap")
    assert not sc.accepted


def test_b9_prop_disc_in_wing_with_embed_ok_fails(mutate):
    def mut(d):
        _comp(d, "prop_l")["position"] = [200, -250, 0]
        a = _att(d, "prop-l")
        a.update(parent="wing", embed_ok=True, location=[200, -250, 0])

    sc = mutate(mut)
    assert FAIL in statuses(sc, "T1.attachment_overlap")


def test_propeller_may_never_be_embed_ok(mutate):
    sc = mutate(lambda d: _att(d, "prop-l").__setitem__("embed_ok", True))
    assert FAIL in statuses(sc, "T1.attachment_overlap")


def test_b10_flight_controller_through_wing_fails(mutate):
    def mut(d):
        fc = _comp(d, "flight_controller")
        fc["geometry"] = {"box": {"size": [60, 400, 10]}}
        fc["position"] = [200, 0, 0]
        _att(d, "fc-mount")["location"] = [200, 0, 0]
        d["attachments"].append({"id": "fc-wing", "parent": "wing", "child": "flight_controller", "method": "bolted",
                                 "location": [200, 0, 0], "embed_ok": True, "rated_load_n": 5})

    sc = mutate(mut)
    assert FAIL in statuses(sc, "T1.attachment_overlap")


def test_b13_static_margin_below_min_fails(mutate):
    sc = mutate(lambda d: _comp(d, "battery").__setitem__("position", [330, 0, -28]))
    assert FAIL in statuses(sc, "T3.static_margin")
    assert not sc.accepted


def test_b14_wing_too_big_for_laser_bed_fails(mutate):
    sc = mutate(lambda d: _comp(d, "wing").__setitem__("manufacturing", {"method": "laser-cut", "machine": "jacobs-laser"}))
    assert FAIL in statuses(sc, "T4.fits_machine")


def test_b15_unknown_machine_fails(mutate):
    sc = mutate(lambda d: _comp(d, "mount_l").__setitem__("manufacturing", {"method": "3d-print-fdm", "machine": "no-such-printer"}))
    assert FAIL in statuses(sc, "T4.machine")


def test_machine_that_lacks_the_method_fails(mutate):
    sc = mutate(lambda d: _comp(d, "mount_l").__setitem__("manufacturing", {"method": "laser-cut", "machine": "jacobs-fdm"}))
    assert FAIL in statuses(sc, "T4.method")


def test_b17_joints_without_location_and_rating_fail_schema(mutate):
    def mut(d):
        for a in d["attachments"]:
            a.pop("location", None)
            a.pop("rated_load_n", None)

    sc = mutate(mut)
    assert FAIL in statuses(sc, "T0.schema")
    assert not sc.accepted


def test_b8_zero_mass_fails_schema(mutate):
    sc = mutate(lambda d: _comp(d, "motor_l").__setitem__("mass_g", 0))
    assert FAIL in statuses(sc, "T0.schema")


def test_skip_blocks_acceptance():
    sc = Scorecard("x", [TierReport(2, "physics", [CheckResult("T2.sim", SKIP, "skipped", "schema/plane.schema.json")])])
    assert not sc.accepted


def test_cli_tier_all_is_accepted():
    res = CliRunner().invoke(cli, ["validate", str(DESIGNS_DIR / "example-tailsitter-wing"), "--tier", "all", "--format", "json"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["accepted"] is True


def _std_keys(node, out=None):
    out = set() if out is None else out
    if isinstance(node, dict):
        for k, v in node.items():
            out.add(k)
            _std_keys(v, out)
    return out


def test_every_criterion_resolves(example):
    sc = validate(load_design(example))
    std_keys = _std_keys(yaml.safe_load((REPO_ROOT / "standards" / "design-standards.yaml").read_text()))
    schema = json.loads((REPO_ROOT / "schema" / "plane.schema.json").read_text())
    machines = {m["id"] for m in yaml.safe_load((REPO_ROOT / "standards" / "manufacturing.yaml").read_text())["machines"]}
    for t in sc.tiers:
        for r in t.results:
            assert r.criterion, f"{r.check_id} has no criterion"
            if r.criterion.startswith("requirements."):
                assert r.criterion.split(".", 1)[1] in schema["properties"]["requirements"]["properties"]
                continue
            fname, _, key = r.criterion.partition("#")
            assert (REPO_ROOT / "standards" / fname).exists() or (REPO_ROOT / fname).exists(), r.criterion
            if fname == "design-standards.yaml":
                assert key in std_keys, f"{r.check_id}: {r.criterion}"
            if fname == "manufacturing.yaml" and key:
                assert key in machines, f"{r.check_id}: {r.criterion}"
