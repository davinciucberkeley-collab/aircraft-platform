"""Plane Studio: a local point-and-click app over the core library (`plane studio`).

It serves the viewer (viewer/) plus a small JSON API on 127.0.0.1 only. Every action calls the same
functions as the CLI and MCP server, so the app can never disagree with CI. Results are cached in
.studio/ (gitignored), keyed by a hash of each design's files and the standards, so restarts are fast.
"""
from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import queue
import re
import shutil
import tempfile
import threading
import traceback
import webbrowser
import zipfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

from . import __version__
from .design import DESIGNS_DIR, REPO_ROOT, SCHEMA_PATH, STANDARDS_PATH, list_designs, load_design
from .index import design_entry, dumps, error_entry

VIEWER_DIR = REPO_ROOT / "viewer"
STUDIO_DIR = REPO_ROOT / ".studio"
DATA_DIR = STUDIO_DIR / "data"
CACHE_FILE = STUDIO_DIR / "cache.json"
BACKUP_DIR = STUDIO_DIR / "backups"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
MAX_BODY = 20 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def design_hash(design_dir: Path) -> str:
    """Hash of everything a design's results depend on: its files, the standards, the schema, the code version."""
    h = hashlib.sha256(__version__.encode())
    for p in (STANDARDS_PATH, SCHEMA_PATH):
        h.update(p.read_bytes() if p.exists() else b"")
    for f in sorted(design_dir.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            st = f.stat()
            h.update(f"{f.relative_to(design_dir).as_posix()}|{st.st_size}|{st.st_mtime_ns}".encode())
    return h.hexdigest()[:12]


class Studio:
    """Design state, the result cache and a single background worker that runs jobs one at a time."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.entries: dict[str, dict] = {}
        self.jobs: list[dict] = []
        self.rev = 0
        self.q: queue.Queue = queue.Queue()
        try:
            self.cache = json.loads(CACHE_FILE.read_text())
        except Exception:  # noqa: BLE001 - a missing or corrupt cache just means recomputing
            self.cache = {}
        threading.Thread(target=self._worker, daemon=True).start()
        self.scan()

    # ---------- state ----------
    def _bump(self):
        self.rev += 1

    def _save_cache(self):
        CACHE_FILE.write_text(json.dumps(self.cache, indent=1))

    def scan(self):
        """Pick up every design on disk: cached results where still valid, otherwise queue a check."""
        seen = set()
        for p in list_designs():
            did = p.parent.name
            seen.add(did)
            hsh = design_hash(p.parent)
            c = self.cache.get(did)
            ok = c and c.get("hash") == hsh and (c["entry"].get("error") or (DATA_DIR / (c["entry"].get("glb") or "_")).exists())
            with self.lock:
                if ok:
                    self.entries[did] = dict(c["entry"], pending=False)
                elif not self.entries.get(did, {}).get("pending"):
                    self.entries[did] = self._placeholder(did, p)
                    self.submit("check", did, f"Check {did}")
        with self.lock:
            for did in list(self.entries):
                if did not in seen:
                    del self.entries[did]
            self._bump()

    def _placeholder(self, did: str, p: Path) -> dict:
        try:
            meta = yaml.safe_load(p.read_text()) or {}
        except Exception:  # noqa: BLE001
            meta = {}
        e = error_entry(did, "", meta if isinstance(meta, dict) else {})
        e["error"] = None
        e["pending"] = True
        return e

    def index(self) -> dict:
        with self.lock:
            designs = sorted(self.entries.values(), key=lambda e: e["id"])
            return {"generated": _now(), "studio": True, "designs": designs}

    def state(self) -> dict:
        with self.lock:
            return {"rev": self.rev, "busy": any(j["state"] in ("queued", "running") for j in self.jobs),
                    "jobs": self.jobs[-20:][::-1]}

    # ---------- jobs ----------
    def submit(self, kind: str, target: str, label: str, **args) -> dict:
        job = {"id": f"j{len(self.jobs) + 1}", "kind": kind, "target": target, "label": label, "state": "queued",
               "message": "", "log": [], "started": None, "finished": None}
        with self.lock:
            self.jobs.append(job)
            if kind == "check" and target in self.entries:
                self.entries[target]["pending"] = True
            self._bump()
        self.q.put((job, args))
        return job

    def _worker(self):
        while True:
            job, args = self.q.get()
            with self.lock:
                job["state"], job["started"] = "running", _now()
                self._bump()
            try:
                msg = getattr(self, "_job_" + job["kind"])(job, **args)
                state = "done"
            except Exception as e:  # noqa: BLE001 - the error is shown to the person in the app
                msg, state = f"{type(e).__name__}: {e}", "error"
                job["log"].append(traceback.format_exc(limit=4))
            with self.lock:
                job["state"], job["message"], job["finished"] = state, msg or "", _now()
                self._bump()

    def _job_check(self, job, **_):
        did = job["target"]
        ddir = DESIGNS_DIR / did
        if not (ddir / "plane.yaml").is_file():
            with self.lock:
                self.entries.pop(did, None)
            return "design no longer exists"
        hsh = design_hash(ddir)
        fid = f"{did}-{hsh}"
        try:
            design = load_design(ddir / "plane.yaml")
            entry = design_entry(design, DATA_DIR, file_id=fid)
            entry["id"] = did
            msg = "accepted" if entry["accepted"] else "checked: " + ", ".join(
                f"T{t} {s}" for t, s in entry["tiers"].items() if s not in ("PASS", "SKIP")) or "checked"
        except Exception as e:  # noqa: BLE001
            entry = error_entry(did, f"{type(e).__name__}: {e}")
            msg = entry["error"]
        for old in DATA_DIR.glob(f"{did}-*.*"):  # drop results for older versions of this design
            if not old.name.startswith(fid + "."):
                old.unlink(missing_ok=True)
        with self.lock:
            entry["pending"] = False
            self.entries[did] = entry
            self.cache[did] = {"hash": hsh, "entry": {k: v for k, v in entry.items() if k != "pending"}}
            self._save_cache()
        return msg

    def _job_import_dbf(self, job, root: str, concept: str, new_id: str):
        from .importers.dbf import import_concept
        out = DESIGNS_DIR / new_id
        import_concept(root, concept=concept, out_dir=str(out), log=lambda m: job["log"].append(str(m)))
        p = out / "plane.yaml"
        data = yaml.safe_load(p.read_text())
        if data.get("id") != new_id:  # the importer names it after the concept; keep the name the person chose
            text = p.read_text()
            p.write_text(re.sub(r"(?m)^id: .*$", f"id: {new_id}", text, count=1))
        self.scan()
        return f"imported into designs/{new_id}"

    def _job_fea(self, job, design_id: str, parts: list):
        from . import fea
        design = load_design(DESIGNS_DIR / design_id / "plane.yaml")
        oc = fea.find_opencae()
        if not oc["found"]:
            raise RuntimeError("OpenCAE is not set up (Stress check > Settings)")
        drop = fea.joint_loads(design)
        done = []
        for i, pid in enumerate(parts, 1):
            with self.lock:
                job["message"] = f"{pid} ({i}/{len(parts)})"
                self._bump()
            try:
                r = fea.run(design, pid, oc, drop=drop, log=lambda m: job["log"].append(str(m)))
                done.append(f"{pid} {r['status']}")
            except Exception as e:  # noqa: BLE001
                done.append(f"{pid} ERROR")
                job["log"].append(f"{pid}: {type(e).__name__}: {e}")
        self.submit("check", design_id, f"Check {design_id}")
        return ", ".join(done)

    def fea_state(self, did: str) -> dict:
        from . import fea
        design = load_design(DESIGNS_DIR / _check_id(did) / "plane.yaml")
        rows = []
        for pid in fea.eligible_parts(design):
            f = fea.result_path(design, pid)
            rec = json.loads(f.read_text()) if f.exists() else None
            row = {"part": pid, "description": design.component(pid).get("description", ""), "status": None}
            if rec:
                row.update(status=rec.get("status"), error=rec.get("error"), notes=rec.get("notes"),
                           up_to_date=rec.get("hash") == fea.part_hash(design, pid), generated=rec.get("generated"),
                           cases=[{k: c.get(k) for k in ("name", "status", "max_von_mises_away_mpa", "max_von_mises_mpa",
                                                        "safety_factor_at_ultimate", "max_displacement_mm", "message")}
                                  for c in rec.get("cases", [])],
                           files=_fea_files(did, pid))
            rows.append(row)
        oc = fea.find_opencae()
        std = load_standards_safe()
        return {"opencae": oc, "parts": rows, "allowable_mpa": std.get("fea_allowable_printed_petg_mpa"),
                "ultimate_factor": std.get("ultimate_factor")}

    # ---------- actions (called from the HTTP thread) ----------
    def new(self, new_id: str, template: str) -> str:
        from .cli import new_design
        new_design(new_id, template)
        self.scan()
        return new_id

    def read_yaml(self, did: str) -> str:
        return (DESIGNS_DIR / _check_id(did) / "plane.yaml").read_text()

    def write_yaml(self, did: str, text: str) -> None:
        path = DESIGNS_DIR / _check_id(did) / "plane.yaml"
        if not path.is_file():
            raise ValueError(f"no design {did!r}")
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML error: {e}") from e
        if not isinstance(data, dict):
            raise ValueError("the file must be a YAML mapping (key: value lines)")
        if str(data.get("id")) != did:
            raise ValueError(f"id must stay {did!r} (to make a copy, use New design)")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, BACKUP_DIR / f"{did}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.yaml")
        path.write_text(text)
        self.scan()

    def read_design(self, did: str) -> dict:
        data = yaml.safe_load(self.read_yaml(did))
        return {"id": did, "data": data, "enums": _schema_enums()}

    def patch(self, did: str, changes: list) -> int:
        """Apply small field edits from the form editor, keeping the file's comments and layout (ruamel round-trip)."""
        from .yamlio import dump, load
        path = DESIGNS_DIR / _check_id(did) / "plane.yaml"
        doc = load(path.read_text())
        if not isinstance(changes, list) or not changes:
            raise ValueError("nothing to save")
        for ch in changes:
            node, keys = doc, ch.get("path") or []
            if not keys:
                raise ValueError("empty path")
            for k in keys[:-1]:
                node = _step(node, k)
            last = keys[-1]
            if not isinstance(last, str):
                raise ValueError("a change must end on a field name")
            value = ch.get("value")
            if value is None or value == "":
                if hasattr(node, "pop"):
                    node.pop(last, None)
            else:
                node[last] = value
        text = dump(doc)
        self.write_yaml(did, text)  # same checks, backup and re-check as a hand edit
        return len(changes)

    def export(self, did: str, fmt: str) -> tuple[bytes, str, str]:
        from .export import export_glb, export_json, export_stl
        design = load_design(DESIGNS_DIR / _check_id(did) / "plane.yaml")
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            if fmt == "glb":
                export_glb(design, t / f"{did}.glb")
                return (t / f"{did}.glb").read_bytes(), f"{did}.glb", "model/gltf-binary"
            if fmt == "json":
                export_json(design, t / f"{did}.json")
                return (t / f"{did}.json").read_bytes(), f"{did}.json", "application/json"
            if fmt == "mjcf":
                from .sim import export_mjcf
                export_mjcf(design, t / "mjcf" / f"{did}.xml")  # zipped with any mesh files it writes beside it
                return _zip(t / "mjcf"), f"{did}-mjcf.zip", "application/zip"
            if fmt == "stl":
                export_stl(design, t / "stl")
                return _zip(t / "stl"), f"{did}-stl.zip", "application/zip"
            if fmt == "report":
                from .checks import validate
                md = validate(design).to_markdown()
                return md.encode(), f"{did}-scorecard.md", "text/markdown; charset=utf-8"
        raise ValueError(f"unknown format {fmt!r}")


def _step(node, key):
    """Follow one path segment: a mapping key, a list index, or {"id": ...} to pick a component or joint."""
    if isinstance(key, dict) and "id" in key:
        for item in node or []:
            if isinstance(item, dict) and str(item.get("id")) == str(key["id"]):
                return item
        raise ValueError(f"no entry with id {key['id']!r}")
    if isinstance(key, int):
        return node[key]
    if isinstance(key, str):
        if key not in node:
            node[key] = {}
        return node[key]
    raise ValueError(f"bad path segment {key!r}")


_ENUMS: dict | None = None


def _schema_enums() -> dict:
    global _ENUMS
    if _ENUMS is None:
        s = json.loads(SCHEMA_PATH.read_text())
        d = s.get("$defs", {})
        _ENUMS = {
            "status": s["properties"]["status"].get("enum", []),
            "component_type": d.get("component", {}).get("properties", {}).get("type", {}).get("enum", []),
            "manufacturing": d.get("component", {}).get("properties", {}).get("manufacturing", {}).get("properties", {}).get("method", {}).get("enum", []),
            "joint_method": d.get("attachment", {}).get("properties", {}).get("method", {}).get("enum", []),
            "rating_basis": d.get("attachment", {}).get("properties", {}).get("rating_basis", {}).get("enum", []),
            "requirements": list(s["properties"].get("requirements", {}).get("properties", {}).keys()),
        }
    return _ENUMS


def load_standards_safe() -> dict:
    try:
        from .design import load_standards
        st = load_standards()["structure"]
        return {k: st[k]["value"] for k in ("fea_allowable_printed_petg_mpa", "ultimate_factor") if k in st}
    except Exception:  # noqa: BLE001
        return {}


def _fea_files(did: str, pid: str) -> list[dict]:
    """Viewable outputs of a stored stress check: OpenCAE reports/projects and ParaView meshes."""
    base = REPO_ROOT / ".studio" / "fea" / did / pid
    out = []
    if base.is_dir():
        for f in sorted(base.rglob("*")):
            if f.suffix in (".html", ".vtu", ".ocae") and f.is_file():
                out.append({"name": f.relative_to(base).as_posix(), "kind": f.suffix[1:]})
    return out


def _zip(folder: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(folder.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(folder).as_posix())
    return buf.getvalue()


def _check_id(did: str) -> str:
    if not isinstance(did, str) or not ID_RE.match(did):
        raise ValueError(f"invalid design id {did!r}")
    return did


def _guess_dbf_root() -> str:
    for cand in (REPO_ROOT.parent / "dbf-combined", REPO_ROOT.parent / "DBF-Combined", REPO_ROOT.parent / "dbf_combined"):
        if cand.is_dir():
            return str(cand)
    return ""


# ---------- HTTP ----------
def make_handler(studio: Studio):
    class Handler(BaseHTTPRequestHandler):
        server_version = "PlaneStudio/" + __version__

        def log_message(self, *a):  # keep the terminal quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200):
            self._send(code, (dumps(obj) + "\n").encode(), "application/json; charset=utf-8")

        def _err(self, msg: str, code: int = 400):
            self._json({"error": msg}, code)

        def _file(self, base: Path, rel: str):
            p = (base / rel).resolve()
            if base.resolve() not in p.parents and p != base.resolve():
                return self._err("not found", 404)
            if p.is_dir():
                p = p / "index.html"
            if not p.is_file():
                return self._err("not found", 404)
            ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            if p.suffix == ".js":
                ctype = "text/javascript; charset=utf-8"
            elif p.suffix == ".glb":
                ctype = "model/gltf-binary"
            self._send(200, p.read_bytes(), ctype)

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise ValueError("request too large")
            raw = self.rfile.read(n) if n else b"{}"
            data = json.loads(raw or b"{}")
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            return data

        def do_GET(self):  # noqa: N802
            u = urlparse(self.path)
            qs = {k: v[0] for k, v in parse_qs(u.query).items()}
            path = u.path
            try:
                if path == "/api/ping":
                    return self._json({"studio": True, "version": __version__, "dbf_root_guess": _guess_dbf_root(),
                                       "designs": sorted(studio.entries)})
                if path == "/api/state":
                    return self._json(studio.state())
                if path == "/api/yaml":
                    return self._json({"id": qs.get("id"), "text": studio.read_yaml(qs.get("id", ""))})
                if path == "/api/fea":
                    return self._json(studio.fea_state(qs.get("id", "")))
                if path == "/api/fea-file":
                    did, pid = _check_id(qs.get("id", "")), _check_id(qs.get("part", ""))
                    base = (REPO_ROOT / ".studio" / "fea" / did / pid).resolve()
                    f = (base / qs.get("name", "")).resolve()
                    if base not in f.parents or not f.is_file() or f.suffix not in (".html", ".vtu", ".ocae"):
                        return self._err("not found", 404)
                    ctype = "text/html; charset=utf-8" if f.suffix == ".html" else "application/octet-stream"
                    extra = {} if f.suffix == ".html" else {"Content-Disposition": f'attachment; filename="{pid}-{f.name}"'}
                    return self._send(200, f.read_bytes(), ctype, extra)
                if path == "/api/design":
                    return self._json(studio.read_design(qs.get("id", "")))
                if path == "/api/export":
                    body, name, ctype = studio.export(qs.get("id", ""), qs.get("format", "glb"))
                    return self._send(200, body, ctype, {"Content-Disposition": f'attachment; filename="{name}"'})
                if path == "/data/index.json":
                    return self._json(studio.index())
                if path.startswith("/data/"):
                    return self._file(DATA_DIR, path[len("/data/"):])
                return self._file(VIEWER_DIR, path.lstrip("/") or "index.html")
            except (ValueError, FileNotFoundError) as e:
                return self._err(str(e))
            except Exception as e:  # noqa: BLE001
                return self._err(f"{type(e).__name__}: {e}", 500)

        def do_POST(self):  # noqa: N802
            if self.headers.get("Origin") not in (None, f"http://127.0.0.1:{self.server.server_port}",
                                                  f"http://localhost:{self.server.server_port}"):
                return self._err("cross-site request refused", 403)
            path = urlparse(self.path).path
            try:
                b = self._body()
                if path == "/api/check":
                    did = _check_id(b.get("id"))
                    return self._json(studio.submit("check", did, f"Check {did}"))
                if path == "/api/check-all":
                    for did in sorted(studio.entries):
                        studio.submit("check", did, f"Check {did}")
                    return self._json({"ok": True})
                if path == "/api/new":
                    did = studio.new(_check_id(b.get("id")), _check_id(b.get("from")))
                    return self._json({"id": did})
                if path == "/api/yaml":
                    studio.write_yaml(b.get("id", ""), b.get("text", ""))
                    return self._json({"ok": True})
                if path == "/api/patch":
                    n = studio.patch(b.get("id", ""), b.get("changes"))
                    return self._json({"ok": True, "changed": n})
                if path == "/api/import-dbf":
                    root = str(b.get("root") or "").strip().strip('"')
                    if not root or not Path(root).is_dir():
                        raise ValueError(f"folder not found: {root or '(empty)'}")
                    new_id = _check_id(b.get("id") or "concept-a")
                    concept = str(b.get("concept") or "A").strip().upper()
                    if not re.fullmatch(r"[A-Z0-9]{1,4}", concept):
                        raise ValueError("concept must be a letter such as A")
                    return self._json(studio.submit("import_dbf", new_id, f"Import concept {concept} from DBF-Combined",
                                                    root=root, concept=concept, new_id=new_id))
                if path == "/api/fea":
                    did = _check_id(b.get("id"))
                    parts = [_check_id(p) for p in (b.get("parts") or [])]
                    if not parts:
                        raise ValueError("choose at least one part")
                    return self._json(studio.submit("fea", did, f"Stress check {did} ({len(parts)} part{'s' if len(parts) > 1 else ''})",
                                                    design_id=did, parts=parts))
                if path == "/api/fea-setup":
                    from . import fea
                    oc = fea.find_opencae(str(b.get("python") or "").strip().strip('"'), str(b.get("root") or "").strip().strip('"'))
                    if not oc["found"]:
                        raise ValueError(f"OpenCAE not found there (python {oc['python']}, folder {oc['root']})")
                    fea.save_config(oc["python"], oc["root"])
                    return self._json(oc)
                if path == "/api/rescan":
                    studio.scan()
                    return self._json({"ok": True})
                return self._err("not found", 404)
            except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
                return self._err(str(e))
            except Exception as e:  # noqa: BLE001
                return self._err(f"{type(e).__name__}: {e}", 500)

    return Handler


def serve(port: int = 8765, open_browser: bool = True):
    studio = Studio()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(studio))
    url = f"http://127.0.0.1:{httpd.server_port}/"
    print(f"Plane Studio is running at {url}")
    print("Keep this window open while you use it. Press Ctrl+C here to stop.")
    pending = sum(1 for e in studio.entries.values() if e.get("pending"))
    if pending:
        print(f"Checking {pending} design(s) in the background; the app shows progress.")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
