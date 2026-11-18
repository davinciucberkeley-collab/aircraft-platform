"""Turn schema components into triangle meshes in the body frame (mm)."""
from __future__ import annotations

import math

import numpy as np
import trimesh

from .design import Design


def rotation_matrix(rpy_deg) -> np.ndarray:
    """Intrinsic roll (x), pitch (y), yaw (z): R = Rz @ Ry @ Rx."""
    r, p, y = (math.radians(a) for a in (rpy_deg or [0, 0, 0]))
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return rz @ ry @ rx


def _transform(component: dict) -> np.ndarray:
    t = np.eye(4)
    t[:3, :3] = rotation_matrix(component.get("rotation_deg"))
    t[:3, 3] = component["position"]
    return t


def lifting_surface_halves(ls: dict) -> list[np.ndarray]:
    """Vertices (local frame, root LE at origin) of each half as a tapered slab."""
    mirrored = ls.get("mirrored", True)
    semi = ls["span"] / 2 if mirrored else ls["span"]
    cr, ct = ls["root_chord"], ls["tip_chord"]
    tr = ls.get("thickness_ratio", 0.12)
    sweep = math.tan(math.radians(ls.get("sweep_le_deg", 0)))
    dihedral = math.tan(math.radians(ls.get("dihedral_deg", 0)))
    halves = []
    for sign in ([1, -1] if mirrored else [1]):
        pts = []
        for y, c in ((0.0, cr), (semi, ct)):
            x0 = y * sweep
            z0 = y * dihedral
            h = c * tr / 2
            for x in (x0, x0 + c):
                for z in (z0 - h, z0 + h):
                    pts.append([x, sign * y, z])
        halves.append(np.array(pts))
    return halves


def _primitive(g: dict) -> trimesh.Trimesh:
    """Box or cylinder (schema geometry or cavity), centred on the local origin."""
    if "box" in g:
        return trimesh.creation.box(extents=g["box"]["size"])
    cyl = g["cylinder"]
    m = trimesh.creation.cylinder(radius=cyl["radius"], height=cyl["length"], sections=32)
    axis = cyl.get("axis", "x")
    if axis == "x":
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
    elif axis == "y":
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    return m


def is_point_mass(component: dict) -> bool:
    """Schema 0.4: a mass at a point, with no extent. It has no mesh, so geometry-based checks skip it."""
    return "point_mass" in component["geometry"]


def _local_parts(component: dict, base_dir=None) -> list[trimesh.Trimesh]:
    """Untransformed parts of a component (wings split per half), local frame."""
    g = component["geometry"]
    if "point_mass" in g:
        return []
    if "lifting_surface" in g:
        return [trimesh.convex.convex_hull(v) for v in lifting_surface_halves(g["lifting_surface"])]
    if "mesh" in g:
        from pathlib import Path
        return [trimesh.load(Path(base_dir or ".") / g["mesh"]["file"], force="mesh")]
    if "box" in g or "cylinder" in g:
        return [_primitive(g)]
    raise ValueError(f"{component['id']}: unknown geometry")


def _apply_cavities(meshes: list[trimesh.Trimesh], component: dict) -> list[trimesh.Trimesh]:
    """Subtract each cavity (schema 0.3) from every part, in the component's local frame (before rotation)."""
    cavities = component.get("cavities") or []
    if not cavities:
        return meshes
    out = []
    for m in meshes:
        for cav in cavities:
            tool = _primitive(cav["geometry"])
            tool.apply_translation(cav["position"])
            diff = trimesh.boolean.difference([m, tool], engine="manifold")
            if diff is None or len(diff.faces) == 0:
                raise ValueError(f"{component['id']}: a cavity removes the whole part "
                                 f"(cavity at {cav['position']})")
            m = diff
        out.append(m)
    return out


def component_parts(component: dict, base_dir=None) -> list[trimesh.Trimesh]:
    """Watertight pieces (wings split per half) in the body frame, with cavities subtracted before the transform.
    A point_mass component has no pieces (empty list)."""
    parts = _apply_cavities(_local_parts(component, base_dir), component)
    t = _transform(component)
    out = []
    for m in parts:
        m = m.copy()
        m.apply_transform(t)
        out.append(m)
    return out


def component_mesh(component: dict, base_dir=None) -> trimesh.Trimesh:
    parts = component_parts(component, base_dir)
    if not parts:
        raise ValueError(f"{component['id']}: a point_mass has no mesh")
    return trimesh.util.concatenate(parts) if len(parts) > 1 else parts[0]


# ---------------------------------------------------------------- articulation (schema 0.2)
def att_label(a: dict) -> str:
    return a.get("id") or f"{a['parent']}->{a['child']}"


def articulated_attachments(design: Design) -> list[dict]:
    return [a for a in design.data.get("attachments", []) if a.get("articulation")]


