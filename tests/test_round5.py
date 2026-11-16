"""Round 5 rules (concept A import review): point-mass placement (A), kinematic_link SKIP (B), planform vs geometry (C),
placeholder ratings (D), and the importer's rating_basis conversion."""
from __future__ import annotations

import copy

import numpy as np
import trimesh

from aircraft_platform.checks import tier0_schema, validate
from aircraft_platform.design import FAIL, PASS, SKIP, WARN, Design, load_design
from aircraft_platform.checks import _planform_parts
from aircraft_platform.geometry import component_parts, lifting_surface_halves, strip_planform
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


# ---------------------------------------------------------------- A (cont.). distributed point masses

def _dist_design(lumps, body_mass=900, prop=False, reason=True) -> dict:
    """Body cube (z -50..50, mass body_mass) plus a top box (z 50..90, x/y +-20) so the envelope reaches z 90.
    `lumps`: (id, position, mass_g, type, distributed). Each lump is tied to the body at its position."""
    comps = [
        {"id": "body", "type": "structure", "geometry": {"box": {"size": [100, 100, 100]}}, "position": [0, 0, 0],
         "mass_g": body_mass, "manufacturing": dict(MFG)},
        {"id": "top", "type": "structure", "geometry": {"box": {"size": [40, 40, 40]}}, "position": [0, 0, 70],
         "mass_g": 10, "manufacturing": dict(MFG)},
    ]
    atts = [{"id": "top-tie", "parent": "body", "child": "top", "method": "glued", "location": [0, 0, 50], "rated_load_n": 20}]
    for lid, pos, mass, typ, distributed in lumps:
        pm = {"distributed": True, "reason": "test lump"} if distributed else {}
        if distributed and not reason:
            pm = {"distributed": True}
        comps.append({"id": lid, "type": typ, "geometry": {"point_mass": pm}, "position": list(pos), "mass_g": mass,
                      "manufacturing": {"method": "purchased"}})
        atts.append({"id": f"{lid}-tie", "parent": "body", "child": lid, "method": "tape", "location": list(pos),
                     "rated_load_n": 50})
    if prop:
        comps.append(_prop_at_origin())
    return {"schema_version": "0.4", "id": "dist", "name": "distributed", "status": "concept",
            "morphology": {"lift": "other", "vtol_method": "none"}, "root": "body", "components": comps,
            "attachments": atts}


def test_distributed_point_inside_envelope_but_off_host_passes():
    # (0, 0, 60): 10 mm above the body top (z 50), inside the hull of body + top box; 20 g of 930 g
    sc = _run(_dist_design([("lump", (0, 0, 60), 20, "other", True)]), tier=1)
    assert statuses(sc, "T1.point_mass_location") == [PASS]
    # the same point as a normal point mass fails the host test (10 mm off the body)
    sc_strict = _run(_dist_design([("lump", (0, 0, 60), 20, "other", False)]), tier=1)
    assert statuses(sc_strict, "T1.point_mass_location") == [FAIL]


def test_distributed_point_outside_envelope_fails():
    sc = _run(_dist_design([("lump", (0, 0, 200), 20, "other", True)]), tier=1)  # envelope top is z 90
    rows = _rows(sc, "T1.point_mass_location")
    assert [r.status for r in rows] == [FAIL]
    assert "lies outside the aircraft's envelope by 110.0 mm" in rows[0].message


def test_distributed_point_inside_prop_disc_fails():
    sc = _run(_dist_design([("lump", (0, 0, 0), 20, "other", True)], prop=True), tier=1)
    rows = _rows(sc, "T1.point_mass_location")
    assert [r.status for r in rows] == [FAIL]
    assert "lies inside the prop disc of prop" in rows[0].message


def test_distributed_on_type_payload_fails():
    sc = _run(_dist_design([("lump", (0, 0, 40), 20, "payload", True)]), tier=1)
    msgs = [r.message for r in _rows(sc, "T1.point_mass_location") if r.status == FAIL]
    assert any("distributed point masses are only for type other" in m and "payload parts" in m for m in msgs), msgs


