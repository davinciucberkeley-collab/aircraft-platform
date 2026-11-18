"""Import a DBF-Combined concept (read only) as a platform design: `plane import dbf --dbf-root PATH`.

Pipeline (see designs/concept-a/README.md for the provenance of every choice):
  1. run the team's own headless CAD build in a subprocess (`python3 -I -B _dbf_dump.py`), dump bodies, PARTS, EDGES,
     joints as JSON; nothing is written inside the source tree
  2. rebuild each part's solid from its prism / revolve / loft bodies (dbf_geometry.py) and write one STL per part;
     fallback to the published GLB mesh for a part that cannot be rebuilt (none needed for concept A)
  3. map parts to components, edges to attachments (rating sources in dbf_ratings.py), write plane.yaml with a source
     comment on every number, and import-report.json with the conversion statistics
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

import numpy as np
import trimesh

from ..design import REPO_ROOT, load_standards
from . import dbf_geometry as geo
from . import dbf_ratings as rt

DEFAULT_OUT = REPO_ROOT / "designs" / "concept-a"
# Children moved by a linkage the schema does not model (servo pushrods, elevon damper stators). The source's pose
# check leaves them out: "Not checked against the moved parts (linkage path not modelled)" in
# redesign/qp/A/cad/out/REPORT.md. Their attachments get kinematic_link: true (schema 0.4).
KINEMATIC_LINK_CHILDS = {"MEC-003-L", "MEC-003-R", "WNG-009-L", "WNG-009-R"}
G = 9.80665

# ----------------------------------------------------------------------------- semantic tables
SERVO_PREFIX = ("MEC-001",)


def part_type(pid: str, name: str) -> str:
    """Schema component type from the source part id (subsystem prefix) and name."""
    p = pid
    if p == "WNG-001":
        return "wing"
    if p.startswith("WNG-006") or p.startswith(("FIN-004", "FIN-006")):
        return "tail_surface"          # elevons; fin fairings (the aerodynamic skin of the fins)
    if p.startswith("PRP-001"):
        return "motor"
    if p.startswith("PRP-002"):
        return "propeller"
    if p == "PRP-003":
        return "esc"
    if p == "AVN-002":
        return "flight_controller"
    if p == "AVN-003":
        return "receiver"
    if p == "PWR-001":
        return "battery"
    if p.startswith("MEC-001"):
        return "servo"
    if p.startswith("GER-"):
        return "landing_gear"
    if p.startswith("CGE-002") or p == "CGE-004":
        return "boom"                  # carbon motor arms and the bridge tube
    if p.startswith(("WNG-002", "WNG-003", "WNG-004", "WNG-005", "WNG-007", "WNG-008", "CGE-001", "CGE-003", "CGE-005",
                     "CGE-006", "CGE-007", "CGE-008", "FIN-001", "FIN-002", "FIN-003", "FIN-005", "AVN-001", "AVN-008")):
        return "structure"
    return "other"                     # sensors, hardware, linkage, harness, dampers, pads, mass proxies


def manufacturing_for(pid: str, part: dict, row: dict | None, proxy: bool) -> tuple[dict, str]:
    """(manufacturing block, why). Machine ids exist in standards/manufacturing.yaml."""
    material = part.get("material") or ""
    text = (row or {}).get("vendor_or_file", "")
    boms = re.findall(r"BOM ([A-Z]\d{2})", text)
    if pid == "HRD-001":
        return {"method": "purchased", "part_number": "BOM R05, R07"}, "fasteners, epoxy, CA bought (parts-a.csv: BOM R05, R07)"
    if pid == "HRN-001":
        return {"method": "hand-cut"}, ("wire, heat-shrink and ties cut and made up by hand (parts-a.csv: Made from BOM W07, W05); "
                                         "the schema has no 'hand-assembled' method")
    if part.get("make_or_buy") == "buy":
        mf = {"method": "purchased"}
        if boms:
            mf["part_number"] = "BOM " + ", ".join(dict.fromkeys(boms))
        return mf, "make_or_buy 'buy' (PARTS) -> purchased; BOM id from parts-a.csv"
    if pid.startswith("WNG-007"):
        return {"method": "hand-cut"}, "lead strip cut by hand (parts-a.csv: Made (lead strip) from BOM R11)"
    if "XPS" in material:
        return {"method": "hotwire-foam"}, "XPS core hot-wired (parts-a.csv: Made (hot-wired XPS, tape skin))"
    if "PETG" in material:
        return {"method": "3d-print-fdm", "machine": "jacobs-fdm"}, "printed PETG (parts-a.csv: Made (printed PETG), BOM R03 Prusa)"
    if "CFRP" in material or "brass" in material:
        return {"method": "hand-cut"}, "cut from the tube stock (parts-a.csv: Made (cut from the ... tube))"
    if "EVA" in material:
        return {"method": "hand-cut"}, ("foam foot pad cut by hand; parts-a.csv says only 'Made (foot pads (BOM R03 line text))', "
                                        "and a foam pad cannot be FDM-printed")
    return {"method": "hand-cut"}, "no rule matched: hand-cut (placeholder)"


CONN_METHOD = {
    "CT-EPOXY": ("glued", ""), "CT-CA": ("glued", ""),
    "CT-TAPE-FOAM": ("tape", ""), "CT-GEL-PAD": ("tape", "adhesive vibration-isolation pad: nearest enum is tape"),
    "CT-HW-SEATED": ("bolted", ""), "CT-A-PROP-NUT": ("bolted", ""), "CT-A-M25-SHCS-MOTOR": ("bolted", ""),
    "CT-A-PROP-ADAPTER": ("bolted", ""), "CT-CLEVIS": ("hinge", ""), "CT-TAPE-HINGE": ("hinge", ""),
    "CT-STRAP-VELCRO": ("clamp", "hook-and-loop strap round the pack: nearest enum is clamp"),
    "CT-TIE": ("zip-tie", ""),
    "CT-SERVO-SPLINE": ("bolted", "arm on a spline held by an M2 retaining screw: nearest enum is bolted"),
}


def _axis_vec(ax) -> np.ndarray:
    if isinstance(ax, str):
        return np.array({"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}[ax.upper()], dtype=float)
    return np.array(ax, dtype=float)


# ----------------------------------------------------------------------------- source access
def _run_dump(root: Path, concept: str) -> dict:
    script = Path(__file__).with_name("_dbf_dump.py")
    with tempfile.TemporaryDirectory(prefix="dbf-dump-") as tmp:
        out = Path(tmp) / "dump.json"
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        p = subprocess.run([sys.executable, "-I", "-B", str(script), str(root), concept, str(out)],
                           capture_output=True, text=True, cwd=tmp, env=env)
        if p.returncode != 0 or not out.exists():
            raise RuntimeError(f"headless CAD build failed ({p.returncode}):\n{p.stdout[-800:]}\n{p.stderr[-1500:]}")
        return json.loads(out.read_text(encoding="utf-8"))


def _read_csv(path: Path, key: str) -> dict[str, dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return {r[key]: r for r in csv.DictReader(f)}


def _canonical(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Same solid, canonical vertex and face order (the boolean kernel's output order is not guaranteed stable)."""
    v = np.round(mesh.vertices.astype(np.float32).astype(np.float64), 6)
    order = np.lexsort(v.T[::-1])
    inv = np.empty_like(order)
    inv[order] = np.arange(len(order))
    f = inv[mesh.faces]
    f = np.array([np.roll(r, -int(np.argmin(r))) for r in f])
    f = f[np.lexsort(f.T[::-1])]
    return trimesh.Trimesh(v[order], f, process=False)


