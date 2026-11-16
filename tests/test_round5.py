"""Round 5 rules (concept A import review): point-mass placement (A), kinematic_link SKIP (B), planform vs geometry (C),
placeholder ratings (D), and the importer's rating_basis conversion."""
from __future__ import annotations

import copy

from aircraft_platform.checks import tier0_schema, validate
from aircraft_platform.design import FAIL, PASS, SKIP, Design, load_design
from aircraft_platform.importers.dbf_ratings import rating, rating_basis

from conftest import EXAMPLE_PATH, statuses
from test_concept_a_rules import linked_design

MFG = {"method": "hand-cut"}


def _run(data: dict, tier: int = 5):
    return validate(Design(data=data, path=None), max_tier=tier)


def _rows(sc, check_id: str):
    return [r for t in sc.tiers for r in t.results if r.check_id == check_id]


def _joint_label(a: dict) -> str:
    return a.get("id") or f"{a['parent']}->{a['child']}"


# ---------------------------------------------------------------- A. point_mass placement

def _body_and_point(pos, extra_components=(), body_size=(100, 100, 100)) -> dict:
    """Cube body (root, centred on the origin) and a 50 g point mass at `pos`, tied to the body."""
    comps = [
        {"id": "body", "type": "structure", "geometry": {"box": {"size": list(body_size)}}, "position": [0, 0, 0],
         "mass_g": 100, "manufacturing": dict(MFG)},
        {"id": "lump", "type": "payload", "geometry": {"point_mass": {}}, "position": list(pos), "mass_g": 50,
         "manufacturing": {"method": "purchased"}},
        *extra_components,
    ]
    return {"schema_version": "0.4", "id": "pm-place", "name": "point mass placement", "status": "concept",
            "morphology": {"lift": "other", "vtol_method": "none"}, "root": "body", "components": comps,
            "attachments": [{"id": "lump-tie", "parent": "body", "child": "lump", "method": "tape",
                             "location": list(pos), "rated_load_n": 50}]}


def _prop_at_origin() -> dict:
    return {"id": "prop", "type": "propeller", "geometry": {"cylinder": {"radius": 50, "length": 10, "axis": "x"}},
            "position": [0, 0, 0], "mass_g": 5, "manufacturing": dict(MFG)}


def test_point_mass_inside_host_passes():
    sc = _run(_body_and_point((0, 0, 40)), tier=1)
    assert statuses(sc, "T1.point_mass_location") == [PASS]


def test_point_mass_within_attach_tolerance_passes():
    sc = _run(_body_and_point((0, 0, 51.5)), tier=1)  # 1.5 mm outside a 2 mm tolerance
    assert statuses(sc, "T1.point_mass_location") == [PASS]


def test_point_mass_50mm_off_its_host_fails():
    sc = _run(_body_and_point((0, 0, 100)), tier=1)  # host top face is at z = 50
    rows = _rows(sc, "T1.point_mass_location")
    assert [r.status for r in rows] == [FAIL]
    assert "50.0 mm from every part it is attached to" in rows[0].message


def test_point_mass_inside_a_prop_disc_fails():
    sc = _run(_body_and_point((0, 0, 0), extra_components=(_prop_at_origin(),)), tier=1)
    rows = _rows(sc, "T1.point_mass_location")
    assert [r.status for r in rows] == [FAIL]
    assert "lies inside the prop disc of prop" in rows[0].message


def test_point_mass_location_fails_through_the_mutate_fixture(mutate):
    def move_off(data):
        data["schema_version"] = "0.4"  # point_mass needs 0.4 (T0.version)
        comp = next(c for c in data["components"] if c["id"] == "battery")
        comp["geometry"] = {"point_mass": {}}
        comp["position"] = [140, 0, -260]
        next(a for a in data["attachments"] if a.get("id") == "battery-bay")["location"] = [140, 0, -260]
    sc = mutate(move_off)
    assert FAIL in statuses(sc, "T1.point_mass_location")


# ---------------------------------------------------------------- B. kinematic_link is SKIP, not WARN

def test_linked_pair_at_pose_is_skip_and_not_accepted():
    sc = _run(linked_design(kinematic=True))
    rows = _rows(sc, "T1.kinematic_link")
    assert rows and all(r.status == SKIP for r in rows)
    assert any(r.message.startswith("pose hover (90°): 1 pair(s) not checked") for r in rows)
    assert sc.accepted is False


