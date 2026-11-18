#!/usr/bin/env python3
"""Claude Code hooks that enforce standards/agents.md.

Subcommands read hook JSON on stdin:
  pre-agent      plan gate before an Agent launch (fails closed)
  pre-edit       edit gate before Edit/Write/NotebookEdit (fails closed)
  pre-bash       snapshots git-visible file state before a Bash call (never blocks)
  post-bash      after a Bash call, blocks (tells the model) if it changed files the caller may not edit
  post-agent     appends an agent_done line to plans/agent-log.jsonl (never blocks)
  subagent-stop  appends a subagent_stop line to plans/agent-log.jsonl (never blocks)

Stdlib only. Set AGENT_HOOKS_ROOT to override the repo root (tests only).
"""
import hashlib
import json
import os
import posixpath
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

PLAN_WINDOW_DAYS = 14
STEP_RE = re.compile(r"^([A-Z]+\d+[a-z]?)\b")
ROLE_TYPES = ("builder", "scout", "tactician", "reviewer")
FAMILIES = ("haiku", "sonnet", "opus")
MAIN_PROTECTED = ("core", "tests", "designs", "schema", ".github")
ENFORCEMENT_FILES = ("tools/agent_hooks.py",)  # lower case; no agent may edit these
ENFORCEMENT_DIR = ".claude"                     # likewise everything under it
CONDUCTOR_LOG = "plans/conductor-edits.md"
AGENT_LOG = "plans/agent-log.jsonl"
FROZEN_FILE = "standards/design-standards.yaml"
AGENT_TYPE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
PLAN_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-.+\.md$")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
FENCE_OPEN_RE = re.compile(r"^\s*(`{3,}|~{3,})")
CONDUCTOR_REASON_MIN_CHARS = 15
CONDUCTOR_REASON_MIN_WORDS = 3
CASE_FOLD = os.name == "nt"
GIT_TIMEOUT = 20
BASH_STATE_DIR = Path(tempfile.gettempdir()) / "agent_hooks_bash"


def repo_root():
    override = os.environ.get("AGENT_HOOKS_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parent.parent


def read_stdin():
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("hook input is not a JSON object")
    return data


def emit_deny(reason):
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()
    return 0


def run_gate(name, fn):
    try:
        ok, reason = fn(read_stdin())
    except Exception as exc:  # fail closed
        ok, reason = False, f"agent_hooks {name} failed closed: {type(exc).__name__}: {exc}"
    if ok:
        return 0
    return emit_deny(reason)


def run_logger(fn):
    try:
        fn(read_stdin())
    except Exception:  # logging must never block work
        pass
    return 0


# ---------- markdown tables ----------

def _cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _clean(cell):
    return cell.replace("`", "").replace("*", "").strip()


def _is_separator(line):
    if not line.strip().startswith("|"):
        return False
    cells = _cells(line)
    return bool(cells) and all(re.fullmatch(r":?-+:?", c) for c in cells)


def strip_noise(text):
    """Blank out HTML comments and fenced code blocks (``` or ~~~), keeping line count."""
    text = COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    out = []
    fence = None
    for line in text.splitlines():
        if fence is None:
            m = FENCE_OPEN_RE.match(line)
            if m:
                fence = m.group(1)
                out.append("")
                continue
            out.append(line)
        else:
            s = line.strip()
            if s and set(s) <= {fence[0]} and len(s) >= len(fence):
                fence = None
            out.append("")
    return "\n".join(out)


def parse_tables(text, required):
    """Return rows (dicts keyed by lower-cased header) of every table whose header has all `required` columns."""
    lines = strip_noise(text).splitlines()
    rows_out = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("|") and i + 1 < len(lines) and _is_separator(lines[i + 1]):
            headers = [_clean(c).lower() for c in _cells(lines[i])]
            j = i + 2
            body = []
            while j < len(lines) and lines[j].strip().startswith("|"):
                body.append(_cells(lines[j]))
                j += 1
            if set(required) <= set(headers):
                for cells in body:
                    row = {}
                    for idx, name in enumerate(headers):
                        row[name] = _clean(cells[idx]) if idx < len(cells) else ""
                    rows_out.append(row)
            i = j
        else:
            i += 1
    return rows_out


# ---------- paths ----------

def norm_rel(s):
    """Normalised POSIX repo-relative path: no backslashes, no leading ./, case-folded only on Windows."""
    s = str(s).strip().replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    s = posixpath.normpath(s) if s else ""
    if s == ".":
        s = ""
    return s.casefold() if CASE_FOLD else s


def is_enforcement(rel):
    low = rel.casefold()
    return low in ENFORCEMENT_FILES or low == ENFORCEMENT_DIR or low.startswith(ENFORCEMENT_DIR + "/")


def _existing_dir(path):
    p = Path(path)
    while not p.is_dir():
        if p.parent == p:
            return None
        p = p.parent
    return p


def git_info(path):
    """(toplevel, git common dir) of the checkout containing `path`, or None if it is not in git."""
    if path is None:
        return None
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(path),
                             capture_output=True, text=True, timeout=GIT_TIMEOUT)
        common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=str(path),
                                capture_output=True, text=True, timeout=GIT_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    if top.returncode != 0 or common.returncode != 0:
        return None
    top_p = Path(top.stdout.strip()).resolve()
    common_p = (Path(path) / common.stdout.strip()).resolve()
    return top_p, common_p


