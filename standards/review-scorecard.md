# Review Scorecard Format v0.1

Every review — human or agent — returns this. No free-form "looks good."

```markdown
# Review: <design id or artifact path> @ <git commit>

## Automated (from `plane validate --tier all`)
| Tier | Result | Details |
|---|---|---|
| 0 Schema | PASS | |
| 1 Geometry | FAIL | wing_l overlaps fuselage by 4 mm at x=120 |
| ... | | |

## Criteria (judgment items)
| Criterion (link into standards/) | Result | Reason |
|---|---|---|
| design-standards.yaml#static_margin | PASS | 11% MAC, within 5–15% |
| manufacturing.yaml#jacobs-laser | N/A | no laser-cut parts |

## Blocking issues
1. ...

## Non-blocking suggestions
1. ...

## Process
| Check | Criterion (standards/agents.md) | Result | Details |
|---|---|---|---|
| Agents run, by role and model (from plans/agent-log.jsonl) | `#how-this-is-enforced` | PASS | builder haiku B15 x2; reviewer opus R1 x1 |
| Launches not in the plan table | `#declaring-agents-up-front` | PASS | none |
| Conductor edits (plans/conductor-edits.md) | `#how-this-is-enforced` | PASS | each file listed, with whether it was justified |
| Citation check (`plane check-citations`) | `#how-this-is-enforced` | PASS | 0 FAIL, 0 WARN |
| Cost check (builder-ready work done by Opus or Sonnet) | `#cost-check` | PASS | none |
```

Rules:
- Process rows are scored against `standards/agents.md`, not against the design. A FAIL there is listed under "Blocking issues".
- A design is **accepted** only when no automated result is FAIL or SKIP and no blocking criterion is FAIL (the validator's `accepted` flag applies this).
- Every row cites a criterion that exists in `standards/`. Link forms: `design-standards.yaml#<leaf key>` (e.g. `static_margin`), `manufacturing.yaml#<machine id>`, `schema/plane.schema.json`, or `requirements.<field>` for a design's own requirement. A test resolves every criterion the validator emits. If you want to judge something that has no criterion, propose the criterion in "Non-blocking suggestions" instead.
