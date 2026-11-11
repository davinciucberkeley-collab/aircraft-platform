"""Loading design files and the shared result types every check returns."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schema" / "plane.schema.json"
STANDARDS_PATH = REPO_ROOT / "standards" / "design-standards.yaml"
DESIGNS_DIR = REPO_ROOT / "designs"

PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"


@dataclass
class Design:
    data: dict[str, Any]
    path: Path | None = None

    @property
    def id(self) -> str:
        return self.data.get("id", "<no id>")

    @property
    def components(self) -> list[dict]:
        return self.data.get("components", [])

    def component(self, cid: str) -> dict:
        for c in self.components:
            if c["id"] == cid:
                return c
        raise KeyError(cid)

    @property
    def base_dir(self) -> Path:
        return self.path.parent if self.path else Path.cwd()


@dataclass
class CheckResult:
    check_id: str          # e.g. "T1.connectivity"
    status: str            # PASS / FAIL / WARN / SKIP
    message: str
    criterion: str = ""    # link into standards/, e.g. "design-standards.yaml#static_margin"
    data: dict = field(default_factory=dict)


@dataclass
class TierReport:
    tier: int
    name: str
    results: list[CheckResult]

    @property
    def status(self) -> str:
        s = [r.status for r in self.results]
        if FAIL in s:
            return FAIL
        if not s or all(x == SKIP for x in s):
            return SKIP
        if WARN in s:
            return WARN
        return PASS


@dataclass
class Scorecard:
    design_id: str
    tiers: list[TierReport]

    @property
    def accepted(self) -> bool:
        return all(t.status != FAIL for t in self.tiers)

    def to_dict(self) -> dict:
        return {
            "design_id": self.design_id,
            "accepted": self.accepted,
            "tiers": [
                {"tier": t.tier, "name": t.name, "status": t.status,
                 "results": [asdict(r) for r in t.results]}
                for t in self.tiers
            ],
        }

    def to_markdown(self) -> str:
        lines = [f"# Scorecard: {self.design_id}", "",
                 f"**Accepted:** {'yes' if self.accepted else 'no'}", "",
                 "| Tier | Status | Check | Result | Criterion |", "|---|---|---|---|---|"]
        for t in self.tiers:
            for r in t.results:
                lines.append(f"| {t.tier} {t.name} | {t.status} | {r.check_id} | {r.status}: {r.message} | {r.criterion} |")
        return "\n".join(lines) + "\n"


def load_design(path: str | Path) -> Design:
    p = Path(path)
    if p.is_dir():
        p = p / "plane.yaml"
    text = p.read_text()
    data = json.loads(text) if p.suffix == ".json" else yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"{p}: top level must be a mapping")
    return Design(data=data, path=p.resolve())


def load_standards() -> dict:
    return yaml.safe_load(STANDARDS_PATH.read_text())


def list_designs() -> list[Path]:
    return sorted(DESIGNS_DIR.glob("*/plane.yaml"))
