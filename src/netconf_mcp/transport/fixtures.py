"""Fixture-backed profile and target loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from netconf_mcp.utils.redact import load_fixture


@dataclass
class SimulatedProfile:
    key: str
    data: dict[str, Any]


class FixtureRepository:
    """Loads immutable fixture inputs for simulator-based operation."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def inventory(self) -> list[dict[str, Any]]:
        payload = load_fixture(self.root / "inventory.json")
        return payload["targets"]

    def profile(self, key: str) -> SimulatedProfile:
        path = self.root / "profiles" / f"{key}.json"
        return SimulatedProfile(key=key, data=load_fixture(path))
