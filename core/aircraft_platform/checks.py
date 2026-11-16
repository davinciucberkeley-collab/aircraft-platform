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
from .geometry import (component_parts, lifting_surface_properties, articulated_attachments, att_label,
                       downstream_ids, posed_component_parts, pose_transforms, pose_angles, is_point_mass,
                       lifting_surface_halves, rotation_matrix)
from .mass import mass_properties

G = 9.80665
RHO_DEFAULT = 1.225  # ISA sea level, kg/m^3 (physical constant, matches the schema default)
STD = "design-standards.yaml#"


# ---------------------------------------------------------------- tier 0
def tier0_schema(design: Design) -> TierReport:
    schema = json.loads(SCHEMA_PATH.read_text())
    errors = sorted(Draft202012Validator(schema).iter_errors(design.data), key=lambda e: list(e.path))
    if errors:
        res = [CheckResult("T0.schema", FAIL, f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}",
                           "schema/plane.schema.json") for e in errors[:20]]
    else:
        res = [CheckResult("T0.schema", PASS, f"matches schema v{design.data.get('schema_version', '0.1')}", "schema/plane.schema.json")]
    uses_v02 = any(a.get("articulation") for a in design.data.get("attachments", [])) or \
        any(k in design.data.get("flight", {}) for k in ("hover_pose", "cruise_pose"))
    if uses_v02 and design.data.get("schema_version") == "0.1":
        res.append(CheckResult("T0.version", FAIL,
                               "articulation / flight.hover_pose / flight.cruise_pose need schema_version \"0.2\"",
                               "schema/plane.schema.json"))
    uses_v03 = any(c.get("cavities") for c in design.data.get("components", []))
    if uses_v03 and design.data.get("schema_version") not in ("0.3", "0.4"):
        res.append(CheckResult("T0.version", FAIL,
                               "cavities need schema_version \"0.3\" or later",
                               "schema/plane.schema.json"))
    uses_v04 = any("point_mass" in c.get("geometry", {}) for c in design.data.get("components", []))
    if uses_v04 and design.data.get("schema_version") != "0.4":
        res.append(CheckResult("T0.version", FAIL,
                               "point_mass geometry needs schema_version \"0.4\"",
                               "schema/plane.schema.json"))
    if any(a.get("kinematic_link") for a in design.data.get("attachments", [])) and design.data.get("schema_version") != "0.4":
        res.append(CheckResult("T0.version", FAIL,
                               "attachment kinematic_link needs schema_version \"0.4\"",
                               "schema/plane.schema.json"))
    uses_planform = [c["id"] for c in design.data.get("components", []) if "planform" in c]
    if uses_planform and design.data.get("schema_version") != "0.4":
        res.append(CheckResult("T0.version", FAIL,
                               "component planform needs schema_version \"0.4\"",
                               "schema/plane.schema.json"))
    if any("rating_basis" in a for a in design.data.get("attachments", [])) and design.data.get("schema_version") != "0.4":
        res.append(CheckResult("T0.version", FAIL,
                               "attachment rating_basis needs schema_version \"0.4\"",
                               "schema/plane.schema.json"))
    both = [c["id"] for c in design.data.get("components", [])
            if "planform" in c and "lifting_surface" in c.get("geometry", {})]
    if both:
        res.append(CheckResult("T0.version", FAIL,
                               "planform is for components whose geometry is not a lifting_surface (would count the wing twice): "
                               + ", ".join(both), "schema/plane.schema.json"))
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
            pts_a = trimesh.sample.sample_surface(pa, 400, seed=1)[0] if len(pa.faces) else pa.vertices
            pts_b = trimesh.sample.sample_surface(pb, 400, seed=1)[0] if len(pb.faces) else pb.vertices
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


class _PairCache:
    """Overlap volume and gap for component pairs. A pair that does not move relative to itself between two
    articulated configurations (both parts carry the same transform, e.g. both static) has exactly the result it
    had in the first configuration, so only pairs with relative motion are recomputed in a pose."""

    def __init__(self):
        self.ov: dict[tuple[str, str], float] = {}
        self.dist: dict[tuple[str, str], float] = {}
        self.loc: dict[str, CheckResult] = {}

    @staticmethod
    def _key(a: str, b: str) -> tuple[str, str]:
        return (a, b) if a <= b else (b, a)

    def overlap(self, meshes, tf, a: str, b: str) -> float:
        static = bool(np.allclose(tf[a], tf[b]))
        key = self._key(a, b)
        if static and key in self.ov:
            return self.ov[key]
        v = _overlap_volume(meshes[a], meshes[b])
        if static:
            self.ov[key] = v
        return v

    def gap(self, meshes, tf, a: str, b: str) -> float:
        static = bool(np.allclose(tf[a], tf[b]))
        key = self._key(a, b)
        if static and key in self.dist:
            return self.dist[key]
        v = _min_distance(meshes[a], meshes[b])
        if static:
            self.dist[key] = v
        return v


