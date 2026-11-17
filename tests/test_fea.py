"""OpenCAE stress check: load-path planning, verdicts and scorecard reporting (no OpenCAE needed),
plus an end-to-end cantilever run against Euler-Bernoulli when OpenCAE is available."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import numpy as np
import pytest
import trimesh

from aircraft_platform import fea
from aircraft_platform.design import DESIGNS_DIR, load_design

CONCEPT_A = DESIGNS_DIR / "concept-a" / "plane.yaml"


@pytest.fixture(scope="module")
def concept_a():
    return load_design(CONCEPT_A)


@pytest.fixture(scope="module")
def drop(concept_a):
    return fea.joint_loads(concept_a)


def test_joint_loads_have_the_right_direction(drop):
    # foot shoe (parent) -> foot pad (child): on landing the ground pushes the pad toward the nose (-x),
    # so the pad pushes the shoe toward -x
    assert drop["landing"]["E-GER-08"]["force_n"][0] < 0
    # motor cup (parent) -> motor (child) at full thrust: the motor pulls the cup along its thrust axis
    f = np.asarray(drop["thrust"]["E-PRP-07"]["force_n"])
    axis = np.asarray([-0.9563, 0.1651, -0.2413])
    assert f @ axis / np.linalg.norm(f) > 0.95 and 7.0 < np.linalg.norm(f) < 9.5


def test_thrust_case_balances(concept_a, drop):
    """Static solve: the root joint loads plus every external load balance (sum of forces on the root's children)."""
    from aircraft_platform.sim import _landing_rotation
    _, _, up = _landing_rotation(concept_a)
    ext = np.zeros(3)
    for c in concept_a.components:
        ext += -up * c["mass_g"] / 1000 * 9.81
        if c["type"] == "motor":
            ax = np.asarray(c["propulsion"]["axis"], float)
            ext += ax / np.linalg.norm(ax) * c["propulsion"]["max_thrust_n"]
    root = concept_a.data["root"]
    on_root = sum(np.asarray(drop["thrust"][a["id"]]["force_n"]) * (1 if a["parent"] == root else -1)
                  for a in concept_a.data["attachments"] if root in (a["parent"], a["child"]))
    own = -up * concept_a.component(root)["mass_g"] / 1000 * 9.81
    # what reaches the root through its joints is everything except the root's own weight
    assert on_root == pytest.approx(ext - own, abs=1e-3)


def test_hub_is_held_by_bridge_and_struts_not_by_wiring(concept_a, drop):
    meta = fea.plan(concept_a, "cge-001", drop=drop)["meta"]
    assert sorted(s["other"] for s in meta["supports"]) == ["cge-004", "cge-005-l", "cge-005-r"]
    loads = {j["other"] for j in meta["load_joints"]}
    assert {"cge-002-ll", "cge-002-lr", "cge-002-ul", "cge-002-ur", "hrn-004-ll"} <= loads
    thrust = next(c for c in meta["cases"] if c["name"] == "thrust")
    arms = [ld for ld in thrust["loads"] if "cge-002" in ld["name"]]
    assert len(arms) == 4, "each of the four motors reaches the hub through its own arm"
    for ld in arms:  # an arm brings its motor's thrust and a bending moment of roughly thrust x arm length
        assert 7 * meta["ultimate_factor"] < np.linalg.norm(ld["force_n"]) < 9.5 * meta["ultimate_factor"]
        assert np.linalg.norm(ld["moment_nmm"]) > 500
    assert any("small separate piece" in n for n in meta["notes"])


def test_motor_cup_carries_its_motor(concept_a, drop):
    p = fea.plan(concept_a, "cge-003-ll", drop=drop)
    meta, job = p["meta"], p["job"]
    assert [s["other"] for s in meta["supports"]] == ["cge-002-ll"]
    thrust = next(c for c in job["cases"] if c["name"] == "thrust")
    (ld,) = thrust["loads"]
    axis = np.asarray([-0.9563, 0.1651, -0.2413])
    # the motor pulls the cup along its thrust axis (less its own weight in the hover attitude)
    assert np.asarray(ld["force"]) @ axis / np.linalg.norm(ld["force"]) > 0.95
    assert len(job["supports"][0]["points"]) >= 6 and job["material_id"] == "db_petg_um"


def test_only_sourced_materials_are_eligible(concept_a):
    parts = fea.eligible_parts(concept_a)
    assert "cge-001" in parts and "ger-001-ll" in parts
    assert "cge-002-ll" not in parts, "CFRP tubes have no sourced material record yet"
    assert "hrn-003-l" not in parts, "printed wiring raceways are not structure"
    with pytest.raises(ValueError, match="no sourced material"):
        fea.plan(concept_a, "cge-002-ll")


def _case(away, peak, eq=True):
    return {"case": "landing", "max_von_mises_away_mpa": away, "max_von_mises_mpa": peak, "max_displacement_mm": 0.01,
            "nodes": 100, "mesh_size_max_mm": 1.0, "equilibrium_ok": eq, "load_on_clamped_faces_n": [0, 0, 0],
            "applied_force_n": [0, 0, 10], "max_von_mises_away_location": [0, 0, 0]}


@pytest.mark.parametrize("away,peak,eq,status", [(5.0, 6.0, True, "PASS"), (5.0, 20.0, True, "WARN"),
                                                 (13.0, 20.0, True, "FAIL"), (5.0, 6.0, False, "FAIL")])
def test_verdicts(away, peak, eq, status):
    meta = {"allowable_mpa": 12.6, "ultimate_factor": 1.5, "notes": []}
    rec = fea.judge(meta, {"cases": [_case(away, peak, eq)]})
    assert rec["status"] == status
    assert rec["cases"][0]["safety_factor_at_ultimate"] == pytest.approx(round(12.6 / away, 2))


def test_coarse_mesh_or_loose_model_is_not_checked():
    meta = {"allowable_mpa": 12.6, "ultimate_factor": 1.5, "notes": [], "wall_mm": {"p5": 0.8, "median": 1.2},
            "part_size_mm": 120.0}
    coarse = dict(_case(200.0, 200.0), element_size_mm=2.5, route="direct-mesh")
    rec = fea.judge(meta, {"cases": [coarse]})
    assert rec["status"] == "NOT CHECKED" and "too coarse" in rec["cases"][0]["message"]
    loose = dict(_case(5.0, 5.0), element_size_mm=1.0, max_displacement_mm=50.0)
    rec = fea.judge(meta, {"cases": [loose]})
    assert rec["status"] == "NOT CHECKED" and "isn't held" in rec["cases"][0]["message"]
    ok = dict(_case(5.0, 6.0), element_size_mm=1.0)
    assert fea.judge(meta, {"cases": [ok]})["status"] == "PASS"


def test_scorecard_rows_and_staleness(tmp_path, monkeypatch):
    src = DESIGNS_DIR / "concept-a"
    dst = tmp_path / "concept-a"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("fea"))
    d = load_design(dst / "plane.yaml")
    rows = fea.tier2_fea(d)
    assert len(rows) == 1 and rows[0].status == "SKIP" and "no OpenCAE stress check" in rows[0].message
    rec = fea.judge({"allowable_mpa": 12.6, "ultimate_factor": 1.5, "notes": [], "allowable_key": "fea_allowable_printed_petg_mpa"},
                    {"cases": [_case(2.0, 3.0)]})
    rec["hash"] = fea.part_hash(d, "ger-001-ll")
    fea.result_path(d, "ger-001-ll").parent.mkdir(parents=True)
    fea.result_path(d, "ger-001-ll").write_text(json.dumps(rec))
    rows = fea.tier2_fea(d)
    ok = [r for r in rows if r.status == "PASS"]
    assert len(ok) == 1 and "ger-001-ll landing" in ok[0].message and ok[0].criterion.endswith("fea_allowable_printed_petg_mpa")
    # any edit to the design makes the stored result out of date
    (dst / "plane.yaml").write_text((dst / "plane.yaml").read_text() + "\n# edited\n")
    d2 = load_design(dst / "plane.yaml")
    assert any(r.status == "SKIP" and "out of date" in r.message for r in fea.tier2_fea(d2))