def test_distributed_single_mass_over_3_percent_fails():
    sc = _run(_dist_design([("lump", (0, 0, 40), 40, "other", True)], body_mass=900), tier=1)  # 40 of 950 g = 4.2%
    msgs = [r.message for r in _rows(sc, "T1.point_mass_location") if r.status == FAIL]
    assert any("may carry at most 3%" in m for m in msgs), msgs


def test_distributed_two_masses_each_ok_but_5_2_percent_total_fails():
    sc = _run(_dist_design([("lump-a", (0, 0, 40), 26, "other", True), ("lump-b", (0, 0, 60), 26, "other", True)],
                           body_mass=938), tier=1)  # 26 g each of 1000 g = 2.6%; 52 g = 5.2% total
    msgs = [r.message for r in _rows(sc, "T1.point_mass_location") if r.status == FAIL]
    assert not any("may carry at most" in m for m in msgs), msgs
    assert any("together carry 52.0 g (5.2% of the 1000 g aircraft); the limit is 5%" in m for m in msgs), msgs


def test_distributed_without_reason_is_t0_fail():
    sc = _run(_dist_design([("lump", (0, 0, 60), 20, "other", True)], reason=False), tier=5)
    assert statuses(sc, "T0.schema") == [FAIL]


# ---------------------------------------------------------------- C (cont.). planform scope includes articulated children

def _elevon_wing(articulated: bool) -> dict:
    """Core box x 0..183.8 (the planform's own part) and a 61.2 mm elevon box x 183.8..245, outboard of it. The planform is
    245 mm chord. The elevon is a child of the core through a joint that carries articulation only when `articulated`."""
    ls = {"span": 900, "root_chord": 245, "tip_chord": 245, "mirrored": True}
    joint = {"id": "elevon-hinge", "parent": "core", "child": "elevon", "method": "hinge", "location": [183.8, 0, 0],
             "rated_load_n": 10}
    if articulated:
        joint["articulation"] = {"type": "revolute", "pivot": [183.8, 0, 0], "axis": [0, 1, 0],
                                 "range_deg": [-21, 21], "poses": {"neutral": 0}}
    return {"schema_version": "0.4", "id": "elevon", "name": "elevon", "status": "concept",
            "morphology": {"lift": "flying-wing", "vtol_method": "none"}, "root": "core",
            "components": [
                {"id": "core", "type": "wing", "geometry": {"box": {"size": [183.8, 900, 10]}}, "position": [91.9, 0, 0],
                 "mass_g": 500, "manufacturing": dict(MFG),
                 "planform": {"lifting_surface": ls, "origin": [0, 0, 0]}},
                {"id": "elevon", "type": "wing", "geometry": {"box": {"size": [61.2, 900, 10]}}, "position": [214.3, 0, 0],
                 "mass_g": 50, "manufacturing": dict(MFG)},
            ],
            "attachments": [joint]}


def test_planform_with_articulated_elevon_matches_union_of_geometry():
    sc = _run(_elevon_wing(articulated=True), tier=3)
    rows = _rows(sc, "T3.planform_matches_geometry")
    assert [r.status for r in rows] == [PASS]
    assert "core, elevon" in rows[0].message


def _t3(sc) -> dict:
    return {r.check_id: r for t in sc.tiers for r in t.results}


def test_declared_planform_shift_changes_no_aero_number():
    """The aero numbers come from the measured geometry: moving the declared outline changes nothing (only a WARN if
    the declared area or span disagree with the geometry)."""
    base = _t3(_run(_planform_box(0.0), tier=3))
    shifted = _t3(_run(_planform_box(3.0), tier=3))
    assert shifted["T3.stall"].data == base["T3.stall"].data
    assert shifted["T3.static_margin"].data == base["T3.static_margin"].data
    assert shifted["T3.planform_matches_geometry"].status == PASS


