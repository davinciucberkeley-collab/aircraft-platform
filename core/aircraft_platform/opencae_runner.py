"""Run one structural job in OpenCAE Studio. Executed by OpenCAE's own Python, not by the platform:

    <opencae python> opencae_runner.py job.json

It imports only OpenCAE, numpy and scipy, so it works in OpenCAE's environment without the platform
installed. The platform (aircraft_platform.fea) writes job.json and reads result.json.

job.json
    name, stl (part surface, mm), units ("mm-N-s"), material_id (OpenCAE database id),
    mesh {size_max, order}, select_tol_mm, singularity_band_mm,
    supports: [{name, points: [[x,y,z], ...]}]          interface sample points on the part surface
    cases: [{name, loads: [{name, points, force: [Fx,Fy,Fz] N, point: [x,y,z], moment: [Mx,My,Mz] N mm}]}]
    project_dir (optional): where to save an .ocae project per case for opening in the GUI
    out: result.json path

Each support becomes a fixed constraint on the faces of the part that touch it; each load is an OpenCAE
remote force (force at a point, carried into the faces of that joint as a uniform traction plus the
moment of the offset) plus, when the joint also carries one, an OpenCAE moment load on the same faces. Faces are picked from the interface points the platform found, never by guessing.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np


def _face_selector(body, tol: float):
    """Map interface points to body faces: a face is selected when it holds interface points."""
    from scipy.spatial import cKDTree
    tess = body.tessellation
    P, T, TF = np.asarray(tess.points), np.asarray(tess.triangles), np.asarray(tess.tri_face)
    cent = P[T].mean(axis=1)
    tree = cKDTree(cent)
    area = 0.5 * np.linalg.norm(np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]]), axis=1)
    face_area = np.bincount(TF[TF >= 0], weights=area[TF >= 0], minlength=len(body.faces))

    def select(points) -> tuple[list[int], dict]:
        pts = np.asarray(points, float).reshape(-1, 3)
        if not len(pts):
            return [], {"points": 0}
        # triangles near any interface point (within tol of the triangle centroid, or the nearest one)
        near = set()
        for idx in tree.query_ball_point(pts, r=tol):
            near.update(idx)
        _, nearest = tree.query(pts)
        near.update(int(i) for i in np.atleast_1d(nearest))
        near = np.array(sorted(near), int)
        hit_area = np.bincount(TF[near], weights=area[near], minlength=len(body.faces))
        faces = [int(f) for f in np.nonzero(hit_area > 0)[0]]
        sel_area = float(face_area[faces].sum())
        return faces, {"points": int(len(pts)), "faces": len(faces), "face_area_mm2": round(sel_area, 2),
                       "touching_area_mm2": round(float(hit_area.sum()), 2)}
    return select


def _material(job: dict):
    """OpenCAE's own record when it has one (its sourced database, or its built-in library), else the record the
    platform sends from standards/design-standards.yaml. Returns (Material, where it came from)."""
    mid = job["material_id"]
    try:
        from opencae.materials import database as db
        m = db.find(mid)
        if m is not None:
            return m, "OpenCAE material database"
    except ImportError:  # OpenCAE versions without the sourced database
        pass
    from opencae.materials import library
    for m in library.builtin_materials() + list(getattr(library, "drone_materials", lambda: [])()):
        if m.id == mid:
            return m, "OpenCAE built-in library"
    rec = job.get("material")
    if not rec:
        raise ValueError(f"material {mid!r} is not in this OpenCAE and the job carries no material record")
    from opencae.project.model import Material
    m = Material(name=rec["name"], youngs_modulus=float(rec["youngs_modulus_mpa"]) * 1e6,
                 poissons_ratio=float(rec["poissons_ratio"]), density=float(rec["density_kg_m3"]), id=mid)
    for k, v in (("is_example", False), ("notes", rec.get("source", ""))):
        if hasattr(m, k):
            setattr(m, k, v)
    return m, "platform standards (design-standards.yaml)"


def _ccx_errors(out) -> str:
    """The distinct CalculiX error lines (it repeats one per element), with counts."""
    from collections import Counter
    errs = Counter(str(e).strip() for e in (getattr(out, "errors", None) or []))
    if not errs:
        return f"return code {getattr(out, 'returncode', '?')}"
    return "; ".join(f"{m} (x{n})" if n > 1 else m for m, n in errs.most_common(3))


class _UseDirect(Exception):
    """OpenCAE's exact-geometry route can't take this part (faceted solid too complex for its CAD meshing)."""


MAX_CAD_FACES = 1200  # above this, OpenCAE's face matching for a faceted STL solid needs too much memory


def _run_case(job: dict, case: dict, log) -> dict:
    """OpenCAE's normal route (STL -> faceted solid -> Gmsh) when it can take the part, else the direct route."""
    if not job.get("force_direct"):
        try:
            return _run_case_session(job, case, log)
        except _UseDirect as e:
            log(f"  {case['name']}: {e}; using the direct mesh route")
            res = _run_case_direct(job, case, log)
            res["route_reason"] = str(e)
            return res
    return _run_case_direct(job, case, log)


