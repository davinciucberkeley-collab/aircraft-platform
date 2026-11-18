"""Structural check of one part in OpenCAE Studio (finite elements, CalculiX).

What it does, for a printed part P of a design:

1. Load path. Joints whose other side is nearer the design's root than P are its supports (clamped);
   every other joint of P carries a load into it.
2. Interfaces. The faces of P that touch each neighbour are found from the meshes (points on P's surface
   within a small gap of the neighbour), so supports and loads go where the parts really meet.
3. Load cases, each multiplied by structure.ultimate_factor:
   - landing: joint forces and moments from the tier-2 drop test (each joint at its largest force: an envelope),
   - thrust: hover at full thrust held at the root, joint forces and moments from a static solve.
4. OpenCAE meshes the part (10-node tetrahedra), solves with CalculiX and returns stresses, displacements
   and its equilibrium check (opencae_runner.py runs inside OpenCAE's own Python).
5. Verdict: the peak von Mises stress away from the clamps must stay at or below the material allowable
   in standards/design-standards.yaml. The peak including the clamp edges is reported too.

Results are written to designs/<id>/fea/<part>.json with a hash of what they depend on, so tier 2 can
report them (and say when they are out of date) without OpenCAE installed.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import trimesh

from .design import REPO_ROOT, STANDARDS_PATH, CheckResult, Design, load_standards
from .geometry import component_parts

STD = "design-standards.yaml#"
RUNNER = Path(__file__).with_name("opencae_runner.py")
CONFIG_FILE = REPO_ROOT / "opencae.local.json"
# platform manufacturing method -> OpenCAE material database id. Only sourced records are used.
MATERIALS = {"3d-print-fdm": ("db_petg_um", "fea_allowable_printed_petg_mpa", "fea_material_printed_petg")}
INTERFACE_GAP_MM = (0.5, 1.5)   # first try, then a wider gap for parts that sit slightly apart in CAD
FALLBACK_RADIUS_MM = 4.0


# ------------------------------------------------------------------ OpenCAE location
def find_opencae(python: str | None = None, root: str | None = None) -> dict:
    """OpenCAE's Python and source folder: arguments, then OPENCAE_PYTHON / OPENCAE_ROOT, then opencae.local.json,
    then a few usual places. Returns {python, root, found, how}."""
    cfg = {}
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
        except json.JSONDecodeError:
            cfg = {}
    py = python or os.environ.get("OPENCAE_PYTHON") or cfg.get("python")
    rt = root or os.environ.get("OPENCAE_ROOT") or cfg.get("root")
    how = "given" if (python or root) else "env" if os.environ.get("OPENCAE_PYTHON") else "opencae.local.json" if cfg else "auto"
    if not rt:
        for cand in sorted(REPO_ROOT.parent.glob("OpenCAE*")) + [REPO_ROOT.parent / "opencaemodel"]:
            if (cand / "opencae" / "app" / "session.py").is_file():
                rt = str(cand)
                break
    if not py:
        home = Path.home()
        exe = "python.exe" if os.name == "nt" else "bin/python"
        for env in ("qt_test", "opencae-gui", "opencae"):
            for base in (home / ".conda" / "envs", home / "miniforge3" / "envs", Path("C:/ProgramData/miniforge3/envs")):
                if (base / env / exe).is_file():
                    py = str(base / env / exe)
                    break
            if py:
                break
    found = bool(py and rt and Path(py).exists() and (Path(rt) / "opencae").is_dir())
    return {"python": py, "root": rt, "found": found, "how": how}


def save_config(python: str, root: str) -> Path:
    CONFIG_FILE.write_text(json.dumps({"python": python, "root": root}, indent=2) + "\n")
    return CONFIG_FILE


# ------------------------------------------------------------------ planning
# Component types that can hold a part up. Wiring, avionics, motors and the like carry load into a part but
# never support it, so they are left out when working out which joints lead toward the root.
STRUCTURAL = {"fuselage", "wing", "tail_surface", "boom", "structure", "landing_gear", "pod"}


def _graph(design: Design):
    """All joints per component, and each component's distance from the root through structural parts only."""
    adj: dict[str, list[dict]] = {}
    for a in design.data.get("attachments", []):
        adj.setdefault(a["parent"], []).append(a)
        adj.setdefault(a["child"], []).append(a)
    types = {c["id"]: c["type"] for c in design.components}
    root = design.data.get("root") or design.components[0]["id"]
    dist, frontier = {root: 0}, [root]
    while frontier:
        nxt = []
        for n in frontier:
            for a in adj.get(n, []):
                m = a["child"] if a["parent"] == n else a["parent"]
                if m not in dist and types.get(m) in STRUCTURAL:
                    dist[m] = dist[n] + 1
                    nxt.append(m)
        frontier = nxt
    return adj, dist


