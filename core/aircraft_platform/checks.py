"""Validation tiers. Each tier function returns a TierReport.

Tier 0  schema         the file matches schema/plane.schema.json
Tier 1  geometry       everything attached, nothing clips, prop discs clear
Tier 2  physics        static joint loads, hover moment balance (MuJoCo drop test: see sim.py)
Tier 3  aero           mass, wing loading, stall speed, static margin, hover T/W
Tier 4  manufacturing  methods/machines exist in standards/manufacturing.yaml
Tier 5  standards      regulatory and named-standard checklist
"""
from __future__ import annotations

import json
import math
import warnings
warnings.filterwarnings('ignore', category=RuntimeWarning, module='trimesh')
from collections import defaultdict, deque

import numpy as np
import trimesh
from jsonschema import Draft202012Validator

from .design import (Design, CheckResult, TierReport, Scorecard, SCHEMA_PATH, REPO_ROOT,
                     PASS, FAIL, WARN, SKIP, load_standards)
from .geometry import component_parts, lifting_surface_properties
from .mass import mass_properties

G = 9.80665
RHO_DEFAULT = 1.225  # ISA sea level, kg/m^3 (physical constant, matches the schema default)
STD = "design-standards.yaml#"
# Convention from design-standards.yaml#embed_max_fraction_of_child: these may be fully contained.
EMBED_PARENTS = {"fuselage", "pod"}
EMBED_CHILDREN = {"battery", "esc", "flight_controller", "receiver", "payload", "servo"}


# ---------------------------------------------------------------- tier 0
def tier0_schema(design: Design) -> TierReport:
    schema = json.loads(SCHEMA_PATH.read_text())
    errors = sorted(Draft202012Validator(schema).iter_errors(design.data), key=lambda e: list(e.path))
    if errors:
        res = [CheckResult("T0.schema", FAIL, f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}",
                           "schema/plane.schema.json") for e in errors[:20]]
    else:
        res = [CheckResult("T0.schema", PASS, "matches schema v0.1", "schema/plane.schema.json")]
    ids = [c["id"] for c in design.components]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        res.append(CheckResult("T0.unique_ids", FAIL, f"duplicate component ids: {sorted(dupes)}",
                               "schema/plane.schema.json"))
    known = set(ids)
    bad = [a for a in design.data.get("attachments", []) if a["parent"] not in known or a["child"] not in known]
    if bad:
        res.append(CheckResult("T0.attachment_refs", FAIL,
                               "attachments reference unknown components: " +
                               ", ".join(f"{a['parent']}->{a['child']}" for a in bad),
                               "schema/plane.schema.json"))
    if design.data.get("root") not in known:
        res.append(CheckResult("T0.root", FAIL, f"root '{design.data.get('root')}' is not a component",
                               "schema/plane.schema.json"))
    return TierReport(0, "schema", res)


# ---------------------------------------------------------------- tier 1
def _overlap_volume(a: list[trimesh.Trimesh], b: list[trimesh.Trimesh]) -> float:
    vol = 0.0
    for pa in a:
        for pb in b:
            lo = np.maximum(pa.bounds[0], pb.bounds[0])
            hi = np.minimum(pa.bounds[1], pb.bounds[1])
            if np.any(hi <= lo):
                continue
            try:
                inter = trimesh.boolean.intersection([pa, pb], engine="manifold")
                vol += abs(inter.volume) if inter is not None and len(inter.faces) else 0.0
            except Exception:
                vol += float(np.prod(hi - lo))  # conservative fallback
    return vol


def _min_distance(a: list[trimesh.Trimesh], b: list[trimesh.Trimesh]) -> float:
    best = math.inf
    for pa in a:
        for pb in b:
            pts_a = trimesh.sample.sample_surface_even(pa, 400, seed=1)[0] if len(pa.faces) else pa.vertices
            pts_b = trimesh.sample.sample_surface_even(pb, 400, seed=1)[0] if len(pb.faces) else pb.vertices
            pts_a = np.vstack([pts_a, pa.vertices])
            pts_b = np.vstack([pts_b, pb.vertices])
            best = min(best, float(np.min(np.abs(trimesh.proximity.signed_distance(pb, pts_a)))),
                       float(np.min(np.abs(trimesh.proximity.signed_distance(pa, pts_b)))))
    return best