# ---------------------------------------------------------------- C. planform matches geometry

def _planform_box(origin_x: float) -> dict:
    """A 245 mm chord x 900 mm span box wing (x 0..245, y +-450) with a same-size planform whose root LE is at origin_x."""
    ls = {"span": 900, "root_chord": 245, "tip_chord": 245, "mirrored": True}
    return {"schema_version": "0.4", "id": "pf", "name": "planform", "status": "concept",
            "morphology": {"lift": "flying-wing", "vtol_method": "none"}, "root": "wng",
            "components": [{"id": "wng", "type": "wing", "geometry": {"box": {"size": [245, 900, 10]}},
                            "position": [122.5, 0, 0], "mass_g": 1000, "manufacturing": dict(MFG),
                            "planform": {"lifting_surface": ls, "origin": [origin_x, 0, 0]}}],
            "attachments": []}


def test_planform_exact_match_passes():
    sc = _run(_planform_box(0.0), tier=3)
    assert statuses(sc, "T3.planform_matches_geometry") == [PASS]


def test_planform_shifted_5mm_aft_fails_and_other_t3_checks_still_run():
    sc = _run(_planform_box(5.0), tier=3)  # limit 2% x 245 mm = 4.9 mm
    rows = _rows(sc, "T3.planform_matches_geometry")
    assert [r.status for r in rows] == [FAIL]
    assert "LE off by -5.0 mm (limit 4.9 mm)" in rows[0].message
    assert "TE off by -5.0 mm (limit 4.9 mm)" in rows[0].message
    assert "T3.stall" in {r.check_id for t in sc.tiers for r in t.results}


# ---------------------------------------------------------------- D. placeholder ratings

def test_placeholder_rating_joint_rows_skip_and_not_accepted(mutate):
    base = load_design(EXAMPLE_PATH)
    label = _joint_label(base.data["attachments"][0])

    def placeholder(data):
        data["schema_version"] = "0.4"  # rating_basis needs 0.4 (T0.version)
        data["attachments"][0]["rating_basis"] = "placeholder"
    sc = mutate(placeholder)
    rows = [r for r in _rows(sc, "T2.joint_load") if r.message.startswith(f"{label}:")]
    assert len(rows) == 1 and rows[0].status == SKIP
    assert "rating is a placeholder, not checked" in rows[0].message and " N;" in rows[0].message
    assert rows[0].data["load_n"] > 0
    assert not any(r.status == PASS and r.message.startswith(f"{label}:") for r in _rows(sc, "T2.joint_load"))
    sim_rows = [r for r in _rows(sc, "T2.sim_drop_loads") if r.message.startswith(f"{label}:")]
    assert all(r.status == SKIP for r in sim_rows)  # empty if mujoco is not installed
    assert sc.accepted is False


def test_rating_basis_needs_schema_040():
    data = copy.deepcopy(load_design(EXAMPLE_PATH).data)
    data["schema_version"] = "0.3"
    data["attachments"][0]["rating_basis"] = "placeholder"
    rep = tier0_schema(Design(data=data, path=None))
    assert any(r.check_id == "T0.version" and r.status == FAIL and "rating_basis" in r.message for r in rep.results)


def test_example_without_rating_basis_has_no_placeholder_skips():
    sc = validate(load_design(EXAMPLE_PATH))
    assert not any(r.status == SKIP and "placeholder" in r.message for t in sc.tiers for r in t.results)
    assert FAIL not in statuses(sc, "T0.version")


def test_rating_basis_conversion_from_kinds():
    assert rating_basis("doc") == "sourced"
    assert rating_basis("placeholder") == "placeholder"
    assert rating_basis("derived") == "derived"
    assert rating_basis("something-else") == "derived"


def test_rating_kinds_from_the_real_rating_function_map_to_basis():
    doc_val, doc_kind, _ = rating({"id": "E-FIN-01", "via": "CT-EPOXY"}, {}, {}, None)
    assert doc_kind == "doc" and rating_basis(doc_kind) == "sourced"
    _, ph_kind, _ = rating({"id": "X-TIE", "via": "CT-TIE"}, {}, {}, None)
    assert ph_kind == "placeholder" and rating_basis(ph_kind) == "placeholder"
    _, d_kind, _ = rating({"id": "X-BOND", "via": "CT-EPOXY"}, {"material": "PETG"}, {"material": "PETG"}, 100.0)
    assert d_kind == "derived" and rating_basis(d_kind) == "derived"
