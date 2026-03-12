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

    def __init__(self, root: Path, inventory_path: Path | None = None):
        self.root = Path(root)
        self.inventory_path = Path(inventory_path or self.root / "inventory.json")

    def inventory(self) -> list[dict[str, Any]]:
        payload = load_fixture(self.inventory_path)
        return payload["targets"]

    def profile(self, key: str) -> SimulatedProfile:
        path = self.root / "profiles" / f"{key}.json"
        return SimulatedProfile(key=key, data=load_fixture(path))