def _point_distance(parts: list[trimesh.Trimesh], p) -> float:
    """0 if p is inside any part, else distance to the nearest surface."""
    best = math.inf
    for m in parts:
        sd = float(trimesh.proximity.signed_distance(m, np.array([p]))[0])  # >0 inside
        best = min(best, 0.0 if sd >= 0 else -sd)
    return best


def tier1_geometry(design: Design, std: dict) -> TierReport:
    g = std["geometry"]
    tol = g["attach_tolerance_mm"]["value"]
    max_int = g["interference_max_mm3"]["value"]
    max_frac = g["glued_overlap_max_fraction"]["value"]
    embed_frac = g["embed_max_fraction_of_child"]["value"]
    meshes = {cid: component_parts(design.component(cid), design.base_dir) for cid in (c["id"] for c in design.components)}
    atts = design.data.get("attachments", [])
    res: list[CheckResult] = []

    # watertight geometry
    leaky = [cid for cid, ps in meshes.items() if not all(p.is_watertight for p in ps)]
    res.append(CheckResult("T1.watertight", FAIL if leaky else PASS,
                           f"non-watertight: {leaky}" if leaky else "all component meshes are closed",
                           STD + "interference_max_mm3"))

    # connectivity
    adj = defaultdict(set)
    for a in atts:
        adj[a["parent"]].add(a["child"]); adj[a["child"]].add(a["parent"])
    root = design.data["root"]
    seen, q = {root}, deque([root])
    while q:
        for n in adj[q.popleft()]:
            if n not in seen:
                seen.add(n); q.append(n)
    loose = sorted(set(meshes) - seen)
    res.append(CheckResult("T1.connectivity", FAIL if loose else PASS,
                           f"not attached to '{root}' (would fall off): {loose}" if loose
                           else f"all {len(meshes)} components connect to '{root}'",
                           STD + "attach_tolerance_mm"))

    # each attachment: parts actually touch, joint point on both, overlap sane
    attached_pairs = set()
    for a in atts:
        p, c = a["parent"], a["child"]
        attached_pairs.add(frozenset((p, c)))
        label = a.get("id") or f"{p}->{c}"
        ptype, ctype = design.component(p)["type"], design.component(c)["type"]
        embed = a.get("embed_ok", False)
        if embed and "propeller" in (ptype, ctype):
            res.append(CheckResult("T1.attachment_overlap", FAIL,
                                   f"{label}: a propeller can never be an embed_ok joint (its swept disc must not pass into a part)",
                                   STD + "embed_max_fraction_of_child"))
            continue
        ov = _overlap_volume(meshes[p], meshes[c])
        if ov <= 0:
            d = _min_distance(meshes[p], meshes[c])
            if d > tol:
                res.append(CheckResult("T1.attachment_contact", FAIL,
                                       f"{label}: parts are {d:.1f} mm apart (tolerance {tol} mm)",
                                       STD + "attach_tolerance_mm", {"gap_mm": round(d, 2)}))
                continue
        elif embed:
            if not (ptype in EMBED_PARENTS and ctype in EMBED_CHILDREN):
                child_vol = sum(x.volume for x in meshes[c])
                frac = ov / child_vol if child_vol else 1.0
                if frac > embed_frac:
                    res.append(CheckResult("T1.attachment_overlap", FAIL,
                                           f"{label}: embed_ok joint overlaps {frac:.0%} of the child {c} (limit {embed_frac:.0%})",
                                           STD + "embed_max_fraction_of_child", {"overlap_fraction_of_child": round(frac, 3)}))
                    continue
        else:
            smaller = min(sum(x.volume for x in meshes[p]), sum(x.volume for x in meshes[c]))
            frac = ov / smaller if smaller else 0
            if frac > max_frac:
                res.append(CheckResult("T1.attachment_overlap", FAIL,
                                       f"{label}: parts overlap {frac:.0%} of the smaller part; set embed_ok if intended",
                                       STD + "glued_overlap_max_fraction", {"overlap_fraction": round(frac, 3)}))
                continue
        loc = a.get("location")
        if loc is None:
            res.append(CheckResult("T1.attachment_location", FAIL, f"{label}: no joint location given",
                                   "schema/plane.schema.json"))
            continue
        dp, dc = _point_distance(meshes[p], loc), _point_distance(meshes[c], loc)
        if max(dp, dc) > tol:
            res.append(CheckResult("T1.attachment_location", FAIL,
                                   f"{label}: joint point is {dp:.1f} mm from {p} and {dc:.1f} mm from {c}",
                                   STD + "attach_tolerance_mm"))
        else:
            res.append(CheckResult("T1.attachment", PASS, f"{label}: {a['method']} joint OK",
                                   STD + "attach_tolerance_mm"))

    # interference between non-attached parts
    ids = list(meshes)
    clashes = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if frozenset((ids[i], ids[j])) in attached_pairs:
                continue
            v = _overlap_volume(meshes[ids[i]], meshes[ids[j]])
            if v > max_int:
                clashes.append((ids[i], ids[j], v))
    for a_, b_, v in clashes:
        kind = "prop strike" if "propeller" in (design.component(a_)["type"], design.component(b_)["type"]) else "clipping"
        res.append(CheckResult("T1.interference", FAIL, f"{kind}: {a_} and {b_} overlap {v:.0f} mm^3",
                               STD + "interference_max_mm3", {"pair": [a_, b_], "volume_mm3": round(v, 1)}))
    if not clashes:
        res.append(CheckResult("T1.interference", PASS, "no clipping between unattached parts",
                               STD + "interference_max_mm3"))
    return TierReport(1, "geometry", res)


