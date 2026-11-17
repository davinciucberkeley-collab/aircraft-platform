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
@click.option("--tier", "max_tier", type=click.Choice(["0", "1", "2", "3", "4", "5", "all"]), default="5",
              show_default=True, help="Highest validation tier to run (all = 5).")
@click.option("--format", "fmt", type=click.Choice(["md", "json"]), default="md", show_default=True)
@click.option("--out", "out_file", type=click.Path(dir_okay=False), default=None,
              help="Write the scorecard to FILE instead of stdout.")
def validate_cmd(path, max_tier, fmt, out_file):
    """Run the validation tiers on PATH and print the scorecard."""
    design = _load(path)
    card = validate(design, max_tier=5 if max_tier == "all" else int(max_tier))
    text = card.to_markdown() if fmt == "md" else _dumps(card.to_dict()) + "\n"
    if out_file:
        Path(out_file).parent.mkdir(parents=True, exist_ok=True)
        Path(out_file).write_text(text)
        click.echo(f"wrote {out_file}")
    else:
        click.echo(text, nl=False)
    sys.exit(0 if card.clean and (card.accepted or card.partial) else 1)


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
    try:
        p = new_design(new_id, template)
    except ValueError as e:
        _fail(str(e))
    click.echo(str(p))


def new_design(new_id: str, template: str = DEFAULT_TEMPLATE) -> Path:
    """Copy designs/TEMPLATE (plane.yaml plus mesh files) to designs/NEW_ID; return the new plane.yaml."""
    if not ID_RE.match(new_id):
        raise ValueError(f"invalid id {new_id!r}: use lowercase letters, digits, - and _")
    target_dir = DESIGNS_DIR / new_id
    if target_dir.exists():
        raise ValueError(f"design {new_id!r} already exists")
    src_dir = DESIGNS_DIR / template
    src = src_dir / "plane.yaml"
    if not src.is_file():
        raise ValueError(f"template {template!r} not found")
    from .yamlio import dump, load
    data = load(src.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"template {src} top level must be a mapping")
    data["id"] = new_id
    data["status"] = "concept"
    data["name"] = f"{data.get('name') or template} (copy: {new_id})"
    lineage = data.setdefault("lineage", {})
    if isinstance(lineage, dict):
        lineage["derived_from"] = [template]
    # Mesh files and other per-design data travel with the copy; README and reviews don't.
    shutil.copytree(src_dir, target_dir, ignore=shutil.ignore_patterns("plane.yaml", "README.md", "*.md", "__pycache__"))
    text = dump(data)
    lines = text.splitlines(keepends=True)
    while lines and lines[0].startswith("#"):  # drop the template's file header (e.g. "GENERATED: edit the importer")
        lines.pop(0)
    head = f"# Copied from designs/{template} by `plane new`; edit freely.\n"
    (target_dir / "plane.yaml").write_text(head + "".join(lines))
    return target_dir / "plane.yaml"


@cli.command("build-index")
@click.option("--out", "out_dir", type=click.Path(file_okay=False), required=True,
              help="Directory to write per-design artifacts and index.json into.")
def build_index_cmd(out_dir):
    """Export glb, scorecard and mass for every design, then write index.json."""
    from .index import design_entry, error_entry
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    for p in list_designs():
        fallback_id = p.parent.name
        try:
            design = load_design(p)
        except Exception as e:  # noqa: BLE001
            entries.append(error_entry(fallback_id, str(e)))
            continue
        try:
            entries.append(design_entry(design, out))
        except Exception as e:  # noqa: BLE001
            entries.append(error_entry(str(design.data.get("id", fallback_id)), str(e), design.data))
    index = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "designs": entries}
    (out / "index.json").write_text(_dumps(index) + "\n")
    click.echo(str(out / "index.json"))


@cli.command("studio")
@click.option("--port", default=8765, show_default=True, help="Local port to serve the app on.")
@click.option("--no-browser", is_flag=True, help="Don't open a browser window.")
def studio_cmd(port, no_browser):
    """Open Plane Studio: the point-and-click app (import, edit, validate, compare, export)."""
    from .studio import serve
    serve(port=port, open_browser=not no_browser)


@cli.command("schema")
def schema_cmd():
    """Print the path of the plane schema."""
    click.echo(str(SCHEMA_PATH))


@cli.group("import")
def import_group():
    """Import a design from another project."""


@import_group.command("dbf")
@click.option("--dbf-root", required=True, type=click.Path(exists=True, file_okay=False), help="DBF-Combined checkout (read only).")
@click.option("--concept", default="A", show_default=True)
@click.option("--id", "new_id", default=None, help="Design id to save as (default concept-<letter>); sets both the folder and the id.")
@click.option("--out", "out", type=click.Path(file_okay=False), default=None, help="Output folder (default designs/<id>).")
def import_dbf_cmd(dbf_root, concept, new_id, out):
    """Rebuild a DBF-Combined concept as a platform design (plane.yaml + meshes/)."""
    from .importers.dbf import import_concept
    new_id = new_id or f"concept-{concept.lower()}"
    if not ID_RE.match(new_id):
        _fail(f"invalid id {new_id!r}: use lowercase letters, digits, - and _")
    out = out or str(DESIGNS_DIR / new_id)
    p = Path(import_concept(dbf_root, concept=concept, out_dir=out, log=lambda m: click.echo(m, err=True)))
    plane = p if p.name == "plane.yaml" else Path(out) / "plane.yaml"
    text = plane.read_text()
    if not re.search(rf"(?m)^id: {re.escape(new_id)}\s*$", text):  # the importer names it after the concept
        plane.write_text(re.sub(r"(?m)^id: .*$", f"id: {new_id}", text, count=1))
    click.echo(str(plane))


def main():
    cli()


if __name__ == "__main__":
    main()