def _is_within(path, base):
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def locate(root, file_path):
    """Return (base, rel) for a target path, or None when it is outside every checkout of this repo.

    base is the repo root, or the top-level of a worktree of the same repo (same git common dir).
    """
    p = Path(file_path)
    if not p.is_absolute():
        p = root / p
    target = p.resolve()
    base = root.resolve()
    info = git_info(_existing_dir(target))
    repo = git_info(base)
    if info and repo and info[1] == repo[1]:
        base = info[0]
    elif not _is_within(target, base):
        return None
    try:
        rel = target.relative_to(base).as_posix()
    except ValueError:
        return None
    if rel in ("", "."):
        return None
    return base, rel


# ---------- plan gate helpers ----------

def plan_date(path):
    """The YYYY-MM-DD prefix of a plan filename, or None when it has none."""
    m = PLAN_DATE_RE.match(path.name)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
    except ValueError:
        return None


def recent_plans(root):
    """Plans whose filename date is within the window. Mtime is ignored: checkouts reset it."""
    plans_dir = root / "plans"
    if not plans_dir.is_dir():
        return []
    today = datetime.now(timezone.utc).date()
    out = []
    for p in sorted(plans_dir.glob("*.md")):
        d = plan_date(p)
        if d is None:
            continue
        age = (today - d).days
        if -1 <= age <= PLAN_WINDOW_DAYS:  # -1 allows a plan dated tomorrow in another timezone
            out.append(p)
    return out


def plan_rows(root):
    rows = []
    for plan in recent_plans(root):
        text = plan.read_text(encoding="utf-8", errors="replace")
        for row in parse_tables(text, ("step", "role", "model")):
            m = STEP_RE.match(row["step"])
            if not m:
                continue
            rows.append({
                "step": m.group(1),
                "role": row["role"],
                "model": row["model"],
                "plan": plan.relative_to(root).as_posix(),
            })
    return rows


def agent_model(root, subagent_type):
    if not subagent_type or not AGENT_TYPE_RE.match(subagent_type):
        return None
    path = root / ".claude" / "agents" / f"{subagent_type}.md"
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^model:\s*(\S+)", line)
        if m:
            return m.group(1).strip("'\"")
    return None


def resolve_model(root, tool_input, subagent_type):
    explicit = tool_input.get("model")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    return agent_model(root, subagent_type) or "unspecified"


def family_of(model):
    low = model.lower()
    for fam in FAMILIES:
        if fam in low:
            return fam
    return None


def model_ok(row_model, model):
    low = row_model.lower()
    if re.search(r"\b(its own|any)\b", low):
        return True
    fam = family_of(model)
    return fam is not None and re.search(rf"\b{fam}\b", low) is not None


