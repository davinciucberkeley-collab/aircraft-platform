"""Per-design viewer artifacts (glb, scorecard, mass) and index entries.

Shared by `plane build-index` (static viewer on GitHub Pages) and `plane studio` (local app),
so both show exactly the same data for a design.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .checks import validate
from .export import export_glb
from .mass import mass_properties


def _jsonable(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, Path):
        return str(o)
    return str(o)


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, default=_jsonable)


def design_entry(design, out_dir: Path, file_id: str | None = None) -> dict:
    """Write <file_id>.glb, .scorecard.json and .mass.json into out_dir and return the index entry.

    file_id defaults to the design id; the studio passes a content-hashed name so browsers never
    show a stale model after an edit.
    """
    meta = design.data
    did = str(meta.get("id", design.base_dir.name))
    fid = file_id or did
    out_dir.mkdir(parents=True, exist_ok=True)
    export_glb(design, out_dir / f"{fid}.glb")
    card = validate(design)
    card_dict = card.to_dict()
    (out_dir / f"{fid}.scorecard.json").write_text(dumps(card_dict) + "\n", encoding="utf-8")
    mp = mass_properties(design)
    (out_dir / f"{fid}.mass.json").write_text(dumps(mp) + "\n", encoding="utf-8")
    return {
        "id": did,
        "name": str(meta.get("name", "")),
        "status": str(meta.get("status", "")),
        "morphology": meta.get("morphology") or {},
        "accepted": bool(card.accepted),
        "mass_g": mp["mass_g"],
        "cg_mm": mp["cg_mm"],
        "glb": f"{fid}.glb",
        "scorecard": f"{fid}.scorecard.json",
        "mass": f"{fid}.mass.json",
        "tiers": {str(t["tier"]): t["status"] for t in card_dict["tiers"]},
        "error": None,
    }


def error_entry(did: str, message: str, meta: dict | None = None) -> dict:
    meta = meta or {}
    return {
        "id": did,
        "name": str(meta.get("name", "")),
        "status": str(meta.get("status", "")),
        "morphology": meta.get("morphology") or {},
        "accepted": False,
        "mass_g": None,
        "cg_mm": None,
        "glb": None,
        "scorecard": None,
        "mass": None,
        "tiers": {},
        "error": message,
    }
