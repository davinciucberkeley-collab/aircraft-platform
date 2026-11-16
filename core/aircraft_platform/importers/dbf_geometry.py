"""Rebuild DBF-Combined CAD bodies (prism / revolve / loft + cuts) as watertight trimesh solids, in millimetres.

The conventions mirror the source's own mesh builders, which are the geometry its interference check and its GLB are
made from (redesign/blender/blender_backend.py: add_prism / add_revolve / add_loft; redesign/manufacturing/
blender_mesh.py: body_object, _despike, subtract; redesign/fusion/fusionkit.py: to3d, UV):

  plane (u, v) of a plane normal to X/Y/Z is (y, z) / (x, z) / (x, y); a point is to3d(axis, offset, (u, v));
  prism   outer loop minus hole loops, extruded from `offset` by the signed `depth` (a hole that crosses the outline is
          "outline minus hole", the same repair blender_mesh.body_object applies);
  revolve closed (a, r) profile swept 360 deg about the axis-aligned line through `center`, SEG = 48 segments (24 when
          the largest radius is <= 4 mm), ring vertex at angle t: i_axis += r cos t, j_axis += r sin t, r = 0 is an apex;
  loft    closed loops on parallel planes joined by ruled quads, capped; smooth = open Catmull-Rom (3 points per segment)
          through each loop first, loops of different length resampled by arc length to the longest.

A component is the union of its bodies minus its cuts (each cut carries its own local-to-world matrix), then moved by
the component matrix. The source stores metres; everything here is scaled to millimetres first.
"""
from __future__ import annotations

import math

import numpy as np
import trimesh

SEG = 48            # blender_backend.SEG
SMOOTH_SUB = 3      # blender_backend.SMOOTH_SUB
AX = {"X": 0, "Y": 1, "Z": 2}
UV = {"X": (1, 2), "Y": (0, 2), "Z": (0, 1)}


class GeometryError(Exception):
    pass


# ------------------------------------------------------------------ helpers copied in behaviour from the source
def _to3d(axis: str, offset: float, uv: np.ndarray) -> np.ndarray:
    """(n, 2) plane points -> (n, 3), the plane normal to `axis` at `offset`."""
    out = np.zeros((len(uv), 3))
    iu, iv = UV[axis]
    out[:, AX[axis]] = offset
    out[:, iu], out[:, iv] = uv[:, 0], uv[:, 1]
    return out


def _despike(loop, eps=1e-9):
    """blender_mesh._despike: drop repeated points and points where the outline doubles back (zero-width spikes)."""
    pts = [list(p) for p in loop]
    changed = True
    while changed and len(pts) > 3:
        changed = False
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            d1, d2 = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
            if abs(d1[0]) + abs(d1[1]) < eps or \
                    (abs(d1[0] * d2[1] - d1[1] * d2[0]) < eps * eps * 1e3 and d1[0] * d2[0] + d1[1] * d2[1] < 0):
                del pts[i]
                changed = True
                break
    return pts


def _open(loop):
    return list(loop[:-1]) if tuple(loop[0]) == tuple(loop[-1]) else list(loop)


def _catmull(pts, sub):
    """blender_backend._catmull: open Catmull-Rom through pts, `sub` points per segment."""
    out = []
    n = len(pts)
    for i in range(n - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, n - 1)]
        for s in range(sub):
            t = s / sub
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                                    + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in range(2)))
    out.append(tuple(pts[-1]))
    return out


def _resample(loop, n):
    """blender_backend._resample: closed loop -> n points evenly spaced by arc length."""
    pts = list(loop) + [loop[0]]
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(loop))]
    total = sum(seg)
    out, i, acc = [], 0, 0.0
    for k in range(n):
        target = total * k / n
        while acc + seg[i] < target and i < len(seg) - 1:
            acc += seg[i]
            i += 1
        t = (target - acc) / seg[i] if seg[i] else 0.0
        out.append(tuple(pts[i][j] + t * (pts[i + 1][j] - pts[i][j]) for j in range(2)))
    return out


# ------------------------------------------------------------------ mesh utilities
def _clean(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    mesh.merge_vertices(merge_tex=True, merge_norm=True)
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    if len(mesh.faces) == 0:
        raise GeometryError("empty mesh")
    trimesh.repair.fix_normals(mesh)  # consistent winding, outward (volume > 0)
    return mesh


def _manifold(mesh: trimesh.Trimesh):
    import manifold3d as m
    return m.Manifold(m.Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
                             tri_verts=np.asarray(mesh.faces, dtype=np.uint32)))


PINCH_MM = 5e-4   # 0.5 micron: pulls coincident-but-distinct vertices apart (see _separate_pinches)