def _broad_phase(meshes: dict[str, list[trimesh.Trimesh]]) -> list[tuple[str, str]]:
    """Pairs of components whose axis-aligned boxes overlap (sort and sweep along x). Only these can clip: the exact
    boolean intersection runs on them and on nothing else (104 parts = 5356 pairs, a few hundred candidates)."""
    ids = [i for i in meshes if meshes[i]]
    lo = {i: np.min([p.bounds[0] for p in meshes[i]], axis=0) for i in ids}
    hi = {i: np.max([p.bounds[1] for p in meshes[i]], axis=0) for i in ids}
    order = sorted(ids, key=lambda i: lo[i][0])
    active: list[str] = []
    pairs = []
    for b in order:
        active = [a for a in active if hi[a][0] > lo[b][0]]
        for a in active:
            if np.all(lo[a] < hi[b]) and np.all(lo[b] < hi[a]):
                pairs.append((a, b))
        active.append(b)
    return pairs


def _fmt_deg(x: float) -> str:
    return f"{x:g}\u00b0"


def _configurations(design: Design, sweep_step_deg: float) -> list[tuple[str, dict[str, float]]]:
    """Extra articulated configurations (beyond 0 deg everywhere) tier 1 must check, deduplicated.
    Each named pose: all joints at that pose if every joint defines it, else each defining joint swept alone.
    Then both range endpoints of each joint, swept alone with the others at 0.
    Then every sweep_step_deg step across each joint's range (min, min+step, ... max), others at 0."""
    joints = articulated_attachments(design)
    if not joints:
        return []
    if sweep_step_deg <= 0:
        raise ValueError("articulation_sweep_step_deg must be positive")
    labels = [att_label(a) for a in joints]
    seen = {tuple(0.0 for _ in joints)}
    out: list[tuple[str, dict[str, float]]] = []

    def add(name: str, ang: dict[str, float]):
        key = tuple(float(ang.get(l, 0.0)) for l in labels)
        if key in seen:
            return
        seen.add(key)
        out.append((name, {l: float(ang.get(l, 0.0)) for l in labels}))

    names = []
    for a in joints:
        for n in a["articulation"].get("poses", {}):
            if n not in names:
                names.append(n)
    for n in names:
        if all(n in a["articulation"].get("poses", {}) for a in joints):
            ang = {att_label(a): a["articulation"]["poses"][n] for a in joints}
            vals = sorted(set(ang.values()))
            shown = _fmt_deg(vals[0]) if len(vals) == 1 else ", ".join(f"{l} {_fmt_deg(v)}" for l, v in ang.items())
            add(f"pose {n} ({shown})", ang)
        else:
            for a in joints:
                if n in a["articulation"].get("poses", {}):
                    v = a["articulation"]["poses"][n]
                    add(f"pose {n} ({att_label(a)} {_fmt_deg(v)})", {att_label(a): v})
    for a in joints:
        lo, hi = a["articulation"]["range_deg"]
        add(f"range min of {att_label(a)} ({_fmt_deg(lo)})", {att_label(a): lo})
        add(f"range max of {att_label(a)} ({_fmt_deg(hi)})", {att_label(a): hi})
    for a in joints:
        label = att_label(a)
        lo, hi = a["articulation"]["range_deg"]
        steps = []
        k = 0
        while lo + k * sweep_step_deg <= hi + 1e-9:
            steps.append(lo + k * sweep_step_deg)
            k += 1
        if not steps or abs(steps[-1] - hi) > 1e-9:
            steps.append(hi)
        for v in steps:
            add(f"sweep {label} {_fmt_deg(v)}", {label: v})
    return out


def _articulation_checks(design: Design, std: dict, meshes: dict) -> list[CheckResult]:
    tol = std["geometry"]["attach_tolerance_mm"]["value"]
    res: list[CheckResult] = []
    for a in articulated_attachments(design):
        label, art = att_label(a), a["articulation"]
        lo, hi = art["range_deg"]
        problems = []
        if lo > hi:
            problems.append(f"range_deg [{lo}, {hi}] is reversed")
        if float(np.linalg.norm(art["axis"])) < 1e-9:
            problems.append("axis is the zero vector")
        for n, ang in art.get("poses", {}).items():
            if not lo <= ang <= hi:
                problems.append(f"pose {n} ({_fmt_deg(ang)}) is outside range [{_fmt_deg(lo)}, {_fmt_deg(hi)}]")
        if a["parent"] in downstream_ids(design, a):
            problems.append("joint lies in a loop of attachments, so the child side is not separable")
        dp = _point_distance(meshes[a["parent"]], art["pivot"])
        dc = _point_distance(meshes[a["child"]], art["pivot"])
        if max(dp, dc) > tol:
            problems.append(f"pivot is {dp:.1f} mm from {a['parent']} and {dc:.1f} mm from {a['child']} at 0\u00b0 (tolerance {tol} mm)")
        if problems:
            res.append(CheckResult("T1.articulation", FAIL, f"{label}: " + "; ".join(problems), STD + "attach_tolerance_mm"))
        else:
            res.append(CheckResult("T1.articulation", PASS,
                                   f"{label}: revolute, range [{_fmt_deg(lo)}, {_fmt_deg(hi)}], poses "
                                   f"{ {k: _fmt_deg(v) for k, v in art.get('poses', {}).items()} }, pivot on both parts",
                                   STD + "attach_tolerance_mm"))
    flight = design.data.get("flight", {})
    known = {n for a in articulated_attachments(design) for n in a["articulation"].get("poses", {})}
    for key in ("hover_pose", "cruise_pose"):
        if key in flight and flight[key] not in known:
            res.append(CheckResult("T1.articulation", FAIL, f"flight.{key} '{flight[key]}' is not a pose of any articulated joint",
                                   "schema/plane.schema.json"))
    return res


