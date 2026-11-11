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


def component_mesh(component: dict, base_dir=None) -> trimesh.Trimesh:
    g = component["geometry"]
    if "box" in g:
        m = trimesh.creation.box(extents=g["box"]["size"])
    elif "cylinder" in g:
        cyl = g["cylinder"]
        m = trimesh.creation.cylinder(radius=cyl["radius"], height=cyl["length"], sections=32)
        axis = cyl.get("axis", "x")
        if axis == "x":
            m.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
        elif axis == "y":
            m.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    elif "lifting_surface" in g:
        parts = [trimesh.convex.convex_hull(v) for v in lifting_surface_halves(g["lifting_surface"])]
        m = trimesh.util.concatenate(parts) if len(parts) > 1 else parts[0]
    elif "mesh" in g:
        from pathlib import Path
        m = trimesh.load(Path(base_dir or ".") / g["mesh"]["file"], force="mesh")
    else:
        raise ValueError(f"{component['id']}: unknown geometry")
    m = m.copy()
    m.apply_transform(_transform(component))
    return m


def component_parts(component: dict, base_dir=None) -> list[trimesh.Trimesh]:
    """Watertight convex pieces (wings split per half) for boolean operations."""
    g = component["geometry"]
    if "lifting_surface" in g:
        t = _transform(component)
        out = []
        for v in lifting_surface_halves(g["lifting_surface"]):
            m = trimesh.convex.convex_hull(v)
            m.apply_transform(t)
            out.append(m)
        return out
    return [component_mesh(component, base_dir)]


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
