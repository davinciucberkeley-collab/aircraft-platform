"""The `plane` command: thin click wrapper over the core library."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
import numpy as np
import yaml

from . import __version__
from .baseline import (baseline_path, baselines_at_ref, compare, growth, keys_of, read_baseline, removed, snapshot,
                       write_baseline)
from .design import DESIGNS_DIR, FAIL, SCHEMA_PATH, SKIP, list_designs, load_design
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
        Path(out_file).write_text(text, encoding="utf-8")
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
    data = load(src.read_text(encoding="utf-8"))
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
    (target_dir / "plane.yaml").write_text(head + "".join(lines), encoding="utf-8")
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
    (out / "index.json").write_text(_dumps(index) + "\n", encoding="utf-8")
    click.echo(str(out / "index.json"))


@cli.command("fea")
@click.argument("path", required=False)
@click.option("--part", "parts", multiple=True, help="Component id to check (repeatable).")
@click.option("--all", "all_parts", is_flag=True, help="Every printed structural part.")
@click.option("--plan", "plan_only", is_flag=True, help="Show supports and loads without running OpenCAE.")
@click.option("--setup", is_flag=True, help="Save the OpenCAE location (with --opencae-python / --opencae-root).")
@click.option("--opencae-python", default=None, help="Python of the environment that has OpenCAE's libraries.")
@click.option("--opencae-root", default=None, help="OpenCAE Studio folder (the one containing opencae/).")
def fea_cmd(path, parts, all_parts, plan_only, setup, opencae_python, opencae_root):
    """Stress-check printed parts in OpenCAE Studio (finite elements, CalculiX)."""
    from . import fea
    oc = fea.find_opencae(opencae_python, opencae_root)
    if setup:
        if not oc["found"]:
            _fail(f"OpenCAE not found with python={oc['python']!r} root={oc['root']!r}")
        click.echo(f"saved {fea.save_config(oc['python'], oc['root'])}")
        if not path:
            return
    if not path:
        _fail("give a design, e.g. plane fea designs/concept-a --part cge-001")
    design = _load(path)
    todo = list(parts) or (fea.eligible_parts(design) if all_parts else [])
    if not todo:
        click.echo("printed structural parts: " + ", ".join(fea.eligible_parts(design)))
        _fail("choose --part ID or --all")
    drop = fea.joint_loads(design)
    if plan_only:
        for pid in todo:
            try:
                click.echo(_dumps(fea.plan(design, pid, drop=drop)["meta"]))
            except ValueError as e:
                click.echo(f"{pid}: {e}")
        return
    if not oc["found"]:
        _fail("OpenCAE not found: run plane fea --setup --opencae-python <python> --opencae-root <folder> once")
    worst = 0
    for pid in todo:
        try:
            r = fea.run(design, pid, oc, drop=drop, log=lambda m: click.echo(m, err=True))
        except Exception as e:  # noqa: BLE001
            click.echo(f"{pid}: ERROR {e}")
            worst = max(worst, 2)
            continue
        cases = "; ".join(f"{c['name']} {c['status']}" + (f" SF {c['safety_factor_at_ultimate']}" if c['status'] != 'SKIP'
                                                          else f" ({c['message']})" if c.get("not_checked") else "")
                          for c in r["cases"])
        click.echo(f"{pid}: {r['status']}  {cases}" + (f"  ({r['error']})" if r["error"] else ""))
        worst = max(worst, 1 if r["status"] == "FAIL" else 0)
    sys.exit(worst)


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
    text = plane.read_text(encoding="utf-8")
    if not re.search(rf"(?m)^id: {re.escape(new_id)}\s*$", text):  # the importer names it after the concept
        plane.write_text(re.sub(r"(?m)^id: .*$", f"id: {new_id}", text, count=1), encoding="utf-8")
    click.echo(str(plane))


@cli.group("baseline")
def baseline_group():
    """Known-failure baselines: CI fails only on regressions."""


def _designs(paths, all_designs):
    if all_designs:
        return [_load(str(p)) for p in list_designs()]
    if not paths:
        _fail("give designs, e.g. plane baseline check designs/concept-a, or --all")
    return [_load(p) for p in paths]


@baseline_group.command("update")
@click.argument("paths", nargs=-1)
@click.option("--all", "all_designs", is_flag=True, help="Every design under designs/.")
def baseline_update_cmd(paths, all_designs):
    """Record the current known failures of each design in its baseline.json."""
    refused = False
    for design in _designs(paths, all_designs):
        folder = design.path.parent
        card = validate(design)
        if snapshot(card)["blocking"]:
            first = snapshot(card)["blocking"][0]
            click.echo(f"{design.id}: refused: schema or tier errors are never baselined "
                       f"({first['check_id']}: {first['message']}); nothing written", err=True)
            refused = True
            continue
        if card.accepted:
            path = baseline_path(folder)
            if path.exists():
                path.unlink()
                click.echo(f"{design.id}: accepted; deleted {path}")
            else:
                click.echo(f"{design.id}: accepted; no baseline needed")
            continue
        path = write_baseline(folder, card)
        click.echo(f"{design.id}: wrote {path} ({len(snapshot(card)['known'])} known)")
    if refused:
        sys.exit(2)


def _md_cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _md_table(rows: list[dict]) -> list[str]:
    lines = ["| check_id | status | message | reason |", "|---|---|---|---|"]
    lines += [f"| {_md_cell(r['check_id'])} | {r['status']} | {_md_cell(r['example'])} | {_md_cell(r['reason'])} |"
              for r in rows]
    return lines


def _renamed_from(folder: str, cur: dict, ref_baselines: dict[str, dict]) -> str | None:
    """A design folder that existed at the base ref, is gone now, and had the same known keys.

    The folder name may appear in a message (e.g. "plane fea <folder> --all"), so it is masked before comparing.
    """
    def masked(keys: frozenset, name: str) -> frozenset:
        return frozenset(k.replace(name, "<design>") for k in keys)

    keys = keys_of(cur)
    if not keys:
        return None
    for old, bl in sorted(ref_baselines.items()):
        if old != folder and not (DESIGNS_DIR / old).is_dir() \
                and masked(keys_of(bl), old) == masked(keys, folder):
            return old
    return None


@baseline_group.command("check")
@click.argument("paths", nargs=-1)
@click.option("--all", "all_designs", is_flag=True, help="Every design under designs/.")
@click.option("--format", "fmt", type=click.Choice(["md", "json"]), default="md", show_default=True)
@click.option("--base-ref", default=None,
              help="Git ref (e.g. origin/main) to compare committed baselines with, for growth, renames and new designs.")
def baseline_check_cmd(paths, all_designs, fmt, base_ref):
    """Compare each design with its baseline.json; exit 1 on regressions or a missing baseline."""
    ref_baselines, ref_designs = baselines_at_ref(base_ref) if base_ref else ({}, set())
    reports = []
    for design in _designs(paths, all_designs):
        folder_path = design.path.parent
        folder = folder_path.name
        card = validate(design)
        snap = snapshot(card)
        base = read_baseline(folder_path)
        cmp = compare(snap, base)
        added, renamed, new_design, gone = [], None, False, []
        if base_ref and base is not None:
            gone = removed(ref_baselines.get(folder), base)
            if folder in ref_baselines:
                added = growth(ref_baselines[folder], base)
            else:
                renamed = _renamed_from(folder, base, ref_baselines)
                if renamed is None and folder not in ref_designs:
                    new_design = True
                elif renamed is None:
                    added = growth(None, base)
        reports.append({"design_id": design.id, "folder": folder, "accepted": snap["accepted"],
                        "known": snap["known"], "cmp": cmp, "added": added, "renamed": renamed,
                        "new_design": new_design, "removed": gone,
                        "ok": not cmp["regressions"] and not cmp["missing_baseline"]})

    if fmt == "json":
        click.echo(_dumps([{"design_id": r["design_id"], "accepted": r["accepted"],
                            "known_count": len(r["known"]), "ok": r["ok"],
                            "regressions": r["cmp"]["regressions"], "improvements": r["cmp"]["improvements"],
                            "unchanged_count": r["cmp"]["unchanged_count"],
                            "missing_baseline": r["cmp"]["missing_baseline"],
                            "growth": r["added"], "removed": r["removed"], "renamed_from": r["renamed"],
                            "new_design": r["new_design"]}
                           for r in reports]) + "\n")
    else:
        lines = ["# Baseline check", ""]
        bad = [r["design_id"] for r in reports if not r["ok"]]
        lines.append("**Result:** " + ("pass" if not bad else f"FAIL ({', '.join(bad)})"))
        for r in reports:
            cmp = r["cmp"]
            counts = {s: sum(1 for e in r["known"] if e["status"] == s) for s in (FAIL, SKIP)}
            lines += ["", f"## {r['design_id']}  (`designs/{r['folder']}`)", ""]
            if r["accepted"]:
                lines.append("Accepted. No baseline needed.")
            else:
                lines.append(f"Known results: {len(r['known'])} (FAIL {counts[FAIL]}, SKIP {counts[SKIP]}). "
                             f"Unchanged: {cmp['unchanged_count']}. Regressions: {len(cmp['regressions'])}. "
                             f"Improvements: {len(cmp['improvements'])}.")
            if r["renamed"]:
                lines += ["", f"Renamed from `{r['renamed']}`: same known failures, so nothing is listed as added."]
            if cmp["missing_baseline"]:
                lines += ["", f"**Missing baseline.json.** Run `plane baseline update designs/{r['folder']}` and commit it."]
            if cmp["regressions"]:
                lines += ["", "### Regressions", ""] + _md_table(cmp["regressions"])
            if cmp["improvements"] and cmp["regressions"]:
                lines += ["", "### Other changes (not improvements: this design also has regressions; do not lock these in yet)", ""]
                lines += _md_table(cmp["improvements"])
            elif cmp["improvements"]:
                lines += ["", f"Locked in nothing yet: run `plane baseline update designs/{r['folder']}` and commit to record the improvement.",
                          "", "### Improvements", ""] + _md_table(cmp["improvements"])
            if r["added"]:
                lines += ["", "### Known failures ADDED to the baseline in this change (reviewers: confirm each)", ""]
                lines += _md_table([{"check_id": e["check_id"], "status": e["status"], "example": e["example"],
                                     "reason": e["reason"]} for e in r["added"]])
            if r["removed"]:
                lines += ["", "### Known results REMOVED from the baseline in this change (reviewers: confirm each)", ""]
                lines += _md_table([dict(e, reason="removed") for e in r["removed"]])
            if r["new_design"]:
                n = len(r["known"])
                lines += ["", f"**New design: {n} known failures \u2014 confirm.**", ""]
                lines += _md_table([dict(e, reason="new design") for e in r["known"]])
        click.echo("\n".join(lines) + "\n", nl=False)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            for r in reports:
                for e in r["added"]:
                    click.echo(f"::warning title=Baseline grew ({r['design_id']})::{e['check_id']} {e['example']}")

    if any(not r["ok"] for r in reports):
        sys.exit(1)


def main():
    # Windows consoles default to cp1252, which can't print the degree signs and arrows in our messages.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    cli()


if __name__ == "__main__":
    main()