def _solid(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, list[float]]:
    """The part's main solid. Pieces under 2 % of its volume (slivers, separate small bosses) are left out and
    reported; a part made of several large separate pieces is refused rather than half-analysed."""
    pieces = sorted(mesh.split(only_watertight=False), key=lambda p: -abs(p.volume))
    if len(pieces) <= 1:
        return mesh, []
    main = pieces[0]
    big = [p for p in pieces[1:] if abs(p.volume) > 0.02 * abs(main.volume)]
    if big:
        raise ValueError(f"made of {len(pieces)} separate solids ({', '.join(f'{abs(p.volume):.0f}' for p in [main] + big)}"
                         " mm3); analyse them as separate components")
    return main, [round(abs(p.volume), 1) for p in pieces[1:]]


def _mesh(design: Design, cid: str) -> trimesh.Trimesh | None:
    c = design.component(cid)
    parts = component_parts(c, design.base_dir)
    if not parts:
        return None
    return trimesh.util.concatenate(parts) if len(parts) > 1 else parts[0]


def _interface(samples: np.ndarray, other: trimesh.Trimesh | None, joint_location) -> tuple[np.ndarray, str]:
    if other is not None:
        _, d, _ = trimesh.proximity.closest_point(other, samples)
        for gap in INTERFACE_GAP_MM:
            pts = samples[d <= gap]
            if len(pts) >= 6:
                return pts, f"contact within {gap} mm"
    if joint_location is not None:
        pts = samples[np.linalg.norm(samples - np.asarray(joint_location, float), axis=1) <= FALLBACK_RADIUS_MM]
        if len(pts) >= 6:
            return pts, f"no contact found; surface within {FALLBACK_RADIUS_MM} mm of the joint location"
    return np.zeros((0, 3)), "no interface found"


def _wall_thickness(mesh: trimesh.Trimesh, n: int = 3000) -> dict:
    """Wall thickness from rays cast inward from points on the surface: 5th percentile and median, mm."""
    pts, fi = trimesh.sample.sample_surface_even(mesh, n, seed=3)
    nrm = mesh.face_normals[fi]
    origins = pts - nrm * 1e-3
    locs, ri, _ = mesh.ray.intersects_location(origins, -nrm, multiple_hits=False)
    t = np.linalg.norm(locs - origins[ri], axis=1) if len(ri) else np.array([1.0])
    return {"p5": round(float(np.percentile(t, 5)), 2), "median": round(float(np.median(t)), 2)}


def part_hash(design: Design, part_id: str) -> str:
    """Everything the result depends on: the design file, the part's files, the standards and the runner."""
    h = hashlib.sha256()
    h.update((design.base_dir / "plane.yaml").read_bytes())
    for f in sorted((design.base_dir / "meshes").glob("*")) if (design.base_dir / "meshes").is_dir() else []:
        if f.stem == part_id:
            h.update(f.read_bytes())
    h.update(STANDARDS_PATH.read_bytes())
    h.update(RUNNER.read_bytes())
    return h.hexdigest()[:16]


def eligible_parts(design: Design) -> list[str]:
    out = []
    for c in design.components:
        m = (c.get("manufacturing") or {}).get("method")
        if m in MATERIALS and c["type"] in STRUCTURAL and c.get("geometry") and not c["geometry"].get("point_mass"):
            out.append(c["id"])
    return out


