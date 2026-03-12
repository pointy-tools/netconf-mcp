#!/usr/bin/env python3
"""Show an agent-friendly TNSR domain view from a live target or snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from netconf_mcp.utils.redact import load_fixture
from netconf_mcp.vendors.tnsr import TNSRCollector
from netconf_mcp.vendors.tnsr_views import DOMAIN_CHOICES, build_tnsr_domain_view


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show a concise TNSR domain view.")
    parser.add_argument("--domain", choices=DOMAIN_CHOICES, required=True, help="Domain to display.")
    parser.add_argument("--snapshot", default=None, help="Existing normalized TNSR snapshot JSON.")
    parser.add_argument("--inventory", default=None, help="Inventory JSON for a live TNSR target.")
    parser.add_argument("--target-ref", default="target://lab/tnsr", help="Target ref to inspect.")
    parser.add_argument(
        "--hostkey-policy",
        choices=("strict", "accept-new"),
        default="strict",
        help="Host key policy for live collection.",
    )
    return parser.parse_args()


def _load_target(inventory_path: Path, target_ref: str) -> dict:
    inventory = load_fixture(inventory_path)
    for target in inventory.get("targets", []):
        if target.get("target_ref") == target_ref:
            return target
    raise SystemExit(f"Target {target_ref} not found in {inventory_path}")


def _load_snapshot(args: argparse.Namespace) -> dict:
    if args.snapshot:
        return load_fixture(Path(args.snapshot))
    if args.inventory:
        target = _load_target(Path(args.inventory), args.target_ref)
        snapshot = TNSRCollector().collect(target, hostkey_policy=args.hostkey_policy)
        return snapshot.to_dict()
    raise SystemExit("Provide either --snapshot or --inventory.")


def main() -> None:
    args = _parse_args()
    snapshot = _load_snapshot(args)
    view = build_tnsr_domain_view(snapshot, args.domain)
    print(json.dumps(view, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
