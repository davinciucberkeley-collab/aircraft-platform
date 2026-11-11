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
| design-standards.md#static-margin | PASS | 11% MAC, within 5–15% |
| manufacturing.md#laser-cut-max-sheet | N/A | no laser-cut parts |

## Blocking issues
1. ...

## Non-blocking suggestions
1. ...
```

Rules:
- A design is **accepted** only when every automated tier it claims is PASS and no blocking criterion is FAIL.
- Every row cites a criterion that exists in `standards/`. If you want to judge something that has no criterion, propose the criterion in "Non-blocking suggestions" instead.