PROP_CHAIN_METHODS = ("bolted", "press-fit")   # joints an adapter may use between motor and propeller
PROP_CHAIN_TYPES = ("other", "structure")      # component types an adapter may be
PROP_CHAIN_MAX_INTERMEDIATE = 2


def _motor_prop_path(design: Design, motor: str, atts: list[dict]) -> list[str] | None:
    """Component ids from `motor` to a propeller: a direct attachment (any method), or a chain through at most
    PROP_CHAIN_MAX_INTERMEDIATE parts of type other/structure where every joint is bolted or press-fit.
    None if there is no such path. Breadth-first, so the shortest chain is reported."""
    nbrs = defaultdict(list)
    for a in atts:
        nbrs[a["parent"]].append((a["child"], a["method"]))
        nbrs[a["child"]].append((a["parent"], a["method"]))
    queue = deque([([motor], [])])
    while queue:
        path, methods = queue.popleft()
        for nxt, method in nbrs[path[-1]]:
            if nxt in path:
                continue
            new_path, new_methods = path + [nxt], methods + [method]
            if design.component(nxt)["type"] == "propeller":
                if len(new_path) == 2 or all(m in PROP_CHAIN_METHODS for m in new_methods):
                    return new_path
                continue
            if (design.component(nxt)["type"] in PROP_CHAIN_TYPES and method in PROP_CHAIN_METHODS
                    and len(new_path) - 1 <= PROP_CHAIN_MAX_INTERMEDIATE):
                queue.append((new_path, new_methods))
    return None


