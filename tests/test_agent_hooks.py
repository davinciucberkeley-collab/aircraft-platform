"""Tests for tools/agent_hooks.py, run as subprocesses against a temp repo layout."""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "agent_hooks.py"

PLAN = """# Plan: test

| Step | Role | Model | Output | Pass criterion |
|---|---|---|---|---|
| B15 | Builder | haiku | hooks | tests |
| S9 | Scout (claude-code-guide) | its own | facts | links |
| R1 | Reviewer | opus (reused) | review | scorecard |
"""

BUILDER_MD = """---
name: builder
model: haiku
---
body
"""


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "repo"
    (r / "plans").mkdir(parents=True)
    (r / ".claude" / "agents").mkdir(parents=True)
    (r / ".claude" / "agents" / "builder.md").write_text(BUILDER_MD, encoding="utf-8")
    (r / "plans" / "2026-11-18-test.md").write_text(PLAN, encoding="utf-8")
    return r


def run_hook(sub, root, payload=None, raw=None, cwd=None):
    env = dict(os.environ, AGENT_HOOKS_ROOT=str(root))
    stdin = raw if raw is not None else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), sub],
        input=stdin.encode("utf-8"),
        capture_output=True,
        env=env,
        cwd=str(cwd or root.parent),
    )
    return proc


def decision(proc):
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    out = proc.stdout.decode("utf-8").strip()
    if not out:
        return "allow", ""
    data = json.loads(out)["hookSpecificOutput"]
    assert data["permissionDecision"] == "deny"
    return "deny", data["permissionDecisionReason"]


def launch(root, description, subagent_type="builder", model=None, **extra):
    ti = {"description": description, "prompt": "do it", "subagent_type": subagent_type}
    if model:
        ti["model"] = model
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": ti,
               "session_id": "s", "cwd": str(root)}
    payload.update(extra)
    return run_hook("pre-agent", root, payload)


def edit(root, rel, agent_id=None, agent_type=None):
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Edit",
               "tool_input": {"file_path": str(root / rel)}, "session_id": "s", "cwd": str(root)}
    if agent_id:
        payload["agent_id"] = agent_id
        payload["agent_type"] = agent_type
    return run_hook("pre-edit", root, payload)


# ---------- plan gate ----------

def test_unknown_step_denied(root):
    kind, reason = decision(launch(root, "B99 write something"))
    assert kind == "deny" and "B99" in reason


def test_description_without_step_denied(root):
    kind, _ = decision(launch(root, "write something"))
    assert kind == "deny"


def test_known_step_wrong_model_denied(root):
    kind, reason = decision(launch(root, "B15 write hooks", model="sonnet"))
    assert kind == "deny" and "B15" in reason and "plan" in reason


def test_builder_with_scout_row_denied(root):
    kind, reason = decision(launch(root, "S9 find facts", subagent_type="builder", model="haiku"))
    assert kind == "deny" and "Role" in reason


def test_matching_launch_allowed_with_frontmatter_model(root):
    assert decision(launch(root, "B15 write hooks")) == ("allow", "")


def test_matching_launch_allowed_with_explicit_model(root):
    assert decision(launch(root, "B15 write hooks", model="haiku")) == ("allow", "")


def test_plan_older_than_14_days_denied(root):
    old = time.time() - 15 * 86400
    os.utime(root / "plans" / "2026-11-18-test.md", (old, old))
    kind, reason = decision(launch(root, "B15 write hooks"))
    assert kind == "deny" and "B15" in reason


def test_malformed_stdin_denied_for_gate(root):
    kind, reason = decision(run_hook("pre-agent", root, raw="{not json"))
    assert kind == "deny" and "failed closed" in reason


# ---------- edit gate ----------

def test_main_session_editing_core_denied(root):
    kind, reason = decision(edit(root, "core/x.py"))
    assert kind == "deny" and "conductor" in reason


def test_main_session_editing_core_allowed_with_todays_row(root):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (root / "plans" / "conductor-edits.md").write_text(
        "| Date | File | Reason |\n|---|---|---|\n"
        f"| {today} | core/x.py | hotfix for review round |\n",
        encoding="utf-8",
    )
    assert decision(edit(root, "core/x.py")) == ("allow", "")


def test_main_session_row_for_other_date_still_denied(root):
    (root / "plans" / "conductor-edits.md").write_text(
        "| Date | File | Reason |\n|---|---|---|\n"
        "| 2000-01-01 | core/x.py | old |\n",
        encoding="utf-8",
    )
    kind, _ = decision(edit(root, "core/x.py"))
    assert kind == "deny"


def test_main_session_outside_protected_allowed(root):
    assert decision(edit(root, "plans/notes.md")) == ("allow", "")


def test_scout_editing_core_denied_knowledge_allowed(root):
    assert decision(edit(root, "core/x.py", "a1", "scout"))[0] == "deny"
    assert decision(edit(root, "knowledge/x.md", "a1", "scout")) == ("allow", "")


def test_reviewer_editing_reviews_allowed_designs_denied(root):
    assert decision(edit(root, "reviews/r.md", "a2", "reviewer")) == ("allow", "")
    assert decision(edit(root, "designs/d/plane.yaml", "a2", "reviewer"))[0] == "deny"


def test_builder_editing_frozen_thresholds_denied(root):
    kind, reason = decision(edit(root, "standards/design-standards.yaml", "a3", "builder"))
    assert kind == "deny" and "design-standards" in reason


def test_builder_editing_claude_dir_denied(root):
    assert decision(edit(root, ".claude/settings.json", "a3", "builder"))[0] == "deny"


def test_builder_editing_core_allowed(root):
    assert decision(edit(root, "core/x.py", "a3", "builder")) == ("allow", "")


def test_malformed_stdin_denied_for_edit_gate(root):
    kind, _ = decision(run_hook("pre-edit", root, raw="][", ))
    assert kind == "deny"


# ---------- logger ----------

def test_post_agent_writes_log_line(root):
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "tool_input": {"description": "B15 write hooks", "subagent_type": "builder"},
        "tool_response": {"usage": {"input_tokens": 10, "output_tokens": 5}, "totalTokens": 15,
                          "content": "done"},
        "session_id": "s",
    }
    proc = run_hook("post-agent", root, payload)
    assert proc.returncode == 0 and proc.stdout == b""
    lines = (root / "plans" / "agent-log.jsonl").read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[-1])
    assert entry["event"] == "agent_done"
    assert entry["step"] == "B15"
    assert entry["plan"] == "plans/2026-11-18-test.md"
    assert entry["model"] == "haiku"
    assert entry["caller"] == "main"
    assert entry["usage"]["totalTokens"] == 15
    assert entry["usage"]["usage.input_tokens"] == 10
    assert entry["ts"]


def test_subagent_stop_writes_log_line(root):
    proc = run_hook("subagent-stop", root, {"agent_id": "a9", "agent_type": "builder"})
    assert proc.returncode == 0
    entry = json.loads((root / "plans" / "agent-log.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert entry == {**entry, "event": "subagent_stop", "agent_id": "a9", "agent_type": "builder"}


def test_logger_malformed_stdin_exits_zero_silently(root):
    proc = run_hook("post-agent", root, raw="{not json")
    assert proc.returncode == 0 and proc.stdout == b""
    assert not (root / "plans" / "agent-log.jsonl").exists()
