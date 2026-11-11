---
name: review-design
description: Use when asked to review a design, concept, PR or artifact; produces a scorecard against named standards instead of an open-ended opinion.
---

# Review against standards

## Goal
`reviews/<date>-<design-id>.md` in the format of `standards/review-scorecard.md`, ending in accepted / not accepted.

## Agents
One Reviewer (Opus) per task, reused for every item in that task via SendMessage. Never spawn one reviewer per item.

## Steps
1. Run `plane validate designs/<id> --format md` (MCP: `validate_design`). Paste the scorecard as the "Automated" section unchanged.
2. For each judgment item, find the criterion in `standards/` (design-standards.yaml, manufacturing.yaml, agents.md). Score PASS / FAIL / N/A with a one-line reason and the criterion link.
3. Judge only what validators can't: is the lineage recorded, does the README state the question, are joint ratings plausible for the stated method, is anything modelled too crudely to trust (e.g. static margin ignores the fuselage).
4. Anything you'd like to judge that has no criterion → a "Non-blocking suggestion" proposing the criterion. Never block on an unwritten rule.
5. Write the file and commit it on the design's branch.

## Pass check
- [ ] Every row cites a criterion that exists in `standards/`
- [ ] Automated section is the unedited validator output
- [ ] Verdict follows the rule in review-scorecard.md

## Stop rules
- The validator crashes → report the crash; don't review by hand around it.