def _write_stl(mesh: trimesh.Trimesh, path: Path):
    m = _canonical(mesh)
    tri = m.vertices[m.faces].astype("<f4")
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = (nrm / np.where(ln > 0, ln, 1)).astype("<f4")
    rec = np.zeros(len(tri), dtype=[("n", "<f4", 3), ("t", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["t"] = nrm, tri
    with open(path, "wb") as f:
        f.write(b"aircraft-platform dbf import".ljust(80, b" "))
        f.write(np.uint32(len(tri)).tobytes())
        f.write(rec.tobytes())


def _glb_fallback(pid: str, glb: Path) -> trimesh.Trimesh:
    """The part's mesh from the published GLB (node name = part id), metres, glTF y-up -> mm, z-up, repaired.
    Unused for concept A (all 104 parts rebuild exactly); kept because the plan requires the fallback."""
    scene = trimesh.load(str(glb))
    if pid not in scene.graph.nodes_geometry:
        raise geo.GeometryError(f"{pid}: no node in {glb.name}")
    T, name = scene.graph[pid]
    m = scene.geometry[name].copy()
    m.apply_transform(T)
    m.vertices = (m.vertices @ np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=float).T) * 1000.0  # (x,y,z)gl -> (x,-z,y)
    m.merge_vertices()
    trimesh.repair.fill_holes(m)
    trimesh.repair.fix_normals(m)
    if not (m.is_watertight and m.volume > 0):
        raise geo.GeometryError(f"{pid}: GLB mesh cannot be repaired to a watertight solid")
    return m


# ----------------------------------------------------------------------------- geometry helpers on meshes
def _closest(mesh: trimesh.Trimesh, pts: np.ndarray, chunk: int = 1000):
    """trimesh closest_point in chunks (one call on thousands of points against a large mesh exhausts memory)."""
    cs, ds = [], []
    for i in range(0, len(pts), chunk):
        c, d, _ = trimesh.proximity.closest_point(mesh, pts[i:i + chunk])
        cs.append(c)
        ds.append(d)
    return np.vstack(cs), np.concatenate(ds)


def _contact_point(ma: trimesh.Trimesh, mb: trimesh.Trimesh, n: int = 2500) -> np.ndarray:
    """Midpoint of the closest points of two meshes (sampled both ways). Where many pairs touch, the contact
    sample nearest the mean of the contact midpoints, so the point lies ON a surface, not in a hollow."""
    pa = trimesh.sample.sample_surface(ma, n, seed=1)[0]
    pb = trimesh.sample.sample_surface(mb, n, seed=2)[0]
    ca, da = _closest(mb, pa)
    cb, db = _closest(ma, pb)
    pts = np.vstack([pa, pb])
    cl = np.vstack([ca, cb])
    d = np.concatenate([da, db])
    mid = (pts + cl) / 2
    sel = np.nonzero(d <= d.min() + 0.05)[0]
    centre = mid[sel].mean(axis=0)
    best = sel[int(np.argmin(np.linalg.norm(mid[sel] - centre, axis=1)))]
    return mid[best]


def _contact_area(ma: trimesh.Trimesh, mb: trimesh.Trimesh, eps: float = 0.1) -> float:
    """Bonded area estimate (mm2): area of each mesh's surface lying within (gap + eps) of the other (20000 area-weighted samples), The source models its glue lines with a clearance (0.02-0.5 mm between bonded parts), so the area is
    taken at the measured minimum gap plus eps = 0.1 mm, not at zero distance."""
    x, y = (ma, mb) if ma.area <= mb.area else (mb, ma)       # sample the smaller part: the bond cannot exceed its area
    pts = trimesh.sample.sample_surface(x, 20000, seed=11)[0]
    d = _closest(y, pts)[1]
    return float(x.area) * float((d <= d.min() + eps).mean())   # sampled area fraction, fixed seed


# ----------------------------------------------------------------------------- number formatting
def _n(x: float, nd: int = 4) -> str:
    r = round(float(x), nd)
    if r == 0:
        r = 0.0
    s = f"{r:.{nd}f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _vec(v, nd: int = 4) -> str:
    return "[" + ", ".join(_n(x, nd) for x in v) + "]"


def _s(x: str) -> str:
    return json.dumps(x, ensure_ascii=False)


# ----------------------------------------------------------------------------- main
def import_concept(dbf_root, concept: str = "A", out_dir=None, log=print) -> Path:
    """Regenerate out_dir (default designs/concept-a): plane.yaml, meshes/<id>.stl, import-report.json."""
    root = Path(dbf_root).resolve()
    out = Path(out_dir) if out_dir else DEFAULT_OUT
    qp = root / "redesign" / "qp" / concept
    if not (qp / "cad").is_dir():
        raise FileNotFoundError(f"{qp / 'cad'} not found: not a DBF-Combined checkout with concept {concept}")
    data = _run_dump(root, concept)
    parts_csv = _read_csv(qp / "cad" / "out" / "parts-a.csv", "part_id")
    params = json.loads((qp / f"params-{concept}.json").read_text(encoding="utf-8"))
    std = load_standards()
    glb = root / "redesign" / "site" / "assets" / f"concept-{concept.lower()}.glb"
    mesh_dir = out / "meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    PARTS = data["parts"]
    comps = {c["id"]: c for c in data["comps"]}
    proxies = data["proxies"]
    wire_edges = {w["id"] for w in data["wires"]}

    # ---- geometry
    meshes: dict[str, trimesh.Trimesh] = {}
    report: dict = {"commit": data["commit"], "parts": {}, "fallback": [], "proxies": sorted(proxies)}
    for pid in sorted(comps):
        c = comps[pid]
        how = "rebuilt"
        try:
            m, info = geo.part_mesh(c)
        except geo.GeometryError as e:
            log(f"  {pid}: rebuild failed ({e}); GLB fallback")
            m, info, how = _glb_fallback(pid, glb), {"bodies": 0, "body_volume_ratio": [], "n_cuts": 0}, "glb-fallback"
            report["fallback"].append(pid)
        path = mesh_dir / f"{pid.lower()}.stl"
        _write_stl(m, path)
        back = trimesh.load(path, force="mesh")
        if not (back.is_watertight and back.is_volume and back.volume > 0):
            if how == "rebuilt":  # STL float32 round trip broke it: try the fallback once
                m, how = _glb_fallback(pid, glb), "glb-fallback"
                report["fallback"].append(pid)
                _write_stl(m, path)
                back = trimesh.load(path, force="mesh")
            if not (back.is_watertight and back.volume > 0):
                raise geo.GeometryError(f"{pid}: not watertight after the STL round trip")
        meshes[pid] = back
        r = info["body_volume_ratio"]
        report["parts"][pid] = {"how": how, "bodies": info["bodies"], "cuts": info["n_cuts"], "triangles": int(len(back.faces)),
                                "volume_mm3": round(float(back.volume), 1),
                                "mesh_to_source_volume_min": round(min(r), 4) if r else None,
                                "mesh_to_source_volume_max": round(max(r), 4) if r else None}
    keep = {f"{p.lower()}.stl" for p in comps}
    for old in mesh_dir.glob("*.stl"):
        if old.name not in keep:
            old.unlink()

    # ---- components
    ids = sorted(set(comps) | set(proxies))
    root_id = "WNG-001"
    cg = {}  # centroid of each rebuilt part, for cg_offset
    for pid, m in meshes.items():
        cg[pid] = np.asarray(m.center_mass)

    # ---- attachments: structural edges only, direction from a BFS out of the root
    elevon = {j["edge"]: j for j in data["joints"] if j["kind"] == "revolute" and j["limits"]}
    groups = {g["edge"]: set(g["group"]) for g in data["moving_groups"]}
    edges = [e for e in data["edges"] if e["id"] not in wire_edges]
    moved_all = set().union(*groups.values()) if groups else set()
    bridging, kept = [], []
    for e in edges:
        a, b = e["part_a"], e["part_b"]
        art = e["id"] in elevon
        cross = [(g, (a in grp) != (b in grp)) for g, grp in groups.items()]
        if not art and any(x for _, x in cross):
            bridging.append(e)
        else:
            kept.append(e)
    adj: dict[str, set[str]] = {}
    for e in kept:
        adj.setdefault(e["part_a"], set()).add(e["part_b"])
        adj.setdefault(e["part_b"], set()).add(e["part_a"])
    depth = {root_id: 0}
    q = deque([root_id])
    while q:
        n = q.popleft()
        for m in sorted(adj.get(n, ())):
            if m not in depth:
                depth[m] = depth[n] + 1
                q.append(m)
    unreached = sorted(set(ids) - set(depth))
    if unreached:
        raise RuntimeError(f"parts not reachable from {root_id} without wires and bridging edges: {unreached}")

    atts = []
    for e in kept:
        a, b = e["part_a"], e["part_b"]
        parent, child = (a, b) if depth[a] <= depth[b] else (b, a)   # tie: part_a is the parent
        if e["id"] in elevon:                                        # the hinge: core is the parent
            core = elevon[e["id"]]["b"]
            parent, child = core, elevon[e["id"]]["a"]
        atts.append((e, parent, child))
    # the elevon downstream set must equal the source's moving group
    adjd: dict[str, set[str]] = {}
    for e, p, c in atts:
        adjd.setdefault(p, set()).add(c)
        adjd.setdefault(c, set()).add(p)
    for eid, j in elevon.items():
        seen, st = {j["a"]}, [j["a"]]
        while st:
            n = st.pop()
            for m in adjd.get(n, ()):
                if m in seen or (n == j["a"] and m == j["b"]):
                    continue
                seen.add(m)
                st.append(m)
        if seen != groups[eid]:
            raise RuntimeError(f"{eid}: downstream set {sorted(seen)} differs from the source moving group {sorted(groups[eid])}")

    # location, overlap, embed_ok, area
    att_rows = []
    overlap_fn = _overlap_volume_fn()
    for e, parent, child in atts:
        pm, cm = meshes.get(parent), meshes.get(child)
        row = {"edge": e, "parent": parent, "child": child}
        if pm is None or cm is None:
            solid = pm if pm is not None else cm
            pt_id = parent if pm is None else child
            pos = proxies[pt_id]["cg_declared"]
            row.update(location=[x * 1000.0 for x in pos], embed=False, overlap_frac=None, area=None, point_mass=True)
        else:
            loc = _contact_point(pm, cm)
            ov = overlap_fn(pm, cm)
            smaller = min(pm.volume, cm.volume)
            frac = ov / smaller if smaller else 0.0
            area = _contact_area(pm, cm) if e["via"] in ("CT-EPOXY", "CT-CA", "CT-HW-SEATED", "CT-A-PROP-ADAPTER", "CT-SERVO-SPLINE") else None
            row.update(location=[float(x) for x in loc], embed=bool(frac > std["geometry"]["glued_overlap_max_fraction"]["value"]),
                       overlap_frac=frac, overlap_mm3=ov, area=area, point_mass=False)
        att_rows.append(row)

    # ---- plane.yaml
    text, rating_rows = _write_yaml(data, PARTS, ids, comps, proxies, meshes, cg, parts_csv, params, att_rows, elevon, groups, bridging,
                                    std, out)
    (out / "plane.yaml").write_text(text, encoding="utf-8")
    report["attachments"] = len(att_rows)
    report["bridging_edges_not_emitted"] = [e["id"] for e in bridging]
    report["wire_edges_not_emitted"] = sorted(wire_edges)
    report["ratings"] = rating_rows
    report["embed_ok"] = sorted(r["edge"]["id"] for r in att_rows if r["embed"])
    (out / "import-report.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return out / "plane.yaml"


def _overlap_volume_fn():
    from ..checks import _overlap_volume
    return lambda a, b: _overlap_volume([a], [b])


# ----------------------------------------------------------------------------- yaml
def _write_yaml(data, PARTS, ids, comps, proxies, meshes, cg, parts_csv, params, att_rows, elevon, groups, bridging, std, out):
    from ..checks import _subtree_mass
    from ..design import Design
    P = params
    commit = data["commit"][:8]
    L: list[str] = []
    add = L.append
    mass_total = sum(PARTS[i]["mass_g"] for i in ids)

    add("# Concept A (scaled quad tailsitter flying wing, D-182), imported by `plane import dbf` from")
    add(f"# davinciucberkeley-collab/dbf-combined @ {commit} (read only). GENERATED: edit the importer, not this file.")
    add("# Frame: the source's own (metres; x aft from the wing leading edge, y right, z up in cruise) scaled x1000 to mm;")
    add("# the origin is the wing LE at the centre, not a nose datum. Read README.md for provenance and gaps.")
    add("# Every number cites its source in a comment; anything the source does not give is marked \"placeholder - not from source\".")
    add('schema_version: "0.4"')
    add("id: concept-a")
    add("name: Concept A, scaled quad tailsitter flying wing (D-182)")
    add('authors: ["UC Berkeley DBF capstone team (source repo dbf-combined)", "imported for aircraft-platform by `plane import dbf`"]')
    add("status: designed")
    add("description: >")
    add("  Four canted motors (T-Motor MN2212 KV780, APC 9x4.5 props) on four carbon arms off a printed hub, a 0.90 m x 0.245 m")
    add("  XPS-foam wing (Selig S5010) with two elevons, two fin tubes that double as the four landing feet. Sits on the fin")
    add("  tips nose-up for hover. Built from the team's own CAD (redesign/qp/A/cad/model, stub backend). Nothing built or flown.")
    add("lineage:")
    add("  derived_from: []")
    add(f'  inspired_by: ["dbf-combined@{commit} redesign/qp/A/cad (a_model.py, amodel/), qp/A/params-A.json"]')
    add("morphology:")
    add("  lift: flying-wing")
    add("  vtol_method: tailsitter")
    add("  tail: none            # no tail; two fin tubes (FIN-001/002/004) at y +-380 mm act as fins and landing legs")
    add("  propulsion_count: 4   # PRP-001-UR/UL/LR/LL")
    gate = P["req"]["mass_gate_kg"]["value"]
    cruise = P["mission"]["cruise_ms"]["value"]
    ratio = P["req"]["cruise_ratio"]["value"]
    add("requirements:")
    add(f"  mtow_g: {_n(gate * 1000, 1)}              # params-A.json req.mass_gate_kg 1.47 kg (A-P1 weigh-in gate)")
    add(f"  cruise_speed_mps: {_n(cruise, 1)}        # params-A.json mission.cruise_ms")
    add(f"  stall_speed_max_mps: {_n(cruise / ratio, 2)}    # params-A.json mission.cruise_ms 17 / req.cruise_ratio 1.3 (A-P6: 1.3 Vs < cruise)")
    add(f"  budget_usd: {_n(P['req']['budget_usd']['value'], 0)}           # params-A.json req.budget_usd")
    add("flight:")
    add(f"  cl_max: {_n(P['mission']['clmax']['value'], 2)}            # params-A.json mission.clmax 0.75, EST in the source (measured stall will replace it)")
    add(f"  air_density_kgm3: {_n(P['env']['rho_kgm3']['value'], 2)}   # params-A.json env.rho_kgm3 (MISSION.md s1)")
    add("  # no hover_pose: a tailsitter hovers nose-up with no tilting joint, and the validator then takes -x as up")
    add(f"root: {root_id_slug()}")
    add("")
    add("components:")
    rat_rows = {}
    for pid in ids:
        part = PARTS[pid]
        slug = pid.lower()
        proxy = pid in proxies
        row = parts_csv.get(pid)
        mf, mf_why = manufacturing_for(pid, part, row, proxy)
        t = part_type(pid, part["name"])
        add(f"  # {pid} {part['subsystem']}: {part['name'][:150]}")
        src = f"PARTS[{pid}].mass_g {part['mass_g']} (redesign/qp/A/cad/amodel, via a_model.PARTS)"
        if proxy:
            cgm = proxies[pid]["cg_declared"]
            add(f"  # src: {src}; mass proxy, position = declared cg_xyz_m {cgm} m x1000 (collide.jobs_for skips it: 'mass proxy')")
        else:
            c = comps[pid]
            add(f"  # src: {src}; geometry rebuilt from {len(c['bodies'])} body(ies) + {len(c['cuts'])} cut(s) (dbf_geometry), "
                "STL in meshes/; manufacturing: " + mf_why)
        add(f"  - id: {slug}")
        add(f"    type: {t}")
        distributed = proxy and pid in ("HRD-001", "HRN-001")
        desc = part["name"] + ("; distributed mass proxy (skipped as 'mass proxy' by redesign/collision collide.py)"
                               if distributed else "")
        add(f"    description: {_s(desc)}")
        if proxy:
            if distributed:
                reason = {"HRD-001": "hardware lumps: fasteners and small hardware spread over the airframe; "
                                     "skipped as 'mass proxy' by redesign/collision/collide.py",
                          "HRN-001": "wiring harness routed through the arm tubes and bay; "
                                     "skipped as 'mass proxy' by redesign/collision/collide.py"}[pid]
                add(f"    geometry: {{point_mass: {{distributed: true, reason: {_s(reason)}}}}}")
            else:
                add("    geometry: {point_mass: {}}")
            add(f"    position: {_vec([x * 1000 for x in proxies[pid]['cg_declared']], 3)}")
        else:
            add(f"    geometry: {{mesh: {{file: meshes/{slug}.stl}}}}")
            add("    position: [0, 0, 0]")
            if part.get("cg") and not part.get("mass_proxy"):
                off = np.array(part["cg"]) * 1000 - cg[pid]
                add(f"    cg_offset: {_vec(off, 3)}   # PARTS cg minus the mesh centroid")
        add(f"    mass_g: {_n(part['mass_g'], 3)}")
        if part.get("material"):
            add(f"    material: {_s(part['material'])}")
        if pid == "WNG-001":  # mesh wing: its aero planform for tier 3 (schema 0.4 component.planform)
            add("    # planform: amodel/common.py line 32 `C, B = 0.245, 0.90` (chord, span, DOC STRUCTURES s1); origin = frame origin at the "
                "wing LE (common.py line 12); rectangular, no sweep/dihedral constants in common.py")
            add("    planform: {lifting_surface: {span: 900, root_chord: 245, tip_chord: 245, sweep_le_deg: 0, dihedral_deg: 0, "
                "mirrored: true, airfoil: S5010}, origin: [0, 0, 0]}")
        mfs = "{" + ", ".join(f"{k}: {_s(v) if k != 'method' else v}" for k, v in mf.items()) + "}"
        add(f"    manufacturing: {mfs}")
        if t == "motor":
            R = np.array(comps[pid]["matrix"])[:3, :3]
            ax = -R[:, 0]                                    # motor-local thrust is toward -x (propulsion.py header)
            ax = ax / np.linalg.norm(ax)
            add("    # thrust force direction: component matrix @ (-1, 0, 0); motor-local x is the shaft, thrust toward -x (amodel/propulsion.py")
            add("    # header), cant 17 deg (amodel/common.py CANT, params-A.json prop.cant_deg). max_thrust_n 8.81 = 898 gf x 9.807: prop_a.py")
            add("    # output 'fresh 16.8 V duty 0.90 ... 898 gf x0.93' (APC 9x4.5MR table, 0.93 derate, Q_M_SPIN_MAX 0.90 cap, A.param)")
            add(f"    propulsion: {{max_thrust_n: 8.81, axis: {_vec(ax, 4)}, role: both}}")
        add("")

    add("attachments:")
    design_stub = {"components": [{"id": i.lower(), "mass_g": PARTS[i]["mass_g"]} for i in ids], "attachments": []}
    # placeholder values need the platform's own demand: build a throwaway Design from the final graph
    for r in att_rows:
        design_stub["attachments"].append({"parent": r["parent"].lower(), "child": r["child"].lower()})
    stub = Design(data=design_stub, path=None)
    n_fac = std["structure"]["landing_load_factor"]["value"] * std["structure"]["ultimate_factor"]["value"]
    for r in att_rows:
        e, parent, child = r["edge"], r["parent"], r["child"]
        val, kind, srcv = rt.rating(e, PARTS[parent], PARTS[child], r["area"])
        if val is None:
            demand = _subtree_mass(stub, parent.lower(), child.lower()) / 1000 * G * n_fac
            val = math.ceil(demand * 10) / 10
            js = e.get("retention", {}).get("load_n")
            if js:
                val = max(val, js)
                srcv += f"; retention.load_n {js} N in EDGES"
            srcv += f" ({n_fac:g} x g x subtree mass = {demand:.2f} N, rounded up)"
        method, mnote = CONN_METHOD[e["via"]]
        rat = {"edge": e["id"], "parent": parent, "child": child, "kind": kind, "rated_load_n": val, "source": srcv}
        rat_rows[e["id"]] = rat
        note = e["notes"].strip().replace("\n", " ")
        add(f"  # {e['id']} {e['via']} ({parent} -> {child}): {note[:170]}")
        extra = f"; method note: {mnote}" if mnote else ""
        add(f"  # rating [{kind}] {srcv}{extra}")
        if r["embed"]:
            add(f"  # embed_ok: measured overlap {r['overlap_frac']:.1%} of the smaller part ({r['overlap_mm3']:.1f} mm3) exceeds "
                f"glued_overlap_max_fraction {std['geometry']['glued_overlap_max_fraction']['value']:.0%}, so the parts interpenetrate by design")
        fields = [f"id: {e['id']}", f"parent: {parent.lower()}", f"child: {child.lower()}", f"method: {method}",
                  f"location: {_vec(r['location'], 3)}"]
        if r["embed"]:
            fields.append("embed_ok: true")
        fields.append(f"rated_load_n: {_n(val, 1)}")
        fields.append(f"rating_basis: {rt.rating_basis(kind)}")
        if child in KINEMATIC_LINK_CHILDS:
            add("  # kinematic_link: linkage path not modelled, same as redesign/qp/A/cad/out/REPORT.md 'Not checked against the moved parts'")
            fields.append("kinematic_link: true")
        if e["id"] in elevon:
            j = elevon[e["id"]]
            piv = [x * 1000 for x in j["origin"]]
            ax = -_axis_vec(j["axis"])
            lim = j["limits"]
            add(f"  # articulation: pivot = joint origin of {e['id']} x1000 (hinge line x 183.75 = (1 - ELEV_FRAC 0.25) x chord 245, mid-span of the elevon);")
            add(f"  # axis = -Y so that a positive angle lifts the trailing edge (the source rotates about +Y, +angle = trailing edge down);")
            add(f"  # range +-{lim[1]:g} deg = joint limits (ELEV_STOP 21, amodel/common.py); poses: neutral 0, up +21, down -21")
            add(f"  - {{{', '.join(fields)},")
            add(f"     articulation: {{type: revolute, pivot: {_vec(piv, 3)}, axis: {_vec(ax, 3)}, range_deg: [{_n(lim[0], 1)}, {_n(lim[1], 1)}],")
            add(f"                    poses: {{neutral: 0, up: {_n(lim[1], 1)}, down: {_n(lim[0], 1)}}}}}}}")
        else:
            add("  - {" + ", ".join(fields) + "}")
    return "\n".join(L) + "\n", rat_rows


def root_id_slug() -> str:
    return "wng-001"
