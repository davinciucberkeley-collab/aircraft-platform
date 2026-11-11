"""Shared fixtures for validator tests. Mutations start from the example design."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Callable

import pytest

from aircraft_platform.checks import validate
from aircraft_platform.design import DESIGNS_DIR, Design, Scorecard, load_design

EXAMPLE_PATH = DESIGNS_DIR / "example-tailsitter-wing" / "plane.yaml"


def statuses(scorecard: Scorecard, check_id: str) -> list[str]:
    """Statuses of every result with this check_id, across all tiers."""
    return [r.status for t in scorecard.tiers for r in t.results if r.check_id == check_id]


@pytest.fixture
def example() -> Path:
    return EXAMPLE_PATH


@pytest.fixture
def mutate(example: Path) -> Callable[[Callable[[dict], None]], Scorecard]:
    def _mutate(fn: Callable[[dict], None]) -> Scorecard:
        base = load_design(example)
        data = copy.deepcopy(base.data)
        fn(data)
        design = Design(data=data, path=example)
        return validate(design)

    return _mutate
