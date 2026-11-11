# MCP server

`plane-mcp` exposes the aircraft platform to Claude as MCP tools over stdio. Claude can list,
read, validate, measure, export and save designs as YAML without hand-editing HTML or files.
Logic lives in `core/aircraft_platform/`; the server is `core/aircraft_platform/mcp_server.py`.

## Tools

- `list_designs()` - id, name, status and morphology of every design.
- `get_design(design_id)` - raw plane.yaml text.
- `validate_design(design_id, max_tier=5)` - scorecard across validation tiers 0-5.
- `get_mass_properties(design_id)` - total mass, CG, inertia and per-component mass.
- `export_design(design_id, format)` - write glb, stl or json to `build/`; returns the paths.
- `save_design(design_id, yaml_text, overwrite=False)` - schema-check then write designs/<id>/plane.yaml.
- `get_schema()` - the plane.yaml JSON schema.
- `get_standards()` - design standards plus the agent standard.

## Setup

Install the MCP extra inside the repo, then register the server with Claude Code:

```
pip install -e ".[mcp]"
claude mcp add aircraft-platform -- plane-mcp
```

Run the `claude mcp add` command from the repo root.

For Claude Desktop, add this to `claude_desktop_config.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "aircraft-platform": {
      "command": "plane-mcp"
    }
  }
}
```