def _run_case_session(job: dict, case: dict, log) -> dict:
    from opencae.app.session import Session
    from opencae.geometry.references import make_ref
    from opencae.project.model import Constraint, Load

    t0 = time.time()
    s = Session()
    s.new(f"{job['name']} - {case['name']}", job.get("units", "mm-N-s"))
    s.project.description = job.get("description", "")
    s.import_geometry(Path(job["stl"]), to_solid=True)
    body = s.analysis_body()
    if body is None:
        raise _UseDirect("STL could not be turned into one solid (" + "; ".join(s.regen.errors.values()) + ")")
    if len(body.faces) > MAX_CAD_FACES:
        raise _UseDirect(f"faceted solid has {len(body.faces)} faces")
    mat, mat_from = _material(job)
    if mat.id not in [m.id for m in s.project.materials]:
        s.project.materials.append(mat)
    s.project.assign_material(body.id, mat.id)

    select = _face_selector(body, float(job.get("select_tol_mm", 0.6)))
    sel_info, support_faces = {}, []
    cons = []
    for sup in job["supports"]:
        faces, info = select(sup["points"])
        sel_info["support " + sup["name"]] = info
        if not faces:
            raise ValueError(f"support {sup['name']}: no faces found at the interface")
        support_faces += faces
        cons.append(Constraint("fixed", [make_ref(body, "face", f) for f in faces], name=sup["name"]))
    loads, applied = [], np.zeros(3)
    for ld in case["loads"]:
        F = np.asarray(ld["force"], float)
        M = np.asarray(ld.get("moment", [0, 0, 0]), float)
        mag, mmag = float(np.linalg.norm(F)), float(np.linalg.norm(M))
        if mag < 1e-9 and mmag < 1e-9:
            continue
        faces, info = select(ld["points"])
        shared = [f for f in faces if f in support_faces]
        faces = [f for f in faces if f not in support_faces]  # a clamped face can't carry a load
        info["faces_shared_with_supports_dropped"] = len(shared)
        sel_info["load " + ld["name"]] = info
        if not faces and shared:
            info["note"] = "every face of this joint is also clamped: the load goes straight into the support"
            continue
        if not faces:
            raise ValueError(f"load {ld['name']}: no faces found at the interface")
        refs = [make_ref(body, "face", f) for f in faces]
        if mag >= 1e-9:
            loads.append(Load("remote_force", refs, {"magnitude": mag, "direction": (F / mag).tolist(),
                                                     "point": list(map(float, ld["point"]))}, name=ld["name"]))
        if mmag >= 1e-9:
            loads.append(Load("moment", list(refs), {"magnitude": mmag, "direction": (M / mmag).tolist()},
                              name=ld["name"] + " (moment)"))
        applied += F
    s.project.constraints = cons
    s.project.loads = loads
    ms = s.project.mesh_settings
    ms.size_max = float(job["mesh"]["size_max"])
    ms.element_order = int(job["mesh"].get("order", 2))
    if not loads:
        return {"case": case["name"], "skipped": "no load reaches this part in this case (or only clamped faces)",
                "selection": sel_info}
    log(f"  {case['name']}: meshing (size {ms.size_max} mm)")
    try:
        s.generate_mesh()
    except Exception as e:  # noqa: BLE001 - Gmsh rejects some faceted solids (overlapping facets)
        raise _UseDirect(f"OpenCAE meshing failed ({str(e)[:120]})") from e
    log(f"  {case['name']}: {s.mesh.n_nodes} nodes, solving with CalculiX")
    out, issues = s.run_solver()
    errs = [str(i) for i in issues if getattr(i, "severity", "") == "error"]
    if not out or not out.success:  # e.g. inverted elements in a faceted solid: the direct route meshes afresh
        raise _UseDirect("OpenCAE's solve failed (" + ("; ".join(errs) if errs else _ccx_errors(out))[:160] + ")")
    rs = s.results
    sm = rs.summary()
    vm = np.asarray(rs.quantity("S_vm"), float)
    nodes = np.asarray(rs.mesh.nodes, float)
    # away from the clamped faces: a rigid clamp is a stress singularity, so report both values
    band = float(job.get("singularity_band_mm", 2.0))
    from scipy.spatial import cKDTree
    sup_pts = np.vstack([np.asarray(sp["points"], float).reshape(-1, 3) for sp in job["supports"]])
    dist, _ = cKDTree(sup_pts).query(nodes)
    away = dist > band
    vm_away = float(vm[away].max()) if away.any() else float("nan")
    j_away = int(np.argmax(np.where(away, vm, -1.0)))
    from opencae.postprocessing.results import equilibrium_check
    eq = equilibrium_check(s.project.results.summary) or {}
    react = np.asarray(eq.get("reactions", [np.nan] * 3), float)
    res = {
        "case": case["name"], "route": "opencae-cad", "material_from": mat_from,
        "nodes": int(s.mesh.n_nodes), "elements": int(getattr(s.mesh, "n_elements", 0) or 0),
        "mesh_size_max_mm": ms.size_max, "element_order": ms.element_order,
        "max_von_mises_mpa": float(sm.get("max_von_mises_nodal", float("nan"))),
        "max_von_mises_location": sm.get("max_von_mises_location"),
        "max_von_mises_away_mpa": vm_away, "max_von_mises_away_location": nodes[j_away].tolist(),
        "singularity_band_mm": band,
        "max_displacement_mm": float(sm["max_displacement"]),
        "applied_force_n": applied.tolist(), "reaction_force_n": react.tolist(),
        "load_on_clamped_faces_n": np.asarray(eq.get("on_constrained", [0, 0, 0]), float).tolist(),
        "equilibrium_error": float(eq.get("relative", float("nan"))), "equilibrium_ok": bool(eq.get("ok", False)),
        "selection": sel_info, "wall_time_s": round(time.time() - t0, 1),
    }
    if job.get("project_dir"):
        pd = Path(job["project_dir"])
        pd.mkdir(parents=True, exist_ok=True)
        stem = f"{job['name']}-{case['name']}".replace(" ", "_")
        p = s.save(pd / f"{stem}.ocae")
        res["project"] = str(p)
        try:
            from opencae.postprocessing.report import write_report
            res["report"] = str(write_report(s, pd / f"{stem}_report.html", notes=job.get("description", "")))
        except Exception as e:  # noqa: BLE001 - the numbers are the result; the report is a convenience
            res["report_error"] = f"{type(e).__name__}: {e}"
    return res