def _contact_and_clash_checks(design: Design, std: dict, meshes: dict, tf: dict, atts: list[dict],
                              cache: _PairCache | None = None) -> list[CheckResult]:
    """Attachment contact / overlap / containment, motor-prop pairing and interference for ONE configuration.
    `meshes` holds solid components only (point masses, schema 0.4, are absent); `cache` shares results between
    configurations (see _PairCache)."""
    cache = cache or _PairCache()
    tf = {**{cid: np.eye(4) for cid in meshes}, **tf}
    g = std["geometry"]
    tol = g["attach_tolerance_mm"]["value"]
    max_int = g["interference_max_mm3"]["value"]
    max_frac = g["glued_overlap_max_fraction"]["value"]
    embed_frac = g["embed_max_fraction_of_child"]["value"]
    contain_min = g["containment_min_fraction"]["value"]
    res: list[CheckResult] = []
    adj = defaultdict(set)
    for a in atts:
        adj[a["parent"]].add(a["child"]); adj[a["child"]].add(a["parent"])

    # each attachment: parts actually touch, joint point on both, overlap sane
    attached_pairs = set()
    for a in atts:
        p, c = a["parent"], a["child"]
        attached_pairs.add(frozenset((p, c)))
        label = a.get("id") or f"{p}->{c}"
        ptype, ctype = design.component(p)["type"], design.component(c)["type"]
        embed = a.get("embed_ok", False)
        if p not in meshes or c not in meshes:  # an end is a point mass: no extent to touch or overlap
            res.append(CheckResult("T1.attachment", PASS, f"{label}: {a['method']} joint to a point mass "
                                   f"({p if p not in meshes else c}): no contact or location check",
                                   STD + "attach_tolerance_mm"))
            continue
        if embed and "propeller" in (ptype, ctype):
            res.append(CheckResult("T1.attachment_overlap", FAIL,
                                   f"{label}: a propeller can never be an embed_ok joint (its swept disc must not pass into a part)",
                                   STD + "embed_max_fraction_of_child"))
            continue
        ov = cache.overlap(meshes, tf, p, c)
        if ov <= 0:
            d = cache.gap(meshes, tf, p, c)
            if d > tol:
                res.append(CheckResult("T1.attachment_contact", FAIL,
                                       f"{label}: parts are {d:.1f} mm apart (tolerance {tol} mm)",
                                       STD + "attach_tolerance_mm", {"gap_mm": round(d, 2)}))
                continue
        elif embed:
            child_vol = sum(x.volume for x in meshes[c])
            frac = ov / child_vol if child_vol else 1.0
            # Over the limit is allowed only if the child is geometrically inside the parent (a bay);
            # a part poking through its parent never is. `type` is never consulted.
            if frac > embed_frac and frac < contain_min:
                res.append(CheckResult("T1.attachment_overlap", FAIL,
                                       f"{label}: embed_ok joint overlaps {frac:.0%} of the child {c} "
                                       f"(limit {embed_frac:.0%} unless the child is >= {contain_min:.0%} inside the parent)",
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
        # a non-articulated joint whose two ends carry the same transform has the static result: reuse it
        same_motion = (not a.get("articulation")) and bool(np.allclose(tf[p], tf[c]))
        if same_motion and label in cache.loc:
            res.append(cache.loc[label])
            continue
        if a.get("articulation"):
            loc = a["articulation"]["pivot"]  # the pivot is the one point that does not move with the joint
        elif not np.allclose(tf[c], np.eye(4)):
            loc = (tf[c] @ np.append(np.array(loc, dtype=float), 1.0))[:3]
        dp, dc = _point_distance(meshes[p], loc), _point_distance(meshes[c], loc)
        if max(dp, dc) > tol:
            r = CheckResult("T1.attachment_location", FAIL,
                            f"{label}: joint point is {dp:.1f} mm from {p} and {dc:.1f} mm from {c}",
                            STD + "attach_tolerance_mm")
        else:
            r = CheckResult("T1.attachment", PASS, f"{label}: {a['method']} joint OK",
                            STD + "attach_tolerance_mm")
        if same_motion:
            cache.loc[label] = r
        res.append(r)

    # every motor must drive an attached propeller (so a mislabelled prop leaves its motor prop-less)
    for comp in design.components:
        if "propulsion" not in comp:
            continue
        path = _motor_prop_path(design, comp["id"], atts)
        if path is None:
            res.append(CheckResult("T1.motor_has_prop", FAIL,
                                   f"{comp['id']}: has a propulsion block but no propeller attached directly or through "
                                   f"up to {PROP_CHAIN_MAX_INTERMEDIATE} bolted or press-fit other/structure parts",
                                   STD + "embed_max_fraction_of_child"))
        elif len(path) == 2:
            res.append(CheckResult("T1.motor_has_prop", PASS, f"{comp['id']}: drives an attached propeller",
                                   STD + "embed_max_fraction_of_child"))
        else:
            res.append(CheckResult("T1.motor_has_prop", PASS,
                                   f"{' -> '.join(path)}: drives its propeller through an adapter chain",
                                   STD + "embed_max_fraction_of_child", {"path": path}))

    # interference between non-attached parts (broad phase first: only boxes that overlap get the exact boolean)
    # kinematic_link children are moved by a linkage the schema does not model: a pair of one such child and a
    # part moved by this configuration is not checked here, and is reported once as a WARN (never silently dropped)
    linked = {a["child"] for a in atts if a.get("kinematic_link")}
    moved = {cid for cid in meshes if not np.allclose(tf[cid], np.eye(4))}
    unchecked = []
    clashes = []
    for a_, b_ in _broad_phase(meshes):
        if frozenset((a_, b_)) in attached_pairs:
            continue
        if (a_ in linked and b_ in moved) or (b_ in linked and a_ in moved):
            unchecked.append((a_, b_))
            continue
        v = cache.overlap(meshes, tf, a_, b_)
        if v > max_int:
            clashes.append((a_, b_, v))
    clashes.sort()
    for a_, b_, v in clashes:
        kind = "prop strike" if "propeller" in (design.component(a_)["type"], design.component(b_)["type"]) else "clipping"
        res.append(CheckResult("T1.interference", FAIL, f"{kind}: {a_} and {b_} overlap {v:.0f} mm^3",
                               STD + "interference_max_mm3", {"pair": [a_, b_], "volume_mm3": round(v, 1)}))
    if not clashes:
        res.append(CheckResult("T1.interference", PASS, "no clipping between unattached parts",
                               STD + "interference_max_mm3"))
    if unchecked:
        ids = sorted({i for pair in unchecked for i in pair})
        shown = ", ".join(ids[:6]) + (", \u2026" if len(ids) > 6 else "")
        res.append(CheckResult("T1.kinematic_link", SKIP,
                               f"{len(unchecked)} pair(s) not checked \u2014 linkage path not modelled: {shown}",
                               "schema/plane.schema.json", {"pairs": [list(p) for p in unchecked]}))
    return res


def _inside(parts: list[trimesh.Trimesh], p) -> bool:
    """True if p lies strictly inside one of the parts (a point on the surface does not count)."""
    return any(float(trimesh.proximity.signed_distance(m, np.array([p]))[0]) > 1e-6 for m in parts)


def _point_mass_checks(design: Design, std: dict, meshes: dict, atts: list[dict]) -> list[CheckResult]:
    """Schema 0.4 point_mass placement.
    Strict (default): (i) at its position (+cg_offset) it lies inside, or within attach_tolerance_mm of, a part it is
    attached to that has geometry.
    Distributed (distributed: true, type other only, with a reason): (i) it lies inside the envelope (convex hull of all
    non-propeller geometry), within attach_tolerance_mm, and its mass is capped per item and in total.
    Both: (ii) it is not inside any propeller's geometry (the prop disc).
    Static configuration only: a point mass on an articulated part is not posed."""
    tol = std["geometry"]["attach_tolerance_mm"]["value"]
    lim_each = std["geometry"]["distributed_mass_max_fraction_each"]["value"]
    lim_total = std["geometry"]["distributed_mass_max_fraction_total"]["value"]
    total_g = sum(c["mass_g"] for c in design.components)
    props = [c["id"] for c in design.components if c["type"] == "propeller" and c["id"] in meshes]
    res: list[CheckResult] = []
    envelope = None  # convex hull of all non-propeller geometry, built once if a distributed mass needs it
    dist_g = 0.0
    for pm in design.components:
        if not is_point_mass(pm):
            continue
        cid = pm["id"]
        p = np.array(pm["position"], dtype=float) + np.array(pm.get("cg_offset", [0, 0, 0]), dtype=float)
        at = f"({p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f}) mm"
        distributed = bool(pm["geometry"]["point_mass"].get("distributed", False))
        problems: list[str] = []
        extra: list[CheckResult] = []
        hosts = sorted({a["child"] if a["parent"] == cid else a["parent"] for a in atts if cid in (a["parent"], a["child"])}
                       & set(meshes))
        if distributed:
            dist_g += pm["mass_g"]
            if pm["type"] != "other":
                extra.append(CheckResult("T1.point_mass_location", FAIL,
                                         f"{cid}: distributed point masses are only for type other (lumped hardware, harness); "
                                         f"{pm['type']} parts must be modelled with geometry",
                                         STD + "distributed_mass_max_fraction_each"))
            share = pm["mass_g"] / total_g
            if share > lim_each:
                extra.append(CheckResult("T1.point_mass_location", FAIL,
                                         f"{cid}: {pm['mass_g']:.1f} g is {share:.1%} of the {total_g:.0f} g aircraft; "
                                         f"a distributed point mass may carry at most {lim_each:.0%}",
                                         STD + "distributed_mass_max_fraction_each"))
            if envelope is None:
                pts = np.vstack([m.vertices for k in meshes if k not in props for m in meshes[k]])
                envelope = [trimesh.convex.convex_hull(pts)]
            d = _point_distance(envelope, p)
            if d > tol:
                problems.append(f"{cid} at {at} lies outside the aircraft's envelope by {d:.1f} mm "
                                f"(distributed mass must lie inside the convex hull of the geometry; tolerance {tol} mm)")
        elif not hosts:
            problems.append(f"{cid} at {at} has no attached part with geometry to sit on")
        else:
            d = min(_point_distance(meshes[h], p) for h in hosts)
            if d > tol:
                problems.append(f"{cid} at {at} is {d:.1f} mm from every part it is attached to "
                                f"({', '.join(hosts)}; tolerance {tol} mm)")
        for pid in props:
            if _inside(meshes[pid], p):
                problems.append(f"{cid} at {at} lies inside the prop disc of {pid}")
        if problems:
            res += [CheckResult("T1.point_mass_location", FAIL, m, STD + "attach_tolerance_mm") for m in problems]
        elif distributed:
            res.append(CheckResult("T1.point_mass_location", PASS,
                                   f"{cid} at {at}: distributed mass inside the aircraft's envelope, outside every prop disc",
                                   STD + "attach_tolerance_mm"))
        else:
            res.append(CheckResult("T1.point_mass_location", PASS,
                                   f"{cid} at {at}: on or within {tol} mm of an attached part, outside every prop disc",
                                   STD + "attach_tolerance_mm"))
        res += extra
    if dist_g / total_g > lim_total:
        res.append(CheckResult("T1.point_mass_location", FAIL,
                               f"distributed point masses together carry {dist_g:.1f} g ({dist_g / total_g:.1%} of the "
                               f"{total_g:.0f} g aircraft); the limit is {lim_total:.0%}",
                               STD + "distributed_mass_max_fraction_total"))
    return res


def tier1_geometry(design: Design, std: dict) -> TierReport:
    all_ids = [c["id"] for c in design.components]
    # point masses (schema 0.4) have no mesh: they count for connectivity and mass, not for any geometry check
    meshes = {c["id"]: component_parts(c, design.base_dir) for c in design.components if not is_point_mass(c)}
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
    loose = sorted(set(all_ids) - seen)
    res.append(CheckResult("T1.connectivity", FAIL if loose else PASS,
                           f"not attached to '{root}' (would fall off): {loose}" if loose
                           else f"all {len(all_ids)} components connect to '{root}'",
                           STD + "attach_tolerance_mm"))

    identity = {cid: np.eye(4) for cid in all_ids}
    cache = _PairCache()
    res += _contact_and_clash_checks(design, std, meshes, identity, atts, cache)
    res += _point_mass_checks(design, std, meshes, atts)

    # articulated joints: the same contact / overlap / interference checks in every configuration
    if articulated_attachments(design):
        res += _articulation_checks(design, std, meshes)
        for name, ang in _configurations(design, std["geometry"]["articulation_sweep_step_deg"]["value"]):
            pm = {cid: ps for cid, ps in posed_component_parts(design, ang).items() if cid in meshes}
            tf = pose_transforms(design, ang)
            sub = _contact_and_clash_checks(design, std, pm, tf, atts, cache)
            static_fails = {(r.check_id, r.message) for r in res if r.status == FAIL}
            # a failure that is already in the static results is not pose-specific: report it once
            fails = [r for r in sub if r.status == FAIL and (r.check_id, r.message) not in static_fails]
            for r in fails:
                r.message = f"{name}: {r.message}"
                r.data = {**r.data, "configuration": name}
            res += fails
            for r in sub:
                if r.status in (WARN, SKIP):
                    r.message = f"{name}: {r.message}"
                    r.data = {**r.data, "configuration": name}
                    res.append(r)
            if not fails and not any(r.status == SKIP for r in sub):
                res.append(CheckResult("T1.pose", PASS,
                                       f"{name}: attachments, overlap and interference all OK",
                                       STD + "interference_max_mm3", {"configuration": name}))
    return TierReport(1, "geometry", res)


# ---------------------------------------------------------------- hover thrust
def _hover_up(design: Design) -> np.ndarray:
    """'Up' in the body frame for hover. A declared hover_pose uses the posed thrust axes with body +z up;
    a tailsitter hovers nose-up (-x); anything else is body +z."""
    if design.data.get("flight", {}).get("hover_pose"):
        return np.array([0.0, 0.0, 1.0])
    if design.data["morphology"].get("vtol_method") == "tailsitter":
        return np.array([-1.0, 0.0, 0.0])
    return np.array([0.0, 0.0, 1.0])


def _upward_lift(design: Design, tf: dict[str, np.ndarray], up: np.ndarray) -> list[tuple[dict, np.ndarray]]:
    """For each lift motor (role lift or both): (motor, upward thrust vector in N). Only the component of
    the thrust along `up` counts: max(0, dot(unit_axis, up)) * max_thrust_n, directed along `up`."""
    out = []
    for m in design.components:
        if m["type"] != "motor" or m["propulsion"].get("role", "both") not in ("lift", "both"):
            continue
        ax = tf[m["id"]][:3, :3] @ np.array(m["propulsion"]["axis"], dtype=float)
        ax = ax / np.linalg.norm(ax)
        out.append((m, up * max(0.0, float(np.dot(ax, up))) * m["propulsion"]["max_thrust_n"]))
    return out


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
        if a.get("rating_basis") == "placeholder":
            res.append(CheckResult("T2.joint_load", SKIP,
                                   f"{label}: carries {load:.1f} N; rating is a placeholder, not checked",
                                   STD + "landing_load_factor", {"load_n": round(load, 2)}))
            continue
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
        hover_pose = design.data.get("flight", {}).get("hover_pose")
        h_ang = pose_angles(design, hover_pose)
        if hover_pose:  # CG, motor positions and thrust axes at the hover configuration
            mp = mass_properties(design, h_ang)
        posed = posed_component_parts(design, h_ang)
        h_tf = pose_transforms(design, h_ang)
        cg = np.array(mp["cg_mm"])
        torque = np.zeros(3)
        force = np.zeros(3)
        for m, f in _upward_lift(design, h_tf, _hover_up(design)):
            parts = posed[m["id"]]
            pos = np.mean([p.center_mass for p in parts], axis=0)
            force += f
            torque += np.cross((pos - cg) / 1000, f)
        ag = std["aero"]
        lever = ag["hover_moment_reference_lever_m"]["value"]
        pass_r, fail_r = ag["hover_moment_pass_ratio"]["value"], ag["hover_moment_fail_ratio"]["value"]
        at_pose = f" at pose {hover_pose}" if hover_pose else ""
        if float(np.linalg.norm(force)) < 1e-9:
            res.append(CheckResult("T2.hover_moment", FAIL,
                                   "no lift motor has upward thrust at hover, so the hover moment is undefined" + at_pose,
                                   STD + "hover_moment_pass_ratio"))
        else:
            span_ref = max(1e-6, float(np.linalg.norm(force)) * lever)
            imbalance = float(np.linalg.norm(torque - np.dot(torque, force) / np.dot(force, force) * force))
            ratio = imbalance / span_ref
            status = PASS if ratio < pass_r else WARN if ratio < fail_r else FAIL
            res.append(CheckResult("T2.hover_moment", status,
                                   f"equal-thrust hover moment about CG {imbalance:.2f} N*m "
                                   f"({ratio:.0%} of a {lever * 100:g} cm thrust offset)" + at_pose,
                                   STD + "hover_moment_pass_ratio",
                                   {"moment_nm": round(imbalance, 3)}))
    return TierReport(2, "physics", res)


# ---------------------------------------------------------------- tier 3
def _articulated_subtree(design: Design, cid: str) -> list[str]:
    """cid plus every component reached from it through attachments that carry articulation (control surfaces),
    recursively, at 0 deg. Plain (non-articulated) children are not included."""
    out, stack = [cid], [cid]
    while stack:
        n = stack.pop()
        for a in design.data.get("attachments", []):
            if a["parent"] == n and a.get("articulation") and a["child"] not in out:
                out.append(a["child"])
                stack.append(a["child"])
    return out


def _planform_checks(design: Design, std: dict) -> list[CheckResult]:
    """Schema 0.4 planform: at each spanwise station (0, 25, 50, 75, 95 % of the semi-span, both sides if mirrored) the
    real geometry's chordwise extent must match the planform's leading and trailing edge there, within
    planform_match_tolerance_fraction x root_chord. The geometry is the component plus its articulated children at 0 deg.
    Compared in the planform's own axes (x chordwise from the root LE, y spanwise), so rotation_deg is allowed."""
    tol = std["aero"]["planform_match_tolerance_fraction"]["value"]
    stations = (0.0, 0.25, 0.50, 0.75, 0.95)
    res: list[CheckResult] = []
    for c in design.components:
        if "planform" not in c:
            continue
        if is_point_mass(c):
            res.append(CheckResult("T3.planform_matches_geometry", FAIL,
                                   f"{c['id']}: a planform needs geometry to match, and a point mass has none",
                                   STD + "planform_match_tolerance_fraction"))
            continue
        pf = c["planform"]
        ls = pf["lifting_surface"]
        origin = np.array(pf["origin"], dtype=float)
        rot = rotation_matrix(pf.get("rotation_deg"))
        geo_ids = _articulated_subtree(design, c["id"])
        scope = f"the geometry of {', '.join(geo_ids)}"
        to_pf = np.eye(4)  # body frame -> planform frame
        to_pf[:3, :3] = rot.T
        to_pf[:3, 3] = -rot.T @ origin
        parts = []
        for k in geo_ids:
            for m in component_parts(design.component(k), design.base_dir):
                m = m.copy()
                m.apply_transform(to_pf)
                parts.append(m)
        if not parts:
            res.append(CheckResult("T3.planform_matches_geometry", FAIL, f"{c['id']}: no geometry for {scope}",
                                   STD + "planform_match_tolerance_fraction"))
            continue
        mirrored = ls.get("mirrored", True)
        semi = ls["span"] / 2 if mirrored else ls["span"]
        cr, ct = ls["root_chord"], ls["tip_chord"]
        sweep = math.tan(math.radians(ls.get("sweep_le_deg", 0)))
        lim = tol * cr
        rows = []  # (label, dLE, dTE) with None for a station that has no geometry
        for f in stations:
            for side in ((1,) if (f == 0 or not mirrored) else (1, -1)):
                y = side * f * semi
                ay = abs(y)
                le = ay * sweep  # same planform outline as lifting_surface_halves
                te = le + cr + (ct - cr) * ay / semi
                sign = "" if f == 0 or not mirrored else ("+" if side > 0 else "-")
                label = f"{sign}{f * 100:.0f}%"
                lo, hi = [], []
                for m in parts:
                    sec = m.section(plane_origin=[0.0, y, 0.0], plane_normal=[0.0, 1.0, 0.0])
                    if sec is not None:
                        xs = sec.vertices[:, 0]
                        lo.append(float(xs.min()))
                        hi.append(float(xs.max()))
                rows.append((label, min(lo) - le, max(hi) - te) if lo else (label, None, None))
        bad = []
        for label, dle, dte in rows:
            if dle is None:
                bad.append((math.inf, f"{label} span: no geometry at this station"))
                continue
            worst = max(abs(dle), abs(dte))
            if worst > lim:
                bad.append((worst, f"{label} span: LE {dle:+.1f} mm, TE {dte:+.1f} mm"))
        data = {"stations": len(rows), "limit_mm": round(lim, 2)}
        if bad:
            bad.sort(key=lambda t: -t[0])
            shown = "; ".join(t[1] for t in bad[:3])
            res.append(CheckResult("T3.planform_matches_geometry", FAIL,
                                   f"{c['id']}: planform does not match {scope} at {len(bad)} of {len(rows)} stations "
                                   f"(limit {lim:.1f} mm), worst first: {shown}",
                                   STD + "planform_match_tolerance_fraction", data))
        else:
            res.append(CheckResult("T3.planform_matches_geometry", PASS,
                                   f"{c['id']}: planform LE and TE match {scope} at all {len(rows)} stations "
                                   f"(0-95% of the span from the root, within {lim:.1f} mm)",
                                   STD + "planform_match_tolerance_fraction", data))
    return res


def tier3_aero(design: Design, std: dict, mp: dict) -> TierReport:
    a = std["aero"]
    res: list[CheckResult] = []
    res += _planform_checks(design, std)  # reported even if a later aero check fails
    req = design.data.get("requirements", {})
    flight = design.data.get("flight", {})
    mass = mp["mass_g"]
    weight_n = mass / 1000 * G
    if "mtow_g" in req:
        res.append(CheckResult("T3.mass", PASS if mass <= req["mtow_g"] else FAIL,
                               f"{mass:.0f} g vs MTOW {req['mtow_g']} g", "requirements.mtow_g"))

    cruise_pose = flight.get("cruise_pose")
    c_ang = pose_angles(design, cruise_pose)
    c_tf = pose_transforms(design, c_ang)
    if cruise_pose:  # static margin and aft-surface geometry at the cruise configuration
        mp = mass_properties(design, c_ang)
    # (component, lifting-surface component, properties). A planform (schema 0.4) is wrapped in a pseudo-component
    # so that it goes through the same lifting_surface_properties; it is not a geometry component.
    surfaces = []
    for c in design.components:
        if "lifting_surface" in c["geometry"]:
            ls_c = c
        elif "planform" in c:
            pf = c["planform"]
            ls_c = {"geometry": {"lifting_surface": pf["lifting_surface"]}, "position": pf["origin"],
                    "rotation_deg": pf.get("rotation_deg", [0, 0, 0])}
        else:
            continue
        surfaces.append((c, ls_c, lifting_surface_properties(ls_c, c_tf[c["id"]] if cruise_pose else None)))
    lifting = [(c, ls_c, p) for c, ls_c, p in surfaces if p["lifting"]]
    if lifting and design.data["morphology"]["lift"] != "multirotor":
        main_c, main_ls, main = max(lifting, key=lambda cp: cp[2]["area_mm2"])
        main_from_planform = "planform" in main_c and "lifting_surface" not in main_c["geometry"]
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
        for c, _ls, p in lifting:
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
                               "fuselage effect not modelled)"
                               + (" (planform declared; mesh wing)" if main_from_planform else ""),
                               STD + "static_margin", {"static_margin": round(sm, 4), "x_np_mm": round(x_np, 1)}))
        lat = abs(mp["cg_mm"][1]) / main_ls["geometry"]["lifting_surface"]["span"]
        lim = a["lateral_cg_max_fraction_span"]["value"]
        res.append(CheckResult("T3.lateral_cg", PASS if lat <= lim else FAIL,
                               f"CG y offset {lat:.1%} of span (limit {lim:.0%})", STD + "lateral_cg_max_fraction_span"))
    elif design.data["morphology"]["lift"] != "multirotor":
        res.append(CheckResult("T3.stall", FAIL, "no lifting surface found on a winged design",
                               STD + "cl_max_default"))

    if design.data["morphology"].get("vtol_method", "none") != "none" or design.data["morphology"]["lift"] == "multirotor":
        hover_pose = flight.get("hover_pose")
        h_tf = pose_transforms(design, pose_angles(design, hover_pose))
        lift = _upward_lift(design, h_tf, _hover_up(design))
        thrust = sum(float(np.linalg.norm(f)) for _, f in lift)
        rated = sum(m["propulsion"]["max_thrust_n"] for m, _ in lift)
        tw = thrust / weight_n if weight_n else 0
        lim = a["hover_thrust_to_weight_min"]["value"]
        res.append(CheckResult("T3.hover_tw", PASS if tw >= lim else FAIL,
                               f"hover T/W {tw:.2f} (upward thrust {thrust:.1f} N of {rated:.1f} N rated; minimum {lim})"
                               + (f" at pose {hover_pose}" if hover_pose else ""), STD + "hover_thrust_to_weight_min",
                               {"thrust_to_weight": round(tw, 3)}))
    return TierReport(3, "aero", res)


