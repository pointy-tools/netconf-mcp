#!/usr/bin/env python3
"""Run a read-only MCP smoke flow against a live NETCONF lab target."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from netconf_mcp.mcp.server import create_server


TNSR_CONFIG_PROBES = [
    "/interfaces-config/interface/name",
    "/interfaces-config/interface[name='LAN']/enabled",
    "/interfaces-config/interface[name='LAN']/ipv4/address/ip",
    "/interfaces-config/interface[name='WAN']/enabled",
    "/interfaces-config/interface[name='WAN']/ipv4/address/ip",
    "/host-if-config/interface[name='eth0']/enabled",
    "/ssh-server-config/host/netconf-subsystem/enable",
    "/ssh-server-config/host/netconf-subsystem/port",
    "/route-table-config/static-routes/route-table/name",
    "/route-table-config/static-routes/route-table/ipv4-routes/route/destination-prefix",
    "/route-config/dynamic/bgp/routers/router/asn",
    "/route-config/dynamic/bgp/routers/router/router-id",
    "/route-config/dynamic/bgp/routers/router/neighbors/neighbor/peer",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only NETCONF MCP smoke runner for a live lab target."
    )
    parser.add_argument(
        "--inventory",
        required=True,
        help="Path to an inventory JSON file with a live-ssh target entry.",
    )
    parser.add_argument(
        "--target-ref",
        default="target://lab/tnsr",
        help="Target ref to probe from the inventory.",
    )
    parser.add_argument(
        "--oper-xpath",
        default=None,
        help="Optional operational xpath for datastore.get.",
    )
    parser.add_argument(
        "--config-xpath",
        default=None,
        help="Optional config xpath for datastore.get_config.",
    )
    parser.add_argument(
        "--hostkey-policy",
        choices=("strict", "accept-new"),
        default="strict",
        help="Host key policy for session open. Use accept-new for initial lab probing.",
    )
    parser.add_argument(
        "--profile",
        choices=("custom", "tnsr"),
        default="tnsr",
        help="Probe profile to run. TNSR is the default primary target profile.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print compact summaries for successful probe values instead of full payloads.",
    )
    return parser.parse_args()


def _dump_step(label: str, payload: dict[str, Any]) -> None:
    print(f"\n## {label}")
    print(json.dumps(payload, indent=2, sort_keys=True))


def _require_ok(label: str, payload: dict[str, Any]) -> None:
    _dump_step(label, payload)
    if payload.get("status") != "ok":
        raise SystemExit(1)


def _config_probes(args: argparse.Namespace) -> list[str]:
    probes: list[str] = []
    if args.profile == "tnsr":
        probes.extend(TNSR_CONFIG_PROBES)
    if args.config_xpath:
        probes.append(args.config_xpath)
    # preserve order while dropping duplicates
    return list(dict.fromkeys(probes))


def _print_probe_result(xpath: str, payload: dict[str, Any], *, summary_only: bool) -> None:
    if not summary_only:
        _dump_step(f"datastore.get_config {xpath}", payload)
        return

    print(f"\n## datastore.get_config {xpath}")
    if payload.get("status") == "ok":
        value = payload.get("data", {}).get("value")
        print(json.dumps({"status": "ok", "xpath": xpath, "value": value}, indent=2, sort_keys=True))
        return
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "xpath": xpath,
                "error": payload.get("error", {}),
            },
            indent=2,
            sort_keys=True,
        )
    )


def main() -> None:
    args = _parse_args()
    inventory_path = Path(args.inventory)
    runtime = create_server(Path("tests/fixtures"), inventory_path=inventory_path)
    tool = runtime.get_server()

    inventory = tool._tools["inventory.list_targets"](
        {"arguments": {"filter": {"status": "online"}}}
    )
    _require_ok("inventory.list_targets", inventory)

    matching = [
        item for item in inventory["data"]["targets"] if item["target_ref"] == args.target_ref
    ]
    if not matching:
        print(f"Target {args.target_ref} not found in filtered inventory.")
        raise SystemExit(1)

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": args.target_ref,
            "arguments": {
                "credential_ref": "cred://external/live-target",
                "hostkey_policy": args.hostkey_policy,
            },
        }
    )
    _require_ok("netconf.open_session", open_session)
    session_ref = open_session["data"]["session_ref"]

    capabilities = tool._tools["netconf.discover_capabilities"](
        {"session_ref": session_ref}
    )
    _require_ok("netconf.discover_capabilities", capabilities)

    yang_library = tool._tools["yang.get_library"]({"session_ref": session_ref})
    _require_ok("yang.get_library", yang_library)

    monitoring = tool._tools["netconf.get_monitoring"](
        {"session_ref": session_ref, "arguments": {"scope": "all"}}
    )
    _require_ok("netconf.get_monitoring", monitoring)

    for config_xpath in _config_probes(args):
        config = tool._tools["datastore.get_config"](
            {
                "session_ref": session_ref,
                "arguments": {
                    "datastore": "running",
                    "xpath": config_xpath,
                },
            }
        )
        _print_probe_result(config_xpath, config, summary_only=args.summary_only)

    if args.oper_xpath:
        operational = tool._tools["datastore.get"](
            {
                "session_ref": session_ref,
                "arguments": {
                    "datastore": "operational",
                    "xpath": args.oper_xpath,
                },
            }
        )
        _dump_step("datastore.get", operational)

    print("\nSmoke flow completed.")


if __name__ == "__main__":
    main()
