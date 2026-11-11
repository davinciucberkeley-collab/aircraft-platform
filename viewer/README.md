# Viewer

Static site that displays every design in `designs/` with no per-design HTML. It only reads generated data.

```
plane build-index --out viewer/data
python3 -m http.server -d viewer      # http://localhost:8000
```

`viewer/data/` is a build output (gitignored). Adding a design means adding `designs/<name>/plane.yaml` and re-running `build-index`; the viewer picks it up.

## Data contract (`data/`)
- `index.json`: `{generated, designs: [{id, name, status, morphology, accepted, mass_g, cg_mm, glb, scorecard, mass, tiers:{"0":"PASS",...}, error}]}`. A non-null `error` is shown in place of the model.
- `<id>.glb`: metres, y-up, one named node per component (node name = component id).
- `<id>.scorecard.json`: `{design_id, accepted, tiers:[{tier, name, status, results:[{check_id, status, message, criterion, data}]}]}`. A result whose `data.pair` is two component ids highlights both on click.
- `<id>.mass.json`: `{mass_g, cg_mm, inertia_gmm2, per_component:[{id, mass_g, cg_mm}]}`.

## Features
Sidebar with text and VTOL-method filters; 3D view with click-to-highlight and CG marker; scorecard with FAIL rows first; compare mode (two viewports plus table of mass, CG, tiers and key numbers). Deep links: `#d=<id>` or `#a=<id>&b=<id>`.

three.js 0.160.0 loads from cdn.jsdelivr.net, so the page needs network access. Deployed by `.github/workflows/pages.yml`.