def plan(design: Design, part_id: str, drop: dict | None = None) -> dict:
    """The job for opencae_runner plus what it means (supports, loads and where they came from)."""
    std = load_standards()
    comp = design.component(part_id)
    method = (comp.get("manufacturing") or {}).get("method")
    if method not in MATERIALS:
        raise ValueError(f"{part_id}: no sourced material for manufacturing method {method!r} yet "
                         f"(supported: {', '.join(MATERIALS)})")
    material_id, allow_key, mat_key = MATERIALS[method]
    s_cfg = std["structure"]
    ult = float(s_cfg["ultimate_factor"]["value"])
    adj, dist = _graph(design)
    if part_id not in dist:
        raise ValueError(f"{part_id} is not connected to the root {design.data.get('root')!r}")
    joints = adj.get(part_id, [])
    if not joints:
        raise ValueError(f"{part_id} has no joints")
    mesh = _mesh(design, part_id)
    if mesh is None:
        raise ValueError(f"{part_id} has no geometry")
    try:
        mesh, dropped = _solid(mesh)
    except ValueError as e:
        raise ValueError(f"{part_id}: {e}") from e
    n = int(np.clip(mesh.area / 0.25, 3000, 30000))  # about one sample per 0.5 x 0.5 mm
    samples, _ = trimesh.sample.sample_surface_even(mesh, n, seed=7)

    others: dict[str, trimesh.Trimesh | None] = {}
    supports, load_joints, notes = [], [], []
    if dropped:
        notes.append(f"left out {len(dropped)} small separate piece(s) of the part ({', '.join(map(str, dropped))} mm3)")
    for a in joints:
        other = a["child"] if a["parent"] == part_id else a["parent"]
        if other not in others:
            others[other] = _mesh(design, other)
        pts, how = _interface(samples, others[other], a.get("location"))
        entry = {"joint": a.get("id"), "other": other, "method": a.get("method"), "location": a.get("location"),
                 "points": pts, "how": how, "part_is_parent": a["parent"] == part_id}
        if not len(pts):
            notes.append(f"{a.get('id')} ({other}): {how}; left out")
            continue
        (supports if dist.get(other, 1e9) < dist[part_id] else load_joints).append(entry)
    if not supports:
        raise ValueError(f"{part_id}: no structural joint leads toward the root, so there is nothing to hold it")

    if drop is None:
        drop = joint_loads(design)
    cases = []
    about = {"landing": "tier-2 drop test, each joint at the instant of its largest force (an envelope), "
                        f"force and moment, x {ult} ultimate factor",
             "thrust": "hover at full thrust held at the root: every motor at max_thrust_n plus gravity, joint "
                       f"forces and moments from a static solve, x {ult} ultimate factor"}
    for name in ("landing", "thrust"):
        loads = []
        for e in load_joints:
            jl = drop.get(name, {}).get(e["joint"])
            if not jl:
                notes.append(f"{name}: no joint load for {e['joint']}")
                continue
            F, T = np.asarray(jl["force_n"], float), np.asarray(jl["torque_nm"], float)
            if not e["part_is_parent"]:  # the joint data is the load on the parent; the child feels the opposite
                F, T = -F, -T
            if np.linalg.norm(F) < 1e-6 and np.linalg.norm(T) < 1e-9:
                continue
            loads.append({"name": f"{e['joint']} from {e['other']}", "points": e["points"].tolist(),
                          "force": (F * ult).tolist(), "moment": (T * 1000 * ult).tolist(),  # N m -> N mm
                          "point": jl["at_mm"]})
        cases.append({"name": name, "about": about[name], "loads": loads})

    t_char = float(2 * mesh.volume / max(mesh.area, 1e-9))  # about half the wall thickness for thin walls
    walls = _wall_thickness(mesh)
    size = float(np.clip(min(1.5 * t_char, walls["median"]), 0.5, 4.0))
    job = {
        "name": f"{design.id}-{part_id}", "units": "mm-N-s", "material_id": material_id,
        "material": dict(std["structure"][mat_key]["value"], source=std["structure"][mat_key]["source"]),
        "description": f"{design.id} / {part_id}: {comp.get('description', '')}. Generated by plane fea.",
        "mesh": {"size_max": round(size, 2), "order": 2},
        "select_tol_mm": 0.8, "singularity_band_mm": float(s_cfg["fea_singularity_band_mm"]["value"]),
        "supports": [{"name": f"{e['joint']} to {e['other']}", "points": e["points"].tolist()} for e in supports],
        "cases": [{"name": c["name"], "loads": c["loads"]} for c in cases],
    }
    meta = {
        "part": part_id, "material_id": material_id, "allowable_key": allow_key,
        "allowable_mpa": float(s_cfg[allow_key]["value"]), "ultimate_factor": ult,
        "wall_mm": walls, "part_size_mm": round(float(np.linalg.norm(mesh.extents)), 2),
        "supports": [{k: e[k] for k in ("joint", "other", "how")} for e in supports],
        "load_joints": [{k: e[k] for k in ("joint", "other", "how")} for e in load_joints],
        "cases": [{"name": c["name"], "about": c["about"],
                   "loads": [{"name": x["name"], "force_n": [round(v, 3) for v in x["force"]],
                              "moment_nmm": [round(v, 2) for v in x["moment"]], "at_mm": x["point"]}
                             for x in c["loads"]]} for c in cases],
        "notes": notes,
    }
    return {"job": job, "meta": meta, "mesh": mesh}