# ---------------------------------------------------------------- tier 2
def _subtree_mass(design: Design, parent: str, child: str) -> float:
    """Mass on the child side if the parent-child joint were cut."""
    adj = defaultdict(set)
    for a in design.data.get("attachments", []):
        adj[a["parent"]].add(a["child"]); adj[a["child"]].add(a["parent"])
    seen, q = {child}, deque([child])
    while q:
        n = q.popleft()
        for m in adj[n]:
            if m not in seen and not (n == child and m == parent):
                seen.add(m); q.append(m)
    if parent in seen:  # joint is in a loop: load is shared, use child mass only
        seen = {child}
    return sum(design.component(i)["mass_g"] for i in seen)


def tier2_physics(design: Design, std: dict, mp: dict) -> TierReport:
    res: list[CheckResult] = []
    n = std["structure"]["landing_load_factor"]["value"] * std["structure"].get("ultimate_factor", {}).get("value", 1.0)
    for a in design.data.get("attachments", []):
        label = a.get("id") or f"{a['parent']}->{a['child']}"
        load = _subtree_mass(design, a["parent"], a["child"]) / 1000 * G * n
        rated = a.get("rated_load_n")
        if rated is None:
            res.append(CheckResult("T2.joint_load", FAIL, f"{label}: carries {load:.1f} N at {n}g, no rated_load_n given",
                                   STD + "landing_load_factor", {"load_n": round(load, 2)}))
        elif rated < load:
            res.append(CheckResult("T2.joint_load", FAIL, f"{label}: {load:.1f} N at {n}g exceeds rating {rated} N",
                                   STD + "landing_load_factor", {"load_n": round(load, 2)}))
        else:
            res.append(CheckResult("T2.joint_load", PASS, f"{label}: {load:.1f} N <= {rated} N",
                                   STD + "landing_load_factor"))

    lift_motors = [c for c in design.components if c["type"] == "motor"
                   and c["propulsion"].get("role", "both") in ("lift", "both")]
    if design.data["morphology"].get("vtol_method", "none") != "none" and lift_motors:
        cg = np.array(mp["cg_mm"])
        torque = np.zeros(3)
        force = np.zeros(3)
        for m in lift_motors:
            parts = component_parts(m, design.base_dir)
            pos = np.mean([p.center_mass for p in parts], axis=0)
            axis = np.array(m["propulsion"]["axis"], dtype=float)
            axis /= np.linalg.norm(axis)
            f = axis * m["propulsion"]["max_thrust_n"]
            force += f
            torque += np.cross((pos - cg) / 1000, f)
        ag = std["aero"]
        lever = ag["hover_moment_reference_lever_m"]["value"]
        pass_r, fail_r = ag["hover_moment_pass_ratio"]["value"], ag["hover_moment_fail_ratio"]["value"]
        span_ref = max(1e-6, float(np.linalg.norm(force)) * lever)
        imbalance = float(np.linalg.norm(torque - np.dot(torque, force) / np.dot(force, force) * force))
        ratio = imbalance / span_ref
        status = PASS if ratio < pass_r else WARN if ratio < fail_r else FAIL
        res.append(CheckResult("T2.hover_moment", status,
                               f"equal-thrust hover moment about CG {imbalance:.2f} N*m "
                               f"({ratio:.0%} of a {lever * 100:g} cm thrust offset)",
                               STD + "hover_moment_pass_ratio",
                               {"moment_nm": round(imbalance, 3)}))
    return TierReport(2, "physics", res)