def _adjacency(design: Design) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = {}
    for a in design.data.get("attachments", []):
        adj.setdefault(a["parent"], set()).add(a["child"])
        adj.setdefault(a["child"], set()).add(a["parent"])
    return adj


def downstream_ids(design: Design, att: dict) -> set[str]:
    """Components on the CHILD side of `att`: reached from the child without crossing this joint.
    If the joint lies in a loop the parent is reachable and the result contains it (T1.articulation FAILs that)."""
    adj = _adjacency(design)
    seen, stack = {att["child"]}, [att["child"]]
    while stack:
        n = stack.pop()
        for m in adj.get(n, ()):
            if m in seen or (n == att["child"] and m == att["parent"]):
                continue
            seen.add(m)
            stack.append(m)
    return seen


def _depth(design: Design, cid: str) -> int:
    adj = _adjacency(design)
    dist, frontier = {design.data["root"]: 0}, [design.data["root"]]
    while frontier:
        nxt = []
        for n in frontier:
            for m in adj.get(n, ()):
                if m not in dist:
                    dist[m] = dist[n] + 1
                    nxt.append(m)
        frontier = nxt
    return dist.get(cid, 0)


def joint_rotation(articulation: dict, angle_deg: float) -> np.ndarray:
    """4x4 rotation by angle_deg about the joint axis through its pivot (body frame, as written at 0 deg)."""
    axis = np.array(articulation["axis"], dtype=float)
    pivot = np.array(articulation["pivot"], dtype=float)
    return trimesh.transformations.rotation_matrix(math.radians(angle_deg), axis / np.linalg.norm(axis), pivot)


def pose_transforms(design: Design, angles: dict[str, float] | None) -> dict[str, np.ndarray]:
    """Component id -> 4x4 transform for the configuration `angles` (joint label -> degrees; missing = 0).
    Nested joints compose with the joint nearest the root applied last."""
    out = {c["id"]: np.eye(4) for c in design.components}
    if not angles:
        return out
    joints = [a for a in articulated_attachments(design) if abs(angles.get(att_label(a), 0.0)) > 1e-12]
    joints.sort(key=lambda a: _depth(design, a["parent"]), reverse=True)  # innermost (deepest) first
    for a in joints:
        r = joint_rotation(a["articulation"], angles[att_label(a)])
        for cid in downstream_ids(design, a):
            if cid in out:
                out[cid] = r @ out[cid]
    return out


def posed_component_parts(design: Design, angles: dict[str, float] | None = None) -> dict[str, list[trimesh.Trimesh]]:
    """Watertight parts of every component with the articulated joints at `angles` (None = 0 deg, as written)."""
    tf = pose_transforms(design, angles)
    out = {}
    for c in design.components:
        parts = component_parts(c, design.base_dir)
        t = tf[c["id"]]
        if not np.allclose(t, np.eye(4)):
            parts = [p.copy() for p in parts]
            for p in parts:
                p.apply_transform(t)
        out[c["id"]] = parts
    return out


def pose_angles(design: Design, pose_name: str | None) -> dict[str, float]:
    """Joint label -> angle for a named pose (joints that do not define it stay at 0). None -> all 0."""
    if not pose_name:
        return {}
    return {att_label(a): float(a["articulation"].get("poses", {}).get(pose_name, 0.0))
            for a in articulated_attachments(design)}


def design_meshes(design: Design) -> dict[str, list[trimesh.Trimesh]]:
    return {c["id"]: component_parts(c, design.base_dir) for c in design.components}


def lifting_surface_properties(component: dict, pose: np.ndarray | None = None) -> dict:
    """Area (mm^2), aspect ratio, MAC (mm) and the body-frame x of the MAC quarter-chord."""
    ls = component["geometry"]["lifting_surface"]
    mirrored = ls.get("mirrored", True)
    semi = ls["span"] / 2 if mirrored else ls["span"]
    cr, ct = ls["root_chord"], ls["tip_chord"]
    lam = ct / cr
    s_half = semi * (cr + ct) / 2
    area = s_half * (2 if mirrored else 1)
    span = ls["span"] if mirrored else 2 * semi  # effective span for AR of a single panel (reflection)
    ar = span ** 2 / (area if mirrored else 2 * area)
    mac = (2 / 3) * cr * (1 + lam + lam ** 2) / (1 + lam)
    y_mac = semi / 3 * (1 + 2 * lam) / (1 + lam)
    x_le_mac = y_mac * math.tan(math.radians(ls.get("sweep_le_deg", 0)))
    local_ac = np.array([x_le_mac + 0.25 * mac, 0.0, 0.0])
    ac_body = rotation_matrix(component.get("rotation_deg")) @ local_ac + np.array(component["position"])
    if pose is not None:  # articulated joint at a pose: 4x4 transform of the component's subtree
        ac_body = pose[:3, :3] @ ac_body + pose[:3, 3]
    return {"area_mm2": area, "aspect_ratio": ar, "mac_mm": mac, "x_ac_mm": float(ac_body[0]),
            "lifting": ls.get("lifting", True)}