@pytest.mark.skipif(not fea.find_opencae()["found"], reason="OpenCAE not set up on this machine")
@pytest.mark.parametrize("mesher", ["opencae-cad", "direct", "tetwild"])
def test_cantilever_matches_beam_theory(tmp_path, mesher):
    """200 x 20 x 20 mm steel cantilever, 1000 N tip load: FL^3/3EI = 1.000 mm; root bending stress at 20 mm
    from the clamp M c / I = 1000 * 180 * 10 / 13333 = 135 MPa."""
    import subprocess
    oc = fea.find_opencae()
    b = trimesh.creation.box(extents=[200, 20, 20])
    b.apply_translation([100, 0, 0])
    b.export(tmp_path / "beam.stl")
    pts, _ = trimesh.sample.sample_surface_even(b, 20000, seed=1)
    job = {"name": "cantilever", "stl": str(tmp_path / "beam.stl"), "material_id": "mat_steel",
           "mesh": {"size_max": 4.0, "order": 2}, "select_tol_mm": 0.6, "singularity_band_mm": 20.0,
           "supports": [{"name": "root", "points": pts[np.abs(pts[:, 0]) < 0.05].tolist()}],
           "cases": [{"name": "tip", "loads": [{"name": "tip", "points": pts[np.abs(pts[:, 0] - 200) < 0.05].tolist(),
                                                "force": [0, 0, -1000.0], "point": [200, 0, 0]}]}],
           "out": str(tmp_path / "res.json"), "force_direct": mesher != "opencae-cad",
           "mesher": "tetwild" if mesher == "tetwild" else None}
    (tmp_path / "job.json").write_text(json.dumps(job))
    env = dict(os.environ, PYTHONPATH=oc["root"])
    subprocess.run([oc["python"], str(fea.RUNNER), str(tmp_path / "job.json")], env=env, cwd=tmp_path, timeout=900)
    res = json.loads((tmp_path / "res.json").read_text())
    assert res["error"] is None, res.get("traceback")
    (c,) = res["cases"]
    assert c["max_displacement_mm"] == pytest.approx(1.0, rel=0.02)
    assert c["max_von_mises_away_mpa"] == pytest.approx(135.0, rel=0.03)
    assert c["equilibrium_ok"]