def test_planform_area_mismatch_is_warn_not_fail():
    """Declared 245 x 900 planform on a 200 x 900 box: the planform row WARNs with both areas; the numbers still come from
    the box (no FAIL from the cross-check)."""
    data = _planform_box(0.0)
    data["components"][0]["geometry"] = {"box": {"size": [220, 900, 10]}}  # -10.2% area: inside the 15% WARN band
    t3 = _t3(_run(data, tier=3))
    assert t3["T3.planform_matches_geometry"].status == WARN
    assert "declared area 220500 mm^2 vs measured 198000 mm^2" in t3["T3.planform_matches_geometry"].message
    assert t3["T3.stall"].status in (PASS, FAIL)
    assert "(mesh wing: chord measured at 41 stations)" in t3["T3.static_margin"].message


def test_planform_without_articulation_on_elevon_fails_and_changes_numbers():
    """Without the elevon's articulation block the elevon is not part of the wing: the measured chord is 183.8 mm,
    so the declared 245 mm planform WARNs and the measured MAC and x_ac differ from the articulated wing."""
    with_art = _t3(_run(_elevon_wing(articulated=True), tier=3))
    without = _t3(_run(_elevon_wing(articulated=False), tier=3))
    assert with_art["T3.planform_matches_geometry"].status == PASS
    assert without["T3.planform_matches_geometry"].status == FAIL  # -25% area: beyond the 15% band
    assert "declared and measured lifting areas disagree" in without["T3.planform_matches_geometry"].message
    assert without["T3.planform_matches_geometry"].message.startswith("core: declared and measured lifting areas")
    assert without["T3.static_margin"].data != with_art["T3.static_margin"].data


def _notched_box() -> dict:
    data = _planform_box(0.0)
    comp = data["components"][0]
    comp["geometry"] = {"box": {"size": [245, 900, 10]}}
    comp["cavities"] = [{"geometry": {"box": {"size": [140, 450, 20]}}, "position": [70, 0, 0]}]
    return data


def test_notched_mesh_wing_strip_matches_analytic():
    """Chord 245 mm outboard of |y| = 225 mm, 122.5 mm inboard (trailing half removed). Analytic area 165375 mm^2 and
    chord-weighted quarter-chord x_ac 51.04 mm from the LE (LE at x = 0)."""
    data = _notched_box()
    m = strip_planform({"box": component_parts(data["components"][0])}, "box")
    area = 2 * 225 * 245 + 450 * 122.5
    x_ac = (0.25 * 122.5 * 122.5 * 450 + 0.25 * 245 * 245 * 450) / area
    assert abs(m["area_mm2"] / area - 1) <= 0.01
    assert abs(m["x_ac_mm"] - x_ac) <= 1.0
    t3 = _t3(_run(data, tier=3))
    assert t3["T3.planform_matches_geometry"].status == FAIL  # -25% area: beyond the 15% band


def test_tapered_mesh_wing_strip_matches_analytic():
    """Tapered half-wings (root 245, tip 120 mm, span 900, LE straight): analytic area and x_ac."""
    ls = {"span": 900, "root_chord": 245, "tip_chord": 120, "mirrored": True}
    parts = [trimesh.convex.convex_hull(v) for v in lifting_surface_halves(ls)]
    m = strip_planform({"tail": parts}, "tail")
    semi, cr, ct = 450.0, 245.0, 120.0
    y = np.linspace(0, semi, 200001)
    c = cr + (ct - cr) * y / semi
    area = 2 * np.trapezoid(c, y)
    x_ac = 2 * np.trapezoid(0.25 * c * c, y) / area
    assert abs(m["area_mm2"] / area - 1) <= 0.01
    assert abs(m["x_ac_mm"] - x_ac) <= 1.0


def test_rectangular_box_wing_is_exact():
    """Box wing 245 mm chord, 900 mm span, LE at x = 0: MAC = chord within 0.5 %, x_ac = LE + c/4 within 0.5 mm,
    area within 0.1 %."""
    box = trimesh.creation.box(extents=[245, 900, 10])
    box.apply_translation([122.5, 0, 0])
    m = strip_planform({"box": [box]}, "box")
    assert abs(m["mac_mm"] / 245 - 1) <= 0.005
    assert abs(m["x_ac_mm"] - (0 + 245 / 4)) <= 0.5
    assert abs(m["area_mm2"] / (245 * 900) - 1) <= 0.001


def _planform_as(ctype: str, size=(245, 900, 10)) -> dict:
    data = _planform_box(0.0)
    data["components"][0]["type"] = ctype
    data["components"][0]["geometry"] = {"box": {"size": list(size)}}
    return data


