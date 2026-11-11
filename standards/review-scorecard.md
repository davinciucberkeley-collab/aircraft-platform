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
```

Rules:
- A design is **accepted** only when no automated result is FAIL or SKIP and no blocking criterion is FAIL (the validator's `accepted` flag applies this).
- Every row cites a criterion that exists in `standards/`. Link forms: `design-standards.yaml#<leaf key>` (e.g. `static_margin`), `manufacturing.yaml#<machine id>`, `schema/plane.schema.json`, or `requirements.<field>` for a design's own requirement. A test resolves every criterion the validator emits. If you want to judge something that has no criterion, propose the criterion in "Non-blocking suggestions" instead.