# ---------------------------------------------------------------- tier 4
SHEET_METHODS = {"laser-cut", "waterjet", "cnc-router"}
MFG = "manufacturing.yaml"


def _obb_extents(parts: list[trimesh.Trimesh]) -> list[float]:
    """Sorted (ascending) extents of the part's oriented bounding box: independent of how it is rotated."""
    mesh = trimesh.util.concatenate(parts) if len(parts) > 1 else parts[0]
    return sorted(float(x) for x in mesh.bounding_box_oriented.primitive.extents)


def _fits(extents: list[float], bed: list[float], sheet: bool) -> bool:
    """extents are OBB extents. Sheet processes compare the two largest extents to the bed's X/Y (either
    orientation) and the smallest extent (the sheet thickness) only to a third bed value if one is given."""
    e = sorted(extents)
    v = sorted(bed)
    eps = 1e-3
    if sheet or len(v) == 2:
        if len(v) < 2 or e[2] > max(v[-2:]) + eps or e[1] > min(v[-2:]) + eps:
            return False
        return len(v) < 3 or e[0] <= v[0] + eps
    return all(x <= y + eps for x, y in zip(e, v))


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
            res.append(CheckResult("T4.method", FAIL, f"{c['id']}: no manufacturing method", MFG))
            continue
        method, mid = mf["method"], mf.get("machine")
        if mid is None:
            if method in free_methods:
                res.append(CheckResult("T4.method", PASS, f"{c['id']}: {method}", MFG))
            elif method not in all_methods:
                res.append(CheckResult("T4.method", FAIL, f"{c['id']}: no available machine does {method}", MFG))
            else:
                res.append(CheckResult("T4.machine", FAIL,
                                       f"{c['id']}: in-house method {method} needs a `machine` so fit can be checked", MFG))
            continue
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
            res.append(CheckResult("T4.fits_machine", SKIP,
                                   f"{c['id']}: fit not verified — add build_volume_mm to manufacturing.yaml ({mid})",
                                   f"{MFG}#{mid}"))
            continue
        if is_point_mass(c):  # schema 0.4: no extent, so nothing to fit on a bed
            res.append(CheckResult("T4.method", PASS, f"{c['id']}: {method} on {mid}, point mass (no extent to fit)",
                                   f"{MFG}#{mid}"))
            continue
        sheet = method in SHEET_METHODS
        ext = _obb_extents(component_parts(c, design.base_dir))
        shown = [round(x, 1) for x in ext]
        if not _fits(ext, bed, sheet):
            res.append(CheckResult("T4.fits_machine", FAIL,
                                   f"{c['id']}: oriented extents {shown} mm do not fit {mid} bed {sorted(bed)}",
                                   f"{MFG}#{mid}"))
            continue
        note = ""
        if sheet and len(bed) < 3:
            note = f" (sheet thickness {shown[0]} mm; {mid} lists no thickness limit)"
        res.append(CheckResult("T4.method", PASS, f"{c['id']}: {method} on {mid}, fits{note}", f"{MFG}#{mid}"))
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
        return Scorecard(design.id, tiers, max_tier)
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
        return Scorecard(design.id, tiers, max_tier)

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
    return Scorecard(design.id, tiers, max_tier)
