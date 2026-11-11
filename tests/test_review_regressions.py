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
        fc["geometry"] = {"box": {"size": [60, 400, 40]}}
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
    out = json.loads(res.output)
    assert res.exit_code == 0 and out["accepted"] is True and out["partial"] is False and out["max_tier"] == 5
    assert [t["tier"] for t in out["tiers"]] == [0, 1, 2, 3, 4, 5]


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


# ---- re-review (191d951) blockers -------------------------------------------------------------
import math

from aircraft_platform.design import WARN


def _fc_through_wing(d, relabel=True):
    fc = _comp(d, "flight_controller")
    fc["geometry"] = {"box": {"size": [36, 400, 40]}}
    fc["position"] = [200, 0, 0]
    _att(d, "fc-mount")["location"] = [200, 0, 0]
    _att(d, "fc-mount")["rated_load_n"] = 20
    d["attachments"].append({"id": "fc-wing", "parent": "wing", "child": "flight_controller", "method": "bolted",
                             "location": [200, 100, 0], "embed_ok": True, "rated_load_n": 20})
    if relabel:
        _comp(d, "wing")["type"] = "pod"


def test_n1_relabelled_pod_does_not_hide_fc_through_wing(mutate):
    sc = mutate(_fc_through_wing)
    assert FAIL in statuses(sc, "T1.attachment_overlap")
    assert not sc.accepted


def test_contained_child_may_exceed_embed_limit_regardless_of_type(mutate):
    # battery is 100% inside the fuselage; relabelling it must not change the verdict
    sc = mutate(lambda d: _comp(d, "battery").__setitem__("type", "structure"))
    assert FAIL not in statuses(sc, "T1.attachment_overlap")


def test_part_poking_through_parent_is_not_a_bay(mutate):
    # battery grown 35 mm taller so it sticks out of the fuselage: no longer a bay
    def mut(d):
        b = _comp(d, "battery")
        b["geometry"] = {"box": {"size": [100, 35, 60]}}
        b["position"] = [140, 0, -28]

    sc = mutate(mut)
    assert FAIL in statuses(sc, "T1.attachment_overlap") or FAIL in statuses(sc, "T1.interference")


def test_n1b_prop_relabelled_payload_leaves_motor_propless(mutate):
    def mut(d):
        _comp(d, "wing")["type"] = "pod"
        _comp(d, "prop_l")["type"] = "payload"
        _comp(d, "prop_l")["position"] = [200, -250, 0]
        a = _att(d, "prop-l")
        a.update(parent="wing", embed_ok=True, location=[200, -250, 0])

    sc = mutate(mut)
    assert FAIL in statuses(sc, "T1.motor_has_prop")
    assert not sc.accepted


def test_motor_without_attached_prop_fails(mutate):
    sc = mutate(lambda d: d["attachments"].remove(_att(d, "prop-r")))
    assert FAIL in statuses(sc, "T1.motor_has_prop")


def _strip(d, tilt):
    L = 900
    d["components"].append({"id": "skid", "type": "structure", "geometry": {"box": {"size": [L, 100, 3]}},
                            "position": [250 + (L / 2) * math.cos(math.radians(tilt)), 0, -40], "rotation_deg": [0, tilt, 0],
                            "mass_g": 1, "manufacturing": {"method": "laser-cut", "machine": "jacobs-laser"}})
    d["attachments"].append({"id": "skid-body", "parent": "center_body", "child": "skid", "method": "glued",
                             "location": [250, 0, -40], "rated_load_n": 20})


def test_n2_tilted_laser_strip_still_fails_fit(mutate):
    sc = mutate(lambda d: _strip(d, 60))
    assert FAIL in statuses(sc, "T4.fits_machine")


def test_laser_part_too_thick_for_machine_thickness_limit(mutate, monkeypatch):
    import aircraft_platform.checks as ch
    real = ch._fits
    assert real([3, 100, 400], [813, 457, 5], True)
    assert not real([30, 100, 400], [813, 457, 5], True)
    assert real([30, 100, 400], [813, 457], True)  # no thickness limit listed: not checked


def test_n2c_inhouse_method_without_machine_fails(mutate):
    sc = mutate(lambda d: _comp(d, "wing").__setitem__("manufacturing", {"method": "laser-cut"}))
    assert FAIL in statuses(sc, "T4.machine")


def test_n4_machine_without_build_volume_skips_and_blocks(mutate):
    sc = mutate(lambda d: _comp(d, "wing").__setitem__("manufacturing", {"method": "3d-print-fdm", "machine": "jacobs-fdm"}))
    assert SKIP in statuses(sc, "T4.fits_machine")
    assert not sc.accepted
    msgs = [r.message for t in sc.tiers for r in t.results if r.check_id == "T4.fits_machine"]
    assert any("fit not verified — add build_volume_mm to manufacturing.yaml" in m for m in msgs)


def test_n4b_missing_manufacturing_fails(mutate):
    sc = mutate(lambda d: _comp(d, "wing").pop("manufacturing"))
    assert FAIL in statuses(sc, "T4.method")
    assert not sc.accepted


def test_n6_partial_run_never_accepted(example):
    d = load_design(example)
    sc = validate(d, max_tier=1)
    assert sc.accepted is False
    assert sc.to_dict()["partial"] is True and sc.to_dict()["max_tier"] == 1
    assert "Accepted" not in sc.to_markdown()
    assert "**Partial run (tiers 0–1):**" in sc.to_markdown()


def test_n6_partial_cli_exit_follows_run_tiers(mutate, tmp_path, example):
    runner = CliRunner()
    ok = runner.invoke(cli, ["validate", str(example.parent), "--tier", "3"])
    assert ok.exit_code == 0, ok.output
    assert "no failures" in ok.output
    d = load_design(example).data
    _comp(d, "wing")["position"] = [400, 0, 0]  # moves wing off the body: geometry + margin trouble
    _comp(d, "fin_l")["rotation_deg"] = [0, 0, 0]
    (tmp_path / "plane.yaml").write_text(yaml.safe_dump(d, sort_keys=False))
    bad = runner.invoke(cli, ["validate", str(tmp_path), "--tier", "1"])
    assert bad.exit_code == 1 and "failures found" in bad.output