def joint_loads(design: Design) -> dict:
    """Joint forces and moments per load case (sim.joint_load_cases): {case: {attachment id: {...}}}."""
    from .sim import joint_load_cases
    return joint_load_cases(design)



# ------------------------------------------------------------------ running
def result_path(design: Design, part_id: str) -> Path:
    return design.base_dir / "fea" / f"{part_id}.json"


def run(design: Design, part_id: str, opencae: dict | None = None, keep_project: bool = True,
        log=print, drop: dict | None = None) -> dict:
    """Plan, run OpenCAE, judge, and write designs/<id>/fea/<part>.json. Returns that record."""
    oc = opencae or find_opencae()
    if not oc["found"]:
        raise RuntimeError("OpenCAE not found. Set it once with: plane fea --setup --opencae-python <python of the "
                           "environment with OpenCAE's libraries> --opencae-root <OpenCAE folder>")
    p = plan(design, part_id, drop=drop)
    job, meta = p["job"], p["meta"]
    work = Path(tempfile.mkdtemp(prefix=f"fea-{part_id}-"))
    try:
        p["mesh"].export(work / "part.stl")
        job["stl"] = str(work / "part.stl")
        job["out"] = str(work / "result.json")
        proj_dir = REPO_ROOT / ".studio" / "fea" / design.id / part_id
        if keep_project:
            shutil.rmtree(proj_dir, ignore_errors=True)
            job["project_dir"] = str(proj_dir)
        (work / "job.json").write_text(json.dumps(job))
        env = dict(os.environ, PYTHONPATH=str(oc["root"]) + os.pathsep + os.environ.get("PYTHONPATH", ""),
                   PYTHONIOENCODING="utf-8")
        log(f"{part_id}: {len(job['supports'])} support(s), {sum(len(c['loads']) for c in job['cases'])} load(s); "
            f"running OpenCAE")
        proc = subprocess.run([oc["python"], str(RUNNER), str(work / "job.json")], cwd=str(work), env=env,
                              capture_output=True, text=True, timeout=3600)
        for line in proc.stdout.splitlines():
            log(line)
        if not (work / "result.json").exists():
            raise RuntimeError("OpenCAE run failed:\n" + (proc.stderr or proc.stdout)[-3000:])
        res = json.loads((work / "result.json").read_text())
    finally:
        shutil.rmtree(work, ignore_errors=True)
    for c in res.get("cases", []):  # keep stored records free of machine-specific paths
        for k in ("project", "report"):
            if c.get(k):
                try:
                    c[k] = Path(c[k]).resolve().relative_to(REPO_ROOT.resolve()).as_posix()
                except ValueError:
                    c[k] = Path(c[k]).name
    record = judge(meta, res)
    record.update({"design": design.id, "hash": part_hash(design, part_id),
                   "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "opencae_version": res.get("opencae_version")})
    out = result_path(design, part_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n")
    return record


def judge(meta: dict, res: dict) -> dict:
    allow = meta["allowable_mpa"]
    rec = dict(meta, error=res.get("error"), cases=[], load_cases=meta.get("cases", []))
    worst = None
    wall = (meta.get("wall_mm") or {}).get("median")
    size = meta.get("part_size_mm")
    for c in res.get("cases", []):
        if c.get("skipped"):
            rec["cases"].append({"name": c["case"], "status": "SKIP", "message": c["skipped"]})
            continue
        # is the model good enough to trust? Elements much thicker than the walls make thin parts far too soft,
        # and a part that moves a lot under load isn't being held by its supports.
        elem = float(c.get("element_size_mm") or c.get("mesh_size_max_mm") or 0)
        why = None
        if wall and elem > 2 * wall:
            why = (f"not checked: the mesh ({elem:.1f} mm elements, {c.get('route', '')}) is too coarse for its "
                   f"{wall:.1f} mm walls; needs a finer mesh or exact CAD (STEP)")
        elif size and c["max_displacement_mm"] > 0.02 * size:
            why = (f"not checked: the part moves {c['max_displacement_mm']:.2f} mm under load (over 2 % of its "
                   f"{size:.0f} mm size), so the model isn't held properly")
        if why:
            rec["cases"].append({"name": c["case"], "status": "SKIP", "message": why, "not_checked": True,
                                 "max_von_mises_mpa": round(c["max_von_mises_mpa"], 3),
                                 "max_displacement_mm": round(c["max_displacement_mm"], 4), "project": c.get("project")})
            continue
        s_away, s_all = c["max_von_mises_away_mpa"], c["max_von_mises_mpa"]
        status = "PASS" if s_away <= allow else "FAIL"
        if status == "PASS" and s_all > allow:
            status = "WARN"  # only the clamp-edge singularity exceeds the allowable
        if not c.get("equilibrium_ok", False):
            status = "FAIL"
        sf = min(allow / s_away, 999.0) if s_away > 0 else 999.0  # 999 = "far more than enough"
        on_clamp = float(np.linalg.norm(c.get("load_on_clamped_faces_n", [0, 0, 0])))
        app = float(np.linalg.norm(c.get("applied_force_n", [0, 0, 0])))
        case = {"name": c["case"], "status": status, "max_von_mises_away_mpa": round(s_away, 3),
                "max_von_mises_mpa": round(s_all, 3), "safety_factor_at_ultimate": round(sf, 2),
                "max_displacement_mm": round(c["max_displacement_mm"], 4), "nodes": c["nodes"],
                "mesh_size_max_mm": c["mesh_size_max_mm"], "equilibrium_ok": c.get("equilibrium_ok"),
                "load_share_on_clamped_faces": round(on_clamp / app, 3) if app else 0.0,
                "location_mm": [round(v, 2) for v in c["max_von_mises_away_location"]],
                "project": c.get("project"), "report": c.get("report"), "route": c.get("route"),
                "material_from": c.get("material_from")}
        rec["cases"].append(case)
        if worst is None or s_away > worst["max_von_mises_away_mpa"]:
            worst = case
    order = {"FAIL": 0, "WARN": 1, "SKIP_NC": 2, "PASS": 3, "SKIP": 4}
    keyed = ["SKIP_NC" if c.get("not_checked") else c["status"] for c in rec["cases"]]
    worst_s = min(keyed, key=lambda s: order[s], default="SKIP")
    rec["status"] = "FAIL" if rec["error"] else ("NOT CHECKED" if worst_s == "SKIP_NC" else worst_s)
    rec["worst_case"] = worst["name"] if worst else None
    return rec


# ------------------------------------------------------------------ scorecard
def tier2_fea(design: Design) -> list[CheckResult]:
    """Report stored OpenCAE results (never runs OpenCAE): one row per checked part, one summary row for the rest."""
    parts = eligible_parts(design)
    if not parts:
        return []
    out, missing, stale = [], [], []
    for pid in parts:
        f = result_path(design, pid)
        if not f.exists():
            missing.append(pid)
            continue
        try:
            rec = json.loads(f.read_text())
        except json.JSONDecodeError:
            missing.append(pid)
            continue
        if rec.get("hash") != part_hash(design, pid):
            stale.append(pid)
            continue
        crit = STD + rec.get("allowable_key", "fea_allowable_printed_petg_mpa")
        if rec.get("error"):
            out.append(CheckResult("T2.fea_strength", "FAIL", f"{pid}: OpenCAE run failed: {rec['error']}", crit,
                                   {"component": pid}))
            continue
        for c in rec["cases"]:
            if c["status"] == "SKIP":
                if c.get("not_checked"):
                    out.append(CheckResult("T2.fea_strength", "SKIP", f"{pid} {c['name']}: {c['message']}", crit,
                                           {"component": pid}))
                continue
            msg = (f"{pid} {c['name']}: {c['max_von_mises_away_mpa']:.2f} MPa peak away from the clamps vs "
                   f"{rec['allowable_mpa']} MPa allowable at {rec['ultimate_factor']}x load "
                   f"(SF {c['safety_factor_at_ultimate']}; {c['max_von_mises_mpa']:.2f} MPa at the clamp edges)")
            if not c.get("equilibrium_ok"):
                msg += "; equilibrium check failed"
            out.append(CheckResult("T2.fea_strength", c["status"], msg, crit,
                                   {k: c[k] for k in ("max_von_mises_away_mpa", "safety_factor_at_ultimate",
                                                      "max_displacement_mm")} | {"component": pid}))
    if stale:
        out.append(CheckResult("T2.fea_strength", "SKIP", f"stress results out of date for {len(stale)} part(s) "
                               f"({', '.join(stale[:6])}{'…' if len(stale) > 6 else ''}): re-run plane fea",
                               STD + "fea_allowable_printed_petg_mpa", {"parts": stale}))
    if missing:
        out.append(CheckResult("T2.fea_strength", "SKIP", f"{len(missing)} printed part(s) have no OpenCAE stress "
                               f"check yet (plane fea {design.base_dir.name} --all)",
                               STD + "fea_allowable_printed_petg_mpa", {"parts": missing}))
    return out
