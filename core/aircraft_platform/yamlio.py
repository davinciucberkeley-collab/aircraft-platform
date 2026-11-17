"""Round-trip YAML editing that keeps comments and the repo's layout (used by `plane new` and Plane Studio)."""
from __future__ import annotations

import io

from ruamel.yaml import YAML


def rt_yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def load(text: str):
    return rt_yaml().load(text)


def dump(doc) -> str:
    buf = io.StringIO()
    rt_yaml().dump(doc, buf)
    return buf.getvalue()
