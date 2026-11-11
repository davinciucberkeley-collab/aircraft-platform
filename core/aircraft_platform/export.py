"""Exports from the canonical design to other formats."""
from __future__ import annotations

import colorsys
import json
from pathlib import Path

import numpy as np
import trimesh

from .design import Design
from .geometry import component_parts

TYPE_HUES = {"fuselage": 0.58, "wing": 0.55, "tail_surface": 0.5, "motor": 0.0, "propeller": 0.08,
             "battery": 0.15, "structure": 0.75, "flight_controller": 0.33}


def to_scene(design: Design) -> trimesh.Scene:
    """Scene in metres, z-up body frame converted to glTF y-up, one named node per component."""
    scene = trimesh.Scene()
    flip = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=float)  # z-up -> y-up
    for c in design.components:
        mesh = trimesh.util.concatenate(component_parts(c, design.base_dir))
        mesh.apply_scale(0.001)
        mesh.apply_transform(flip)
        h = TYPE_HUES.get(c["type"], 0.9)
        alpha = 90 if c["type"] == "propeller" else 255
        rgb = [int(255 * x) for x in colorsys.hsv_to_rgb(h, 0.45, 0.85)]
        mesh.visual.face_colors = rgb + [alpha]
        scene.add_geometry(mesh, node_name=c["id"], geom_name=c["id"],
                           metadata={"type": c["type"], "mass_g": c["mass_g"]})
    return scene


def export_glb(design: Design, out: str | Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(to_scene(design).export(file_type="glb"))
    return out


def export_stl(design: Design, out_dir: str | Path) -> list[Path]:
    """One STL per component, in mm, for manufacturing."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for c in design.components:
        p = out_dir / f"{c['id']}.stl"
        trimesh.util.concatenate(component_parts(c, design.base_dir)).export(p)
        paths.append(p)
    return paths


def export_json(design: Design, out: str | Path) -> Path:
    out = Path(out)
    out.write_text(json.dumps(design.data, indent=2))
    return out


FORMATS = {"glb": export_glb, "stl": export_stl, "json": export_json}