def _gmsh_volume(stl: str, size_max: float, order: int):
    """Tetrahedral mesh straight from a closed STL: classify its facets into surfaces, remesh them, fill the
    volume. Falls back to keeping the STL triangles as the surface mesh if remeshing fails."""
    import math
    import gmsh
    from opencae.meshing.elements import solid_type
    gmsh.initialize(["-noenv"])
    gmsh.option.setNumber("General.Terminal", 0)
    try:
        last = None
        for remesh in (True, False):
            gmsh.clear()
            gmsh.merge(stl)
            try:
                if remesh:
                    gmsh.model.mesh.classifySurfaces(40 * math.pi / 180, True, True, math.pi)
                    gmsh.model.mesh.createGeometry()
                surfs = [t for _, t in gmsh.model.getEntities(2)]
                loop = gmsh.model.geo.addSurfaceLoop(surfs)
                gmsh.model.geo.addVolume([loop])
                gmsh.model.geo.synchronize()
                gmsh.option.setNumber("Mesh.MeshSizeMax", size_max)
                gmsh.option.setNumber("Mesh.MeshSizeMin", size_max / 5)
                gmsh.option.setNumber("Mesh.Algorithm3D", 1)
                gmsh.option.setNumber("Mesh.Optimize", 1)
                gmsh.model.mesh.generate(3)
                if order == 2:
                    gmsh.option.setNumber("Mesh.SecondOrderLinear", 1)  # straight edges: no inverted curved tets
                    gmsh.model.mesh.setOrder(2)
                tags, xyz, _ = gmsh.model.mesh.getNodes()
                etype = 11 if order == 2 else 4
                et, etags, enodes = gmsh.model.mesh.getElements(3)
                k = list(et).index(etype)
                index = {int(t): i for i, t in enumerate(tags)}
                el = np.vectorize(index.get)(np.asarray(enodes[k], np.int64).reshape(-1, 10 if order == 2 else 4))
                st = solid_type("C3D10" if order == 2 else "C3D4")
                el = el[:, list(st.gmsh_to_ccx)]
                return (np.asarray(xyz, float).reshape(-1, 3), el, ("surface remeshed" if remesh else "STL facets kept"),
                        size_max)
            except Exception as e:  # noqa: BLE001 - try the next way
                last = e
    finally:
        gmsh.finalize()
    return _tetwild_volume(stl, size_max, order, f"Gmsh could not mesh the part ({str(last)[:100]})")