# ---------------------------------------------------------------- tier 3
def tier3_aero(design: Design, std: dict, mp: dict) -> TierReport:
    a = std["aero"]
    res: list[CheckResult] = []
    req = design.data.get("requirements", {})
    flight = design.data.get("flight", {})
    mass = mp["mass_g"]
    weight_n = mass / 1000 * G
    if "mtow_g" in req:
        res.append(CheckResult("T3.mass", PASS if mass <= req["mtow_g"] else FAIL,
                               f"{mass:.0f} g vs MTOW {req['mtow_g']} g", "requirements.mtow_g"))

    surfaces = [(c, lifting_surface_properties(c)) for c in design.components
                if "lifting_surface" in c["geometry"]]
    lifting = [(c, p) for c, p in surfaces if p["lifting"]]
    if lifting and design.data["morphology"]["lift"] != "multirotor":
        main_c, main = max(lifting, key=lambda cp: cp[1]["area_mm2"])
        s_m2 = main["area_mm2"] / 1e6
        rho = flight.get("air_density_kgm3", RHO_DEFAULT)
        clmax = flight.get("cl_max", a["cl_max_default"]["value"])
        v_stall = math.sqrt(2 * weight_n / (rho * s_m2 * clmax))
        wl = mass / (main["area_mm2"] / 1e4)  # g/dm^2
        msg = f"wing loading {wl:.1f} g/dm^2, stall {v_stall:.1f} m/s (CLmax {clmax})"
        st = PASS
        if "stall_speed_max_mps" in req and v_stall > req["stall_speed_max_mps"]:
            st = FAIL; msg += f" > required {req['stall_speed_max_mps']} m/s"
        res.append(CheckResult("T3.stall", st, msg, STD + "cl_max_default",
                               {"wing_loading_g_dm2": round(wl, 2), "stall_mps": round(v_stall, 2)}))

        # neutral point: lift-slope-weighted AC of lifting surfaces, downwash on aft surfaces
        def slope(ar):  # Helmbold, per rad
            return 2 * math.pi * ar / (2 + math.sqrt(ar ** 2 + 4))
        a_w = slope(main["aspect_ratio"])
        deps = 2 * a_w / (math.pi * main["aspect_ratio"])
        num = den = 0.0
        for c, p in lifting:
            k = slope(p["aspect_ratio"]) * p["area_mm2"]
            if c is not main_c:
                k *= a["aft_surface_efficiency"]["value"] * ((1 - deps) if p["x_ac_mm"] > main["x_ac_mm"] else 1.0)
            num += k * p["x_ac_mm"]; den += k
        x_np = num / den
        sm = (x_np - mp["cg_mm"][0]) / main["mac_mm"]
        lo, hi = a["static_margin"]["min"], a["static_margin"]["max"]
        st = PASS if lo <= sm <= hi else FAIL
        res.append(CheckResult("T3.static_margin", st,
                               f"{sm:.1%} MAC (NP x={x_np:.0f} mm, CG x={mp['cg_mm'][0]:.0f} mm; target {lo:.0%}-{hi:.0%}; "
                               "fuselage effect not modelled)",
                               STD + "static_margin", {"static_margin": round(sm, 4), "x_np_mm": round(x_np, 1)}))
        lat = abs(mp["cg_mm"][1]) / main_c["geometry"]["lifting_surface"]["span"]
        lim = a["lateral_cg_max_fraction_span"]["value"]
        res.append(CheckResult("T3.lateral_cg", PASS if lat <= lim else FAIL,
                               f"CG y offset {lat:.1%} of span (limit {lim:.0%})", STD + "lateral_cg_max_fraction_span"))
    elif design.data["morphology"]["lift"] != "multirotor":
        res.append(CheckResult("T3.stall", FAIL, "no lifting surface found on a winged design",
                               STD + "cl_max_default"))

    if design.data["morphology"].get("vtol_method", "none") != "none" or design.data["morphology"]["lift"] == "multirotor":
        thrust = sum(c["propulsion"]["max_thrust_n"] for c in design.components
                     if c["type"] == "motor" and c["propulsion"].get("role", "both") in ("lift", "both"))
        tw = thrust / weight_n if weight_n else 0
        lim = a["hover_thrust_to_weight_min"]["value"]
        res.append(CheckResult("T3.hover_tw", PASS if tw >= lim else FAIL,
                               f"hover T/W {tw:.2f} (minimum {lim})", STD + "hover_thrust_to_weight_min",
                               {"thrust_to_weight": round(tw, 3)}))
    return TierReport(3, "aero", res)