def strip_planform(owners: dict[str, list[trimesh.Trimesh]], root: str, n: int = 41, gap_tol: float = 3.0,
                   control_frac: float = 0.15) -> dict:
    """Aero numbers of a mesh wing measured from its geometry only (the declared planform is never used here).
    `owners` maps each component id of the wing (the root and its articulated children, control surfaces) to its
    body-frame meshes; `root` is the planform component. Chord runs along body x (freestream). The span axis is body y
    or body z, whichever the geometry's extent is larger along. The span extent is split into n equal strips of width
    dy, each sliced at its centre by a plane normal to the span axis. Per strip every owner's section is projected onto
    x as intervals (one per closed loop, tagged with its owner). Intervals are merged in x order when the gap is at most:
      - control_frac x the strip's material envelope (min x to max x of all owners), between root material and a control
        surface's material (hinge gaps, balance pockets);
      - gap_tol otherwise.
    The chord is the LONGEST merged group, LE its min x; other groups are detached material, ignored and listed. A strip
    with no section counts as c = 0 and is listed.
    Midpoint rule: S = sum c_i dy, MAC = sum c_i^2 dy / S, x_ac = sum (LE_i + c_i/4) c_i dy / S, AR = b^2 / S, b = span extent.
    Returns the lifting_surface_properties keys plus span_mm, span_axis, missing_stations, ignored_strips
    ([strip, detached length mm] pairs), control_gap_strips ([strip, bridged gap mm] pairs above gap_tol), source and strip_data (per-strip
    centres, LE x and chord, with the span axis index and extent: input of the vortex-lattice model in aero.py)."""
    allv = np.vstack([m.vertices for meshes in owners.values() for m in meshes])
    ext = allv.max(axis=0) - allv.min(axis=0)
    axis = 1 if ext[1] >= ext[2] else 2
    e = np.zeros(3)
    e[axis] = 1.0
    lo_s, hi_s = float(allv[:, axis].min()), float(allv[:, axis].max())
    b = hi_s - lo_s
    dy = b / n
    centres = lo_s + (np.arange(n) + 0.5) * dy
    chord = np.zeros(n)
    le = np.zeros(n)
    missing: list[int] = []
    ignored: list[list[float]] = []
    control_gaps: list[list[float]] = []
    for i, c_pos in enumerate(centres):
        origin = np.zeros(3)
        origin[axis] = c_pos
        ivs: list[tuple[float, float, str]] = []
        for owner, meshes in owners.items():
            for m in meshes:
                sec = m.section(plane_origin=origin, plane_normal=e)
                if sec is None:
                    continue
                for ent in sec.entities:
                    xs = sec.vertices[ent.points][:, 0]
                    ivs.append((float(xs.min()), float(xs.max()), owner))
        if not ivs:
            missing.append(i)
            continue
        envelope = max(h for _, h, _ in ivs) - min(l for l, _, _ in ivs)
        ivs.sort(key=lambda t: t[0])
        merged: list[list] = []  # [lo, hi, owners]
        for lo, hi, ow in ivs:
            if merged:
                grp = merged[-1]
                gap = lo - grp[1]
                cross = (ow != root and root in grp[2]) or (ow == root and any(o != root for o in grp[2]))
                limit = max(gap_tol, control_frac * envelope) if cross else gap_tol
                if gap <= limit:
                    if cross and gap > gap_tol:
                        control_gaps.append([i, round(gap, 2)])
                    grp[1] = max(grp[1], hi)
                    grp[2].add(ow)
                    continue
            merged.append([lo, hi, {ow}])
        main = max(merged, key=lambda gr: gr[1] - gr[0])
        le[i] = main[0]
        chord[i] = main[1] - main[0]
        rest = [gr[1] - gr[0] for gr in merged if gr is not main]
        if rest:
            ignored.append([i, round(max(rest), 2)])
    area = float(np.sum(chord) * dy)
    mac = float(np.sum(chord ** 2) * dy / area)
    x_ac = float(np.sum((le + 0.25 * chord) * chord) * dy / area)
    return {"area_mm2": area, "aspect_ratio": b ** 2 / area, "mac_mm": mac, "x_ac_mm": x_ac,
            "lifting": True, "span_mm": b, "span_axis": "yz"[axis - 1], "missing_stations": missing,
            "ignored_strips": ignored, "control_gap_strips": control_gaps,
            "source": f"geometry strips ({n} stations)",
            "strip_data": {"axis": axis, "lo": lo_s, "hi": hi_s, "centres": centres.tolist(), "le": le.tolist(),
                           "chord": chord.tolist()}}
