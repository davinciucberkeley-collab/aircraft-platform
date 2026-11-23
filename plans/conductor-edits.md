# Conductor edits

The main session (conductor) may not edit core/, tests/, designs/, schema/ or .github/ directly. The edit gate in tools/agent_hooks.py allows such an edit only when this table has a row with today's date (UTC), the repo-relative file path and a non-empty Reason. Each row is evidence for review. Prefer handing the change to a builder.

| Date | File | Reason |
|---|---|---|
| 2026-11-23 | .claude/agents/scout.md | Agent standard v0.2: scouts now research how others solved a problem and record options in the approaches template |
| 2026-11-23 | .claude/agents/reviewer.md | Agent standard v0.2: a fresh reviewer for each batch, and each review asks what could be removed |
| 2026-11-23 | .claude/agents/tactician.md | Agent standard v0.2: fix briefs consider removing, modifying and consolidating before adding; two failed fixes stop |
| 2026-11-23 | .claude/agents/advisor.md | Agent standard v0.2 adds the advisor role as a read-only Opus agent definition for drifting work |
| 2026-11-23 | .claude/agents/auditor.md | Agent standard v0.2 adds the auditor role as a read-only Haiku agent that checks long runs for stalls |
