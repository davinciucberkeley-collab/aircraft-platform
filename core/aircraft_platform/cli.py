"""The `plane` command: thin click wrapper over the core library."""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
import numpy as np
import yaml

from . import __version__
from .design import DESIGNS_DIR, SCHEMA_PATH, list_designs, load_design
from .checks import validate
from .export import export_glb, export_stl, export_json
from .mass import mass_properties

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
DEFAULT_TEMPLATE = "example-tailsitter-wing"


def _jsonable(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, Path):
        return str(o)
    return str(o)


def _dumps(obj) -> str:
    return json.dumps(obj, indent=2, default=_jsonable)


def _fail(msg: str, code: int = 2):
    click.echo(f"plane: {msg}", err=True)
    sys.exit(code)


def _load(path: str):
    try:
        return load_design(path)
    except Exception as e:  # noqa: BLE001 - report any load failure cleanly
        _fail(f"cannot load {path}: {e}")


@click.group()
@click.version_option(__version__, prog_name="plane")
def cli():
    """Aircraft design platform command line."""


@cli.command("validate")
@click.argument("path")
@click.option("--tier", "max_tier", type=int, default=5, show_default=True,
              help="Highest validation tier to run.")
@click.option("--format", "fmt", type=click.Choice(["md", "json"]), default="md", show_default=True)
@click.option("--out", "out_file", type=click.Path(dir_okay=False), default=None,
              help="Write the scorecard to FILE instead of stdout.")
def validate_cmd(path, max_tier, fmt, out_file):
    """Run the validation tiers on PATH and print the scorecard."""
    design = _load(path)
    card = validate(design, max_tier=max_tier)
    text = card.to_markdown() if fmt == "md" else _dumps(card.to_dict()) + "\n"
    if out_file:
        Path(out_file).parent.mkdir(parents=True, exist_ok=True)
        Path(out_file).write_text(text)
        click.echo(f"wrote {out_file}")
    else:
        click.echo(text, nl=False)
    sys.exit(0 if card.accepted else 1)


@cli.command("mass")
@click.argument("path")
def mass_cmd(path):
    """Print mass properties of PATH as JSON."""
    click.echo(_dumps(mass_properties(_load(path))))


@cli.command("export")
@click.argument("path")
@click.option("--format", "fmt", type=click.Choice(["glb", "stl", "json", "mjcf"]), required=True)
@click.option("--out", "out", type=click.Path(), required=True,
              help="File path for glb/json/mjcf; directory for stl.")
def export_cmd(path, fmt, out):
    """Export PATH to glb, stl or json."""
    design = _load(path)
    try:
        if fmt == "stl":
            written = export_stl(design, out)
        elif fmt == "glb":
            written = export_glb(design, out)
        elif fmt == "mjcf":
            from .sim import export_mjcf
            written = export_mjcf(design, out)
        else:
            written = export_json(design, out)
    except Exception as e:  # noqa: BLE001
        _fail(f"export failed: {e}", code=1)
    paths = written if isinstance(written, list) else [written]
    for p in paths:
        click.echo(str(p))


@cli.command("list")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table", show_default=True)
def list_cmd(fmt):
    """List every design under designs/."""
    rows = []
    for p in list_designs():
        try:
            d = load_design(p).data
        except Exception as e:  # noqa: BLE001
            rows.append({"id": p.parent.name, "name": f"<error: {e}>", "status": "", "lift": "", "vtol_method": ""})
            continue
        morph = d.get("morphology") or {}
        rows.append({
            "id": str(d.get("id", p.parent.name)),
            "name": str(d.get("name", "")),
            "status": str(d.get("status", "")),
            "lift": str(morph.get("lift", "")),
            "vtol_method": str(morph.get("vtol_method", "")),
        })
    if fmt == "json":
        click.echo(_dumps(rows))
        return
    if not rows:
        click.echo("no designs found")
        return
    headers = ["id", "name", "status", "lift", "vtol_method"]
    widths = {h: max(len(h), *(len(r[h]) for r in rows)) for h in headers}
    click.echo("  ".join(h.ljust(widths[h]) for h in headers).rstrip())
    for r in rows:
        click.echo("  ".join(r[h].ljust(widths[h]) for h in headers).rstrip())


@cli.command("new")
@click.argument("new_id")
@click.option("--from", "template", default=DEFAULT_TEMPLATE, show_default=True,
              help="Design id to copy from.")
def new_cmd(new_id, template):
    """Create designs/NEW_ID/plane.yaml from a template design."""
    if not ID_RE.match(new_id):
        _fail(f"invalid id {new_id!r}: must match {ID_RE.pattern}")
    target_dir = DESIGNS_DIR / new_id
    if target_dir.exists():
        _fail(f"design {new_id!r} already exists at {target_dir}")
    src = DESIGNS_DIR / template / "plane.yaml"
    if not src.is_file():
        _fail(f"template {template!r} not found at {src}")
    data = yaml.safe_load(src.read_text())
    if not isinstance(data, dict):
        _fail(f"template {src} top level must be a mapping")
    data["id"] = new_id
    data["status"] = "concept"
    data["name"] = new_id
    target_dir.mkdir(parents=True)
    (target_dir / "plane.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    click.echo(str(target_dir / "plane.yaml"))


@cli.command("build-index")
@click.option("--out", "out_dir", type=click.Path(file_okay=False), required=True,
              help="Directory to write per-design artifacts and index.json into.")
def build_index_cmd(out_dir):
    """Export glb, scorecard and mass for every design, then write index.json."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    for p in list_designs():
        fallback_id = p.parent.name
        try:
            design = load_design(p)
            did = str(design.data.get("id", fallback_id))
            meta = design.data
        except Exception as e:  # noqa: BLE001
            entries.append(_error_entry(fallback_id, str(e)))
            continue
        try:
            export_glb(design, out / f"{did}.glb")
            card = validate(design)
            card_dict = card.to_dict()
            (out / f"{did}.scorecard.json").write_text(_dumps(card_dict) + "\n")
            mp = mass_properties(design)
            (out / f"{did}.mass.json").write_text(_dumps(mp) + "\n")
            entries.append({
                "id": did,
                "name": str(meta.get("name", "")),
                "status": str(meta.get("status", "")),
                "morphology": meta.get("morphology") or {},
                "accepted": bool(card.accepted),
                "mass_g": mp["mass_g"],
                "cg_mm": mp["cg_mm"],
                "glb": f"{did}.glb",
                "scorecard": f"{did}.scorecard.json",
                "mass": f"{did}.mass.json",
                "tiers": {str(t["tier"]): t["status"] for t in card_dict["tiers"]},
                "error": None,
            })
        except Exception as e:  # noqa: BLE001
            entries.append(_error_entry(did, str(e), meta))
    index = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "designs": entries}
    (out / "index.json").write_text(_dumps(index) + "\n")
    click.echo(str(out / "index.json"))


def _error_entry(did: str, message: str, meta: dict | None = None) -> dict:
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


@cli.command("schema")
def schema_cmd():
    """Print the path of the plane schema."""
    click.echo(str(SCHEMA_PATH))


def main():
    cli()


if __name__ == "__main__":
    main()
