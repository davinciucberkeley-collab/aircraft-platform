"""MCP server: lets Claude list, read, validate, measure, export and save designs without hand-editing files.

Run over stdio with the `plane-mcp` entry point. Thin wrapper: all logic lives in design.py,
checks.py, mass.py and export.py.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP

from .checks import validate
from .design import (Design, DESIGNS_DIR, REPO_ROOT, SCHEMA_PATH, STANDARDS_PATH,
                     list_designs as _design_files, load_design)
from .export import export_glb, export_json, export_stl
from .mass import mass_properties

mcp = FastMCP("aircraft-platform")

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_EXPORT_DIR = REPO_ROOT / "build"


def _design_path(design_id: str, must_exist: bool = True) -> Path:
    if not isinstance(design_id, str) or not _ID_RE.match(design_id):
        raise ValueError(f"invalid design id {design_id!r}: use lowercase letters, digits, '-' and '_' "
                         "and start with a letter or digit")
    path = DESIGNS_DIR / design_id / "plane.yaml"
    if must_exist and not path.is_file():
        raise ValueError(f"no design '{design_id}': {path} does not exist (see list_designs)")
    return path


@mcp.tool()
def list_designs() -> list[dict]:
    """List every design in the repo with its id, name, status and morphology.

    Use this first to find out which design ids exist before calling any other design tool.
    """
    out = []
    for path in _design_files():
        data = yaml.safe_load(path.read_text()) or {}
        out.append({
            "id": data.get("id", path.parent.name),
            "name": data.get("name"),
            "status": data.get("status"),
            "morphology": data.get("morphology"),
        })
    return out


@mcp.tool()
def get_design(design_id: str) -> str:
    """Return the raw plane.yaml text of one design.

    Use this to read a design's full definition before editing it or to copy it as a starting point
    for save_design.
    """
    return _design_path(design_id).read_text()


@mcp.tool()
def validate_design(design_id: str, max_tier: int = 5) -> dict:
    """Run the validation tiers on a design and return its scorecard.

    Use this after changing a design, or to check whether a design is accepted. Tiers: 0 schema,
    1 geometry, 2 physics, 3 aero, 4 manufacturing, 5 standards. Lower max_tier to run only the
    early, faster checks. The result has 'accepted' (bool) and per-check results with messages.
    """
    design = load_design(_design_path(design_id))
    return validate(design, max_tier).to_dict()


@mcp.tool()
def get_mass_properties(design_id: str) -> dict:
    """Return total mass (g), centre of gravity (mm, body frame), inertia about the CG (g*mm^2)
    and per-component mass and CG.

    Use this when you need mass or balance numbers, for example to check a weight change or CG shift.
    """
    return mass_properties(load_design(_design_path(design_id)))


@mcp.tool()
def export_design(design_id: str, format: str) -> list[str]:
    """Export a design for viewing or fabrication and return the written file paths.

    format must be one of:
      "glb"  - one glTF binary scene for the 3D viewer, written to build/<id>.glb
      "stl"  - one STL per component in mm for manufacturing, written to build/<id>-stl/
      "json" - the canonical design as JSON, written to build/<id>.json
    Any other format is rejected.
    """
    if format not in ("glb", "stl", "json"):
        raise ValueError(f"unsupported format {format!r}: use 'glb', 'stl' or 'json'")
    design = load_design(_design_path(design_id))
    if format == "glb":
        written = [export_glb(design, _EXPORT_DIR / f"{design_id}.glb")]
    elif format == "stl":
        written = export_stl(design, _EXPORT_DIR / f"{design_id}-stl")
    else:
        written = [export_json(design, _EXPORT_DIR / f"{design_id}.json")]
    return [str(p) for p in written]


@mcp.tool()
def save_design(design_id: str, yaml_text: str, overwrite: bool = False) -> dict:
    """Validate new plane.yaml text and save it as designs/<id>/plane.yaml.

    Use this to create or update a design from YAML you have written. The YAML's 'id' must equal
    design_id. The schema check (tier 0) runs before anything is written; if it fails, nothing is
    saved and the scorecard explains why. Set overwrite=true to replace an existing design.
    Returns {"saved": bool, "path": ..., "scorecard": ...}.
    """
    path = _design_path(design_id, must_exist=False)
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise ValueError(f"yaml_text is not valid YAML: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("yaml_text: top level must be a mapping")
    if data.get("id") != design_id:
        raise ValueError(f"yaml 'id' is {data.get('id')!r} but design_id is {design_id!r}")

    precheck = validate(Design(data=data, path=path), max_tier=0)
    if not precheck.accepted:
        return {"saved": False, "scorecard": precheck.to_dict()}
    if path.exists() and not overwrite:
        raise ValueError(f"design '{design_id}' already exists; pass overwrite=true to replace it")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml_text)
    return {"saved": True, "path": str(path),
            "scorecard": validate(load_design(path)).to_dict()}


@mcp.tool()
def get_schema() -> dict:
    """Return the JSON schema that every plane.yaml must match.

    Use this before writing a new design from scratch so the YAML passes tier 0.
    """
    return json.loads(SCHEMA_PATH.read_text())


@mcp.tool()
def get_standards() -> str:
    """Return the design standards (standards/design-standards.yaml) followed by the agent
    standard (standards/agents.md), separated by a line '---'.

    Use this to learn the numeric limits and the rules the validators enforce.
    """
    agents = (REPO_ROOT / "standards" / "agents.md").read_text()
    return STANDARDS_PATH.read_text() + "\n---\n" + agents


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
