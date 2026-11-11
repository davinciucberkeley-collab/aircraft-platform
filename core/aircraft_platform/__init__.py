"""Aircraft design platform core: one library behind the CLI, the MCP server and the viewer."""
from .design import Design, Scorecard, load_design, list_designs
from .checks import validate
from .mass import mass_properties

__all__ = ["Design", "Scorecard", "load_design", "list_designs", "validate", "mass_properties"]
__version__ = "0.1.0"
