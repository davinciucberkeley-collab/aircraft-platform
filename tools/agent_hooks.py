#!/usr/bin/env python3
"""Claude Code hooks that enforce standards/agents.md.

Subcommands read hook JSON on stdin:
  pre-agent      plan gate before an Agent launch (fails closed)
  pre-edit       edit gate before Edit/Write/NotebookEdit (fails closed)
  post-agent     appends an agent_done line to plans/agent-log.jsonl (never blocks)
  subagent-stop  appends a subagent_stop line to plans/agent-log.jsonl (never blocks)

Stdlib only. Set AGENT_HOOKS_ROOT to override the repo root (tests only).
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PLAN_WINDOW_DAYS = 14
STEP_RE = re.compile(r"^([A-Z]+\d+[a-z]?)\b")
ROLE_TYPES = ("builder", "scout", "tactician", "reviewer")
FAMILIES = ("haiku", "sonnet", "opus")
MAIN_PROTECTED = ("core", "tests", "designs", "schema", ".github")
CONDUCTOR_LOG = "plans/conductor-edits.md"
AGENT_LOG = "plans/agent-log.jsonl"
FROZEN_FILE = "standards/design-standards.yaml"
AGENT_TYPE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


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


def parse_tables(text, required):
    """Return rows (dicts keyed by lower-cased header) of every table whose header has all `required` columns."""
    lines = text.splitlines()
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


# ---------- plan gate helpers ----------

def recent_plans(root):
    plans_dir = root / "plans"
    if not plans_dir.is_dir():
        return []
    cutoff = time.time() - PLAN_WINDOW_DAYS * 86400
    return [p for p in sorted(plans_dir.glob("*.md")) if p.stat().st_mtime >= cutoff]


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
    if subagent_type not in ROLE_TYPES:
        return True
    return subagent_type in role.lower()


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

def repo_rel(root, file_path):
    p = Path(file_path)
    if not p.is_absolute():
        p = root / p
    try:
        rel = p.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    rel_s = rel.as_posix()
    return None if rel_s in ("", ".") else rel_s


def _clean_path(cell):
    return _clean(cell).replace("\\", "/").lstrip("./") if cell else ""


def conductor_approved(root, rel):
    log = root / CONDUCTOR_LOG
    if not log.is_file():
        return False
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    text = log.read_text(encoding="utf-8", errors="replace")
    for row in parse_tables(text, ("date", "file", "reason")):
        if (row["date"] == today and _clean_path(row["file"]) == rel
                and row["reason"].strip()):
            return True
    return False


def gate_edit(data):
    root = repo_root()
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        raise ValueError("tool_input is not an object")
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not target:
        return True, None
    rel = repo_rel(root, str(target))
    if rel is None:
        return True, None
    top = rel.split("/")[0]
    agent_type = str(data.get("agent_type") or "")

    if not data.get("agent_id"):  # main session = conductor
        if top in MAIN_PROTECTED and not conductor_approved(root, rel):
            return False, (f"Edit blocked: the conductor (main session) may not edit {rel}. "
                           "Fix: hand the change to a builder (launch it with a plan step id), or "
                           f"log it in {CONDUCTOR_LOG} with today's date (UTC), File '{rel}' and a Reason, then retry.")
        return True, None

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
    if rel == FROZEN_FILE or top == ".claude":
        return False, (f"Edit blocked: {rel} is not editable by {agent_type or 'this'} agents. "
                       "Thresholds change only by a conductor-reviewed proposal in standards/proposals/; "
                       ".claude/ rules are set by the conductor.")
    return True, None


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


HANDLERS = {
    "pre-agent": lambda: run_gate("pre-agent", gate_agent),
    "pre-edit": lambda: run_gate("pre-edit", gate_edit),
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