def _tetwild_volume(stl: str, size_max: float, order: int, why: str):
    """fTetWild (pytetwild) tolerates the near-touching or self-intersecting facets Gmsh rejects. It wraps the
    surface within 0.1 % of the part size. Mid-side nodes are added on straight edges for C3D10."""
    try:
        import pytetwild
    except ImportError as e:
        raise RuntimeError(why + "; install pytetwild in OpenCAE's environment for a fallback mesher") from e
    import meshio
    m = meshio.read(stl)
    # fTetWild's cost rises steeply with refinement; 2.5 mm edges keep a hub-sized part to a few minutes
    v, t = pytetwild.tetrahedralize(np.asarray(m.points, float), np.asarray(m.cells_dict["triangle"], np.int32),
                                    edge_length_abs=max(size_max, 2.5), stop_energy=20.0, num_opt_iter=40)
    v, t = np.asarray(v, float), np.asarray(t, np.int64)
    a, b, c, d = (v[t[:, i]] for i in range(4))
    neg = np.einsum("ij,ij->i", np.cross(b - a, c - a), d - a) < 0
    t[neg] = t[neg][:, [0, 2, 1, 3]]  # positive orientation for CalculiX
    if order == 1:
        return v, t, why + "; meshed with fTetWild", max(size_max, 2.5)
    # CalculiX C3D10 mid-side nodes on edges 12, 23, 31, 14, 24, 34
    pairs = [(0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)]
    e = np.sort(np.concatenate([t[:, [i, j]] for i, j in pairs]), axis=1)
    uniq, inv = np.unique(e, axis=0, return_inverse=True)
    mid = (v[uniq[:, 0]] + v[uniq[:, 1]]) / 2
    ids = len(v) + inv.reshape(len(pairs), len(t)).T
    return np.vstack([v, mid]), np.hstack([t, ids]), why + "; meshed with fTetWild", max(size_max, 2.5)


def _remote_force(nodes: np.ndarray, faces: np.ndarray, F: np.ndarray, P: np.ndarray, nodal: np.ndarray,
                  M_extra: np.ndarray | None = None):
    """OpenCAE's remote force and moment (boundary_conditions.resolve): uniform traction F on the faces plus the
    moment (P - c) x F + M_extra as linearly varying nodal forces with zero net force. Adds into `nodal`."""
    from opencae.meshing.elements import surface_integrals
    wN, _, _ = surface_integrals(nodes, faces)
    w = np.zeros(len(nodes))
    np.add.at(w, faces.ravel(), wN.ravel())
    idx = np.nonzero(w > 0)[0]
    wn = w[idx]
    c = (wn[:, None] * nodes[idx]).sum(axis=0) / wn.sum()
    nodal[idx] += (wn / wn.sum())[:, None] * F[None, :]
    M = np.cross(P - c, F) + (np.zeros(3) if M_extra is None else np.asarray(M_extra, float))
    if np.linalg.norm(M) > 0:
        r = nodes[idx] - c
        J = (wn[:, None, None] * (np.einsum("ij,ij->i", r, r)[:, None, None] * np.eye(3)[None]
                                   - r[:, :, None] * r[:, None, :])).sum(axis=0)
        a = np.linalg.lstsq(J, M, rcond=None)[0]
        nodal[idx] += wn[:, None] * np.cross(a, r)
    return idx