# ---------------------------------------------------------------- tier 4
SHEET_METHODS = {"laser-cut", "waterjet", "cnc-router"}
MFG = "manufacturing.yaml"


def _fits(extents: list[float], bed: list[float], sheet: bool) -> bool:
    """extents/bed are sorted ascending. Sheet processes (2 bed values, or a sheet method) compare the two
    largest extents to the bed and the smallest extent only to a third value if one is given."""
    e = sorted(extents)
    v = sorted(bed)
    if sheet or len(v) == 2:
        if len(v) < 2 or e[2] > max(v[-2:]) or e[1] > min(v[-2:]):
            return False
        return len(v) < 3 or e[0] <= v[0]
    return all(x <= y for x, y in zip(e, v))


def tier4_manufacturing(design: Design) -> TierReport:
    import yaml
    path = REPO_ROOT / "standards" / "manufacturing.yaml"
    if not path.exists():
        return TierReport(4, "manufacturing", [CheckResult("T4.capabilities", SKIP, "standards/manufacturing.yaml not written yet", MFG)])
    caps = yaml.safe_load(path.read_text()) or {}
    machines = {m["id"]: m for m in caps.get("machines", [])}
    free_methods = set(caps.get("machine_optional_methods", []))
    all_methods = {m for mm in machines.values() for m in mm.get("methods", [])} | free_methods
    res = []
    for c in design.components:
        mf = c.get("manufacturing")
        if not mf:
            res.append(CheckResult("T4.method", WARN, f"{c['id']}: no manufacturing method", MFG))
            continue
        method, mid = mf["method"], mf.get("machine")
        if mid is not None:
            mach = machines.get(mid)
            if mach is None:
                res.append(CheckResult("T4.machine", FAIL, f"{c['id']}: machine '{mid}' is not in standards/manufacturing.yaml", MFG))
                continue
            if method not in mach.get("methods", []):
                res.append(CheckResult("T4.method", FAIL,
                                       f"{c['id']}: {mid} does not do {method} (it does {mach.get('methods', [])})",
                                       f"{MFG}#{mid}"))
                continue
            bed = mach.get("build_volume_mm")
            if not bed:
                res.append(CheckResult("T4.fits_machine", WARN, f"{c['id']}: {mid} has no build_volume_mm, fit not checked",
                                       f"{MFG}#{mid}"))
                continue
            ext = [float(x) for x in np.ptp(np.vstack([p.vertices for p in component_parts(c, design.base_dir)]), axis=0)]
            if not _fits(ext, bed, method in SHEET_METHODS):
                res.append(CheckResult("T4.fits_machine", FAIL,
                                       f"{c['id']}: {sorted(round(x) for x in ext)} mm does not fit {mid} bed {sorted(bed)}",
                                       f"{MFG}#{mid}"))
                continue
            res.append(CheckResult("T4.method", PASS, f"{c['id']}: {method} on {mid}, fits", f"{MFG}#{mid}"))
            continue
        if method not in all_methods:
            res.append(CheckResult("T4.method", FAIL, f"{c['id']}: no available machine does {method}", MFG))
            continue
        res.append(CheckResult("T4.method", PASS, f"{c['id']}: {method}", MFG))
    return TierReport(4, "manufacturing", res)