def role_ok(role, subagent_type):
    """Does a plan row's Role accept this subagent_type?

    A role agent (builder, scout, tactician, reviewer) matches only when it is the first word of the Role
    cell, so "builder (not reviewer)" is a builder row. Any other type (general-purpose, missing,
    claude-code-guide, ...) is accepted only when the Role names it, or the Role says "its own" and its
    first word is not a role agent. general-purpose is never accepted for a row whose Role is a role agent.
    """
    low = role.lower()
    tokens = set(re.findall(r"[a-z0-9_.-]+", low))
    first = re.match(r"[a-z0-9_.-]+", low.strip())
    first = first.group(0) if first else ""
    if subagent_type in ROLE_TYPES:
        return first == subagent_type
    if first in ROLE_TYPES and subagent_type == "general-purpose":
        return False
    if subagent_type in tokens:
        return True
    if "its own" in low and first not in ROLE_TYPES:
        return subagent_type != "general-purpose"
    return False


def gate_agent(data):
    root = repo_root()
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        raise ValueError("tool_input is not an object")
    desc = str(tool_input.get("description") or "").strip()
    m = STEP_RE.match(desc)
    if not m:
        return False, ("Agent launch blocked: the description must start with a plan step id "
                       "(for example 'B15 write hooks'). Fix: add the step to an agent table in plans/ "
                       "and start the description with its id.")
    step = m.group(1)
    subagent_type = str(tool_input.get("subagent_type") or "general-purpose")
    model = resolve_model(root, tool_input, subagent_type)
    rows = [r for r in plan_rows(root) if r["step"] == step]
    if not rows:
        return False, (f"Agent launch blocked: step {step} is not in any agent table in plans/ "
                       f"changed in the last {PLAN_WINDOW_DAYS} days. Fix: add a row for {step} "
                       "(Step | Role | Model) to an agent table in plans/ before launching.")
    problems = []
    for row in rows:
        if not role_ok(row["role"], subagent_type):
            problems.append(f"{row['plan']} row {step} has Role '{row['role']}' "
                            f"but subagent_type is {subagent_type}")
        elif not model_ok(row["model"], model):
            problems.append(f"{row['plan']} row {step} has Model '{row['model']}' "
                            f"but this launch uses model {model}")
        else:
            return True, None
    first = rows[0]
    return False, (f"Agent launch blocked for step {step} in plan {first['plan']}: {problems[0]}. "
                   f"Fix: add a row for {step} to an agent table in plans/ that matches this launch, "
                   f"or launch with model {first['model']} and the role in that row.")


# ---------- edit gate ----------

def _clean_path(cell):
    return norm_rel(_clean(cell)) if cell else ""


def conductor_approved(base, rel):
    log = base / CONDUCTOR_LOG
    if not log.is_file():
        return False
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    text = log.read_text(encoding="utf-8", errors="replace")
    for row in parse_tables(text, ("date", "file", "reason")):
        reason = row["reason"].strip()
        if (row["date"] == today and _clean_path(row["file"]) == norm_rel(rel)
                and len(reason) >= CONDUCTOR_REASON_MIN_CHARS
                and len(reason.split()) >= CONDUCTOR_REASON_MIN_WORDS):
            return True
    return False


