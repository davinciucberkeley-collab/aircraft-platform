"""Mass properties: total mass (g), CG (mm, body frame), inertia about CG (g*mm^2)."""
from __future__ import annotations

import numpy as np
import trimesh

from .design import Design
from .geometry import component_parts


def component_cg(component: dict, parts: list[trimesh.Trimesh]) -> np.ndarray:
    vols = np.array([max(p.volume, 1e-9) for p in parts])
    cents = np.array([p.center_mass for p in parts])
    centroid = (cents * vols[:, None]).sum(0) / vols.sum()
    return centroid + np.array(component.get("cg_offset", [0, 0, 0]), dtype=float)


def mass_properties(design: Design) -> dict:
    total = 0.0
    moment = np.zeros(3)
    entries = []
    for c in design.components:
        parts = component_parts(c, design.base_dir)
        m = float(c["mass_g"])
        cg = component_cg(c, parts)
        entries.append((c, parts, m, cg))
        total += m
        moment += m * cg
    if total <= 0:
        return {"mass_g": 0.0, "cg_mm": [0, 0, 0], "inertia_gmm2": np.zeros((3, 3)).tolist(), "per_component": []}
    cg = moment / total
    inertia = np.zeros((3, 3))
    per = []
    for c, parts, m, ccg in entries:
        vol = sum(max(p.volume, 1e-9) for p in parts)
        i_local = np.zeros((3, 3))
        for p in parts:
            pm = m * max(p.volume, 1e-9) / vol
            q = p.copy()
            q.density = pm / max(q.volume, 1e-9)
            i_local += q.moment_inertia + pm * _parallel(q.center_mass - ccg)
        d = ccg - cg
        inertia += i_local + m * _parallel(d)
        per.append({"id": c["id"], "mass_g": m, "cg_mm": ccg.round(2).tolist()})
    return {"mass_g": total, "cg_mm": cg.round(2).tolist(), "inertia_gmm2": inertia.round(1).tolist(),
            "per_component": per}


def _parallel(d: np.ndarray) -> np.ndarray:
    return np.dot(d, d) * np.eye(3) - np.outer(d, d)