_MESH_CACHE: dict = {}


def _run_case_direct(job: dict, case: dict, log) -> dict:
    """Same physics with OpenCAE's material database, CalculiX deck writer, solver launcher and result reader;
    only the mesh comes straight from Gmsh instead of OpenCAE's CAD route."""
    from scipy.spatial import cKDTree
    from opencae.app.session import Session
    from opencae.boundary_conditions.resolve import ResolvedModel
    from opencae.meshing.elements import boundary_faces
    from opencae.meshing.mesh_data import FEMesh
    from opencae.postprocessing.results import equilibrium_check
    from opencae.solver.calculix.deck import write_deck
    from opencae.solver.calculix.runner import run_blocking
    from opencae.utilities.units import get_unit_system

    t0 = time.time()
    if not case["loads"]:
        return {"case": case["name"], "skipped": "no load reaches this part in this case"}
    s = Session()
    s.new(f"{job['name']} - {case['name']}", job.get("units", "mm-N-s"))
    mat, mat_from = _material(job)
    size, order = float(job["mesh"]["size_max"]), int(job["mesh"].get("order", 2))
    log(f"  {case['name']}: meshing the STL directly (size {size} mm)")
    key = (job["stl"], size, order, job.get("mesher"))
    if key not in _MESH_CACHE:  # one mesh serves every load case of the part
        if job.get("mesher") == "tetwild":
            _MESH_CACHE[key] = _tetwild_volume(job["stl"], size, order, "fTetWild requested")
        else:
            _MESH_CACHE[key] = _gmsh_volume(job["stl"], size, order)
    nodes, el, how, elem_size = _MESH_CACHE[key]
    etype = "C3D10" if order == 2 else "C3D4"
    mesh = FEMesh(nodes=nodes, elements=el, element_type=etype, body_id="part")
    _, _, bfaces = boundary_faces(el, etype)
    centres = nodes[bfaces[:, :3]].mean(axis=1)
    tol = float(job.get("select_tol_mm", 0.8))

    def faces_at(points):
        pts = np.asarray(points, float).reshape(-1, 3)
        d, _ = cKDTree(pts).query(centres)
        return np.nonzero(d <= tol)[0]

    rm = ResolvedModel()
    sel_info, sup_nodes = {}, set()
    for sup in job["supports"]:
        fi = faces_at(sup["points"])
        if not len(fi):
            raise ValueError(f"support {sup['name']}: no mesh faces at the interface")
        nset = np.unique(bfaces[fi].ravel())
        rm.spc_sets[sup["name"]] = nset
        for n in nset:
            rm.spc[int(n)] = {1: 0.0, 2: 0.0, 3: 0.0}
        sup_nodes.update(int(n) for n in nset)
        sel_info["support " + sup["name"]] = {"points": len(sup["points"]), "mesh_faces": int(len(fi))}
    nodal = np.zeros_like(nodes)
    applied = np.zeros(3)
    for ld in case["loads"]:
        F = np.asarray(ld["force"], float)
        Mx = np.asarray(ld.get("moment", [0, 0, 0]), float)
        if np.linalg.norm(F) < 1e-9 and np.linalg.norm(Mx) < 1e-9:
            continue
        fi_all = faces_at(ld["points"])
        fi = np.array([f for f in fi_all if not set(bfaces[f, :3].tolist()) <= sup_nodes], int)
        if not len(fi) and len(fi_all):
            sel_info["load " + ld["name"]] = {"note": "every face of this joint is also clamped: the load goes "
                                                      "straight into the support"}
            continue
        if not len(fi):
            raise ValueError(f"load {ld['name']}: no free mesh faces at the interface")
        _remote_force(nodes, bfaces[fi], F, np.asarray(ld["point"], float), nodal, Mx)
        applied += F
        sel_info["load " + ld["name"]] = {"points": len(ld["points"]), "mesh_faces": int(len(fi))}
    if not np.any(nodal):
        return {"case": case["name"], "skipped": "no load reaches this part in this case (or only clamped faces)",
                "selection": sel_info}
    rm.nodal_forces = nodal
    rm.applied_force_total = applied
    on_c = nodal[sorted(sup_nodes)].sum(axis=0) if sup_nodes else np.zeros(3)
    rm.applied_on_constrained = on_c
    us = get_unit_system(job.get("units", "mm-N-s"))
    s.project.mesh_settings.element_order = order
    work = Path(job.get("project_dir") or Path(job["out"]).parent) / f"direct-{case['name']}"
    work.mkdir(parents=True, exist_ok=True)
    (work / "job.inp").write_text(write_deck(s.project, mesh, rm, mat, us), encoding="utf-8")
    log(f"  {case['name']}: {len(nodes)} nodes, solving with CalculiX")
    out = run_blocking(s.backend.install, work, "job", 1)
    if not out.success:
        raise RuntimeError("CalculiX did not finish: " + _ccx_errors(out))
    rs = s.backend.read_results(work, "job", mesh)
    sm = rs.summary()
    sm.update({"applied_force_total": applied.tolist(), "applied_on_constrained": on_c.tolist()})
    eq = equilibrium_check(sm) or {}
    vm = np.asarray(rs.quantity("S_vm"), float)
    band = float(job.get("singularity_band_mm", 2.0))
    sup_pts = np.vstack([np.asarray(sp["points"], float).reshape(-1, 3) for sp in job["supports"]])
    dist, _ = cKDTree(sup_pts).query(nodes)
    away = dist > band
    j_away = int(np.argmax(np.where(away, vm, -1.0)))
    try:  # a file anyone can open in ParaView, with stress and displacement on the mesh
        import meshio
        meshio.write(str(work / "result.vtu"), meshio.Mesh(nodes, [("tetra10" if order == 2 else "tetra", el)],
                     point_data={"von_mises_MPa": vm, "displacement_mm": rs.displacement}))
    except Exception:  # noqa: BLE001
        pass
    return {
        "case": case["name"], "route": "direct-mesh", "mesh_note": how, "material_from": mat_from,
        "nodes": int(len(nodes)), "elements": int(len(el)), "mesh_size_max_mm": size, "element_order": order,
        "element_size_mm": elem_size,
        "max_von_mises_mpa": float(vm.max()), "max_von_mises_location": nodes[int(np.argmax(vm))].tolist(),
        "max_von_mises_away_mpa": float(vm[away].max()) if away.any() else float("nan"),
        "max_von_mises_away_location": nodes[j_away].tolist(), "singularity_band_mm": band,
        "max_displacement_mm": float(sm["max_displacement"]),
        "applied_force_n": applied.tolist(), "reaction_force_n": np.asarray(eq.get("reactions", [np.nan] * 3), float).tolist(),
        "load_on_clamped_faces_n": on_c.tolist(),
        "equilibrium_error": float(eq.get("relative", float("nan"))), "equilibrium_ok": bool(eq.get("ok", False)),
        "selection": sel_info, "wall_time_s": round(time.time() - t0, 1), "project": str(work),
    }


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    job = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    log = lambda m: print(m, flush=True)  # noqa: E731
    out = {"name": job["name"], "cases": [], "error": None}
    try:
        import opencae
        out["opencae_version"] = getattr(opencae, "__version__", "unknown")
        for case in job["cases"]:
            out["cases"].append(_run_case(job, case, log))
    except Exception as e:  # noqa: BLE001 - reported to the platform, which shows it
        out["error"] = f"{type(e).__name__}: {e}"
        out["traceback"] = traceback.format_exc(limit=6)
    Path(job["out"]).write_text(json.dumps(out, indent=2), encoding="utf-8")
    return 0 if not out["error"] else 1


if __name__ == "__main__":
    sys.exit(main())
