---
name: research
description: Use when asked to research DIY builds, papers, standards or concepts for the knowledge base; runs Haiku scouts against fixed templates. Recon mode targets gaps in the morphological chart.
---

# Research and recon

## Goal
New, template-conforming files in `knowledge/`, each with real, opened sources.

## Agents
| Step | Role | Model |
|---|---|---|
| Choose topics or gaps, write scout briefs | Tactician | Sonnet (or Conductor if briefs are trivial) |
| Gather into template | Scout | Haiku, several in parallel, disjoint topics |
| Spot-check sources | Reviewer | Opus (one) — sample 20% of entries |

## Templates
- DIY project → `knowledge/TEMPLATE-diy-project.md` → `knowledge/diy-projects/<id>.md`
- Paper / standard / doc → `knowledge/TEMPLATE-source.md` → `knowledge/sources/<prefix>-<id>.md`
- Concept evidence ("does X work?") → structure of `knowledge/concepts/tailsitter-evidence.md`

## Modes
**Survey:** "find N builds about <topic>". One scout per disjoint topic.

**Recon (gap-driven):**
1. List chart cells: `knowledge/morphological-chart.yaml` options × tags in `knowledge/diy-projects/*.md` and `designs/*/plane.yaml` morphology.
2. Pick cells with zero internal designs and few external examples.
3. Brief one scout per cell: "Find builds or papers combining <option A> + <option B>; if none exist, say so" — an empty result is a finding.
4. Add unexplored combinations to `knowledge/concepts/unexplored.md` as candidates for `design-concept`.

## Scout brief must include (builder-ready bar)
Exact output path and template; queries to start from; "only URLs you opened"; "own words, ≤10 words quoted"; "unknown instead of guessing"; stop after ~20 searches and report shortfalls.

## Pass check
- [ ] Every new file parses (frontmatter) and fills every template field
- [ ] Reviewer spot-check found no invented URLs or numbers

## Stop rules
- A source is paywalled or blocked → record it with `verified: false`; don't paraphrase from memory.
