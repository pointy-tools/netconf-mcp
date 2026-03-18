#!/usr/bin/env python3
"""Capture live NETCONF discovery and read evidence for fixture creation."""

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
from netconf_mcp.utils.redact import load_fixture, redact_mapping


CAPTURE_SCHEMA = "netconf-live-capture-v1"
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
        description="Capture live read evidence suitable for fixture artifacts.",
    )
    parser.add_argument(
        "--inventory",
        required=True,
        help="Path to an inventory JSON containing a live-ssh target entry.",
    )
    parser.add_argument(
        "--target-ref",
        default="target://lab/tnsr",
        help="Target ref to capture from the inventory.",
    )
    parser.add_argument(
        "--hostkey-policy",
        choices=("strict", "accept-new"),
        default="strict",
        help="Host key policy for the live NETCONF session.",
    )
    parser.add_argument(
        "--credential-ref",
        default="cred://external/live-target",
        help="Credential reference to pass to open_session (redacted in output).",
    )
    parser.add_argument(
        "--profile",
        choices=("custom", "tnsr"),
        default="tnsr",
        help="Probe profile for config reads.",
    )
    parser.add_argument(
        "--config-xpath",
        action="append",
        default=[],
        help="Optional config read xpath; repeat for multiple probes.",
    )
    parser.add_argument(
        "--oper-xpath",
        action="append",
        default=[],
        help="Optional operational read xpath; repeat for multiple probes.",
    )
    parser.add_argument(
        "--fixture-root",
        default="tests/fixtures",
        help="Fixture root for runtime loading (default: tests/fixtures).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write deterministic JSON capture artifact.",
    )
    return parser.parse_args()


def _load_target(inventory_path: Path, target_ref: str) -> dict[str, Any]:
    inventory = load_fixture(inventory_path)
    for item in inventory.get("targets", []):
        if item.get("target_ref") == target_ref:
            return item
    raise SystemExit(f"Target {target_ref} not found in {inventory_path}")


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _config_probes(profile: str, extra: list[str]) -> list[str]:
    probes: list[str] = []
    if profile == "tnsr":
        probes.extend(TNSR_CONFIG_PROBES)
    probes.extend(extra)
    return _dedupe([probe for probe in probes if probe])


def _sanitize_datastore_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    trimmed = dict(payload)
    trimmed.pop("raw_xml", None)
    return trimmed


def _trim_session_payload(payload: dict[str, Any]) -> dict[str, Any]:
    keys_to_remove = {"session_ref", "session_id", "hello_latency_ms", "framed_version"}
    return {k: v for k, v in payload.items() if k not in keys_to_remove}


def _read_entry(tool_name: str, xpath: str, result: dict[str, Any]) -> dict[str, Any]:
    if result["status"] == "ok":
        payload = _sanitize_datastore_payload(result["data"])  # type: ignore[index]
        return {
            "tool": tool_name,
            "xpath": xpath,
            "status": "ok",
            "policy_decision": result.get("policy_decision", "allowed"),
            "payload": payload,
            "evidence_refs": result.get("evidence_refs", []),
        }

    return {
        "tool": tool_name,
        "xpath": xpath,
        "status": "error",
        "policy_decision": result.get("policy_decision", "blocked"),
        "error": result.get("error", {}),
        "evidence_refs": result.get("evidence_refs", []),
    }


def _collect_capture_payload(
    args: argparse.Namespace,
    *,
    live_client: Any | None = None,
) -> dict[str, Any]:
    inventory_path = Path(args.inventory)
    runtime = create_server(
        Path(args.fixture_root),
        inventory_path=inventory_path,
        live_client=live_client,
    )
    tool = runtime.get_server()
    target = _load_target(inventory_path, args.target_ref)

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": args.target_ref,
            "arguments": {
                "credential_ref": args.credential_ref,
                "hostkey_policy": args.hostkey_policy,
            },
        }
    )
    if open_session["status"] != "ok":
        raise RuntimeError(f"Failed to open session for {args.target_ref}")
    session_ref = open_session["data"]["session_ref"]

    capabilities = tool._tools["netconf.discover_capabilities"]({"session_ref": session_ref})
    if capabilities["status"] != "ok":
        raise RuntimeError("Capability discovery failed")

    yang_library = tool._tools["yang.get_library"]({"session_ref": session_ref})
    if yang_library["status"] != "ok":
        raise RuntimeError("YANG library collection failed")

    monitoring = tool._tools["netconf.get_monitoring"](
        {
            "session_ref": session_ref,
            "arguments": {"scope": "all"},
        }
    )
    if monitoring["status"] != "ok":
        raise RuntimeError("Monitoring collection failed")

    config_paths = _config_probes(args.profile, list(args.config_xpath))
    oper_paths = _dedupe(list(args.oper_xpath))

    config_reads = [
        _read_entry(
            "datastore.get_config",
            xpath,
            tool._tools["datastore.get_config"](
                {
                    "session_ref": session_ref,
                    "arguments": {"datastore": "running", "xpath": xpath},
                }
            ),
        )
        for xpath in config_paths
    ]

    operational_reads = [
        _read_entry(
            "datastore.get",
            xpath,
            tool._tools["datastore.get"](
                {
                    "session_ref": session_ref,
                    "arguments": {"datastore": "operational", "xpath": xpath},
                }
            ),
        )
        for xpath in oper_paths
    ]

    return {
        "capture_schema": CAPTURE_SCHEMA,
        "target_ref": args.target_ref,
        "target": target,
        "session": _trim_session_payload(open_session["data"]),
        "capabilities": capabilities["data"],
        "yang_library": _sanitize_datastore_payload(yang_library["data"]),
        "monitoring": _sanitize_datastore_payload(monitoring["data"]),
        "reads": {
            "config": config_reads,
            "operational": operational_reads,
        },
    }


def _write_capture(output_path: Path, payload: dict[str, Any]) -> None:
    sanitized = redact_mapping(payload)
    output_path.write_text(
        json.dumps(sanitized, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> None:
    args = _parse_args()
    payload = _collect_capture_payload(args)
    output_path = Path(args.output)
    _write_capture(output_path, payload)
    print(f"Wrote live capture artifact: {output_path}")


if __name__ == "__main__":
    main()
