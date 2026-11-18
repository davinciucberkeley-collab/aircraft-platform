"""Tests for tools/agent_hooks.py, run as subprocesses against a temp repo layout."""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import uuid

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "agent_hooks.py"

PLAN = """# Plan: test

| Step | Role | Model | Output | Pass criterion |
|---|---|---|---|---|
| B15 | Builder | haiku | hooks | tests |
| S9 | Scout (claude-code-guide) | its own | facts | links |
| R1 | Reviewer | opus (reused) | review | scorecard |
| S10 | Facts (its own) | its own | facts | links |
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


# ---------- round 13: role rows ----------

def test_general_purpose_on_builder_row_denied(root):
    kind, reason = decision(launch(root, "B15 write hooks", subagent_type="general-purpose", model="haiku"))
    assert kind == "deny" and "Role" in reason


def test_general_purpose_on_reviewer_row_denied(root):
    kind, _ = decision(launch(root, "R1 review", subagent_type="general-purpose", model="opus"))
    assert kind == "deny"


def test_claude_code_guide_on_its_own_row_allowed(root):
    assert decision(launch(root, "S10 facts", subagent_type="claude-code-guide")) == ("allow", "")


def test_general_purpose_on_its_own_row_denied(root):
    kind, _ = decision(launch(root, "S10 facts", subagent_type="general-purpose"))
    assert kind == "deny"


def test_claude_code_guide_on_scout_row_naming_it_allowed(root):
    assert decision(launch(root, "S9 facts", subagent_type="claude-code-guide")) == ("allow", "")


def test_claude_code_guide_on_builder_row_denied(root):
    kind, _ = decision(launch(root, "B15 write hooks", subagent_type="claude-code-guide"))
    assert kind == "deny"


# ---------- round 13: enforcement files ----------

def test_builder_editing_hook_script_denied(root):
    kind, reason = decision(edit(root, "tools/agent_hooks.py", "a4", "builder"))
    assert kind == "deny" and "enforcement" in reason


def test_builder_editing_claude_settings_denied(root):
    assert decision(edit(root, ".claude/settings.json", "a4", "builder"))[0] == "deny"


def test_main_session_editing_hook_script_denied_without_row(root):
    assert decision(edit(root, "tools/agent_hooks.py"))[0] == "deny"


def test_main_session_editing_hook_script_allowed_with_row(root):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (root / "plans" / "conductor-edits.md").write_text(
        "| Date | File | Reason |\n|---|---|---|\n"
        f"| {today} | tools/agent_hooks.py | fix tests |\n",
        encoding="utf-8",
    )
    assert decision(edit(root, "tools/agent_hooks.py")) == ("allow", "")


def test_main_session_editing_settings_allowed_with_dated_row(root):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (root / "plans" / "conductor-edits.md").write_text(
        "| Date | File | Reason |\n|---|---|---|\n"
        f"| {today} | `./.claude/settings.json` | hook fallback |\n",
        encoding="utf-8",
    )
    assert decision(edit(root, ".claude/settings.json")) == ("allow", "")
    assert decision(edit(root, ".claude/agents/builder.md"))[0] == "deny"


def test_github_row_matches(root):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (root / "plans" / "conductor-edits.md").write_text(
        "| Date | File | Reason |\n|---|---|---|\n"
        f"| {today} | .github/workflows/validate.yml | add step |\n",
        encoding="utf-8",
    )
    assert decision(edit(root, ".github/workflows/validate.yml")) == ("allow", "")


# ---------- round 13: settings and worktrees ----------

SETTINGS = Path(__file__).resolve().parents[1] / ".claude" / "settings.json"
GATES = {"pre-agent", "pre-edit", "pre-bash"}


def test_settings_commands_have_fallback_and_gates_block():
    cfg = json.loads(SETTINGS.read_text(encoding="utf-8"))
    seen = set()
    for event, groups in cfg["hooks"].items():
        for group in groups:
            for hook in group["hooks"]:
                m = re.fullmatch(
                    r'python3 "\$CLAUDE_PROJECT_DIR/tools/agent_hooks\.py" (\S+) \|\| '
                    r'python "\$CLAUDE_PROJECT_DIR/tools/agent_hooks\.py" \1',
                    hook["command"])
                assert m, hook["command"]
                sub = m.group(1)
                seen.add(sub)
                if sub in GATES:
                    assert hook.get("onFailure") == "block", sub
                else:
                    assert "onFailure" not in hook, sub
    assert seen == {"pre-agent", "pre-edit", "pre-bash", "post-agent", "post-bash", "subagent-stop"}


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    "-c", "commit.gpgsign=false", *args],
                   cwd=str(cwd), check=True, capture_output=True)


@pytest.fixture
def git_repo(root):
    (root / "core").mkdir()
    (root / "core" / "x.py").write_text("x = 1\n", encoding="utf-8")
    (root / "knowledge").mkdir()
    (root / "knowledge" / "n.md").write_text("n\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _edit_abs(root, abs_path, agent_id=None, agent_type=None):
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Edit",
               "tool_input": {"file_path": str(abs_path)}, "session_id": "s", "cwd": str(root)}
    if agent_id:
        payload["agent_id"] = agent_id
        payload["agent_type"] = agent_type
    return run_hook("pre-edit", root, payload)


def test_worktree_path_gated(git_repo, tmp_path):
    wt = tmp_path / "wt"
    _git(git_repo, "worktree", "add", "-q", str(wt), "-b", "feat")
    assert decision(_edit_abs(git_repo, wt / "core" / "x.py"))[0] == "deny"
    assert decision(_edit_abs(git_repo, wt / "knowledge" / "n.md")) == ("allow", "")


def test_other_repo_path_allowed(git_repo, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    (other / "core").mkdir()
    (other / "core" / "y.py").write_text("y = 1\n", encoding="utf-8")
    _git(other, "init", "-q")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "init")
    assert decision(_edit_abs(git_repo, other / "core" / "y.py")) == ("allow", "")


# ---------- round 13: bash writes after the fact ----------

def _bash(sub, root, tool_use_id, agent_id=None, agent_type=None):
    payload = {"hook_event_name": "PreToolUse" if sub == "pre-bash" else "PostToolUse",
               "tool_name": "Bash", "tool_input": {"command": "sed -i s/1/2/ core/x.py"},
               "tool_use_id": tool_use_id, "cwd": str(root), "session_id": "s"}
    if agent_id:
        payload["agent_id"] = agent_id
        payload["agent_type"] = agent_type
    return run_hook(sub, root, payload)


def test_bash_post_flags_scout_core_write(git_repo):
    tid = uuid.uuid4().hex
    pre = _bash("pre-bash", git_repo, tid, "a5", "scout")
    assert pre.returncode == 0 and pre.stdout == b""
    (git_repo / "core" / "x.py").write_text("x = 2\n", encoding="utf-8")
    post = _bash("post-bash", git_repo, tid, "a5", "scout")
    assert post.returncode == 0
    out = json.loads(post.stdout.decode("utf-8"))
    assert out["decision"] == "block"
    assert "core/x.py" in out["reason"] and "scout" in out["reason"]
    entry = json.loads((git_repo / "plans" / "agent-log.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert entry["event"] == "bash_write_violation"
    assert entry["caller"] == "scout" and entry["files"] == ["core/x.py"]


def test_bash_post_silent_for_scout_knowledge_write(git_repo):
    tid = uuid.uuid4().hex
    _bash("pre-bash", git_repo, tid, "a6", "scout")
    (git_repo / "knowledge" / "n.md").write_text("changed\n", encoding="utf-8")
    post = _bash("post-bash", git_repo, tid, "a6", "scout")
    assert post.returncode == 0 and post.stdout == b""


def test_bash_post_flags_main_session_core_write(git_repo):
    tid = uuid.uuid4().hex
    _bash("pre-bash", git_repo, tid)
    (git_repo / "core" / "x.py").write_text("x = 3\n", encoding="utf-8")
    out = json.loads(_bash("post-bash", git_repo, tid).stdout.decode("utf-8"))
    assert out["decision"] == "block" and "core/x.py" in out["reason"]


def test_bash_post_without_snapshot_is_silent(git_repo):
    post = _bash("post-bash", git_repo, uuid.uuid4().hex, "a7", "scout")
    assert post.returncode == 0 and post.stdout == b""