# ---------------------------------------------------------------- tier 5
def tier5_standards(design: Design, std: dict, mp: dict) -> TierReport:
    r = std["regulatory"]
    m = mp["mass_g"]
    res = [
        CheckResult("T5.part107_mass", PASS if m < r["faa_part107_max_mass_g"]["value"] else FAIL,
                    f"{m:.0f} g vs Part 107 limit {r['faa_part107_max_mass_g']['value']} g", STD + "faa_part107_max_mass_g"),
        CheckResult("T5.registration", PASS,
                    f"{'above' if m > r['faa_registration_mass_g']['value'] else 'below'} the {r['faa_registration_mass_g']['value']} g FAA registration threshold (informational)",
                    STD + "faa_registration_mass_g"),
    ]
    return TierReport(5, "standards", res)


# ---------------------------------------------------------------- runner
# Criterion for results that are not tied to one rule (crashes, blocked tiers).
TIER_CRITERION = {1: STD + "interference_max_mm3", 2: STD + "landing_load_factor", 3: STD + "static_margin",
                  4: "manufacturing.yaml", 5: STD + "faa_part107_max_mass_g"}


def validate(design: Design, max_tier: int = 5) -> Scorecard:
    std = load_standards()
    tiers = [tier0_schema(design)]
    if tiers[0].status == FAIL:
        return Scorecard(design.id, tiers)
    def run(tier: int, name: str, fn):
        """Run one tier; a crash becomes a FAIL result instead of killing the whole scorecard."""
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            return TierReport(tier, name, [CheckResult(f"T{tier}.error", FAIL, f"{type(e).__name__}: {e}", TIER_CRITERION[tier])])

    if max_tier >= 1:
        tiers.append(run(1, "geometry", lambda: tier1_geometry(design, std)))
    try:
        mp = mass_properties(design)
    except Exception as e:  # noqa: BLE001
        later = [(2, "physics"), (3, "aero"), (4, "manufacturing"), (5, "standards")]
        tiers += [TierReport(t, n, [CheckResult(f"T{t}.blocked", FAIL, f"mass properties failed: {e}", TIER_CRITERION[t])])
                  for t, n in later if t <= max_tier]
        return Scorecard(design.id, tiers)

    def tier2():
        rep = tier2_physics(design, std, mp)
        try:
            from .sim import tier2_sim
        except ImportError:
            return rep
        rep.results.extend(tier2_sim(design, std, mp))
        return rep

    if max_tier >= 2:
        tiers.append(run(2, "physics", tier2))
    if max_tier >= 3:
        tiers.append(run(3, "aero", lambda: tier3_aero(design, std, mp)))
    if max_tier >= 4:
        tiers.append(run(4, "manufacturing", lambda: tier4_manufacturing(design)))
    if max_tier >= 5:
        tiers.append(run(5, "standards", lambda: tier5_standards(design, std, mp)))
    return Scorecard(design.id, tiers)
