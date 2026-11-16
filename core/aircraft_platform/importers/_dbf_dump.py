"""Runs in a subprocess as `python3 -I -B _dbf_dump.py <dbf_root> <concept> <out.json>`.

Imports the team's own CAD code from DBF-Combined (read only), builds the concept headless with the stub backend and
dumps plain JSON for the importer: the 3-D bodies per component, the PARTS / EDGES tables, the joints and the moving
groups. Nothing is written inside the source tree (bytecode writing is off).
"""
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True


def main():
    root, concept, out = sys.argv[1], sys.argv[2], sys.argv[3]
    rd = os.path.join(root, "redesign")
    cad = os.path.join(rd, "qp", concept, "cad")
    for p in ("collision", "fusion", "interfaces", "manufacturing", os.path.join("qp", concept, "cad")):
        sys.path.insert(0, os.path.join(rd, p))
    import collide
    import build_all
    from backends.stub_backend import StubBackend

    model = os.path.join(cad, "model")
    ctx, graph, results = build_all.build(StubBackend(), model, os.path.join(model, "modules.txt"), log=lambda *x: None)
    bad = [r for r in results if not r[2]]
    if bad:
        raise SystemExit("CAD modules failed: %s" % bad)
    comps, skipped = collide.jobs_for(ctx, False)
    for c in comps:  # per-component metadata the importer needs
        k = ctx.components[c["id"]]
        c["name"], c["material"], c["mass_g"], c["make_or_buy"] = k.name, k.material, k.mass_g, k.make_or_buy
        c["cg_declared"] = list(k.cg_declared) if k.cg_declared else None
        c["body_vol_m3"] = [sh.volume_centroid()[0] for sh in k.shapes]  # the source's own analytic volumes (check)
        c["at"], c["rotate"] = list(k.at), (None if not k.rotate else [k.rotate[0], k.rotate[1]])
    proxies = {}
    for pid, k in ctx.components.items():
        if k.proxy or not k.shapes:
            proxies[pid] = {"name": k.name, "material": k.material, "mass_g": k.mass_g, "make_or_buy": k.make_or_buy,
                            "cg_declared": list(k.cg_declared) if k.cg_declared else None, "proxy": bool(k.proxy)}
    joints = [{"edge": j.edge, "kind": j.kind, "a": j.a, "b": j.b, "origin": list(j.origin),
               "axis": j.axis if isinstance(j.axis, str) or j.axis is None else list(j.axis),
               "limits": list(j.limits) if j.limits else None} for j in ctx.joints]
    groups = collide.moving_groups(ctx, graph.edges)
    poses = collide.poses(ctx, comps, graph.edges)
    import a_model as m
    consts = {k: getattr(m, k) for k in ("C", "B", "XH", "ELEV_FRAC", "ELEV_Y0", "ELEV_Y1", "ELEV_STOP", "ELEV_POSE",
                                         "CANT", "YM", "ZM", "R_M", "HUB", "SPAR_X")}
    consts["PHI"] = dict(m.PHI)
    consts["motor_R"] = {s: m.motor_R(s) for s in m.ST}
    wires = [{"id": w.edge} for w in ctx.wires]
    edges_graph = {k: {kk: vv for kk, vv in v.items() if kk != "wire"} for k, v in graph.edges.items()}
    try:
        commit = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        commit = ""
    data = {
        "commit": commit, "comps": comps, "skipped": skipped, "proxies": proxies,
        "parts": m.PARTS, "edges": m.EDGES, "graph_edges": edges_graph, "joints": joints,
        "moving_groups": [{"edge": j.edge, "group": sorted(g)} for j, g in groups],
        "poses": [{"name": n, "moved": mv, "linked": lk} for n, o, R, mv, lk in poses],
        "consts": consts, "wires": wires,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True, default=str)


if __name__ == "__main__":
    main()
