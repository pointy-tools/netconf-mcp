#!/usr/bin/env python3
"""Collect and write a normalized Arista EOS snapshot."""

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
from netconf_mcp.vendors.arista import AristaCollector


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect a normalized Arista EOS config snapshot.")
    parser.add_argument("--inventory", required=True, help="Path to inventory JSON containing the live Arista target.")
    parser.add_argument("--target-ref", default="target://lab/arista", help="Target ref to snapshot.")
    parser.add_argument(
        "--output",
        default="arista-snapshot.json",
        help="Path to write normalized snapshot JSON.",
    )
    parser.add_argument(
        "--hostkey-policy",
        choices=("strict", "accept-new"),
        default="strict",
        help="Host key policy for the live NETCONF session.",
    )
    return parser.parse_args()


def _load_target(inventory_path: Path, target_ref: str) -> dict:
    inventory = load_fixture(inventory_path)
    for target in inventory.get("targets", []):
        if target.get("target_ref") == target_ref:
            return target
    raise SystemExit(f"Target {target_ref} not found in {inventory_path}")


def main() -> None:
    args = _parse_args()
    target = _load_target(Path(args.inventory), args.target_ref)
    collector = AristaCollector()
    snapshot = collector.collect_snapshot(target, hostkey_policy=args.hostkey_policy)
    output_path = Path(args.output)
    output_path.write_text(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote normalized snapshot to {output_path}")
    print(f"Interfaces: {len(snapshot.interfaces)}")
    print(f"LAGs: {len(snapshot.lags)}")
    print(f"VLANs: {len(snapshot.vlans)}")
    print(f"VRFs: {len(snapshot.vrfs)}")
    print(f"Static routes: {len(snapshot.static_routes)}")
    print(f"Prefix sets: {len(snapshot.prefix_sets)}")
    print(f"Routing policies: {len(snapshot.routing_policies)}")
    print(f"ACL sets: {len(snapshot.acl_sets)}")
    print(f"ACL bindings: {len(snapshot.acl_bindings)}")
    print(f"MLAG: {'enabled' if snapshot.mlag else 'disabled'}")
    print(f"MLAG interfaces: {len(snapshot.mlag_interfaces)}")
    print(f"EVPN instances: {len(snapshot.evpn_instances)}")
    print(f"VXLAN mappings: {len(snapshot.vxlan_mappings)}")
    if snapshot.warnings:
        print(f"Warnings: {len(snapshot.warnings)}")
        for warning in snapshot.warnings:
            print(f"  - {warning}")


if __name__ == "__main__":
    main()