def test_planform_on_structure_fails_and_is_not_a_lifting_surface():
    """The f1 case: a planform copied onto a fuselage-type box. Rejected by type, and not measured as a wing."""
    sc = _run(_planform_as("structure"), tier=5)
    rows = _rows(sc, "T3.planform_matches_geometry")
    assert [r.status for r in rows] == [FAIL]
    assert "planform declared on a structure; only wing or tail_surface parts are lifting surfaces" in rows[0].message
    assert "T3.stall" not in {r.check_id for t in sc.tiers for r in t.results if "mesh wing" in r.message}
    assert sc.accepted is False


def test_planform_on_battery_fails():
    """The f2 case: a planform on the battery. Rejected by type."""
    sc = _run(_planform_as("battery"), tier=5)
    rows = _rows(sc, "T3.planform_matches_geometry")
    assert [r.status for r in rows] == [FAIL]
    assert "planform declared on a battery" in rows[0].message
    assert sc.accepted is False


def test_planform_area_8_percent_smaller_is_warn_only():
    sc = _run(_planform_as("wing", size=(245, 828, 10)), tier=3)  # -8% area and span
    assert statuses(sc, "T3.planform_matches_geometry") == [WARN]


def test_planform_area_20_percent_smaller_fails():
    sc = _run(_planform_as("wing", size=(245, 720, 10)), tier=3)  # -20% area and span
    assert statuses(sc, "T3.planform_matches_geometry") == [FAIL]
    assert sc.tiers and any(r.status == FAIL for t in sc.tiers for r in t.results if r.check_id == "T3.planform_matches_geometry")


def _owners_box_with_elevon(gap_mm: float, control: bool = True):
    """Core 0..200 mm chord and an elevon 25 mm chord aft of a gap_mm pocket (245 mm chord total). Returns the owner map
    and the planform root id."""
    core = trimesh.creation.box(extents=[200, 900, 10])
    core.apply_translation([100, 0, 0])
    lo = 200 + gap_mm
    elev = trimesh.creation.box(extents=[245 - lo, 900, 10])
    elev.apply_translation([(lo + 245) / 2, 0, 0])
    return {"wing": [core], "elevon": [elev]}, "wing"


def test_hinge_gap_2mm_measures_full_chord():
    owners, root = _owners_box_with_elevon(2.0)
    m = strip_planform(owners, root)
    assert abs(m["area_mm2"] / (245 * 900) - 1) <= 0.001
    assert m["ignored_strips"] == []


def test_balance_pocket_20mm_on_245_chord_measures_full_chord():
    """Wing and elevon separated by a 20 mm pocket (8.2% of chord, inside the 15% control-surface band): full chord."""
    owners, root = _owners_box_with_elevon(20.0)
    m = strip_planform(owners, root)
    assert abs(m["area_mm2"] / (245 * 900) - 1) <= 0.001
    assert m["control_gap_strips"]  # the pocket was bridged and is reported


def test_non_articulated_piece_20mm_away_is_not_measured():
    """A piece that is not articulated to the wing is not one of its owners: it is never measured, so it cannot
    add chord. Measured wing = the wing alone."""
    d = _planform_box(0.0)
    piece = {"id": "piece", "type": "structure", "geometry": {"box": {"size": [25, 900, 10]}},
             "position": [257.5, 0, 0], "mass_g": 5, "manufacturing": dict(MFG)}
    d["components"].append(piece)
    geo_ids, owners = _planform_parts_for(d)
    assert geo_ids == ["wng"]
    m = strip_planform(owners, "wng")
    assert abs(m["area_mm2"] / (245 * 900) - 1) <= 0.001


def _planform_parts_for(data):
    from aircraft_platform.checks import _planform_parts
    dsg = Design(data=data, path=None)
    return _planform_parts(dsg, dsg.component("wng"))


