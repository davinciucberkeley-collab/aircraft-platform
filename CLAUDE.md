# Instructions for Claude in this repo

- Designs live only as `designs/<id>/plane.yaml` conforming to `schema/plane.schema.json`. Never make a one-off HTML page or artifact for a design; the viewer renders every design from generated data.
- Use the `plane` CLI or the `aircraft-platform` MCP tools; don't reimplement validation, mass or export logic.
- A design is done only when `plane validate designs/<id>` exits 0. Fix the design, not the threshold. Thresholds change only in `standards/design-standards.yaml`, with a source.
- Multi-agent work follows `standards/agents.md`: declare the agent table in `plans/` before launching anything; Haiku for anything that meets the builder-ready bar; one reused Opus reviewer that scores against `standards/review-scorecard.md`.
- Skills are in `skills/`; new ones follow `skills/make-skill/SKILL.md`.
- Research goes into `knowledge/` using its templates. Only cite sources you opened; never invent URLs or numbers.