def _separate_pinches(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """A Manifold union of two bodies that touch only along an edge or at a point keeps two distinct vertices at the
    same position (valid topologically). An STL file cannot carry that: on reload the vertices merge and the shared
    edge then has four faces, so the mesh is no longer watertight. Every vertex that has a coincident partner is moved
    PINCH_MM toward the centroid of its own faces' other corners, which separates the pair without changing the shape visibly
    (the source's own fix is a 0.01 mm grow of the bodies, blender_mesh.GROW_MM; this moves 20x less and only where
    needed)."""
    key = np.round(vertices / 1e-5).astype(np.int64)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    inv = np.asarray(inv).reshape(-1)
    pinched = cnt[inv] > 1
    if not pinched.any():
        return vertices
    # move each pinched vertex toward the centroid of the other corners of ITS OWN faces: the two halves of a pinch
    # have different faces, so they move in different directions even where their normals agree
    acc = np.zeros_like(vertices)
    cntf = np.zeros(len(vertices))
    for k in range(3):
        for o in ((k + 1) % 3, (k + 2) % 3):
            np.add.at(acc, faces[:, k], vertices[faces[:, o]] - vertices[faces[:, k]])
            np.add.at(cntf, faces[:, k], 1.0)
    d = acc / np.maximum(cntf, 1)[:, None]
    ln = np.linalg.norm(d, axis=1)
    ok = pinched & (ln > 0)
    out = vertices.copy()
    out[ok] += PINCH_MM * d[ok] / ln[ok, None]
    return out


def _from_manifold(man) -> trimesh.Trimesh:
    out = man.to_mesh()
    v = np.asarray(out.vert_properties)[:, :3].astype(float)
    f = np.asarray(out.tri_verts)
    return trimesh.Trimesh(vertices=_separate_pinches(v, f), faces=f, process=False)


def _boolean(op: str, meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    import manifold3d as m
    mans = []
    for x in meshes:
        mm = _manifold(x)
        if mm.status() != m.Error.NoError:
            raise GeometryError(f"input is not manifold ({mm.status()})")
        mans.append(mm)
    if op == "union":
        res = m.Manifold.batch_boolean(mans, m.OpType.Add)
    else:
        res = m.Manifold.batch_boolean(mans, m.OpType.Subtract)
    return _from_manifold(res)


# ------------------------------------------------------------------ the three body kinds (local frame, mm)
def _prism(s: dict) -> trimesh.Trimesh:
    import manifold3d as m
    loops = [_despike([tuple(p) for p in _open(l)]) for l in s["loops"]]
    loops = [np.asarray(l, dtype=float) * 1000.0 for l in loops if len(l) >= 3]
    if not loops:
        raise GeometryError("prism without a loop")
    depth = float(s["depth"]) * 1000.0
    offset = float(s["offset"]) * 1000.0
    if abs(depth) < 1e-9:
        raise GeometryError("prism of zero depth")
    cs = m.CrossSection([loops[0]], m.FillRule.EvenOdd)
    if len(loops) > 1:
        holes = m.CrossSection([np.asarray(h) for h in loops[1:]], m.FillRule.EvenOdd)
        cs = cs - holes
    if cs.is_empty():
        raise GeometryError("prism cross-section is empty")
    man = m.Manifold.extrude(cs, abs(depth))
    t = _from_manifold(man)
    v = t.vertices
    out = np.zeros_like(v)
    iu, iv = UV[s["axis"]]
    out[:, iu], out[:, iv] = v[:, 0], v[:, 1]
    out[:, AX[s["axis"]]] = offset + math.copysign(1.0, depth) * v[:, 2]
    t = trimesh.Trimesh(out, t.faces, process=False)
    return _clean(t)


def _revolve(s: dict) -> trimesh.Trimesh:
    k = AX[s["axis"]]
    i_ax, j_ax = [q for q in range(3) if q != k]
    prof = [tuple(p) for p in s["profile"]]
    prof = prof[:-1] if prof[0] == prof[-1] else prof
    center = np.asarray(s["center"], dtype=float) * 1000.0
    prof = [(a * 1000.0, r * 1000.0) for a, r in prof]
    rmax = max(r for _, r in prof)
    seg = SEG if rmax > 4.0 else 24           # source: rmax > 0.004 m
    verts: list[list[float]] = []
    rings: list[list[int]] = []
    for a, r in prof:
        if r < 1e-6:                          # source: r < 1e-9 m
            p = center.copy()
            p[k] += a
            verts.append(p.tolist())
            rings.append([len(verts) - 1])
            continue
        ring = []
        for q in range(seg):
            th = 2 * math.pi * q / seg
            p = center.copy()
            p[k] += a
            p[i_ax] += r * math.cos(th)
            p[j_ax] += r * math.sin(th)
            verts.append(p.tolist())
            ring.append(len(verts) - 1)
        rings.append(ring)
    faces = []
    n = len(rings)
    for e in range(n):
        A, B = rings[e], rings[(e + 1) % n]
        if len(A) == 1 and len(B) == 1:
            continue                          # an edge along the axis makes no surface
        for q in range(seg):
            q2 = (q + 1) % seg
            if len(A) == 1:
                faces.append((A[0], B[q], B[q2]))
            elif len(B) == 1:
                faces.append((A[q], B[0], A[q2]))
            else:
                faces.append((A[q], B[q], B[q2]))
                faces.append((A[q], B[q2], A[q2]))
    return _clean(trimesh.Trimesh(np.asarray(verts), np.asarray(faces), process=False))


def _loft(s: dict) -> trimesh.Trimesh:
    import manifold3d as m
    loops = []
    for _, loop in s["sections"]:
        pts = [(u * 1000.0, v * 1000.0) for u, v in _open([tuple(p) for p in loop])]
        loops.append(_catmull(pts, SMOOTH_SUB) if s.get("smooth") else pts)
    n = max(len(x) for x in loops)
    loops = [x if len(x) == n else _resample(x, n) for x in loops]
    verts, rings = [], []
    for (o, _), loop in zip(s["sections"], loops):
        base = len(verts)
        verts.extend(_to3d(s["axis"], float(o) * 1000.0, np.asarray(loop, dtype=float)).tolist())
        rings.append(list(range(base, base + n)))
    faces = []
    for A, B in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            faces.append((A[i], A[j], B[j]))
            faces.append((A[i], B[j], B[i]))
    # caps: triangulate the (planar) end loops; fix_normals orients everything afterwards
    for ring, loop in ((rings[0], loops[0]), (rings[-1], loops[-1])):
        poly = np.asarray(loop, dtype=float)
        area = 0.5 * float(np.sum(poly[:, 0] * np.roll(poly[:, 1], -1) - np.roll(poly[:, 0], -1) * poly[:, 1]))
        order = list(range(n)) if area >= 0 else list(range(n))[::-1]
        tri = m.triangulate([poly[order]])
        for a, b, c in tri:
            faces.append((ring[order[a]], ring[order[b]], ring[order[c]]))
    return _clean(trimesh.Trimesh(np.asarray(verts), np.asarray(faces), process=False))


_KIND = {"prism": _prism, "revolve": _revolve, "loft": _loft}


def body_mesh(shape: dict) -> trimesh.Trimesh:
    """One CAD body (shape_to_json dict, metres) as a closed solid in its component-local frame, millimetres."""
    return _KIND[shape["kind"]](shape)


def _place(mesh: trimesh.Trimesh, matrix) -> trimesh.Trimesh:
    t = np.asarray(matrix, dtype=float).copy()
    t[:3, 3] *= 1000.0                        # local mm -> world mm: R (x_mm) + t_mm
    out = mesh.copy()
    out.apply_transform(t)
    if np.linalg.det(t[:3, :3]) < 0:
        out.invert()
    return out


def _closed(mesh: trimesh.Trimesh) -> bool:
    return bool(mesh.is_watertight and mesh.is_volume and mesh.volume > 0)


def part_mesh(comp: dict) -> tuple[trimesh.Trimesh, dict]:
    """The part's solid in world mm: union of its bodies, minus its cuts. Returns (mesh, info).
    info: bodies, body_volume_ratio (mesh volume / the source's analytic volume per body), n_cuts."""
    M = comp["matrix"]
    local, ratios = [], []
    for i, b in enumerate(comp["bodies"]):
        try:
            lm = body_mesh(b)
        except GeometryError as e:
            raise GeometryError(f"body {i} ({b.get('name', '')!r}, {b['kind']}): {e}") from e
        vols = comp.get("body_vol_m3")
        if vols and vols[i] > 0:
            ratios.append(abs(lm.volume) / (vols[i] * 1e9))
        local.append(lm)
    cuts = []
    for shape, Mc in comp.get("cuts", []):
        try:
            cuts.append(_place(body_mesh(shape), Mc))
        except GeometryError:
            continue
    placed = [_place(lm, M) for lm in local]
    base = placed[0] if len(placed) == 1 else _boolean("union", placed)
    lo, hi = base.bounds
    near = [c for c in cuts if np.all(c.bounds[0] < hi) and np.all(c.bounds[1] > lo)]
    mesh = base
    if near:
        # all cutters at once, else one at a time: either order can leave an edge pinch (see _separate_pinches)
        # that the other does not; take the first result that is closed
        mesh = None
        for mode in ("batch", "sequential"):
            try:
                cand = _boolean("difference", [base] + near) if mode == "batch" else None
                if mode == "sequential":
                    cand = base
                    for cutter in near:
                        cand = _boolean("difference", [cand, cutter])
            except GeometryError:
                continue
            cand = _clean(cand)
            mesh = cand
            if _closed(cand):
                break
        if mesh is None:
            raise GeometryError("cuts failed")
    mesh = _clean(mesh)
    if not _closed(mesh):
        raise GeometryError(f"not watertight after union/cuts (watertight={mesh.is_watertight}, "
                            f"volume={mesh.is_volume}, bodies={len(local)}, cuts={len(cuts)})")
    return mesh, {"bodies": len(placed), "body_volume_ratio": ratios, "n_cuts": len(comp.get("cuts", []))}