def edit_verdict(base, rel, data):
    """Apply the edit rules to one repo-relative path for the caller described by hook data."""
    agent_type = str(data.get("agent_type") or "")
    top = rel.split("/")[0].casefold()

    if not data.get("agent_id"):  # main session = conductor
        if (top in MAIN_PROTECTED or is_enforcement(rel)) and not conductor_approved(base, rel):
            return False, (f"Edit blocked: the conductor (main session) may not edit {rel}. "
                           "Fix: hand the change to a builder (launch it with a plan step id), or "
                           f"log it in {CONDUCTOR_LOG} with today's date (UTC), File '{rel}' and a Reason, then retry.")
        return True, None

    if top == "plans" and agent_type not in ("scout", "reviewer"):
        # Subagents never edit plan tables or the conductor log. A tactician may write its briefs.
        parts = rel.split("/")
        if len(parts) >= 4 and parts[2] == "briefs":
            return True, None
        return False, (f"Edit blocked: {agent_type or 'this'} agents may not edit {rel}. The conductor owns "
                       "plans/*.md and plans/conductor-edits.md; tacticians write briefs under "
                       "plans/<plan-name>/briefs/. Fix: send the table change to the conductor.")

    if is_enforcement(rel):
        return False, (f"Edit blocked: {rel} is enforcement and no agent may edit it, including "
                       f"{agent_type or 'this'} agents. Fix: the conductor logs the change in "
                       f"{CONDUCTOR_LOG} with today's date and a reason, then the main session makes it.")
    if agent_type == "scout":
        if rel.startswith("knowledge/") or rel.startswith("standards/proposals/"):
            return True, None
        return False, (f"Edit blocked: a scout may edit only knowledge/ and standards/proposals/, not {rel}. "
                       "Fix: write findings into knowledge/ using its template.")
    if agent_type == "reviewer":
        if rel.startswith("reviews/"):
            return True, None
        return False, (f"Edit blocked: a reviewer may edit only reviews/, not {rel}. "
                       "Fix: write the scorecard into reviews/ and report the problem to the conductor.")
    if rel.casefold() == FROZEN_FILE.casefold():
        return False, (f"Edit blocked: {rel} is not editable by {agent_type or 'this'} agents. "
                       "Thresholds change only by a conductor-reviewed proposal in standards/proposals/.")
    return True, None


def gate_edit(data):
    root = repo_root()
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        raise ValueError("tool_input is not an object")
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not target:
        return True, None
    loc = locate(root, str(target))
    if loc is None:
        return True, None
    base, rel = loc
    return edit_verdict(base, rel, data)


# ---------- bash writes (detected after the fact) ----------

def _file_state(path):
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if os.path.lexists(path):
        return "other"
    return "missing"


def _git_status_paths(cwd):
    """(toplevel, repo-relative paths listed by git status) for the checkout at cwd, or None."""
    info = git_info(cwd)
    if info is None:
        return None
    try:
        proc = subprocess.run(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                              cwd=str(cwd), capture_output=True, timeout=GIT_TIMEOUT * 3)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    tokens = proc.stdout.split(b"\0")
    paths = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if len(tok) < 4:
            continue
        xy = tok[:2].decode("ascii", "replace")
        paths.append(tok[3:].decode("utf-8", "surrogateescape"))
        if ("R" in xy or "C" in xy) and i < len(tokens):  # rename/copy: the original path follows
            if tokens[i]:
                paths.append(tokens[i].decode("utf-8", "surrogateescape"))
            i += 1
    return info[0], paths


def bash_state_path(tool_use_id):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(tool_use_id))[:200]
    return BASH_STATE_DIR / f"{safe}.json"


def _git_head(cwd):
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(cwd),
                              capture_output=True, text=True, timeout=GIT_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _git_committed_between(cwd, old, new):
    """Paths changed by commits between two HEADs (repo-relative), or [] if unknown."""
    try:
        proc = subprocess.run(["git", "diff", "--name-only", "-z", old, new], cwd=str(cwd),
                              capture_output=True, timeout=GIT_TIMEOUT * 3)
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    return [p.decode("utf-8", "surrogateescape") for p in proc.stdout.split(b"\0") if p]


def pre_bash(data):
    tool_use_id = data.get("tool_use_id")
    if not tool_use_id:
        return
    cwd = Path(str(data.get("cwd") or repo_root()))
    got = _git_status_paths(cwd)
    if got is None:
        return
    top, paths = got
    snap = {"cwd": str(cwd), "toplevel": str(top), "head": _git_head(cwd),
            "files": {p: _file_state(top / p) for p in paths}}
    BASH_STATE_DIR.mkdir(parents=True, exist_ok=True)
    bash_state_path(tool_use_id).write_text(json.dumps(snap), encoding="utf-8")


def changed_since(pre_files, top, post_paths):
    """Paths whose content or dirty/clean state differs between the snapshot and now."""
    post = {p: _file_state(top / p) for p in post_paths}
    changed = []
    for p in sorted(set(pre_files) | set(post)):
        if p in pre_files and p in post:
            if pre_files[p] != post[p]:
                changed.append(p)
        else:  # newly dirty, or dirty before and clean now
            changed.append(p)
    return changed


