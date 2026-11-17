"""Known-failure baselines: CI fails only on regressions, not on every non-accepted design.

A design's baseline.json lists its non-PASS results (FAIL and SKIP). A result's key is its check_id plus its
message with standalone numbers replaced by '#', so values can move without counting as a change.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .design import FAIL, REPO_ROOT, SKIP, Scorecard

SCHEMA_VERSION = 1

# Standalone numbers: not part of an identifier (wng-006-l, E-WNG-20, T2.sim_rest, mec-003 keep their digits).
_NUMBER_RE = re.compile(r"(?<![\w.-])[-+]?\d+(?:\.\d+)?(?![\w.-])")
_PERCENT_RE = re.compile(r"(?<![\w.-])[-+]?\d+(?:\.\d+)?\s*%")
_DEGREE_RE = re.compile(r"(?<![\w.-])[-+]?\d+(?:\.\d+)?°")


def normalize_message(message: str) -> str:
    text = _PERCENT_RE.sub("#%", message)
    text = _DEGREE_RE.sub("#°", text)
    return _NUMBER_RE.sub("#", text)


def key_data(data: dict | None) -> dict:
    """The identity-carrying part of a result's data: strings, bools, and lists of strings (no numbers, no dicts)."""
    out = {}
    for k, v in (data or {}).items():
        if isinstance(v, (str, bool)):
            out[k] = v
        elif isinstance(v, (list, tuple)) and all(isinstance(i, str) for i in v):
            out[k] = list(v)
    return out


def result_key(check_id: str, message: str, data: dict | None = None) -> str:
    key = f"{check_id}|{normalize_message(message)}"
    kd = key_data(data)
    if kd:
        key += "|" + json.dumps(kd, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return key


def snapshot(scorecard: Scorecard) -> dict:
    """FAIL and SKIP results of a scorecard, one entry per key (worse status wins, duplicates get a count)."""
    found: dict[str, dict[str, Any]] = {}
    for tier in scorecard.tiers:
        for r in tier.results:
            if r.status not in (FAIL, SKIP):
                continue
            key = result_key(r.check_id, r.message, r.data)
            entry = found.get(key)
            if entry is None:
                found[key] = {"key": key, "status": r.status, "check_id": r.check_id,
                              "example": r.message, "_n": 1}
                continue
            entry["_n"] += 1
            if r.status == FAIL and entry["status"] == SKIP:
                entry.update(status=FAIL, example=r.message)
    known = []
    for key in sorted(found):
        entry = found[key]
        n = entry.pop("_n")
        if n > 1:
            entry["count"] = n
        known.append(entry)
    return {"schema": SCHEMA_VERSION, "design_id": scorecard.design_id,
            "accepted": scorecard.accepted, "known": known}


def baseline_path(design_dir: Path) -> Path:
    return Path(design_dir) / "baseline.json"


def write_baseline(design_dir: Path, scorecard: Scorecard) -> Path:
    path = baseline_path(design_dir)
    path.write_text(json.dumps(snapshot(scorecard), indent=2, sort_keys=True) + "\n")
    return path


def read_baseline(design_dir: Path) -> dict | None:
    path = baseline_path(design_dir)
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def baseline_at_ref(design_dir: Path, ref: str) -> dict | None:
    """The design's baseline.json as committed at a git ref, or None when it is absent there."""
    try:
        rel = Path(design_dir).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return None
    try:
        proc = subprocess.run(["git", "-C", str(REPO_ROOT), "show", f"{ref}:{rel}/baseline.json"],
                              capture_output=True, text=True)
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout)


def _row(entry: dict, reason: str) -> dict:
    return {"key": entry["key"], "check_id": entry["check_id"], "status": entry["status"],
            "example": entry["example"], "reason": reason}


def compare(current: dict, baseline: dict | None) -> dict:
    """Regressions and improvements of a snapshot against its baseline (None = no baseline.json)."""
    cur = {e["key"]: e for e in current["known"]}
    regressions: list[dict] = []
    improvements: list[dict] = []
    unchanged = 0
    if baseline is None:
        missing = not current["accepted"]
        base: dict[str, dict] = {}
    else:
        missing = False
        base = {e["key"]: e for e in baseline.get("known", [])}

    for key in sorted(cur):
        c = cur[key]
        b = base.get(key)
        if b is None:
            reason = "no baseline.json" if baseline is None else "not in baseline"
            regressions.append(_row(c, reason))
            continue
        c_n, b_n = c.get("count", 1), b.get("count", 1)
        bad, good = [], []
        if c["status"] == FAIL and b["status"] == SKIP:
            bad.append("was SKIP in baseline, now FAIL")
        if c_n > b_n:
            bad.append(f"count rose from {b_n} to {c_n}")
        if b["status"] == FAIL and c["status"] == SKIP:
            good.append("FAIL now SKIP")
        if c_n < b_n:
            good.append(f"count fell from {b_n} to {c_n}")
        if bad:
            regressions.append(_row(c, "; ".join(bad)))
        elif good:
            improvements.append(_row(c, "; ".join(good)))
        else:
            unchanged += 1

    for key in sorted(set(base) - set(cur)):
        improvements.append(_row(base[key], "no longer present"))

    return {"regressions": regressions, "improvements": improvements,
            "unchanged_count": unchanged, "missing_baseline": missing}


def growth(base_baseline: dict | None, new_baseline: dict | None) -> list[dict]:
    """Entries of new_baseline that are new to base_baseline, raised their count, or went SKIP -> FAIL.

    Each returned entry is a copy with a "reason": "added", "count a→b", or "SKIP→FAIL" (joined when several).
    """
    if not new_baseline:
        return []
    old = {e["key"]: e for e in base_baseline.get("known", [])} if base_baseline else {}
    out = []
    for e in new_baseline.get("known", []):
        b = old.get(e["key"])
        if b is None:
            out.append(dict(e, reason="added"))
            continue
        reasons = []
        b_n, e_n = b.get("count", 1), e.get("count", 1)
        if e_n > b_n:
            reasons.append(f"count {b_n}\u2192{e_n}")
        if b["status"] == SKIP and e["status"] == FAIL:
            reasons.append("SKIP\u2192FAIL")
        if reasons:
            out.append(dict(e, reason="; ".join(reasons)))
    return sorted(out, key=lambda e: e["key"])


def keys_of(baseline: dict | None) -> frozenset:
    return frozenset(e["key"] for e in (baseline or {}).get("known", []))


def baselines_at_ref(ref: str) -> tuple[dict[str, dict], set[str]]:
    """({folder: baseline} for every designs/<folder>/baseline.json at a git ref, {folders with a plane.yaml there})."""
    def git(*args: str) -> str | None:
        try:
            proc = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True)
        except OSError:
            return None
        return proc.stdout if proc.returncode == 0 else None

    listing = git("ls-tree", "-r", "--name-only", ref, "--", "designs")
    if listing is None:
        return {}, set()
    baselines, designs = {}, set()
    for line in listing.splitlines():
        parts = line.split("/")
        if len(parts) != 3 or parts[0] != "designs":
            continue
        if parts[2] == "plane.yaml":
            designs.add(parts[1])
        elif parts[2] == "baseline.json":
            text = git("show", f"{ref}:{line}")
            if text is not None:
                baselines[parts[1]] = json.loads(text)
    return baselines, designs
