# Conductor edits

The main session (conductor) may not edit core/, tests/, designs/, schema/ or .github/ directly. The edit gate in tools/agent_hooks.py allows such an edit only when this table has a row with today's date (UTC), the repo-relative file path and a non-empty Reason. Each row is evidence for review. Prefer handing the change to a builder.

| Date | File | Reason |
|---|---|---|