def post_bash(data):
    tool_use_id = data.get("tool_use_id")
    if not tool_use_id:
        return 0
    state = bash_state_path(tool_use_id)
    if not state.is_file():
        return 0
    try:
        snap = json.loads(state.read_text(encoding="utf-8"))
    finally:
        state.unlink(missing_ok=True)
    cwd = Path(str(data.get("cwd") or snap.get("cwd") or repo_root()))
    got = _git_status_paths(cwd)
    if got is None:
        return 0
    top, paths = got
    changed = changed_since(snap.get("files", {}), top, paths)
    old_head, new_head = snap.get("head"), _git_head(cwd)
    if old_head and new_head and old_head != new_head:
        # a command may commit files that are clean afterwards; count every file its commits touched
        changed = sorted(set(changed) | set(_git_committed_between(cwd, old_head, new_head)))
    if not changed:
        return 0
    if data.get("agent_id"):
        caller = str(data.get("agent_type") or "subagent")
    else:
        caller = "main session"
    violations = [p for p in changed if not edit_verdict(top, p, data)[0]]
    if not violations:
        return 0
    try:
        append_log(repo_root(), {
            "ts": now_iso(),
            "event": "bash_write_violation",
            "caller": caller,
            "files": violations,
        })
    except Exception:
        pass
    out = {
        "decision": "block",
        "reason": (f"{', '.join(violations)} were changed by a shell command but {caller} may not edit "
                   "them; revert them or hand the change to the right role"),
    }
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()
    return 0


# ---------- logger ----------

def numeric_usage(obj, path=(), in_usage=False, out=None):
    if out is None:
        out = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            key = str(key)
            flag = in_usage or "token" in key.lower() or "usage" in key.lower()
            name = path + (key,)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)) and flag:
                out[".".join(name)] = value
            elif isinstance(value, (dict, list)):
                numeric_usage(value, name, flag, out)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            name = path + (str(idx),)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)) and in_usage:
                out[".".join(name)] = value
            elif isinstance(value, (dict, list)):
                numeric_usage(value, name, in_usage, out)
    return out


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_log(root, entry):
    path = root / AGENT_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(entry) + "\n")


def log_post_agent(data):
    root = repo_root()
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    desc = str(tool_input.get("description") or "")
    m = STEP_RE.match(desc.strip())
    step = m.group(1) if m else None
    subagent_type = str(tool_input.get("subagent_type") or "general-purpose")
    model = resolve_model(root, tool_input, subagent_type)
    plan = None
    if step:
        rows = [r for r in plan_rows(root) if r["step"] == step]
        best = next((r for r in rows
                     if role_ok(r["role"], subagent_type) and model_ok(r["model"], model)),
                    rows[0] if rows else None)
        plan = best["plan"] if best else None
    entry = {
        "ts": now_iso(),
        "event": "agent_done",
        "step": step,
        "subagent_type": subagent_type,
        "model": model,
        "description": desc,
        "plan": plan,
        "usage": numeric_usage(data.get("tool_response")),
        "caller": str(data.get("agent_type") or "main"),
    }
    append_log(root, entry)


def log_subagent_stop(data):
    entry = {
        "ts": now_iso(),
        "event": "subagent_stop",
        "agent_id": data.get("agent_id"),
        "agent_type": data.get("agent_type"),
    }
    append_log(repo_root(), entry)


def _run_post_bash():
    try:
        return post_bash(read_stdin())
    except Exception:  # detection must never break the tool call
        return 0


HANDLERS = {
    "pre-agent": lambda: run_gate("pre-agent", gate_agent),
    "pre-edit": lambda: run_gate("pre-edit", gate_edit),
    "pre-bash": lambda: run_logger(pre_bash),
    "post-bash": _run_post_bash,
    "post-agent": lambda: run_logger(log_post_agent),
    "subagent-stop": lambda: run_logger(log_subagent_stop),
}


def main(argv):
    if len(argv) < 2 or argv[1] not in HANDLERS:
        sys.stderr.write("usage: agent_hooks.py {" + ",".join(HANDLERS) + "}\n")
        return 2
    return HANDLERS[argv[1]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
