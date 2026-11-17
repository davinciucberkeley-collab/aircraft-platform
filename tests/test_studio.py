"""Plane Studio and the comment-preserving edit path it shares with `plane new`."""
from __future__ import annotations

import json
import shutil
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from aircraft_platform import cli, design as design_mod, studio
from aircraft_platform.yamlio import dump, load

EXAMPLE = design_mod.DESIGNS_DIR / "example-tailsitter-wing"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A designs/ folder holding only the example design, and a private .studio/ cache."""
    designs = tmp_path / "designs"
    shutil.copytree(EXAMPLE, designs / "example-tailsitter-wing")
    for mod in (cli, design_mod, studio):
        monkeypatch.setattr(mod, "DESIGNS_DIR", designs, raising=False)
    monkeypatch.setattr(studio, "STUDIO_DIR", tmp_path / ".studio")
    monkeypatch.setattr(studio, "DATA_DIR", tmp_path / ".studio" / "data")
    monkeypatch.setattr(studio, "CACHE_FILE", tmp_path / ".studio" / "cache.json")
    monkeypatch.setattr(studio, "BACKUP_DIR", tmp_path / ".studio" / "backups")
    return designs


def test_new_design_copies_files_and_keeps_comments(sandbox):
    (sandbox / "example-tailsitter-wing" / "meshes").mkdir()
    (sandbox / "example-tailsitter-wing" / "meshes" / "part.stl").write_text("solid x\nendsolid x\n")
    p = cli.new_design("my-copy", "example-tailsitter-wing")
    text = p.read_text()
    assert (sandbox / "my-copy" / "meshes" / "part.stl").is_file(), "mesh files must travel with the copy"
    assert "id: my-copy" in text and "status: concept" in text
    assert "# stacked ply; FDM fit unverifiable" in text, "inline comments survive the copy"
    assert text.startswith("# Copied from designs/example-tailsitter-wing")
    with pytest.raises(ValueError):
        cli.new_design("my-copy", "example-tailsitter-wing")
    with pytest.raises(ValueError):
        cli.new_design("Bad Name", "example-tailsitter-wing")


def test_patch_changes_only_the_edited_line():
    src = (EXAMPLE / "plane.yaml").read_text()
    doc = load(src)
    studio._step(doc["components"], {"id": "wing"})["mass_g"] = 181
    out = dump(doc)
    changed = [(a, b) for a, b in zip(src.splitlines(), out.splitlines()) if a != b]
    assert len(src.splitlines()) == len(out.splitlines())
    assert changed == [("    mass_g: 180", "    mass_g: 181")]
    with pytest.raises(ValueError):
        studio._step(doc["components"], {"id": "no-such-part"})


def _call(base, path, body=None):
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if r.headers.get_content_type() == "application/json" else raw)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _wait_idle(base, timeout=240):
    t0 = time.time()
    while time.time() - t0 < timeout:
        _, st = _call(base, "/api/state")
        if not st["busy"]:
            return st
        time.sleep(0.3)
    raise AssertionError("studio jobs did not finish")


def test_studio_api_end_to_end(sandbox):
    s = studio.Studio()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), studio.make_handler(s))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        st = _wait_idle(base)
        assert [j["state"] for j in st["jobs"]] == ["done"]
        _, index = _call(base, "/data/index.json")
        (entry,) = index["designs"]
        assert index["studio"] and entry["id"] == "example-tailsitter-wing" and entry["accepted"] and not entry["pending"]
        assert _call(base, "/data/" + entry["glb"])[0] == 200

        # form edit: one field, saved with a backup, re-checked
        code, res = _call(base, "/api/patch", {"id": "example-tailsitter-wing",
                                               "changes": [{"path": ["components", {"id": "wing"}, "mass_g"], "value": 999}]})
        assert code == 200 and res["changed"] == 1
        assert "mass_g: 999" in (sandbox / "example-tailsitter-wing" / "plane.yaml").read_text()
        assert len(list(studio.BACKUP_DIR.glob("*.yaml"))) == 1
        _wait_idle(base)
        _, index = _call(base, "/data/index.json")
        assert index["designs"][0]["mass_g"] > entry["mass_g"]

        # bad edits are refused and leave the file alone
        assert _call(base, "/api/yaml", {"id": "example-tailsitter-wing", "text": "id: [unclosed"})[0] == 400
        assert _call(base, "/api/yaml", {"id": "example-tailsitter-wing", "text": "id: other\n"})[0] == 400
        assert _call(base, "/api/new", {"id": "../escape", "from": "example-tailsitter-wing"})[0] == 400

        # copy, then download the scorecard report
        assert _call(base, "/api/new", {"id": "copy-1", "from": "example-tailsitter-wing"})[0] == 200
        assert (sandbox / "copy-1" / "plane.yaml").is_file()
        _wait_idle(base)
        code, report = _call(base, "/api/export?id=copy-1&format=report")
        assert code == 200 and report.startswith(b"# Scorecard: copy-1")

        # a cross-site POST is refused
        req = urllib.request.Request(base + "/api/check-all", data=b"{}", headers={"Origin": "https://evil.example"})
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=10)
        assert e.value.code == 403
    finally:
        httpd.shutdown()
        httpd.server_close()