def test_s1_declared_yaw_changes_no_aero_number_and_fails_axis():
    """Attack s1: only the declared rotation is yawed 15 deg. The slicing axes come from the geometry, so the aero numbers
    are identical; the declared span direction is 15 deg off the measured span, which FAILs the planform row."""
    base = _t3(_run(_planform_box(0.0), tier=3))
    yawed_data = _planform_box(0.0)
    yawed_data["components"][0]["planform"]["rotation_deg"] = [0, 0, 15]
    yawed = _t3(_run(yawed_data, tier=3))
    assert yawed["T3.static_margin"].data == base["T3.static_margin"].data
    assert yawed["T3.stall"].data == base["T3.stall"].data
    assert yawed["T3.planform_matches_geometry"].status == FAIL
    assert "declared span runs 15.0 deg" in yawed["T3.planform_matches_geometry"].message


def test_s4_detached_forward_strip_is_ignored_and_warned():
    """Attack s4: a 10 x 200 x 1 mm articulated strip 60 mm ahead of the LE (joined by a 1 mm rod, range [0, 0]). The
    60 mm gap is beyond 15% of the local envelope, so the strip is detached: area unchanged, planform WARN."""
    _, base_owners = _planform_parts_for(_planform_box(0.0))
    base = strip_planform(base_owners, "wng")
    d = _planform_box(0.0)
    d["components"].append({"id": "rod2", "type": "structure", "geometry": {"box": {"size": [60, 1, 1]}},
                            "position": [-30, 200, -4.7], "mass_g": 1, "manufacturing": dict(MFG)})
    d["components"].append({"id": "fwdstrip", "type": "structure", "geometry": {"box": {"size": [10, 200, 1]}},
                            "position": [-65, 200, -4.7], "mass_g": 1, "manufacturing": dict(MFG)})
    d["attachments"] += [
        {"id": "E-FAKE-ROD2", "parent": "wng", "child": "rod2", "method": "hinge", "location": [0, 200, -4.7],
         "rated_load_n": 5, "articulation": {"type": "revolute", "pivot": [0, 200, -4.7], "axis": [0, 1, 0],
                                             "range_deg": [0, 0], "poses": {"neutral": 0}}},
        {"id": "E-FAKE-STRIP", "parent": "rod2", "child": "fwdstrip", "method": "hinge", "location": [-60, 200, -4.7],
         "rated_load_n": 5, "articulation": {"type": "revolute", "pivot": [-60, 200, -4.7], "axis": [0, 1, 0],
                                             "range_deg": [0, 0], "poses": {"neutral": 0}}},
    ]
    _, owners = _planform_parts_for(d)
    attacked = strip_planform(owners, "wng")
    assert attacked["area_mm2"] == base["area_mm2"]
    assert attacked["x_ac_mm"] == base["x_ac_mm"]
    rows = _rows(_run(d, tier=3), "T3.planform_matches_geometry")
    assert [r.status for r in rows] == [WARN]
    assert "detached material ignored" in rows[0].message


def test_fin_with_span_along_z_is_measured_along_z():
    """A 60 mm chord x 3 mm thick x 200 mm fin, span along body z. Declared rotation [90, 0, 0] turns the planform's
    span (local y) onto body z, so the declared and measured spans agree."""
    fin = {"id": "fin", "type": "tail_surface", "geometry": {"box": {"size": [60, 3, 200]}}, "position": [30, 0, 100],
           "mass_g": 20, "manufacturing": dict(MFG),
           "planform": {"lifting_surface": {"span": 200, "root_chord": 60, "tip_chord": 60, "mirrored": False},
                        "origin": [0, 0, 0], "rotation_deg": [90, 0, 0]}}
    data = {"schema_version": "0.4", "id": "fin", "name": "fin", "status": "concept",
            "morphology": {"lift": "other", "vtol_method": "none"}, "root": "fin", "components": [fin], "attachments": []}
    dsg = Design(data=data, path=None)
    geo_ids, owners = _planform_parts(dsg, dsg.component("fin"))
    m = strip_planform(owners, "fin")
    assert m["span_axis"] == "z"
    assert abs(m["span_mm"] - 200) < 1e-6
    assert abs(m["area_mm2"] / (60 * 200) - 1) <= 0.001
    assert _rows(_run(data, tier=3), "T3.planform_matches_geometry")[0].status == PASS

