"""Generate source-of-truth proposals from normalized TNSR snapshots."""

from __future__ import annotations

from difflib import unified_diff
import json
from pathlib import Path
from typing import Any

from netconf_mcp.vendors.tnsr import (
    BGPNeighborRecord,
    BGPSnapshot,
    InterfaceRecord,
    StaticRouteRecord,
    TNSRSnapshot,
)


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted(dict.fromkeys(values))


def _render_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_managed_tnsr_config(snapshot: TNSRSnapshot) -> dict[str, Any]:
    """Project a live snapshot into a stable repo-managed config shape."""

    interfaces = sorted(
        (
            {
                "name": item.name,
                "kind": item.kind,
                "enabled": item.enabled,
                "description": item.description,
                "ipv4_addresses": _sorted_unique(item.ipv4_addresses),
            }
            for item in snapshot.interfaces
        ),
        key=lambda item: (item["kind"], item["name"]),
    )

    static_routes = sorted(
        (
            {
                "table": item.table,
                "destination_prefix": item.destination_prefix,
                "next_hop": item.next_hop,
                "interface": item.interface,
            }
            for item in snapshot.static_routes
        ),
        key=lambda item: (item["table"], item["destination_prefix"], item["interface"] or "", item["next_hop"] or ""),
    )

    neighbors = sorted(
        (
            {
                "peer": item.peer,
                "enabled": item.enabled,
                "peer_group": item.peer_group,
                "remote_asn": item.remote_asn,
                "description": item.description,
                "update_source": item.update_source,
            }
            for item in snapshot.bgp.neighbors
        ),
        key=lambda item: item["peer"],
    )

    capabilities = _sorted_unique(snapshot.capabilities)
    module_inventory = sorted(
        (
            dict(item)
            for item in snapshot.module_inventory
        ),
        key=lambda item: (
            str(item.get("name") or item.get("module") or ""),
            str(item.get("revision") or ""),
        ),
    )

    return {
        "schema_version": "tnsr-managed-config-v1",
        "device": {
            "name": snapshot.device.get("name"),
            "vendor": snapshot.device.get("vendor"),
            "os": snapshot.device.get("os"),
            "host": snapshot.device.get("host"),
            "site": snapshot.device.get("site"),
            "role": snapshot.device.get("role") or [],
            "target_ref": snapshot.target_ref,
        },
        "config": {
            "interfaces": interfaces,
            "routing": {
                "static_routes": static_routes,
            },
            "bgp": {
                "asn": snapshot.bgp.asn,
                "router_id": snapshot.bgp.router_id,
                "neighbors": neighbors,
                "network_announcements": _sorted_unique(snapshot.bgp.network_announcements),
            },
        },
        "observed_state": {
            "netconf_capabilities": capabilities,
            "yang_modules": module_inventory,
        },
        "metadata": {
            "generated_from_snapshot_type": snapshot.snapshot_type,
            "collected_at_utc": snapshot.collected_at_utc,
        },
    }


def build_managed_tnsr_config_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Helper for CLI/tests that start from JSON payloads."""

    snapshot = TNSRSnapshot(
        snapshot_type=payload["snapshot_type"],
        collected_at_utc=payload["collected_at_utc"],
        target_ref=payload["target_ref"],
        device=payload["device"],
        capabilities=list(payload.get("capabilities", [])),
        module_inventory=list(payload.get("module_inventory", [])),
        interfaces=[
            InterfaceRecord(
                name=item["name"],
                kind=item["kind"],
                enabled=item.get("enabled"),
                description=item.get("description"),
                ipv4_addresses=list(item.get("ipv4_addresses", [])),
            )
            for item in payload.get("interfaces", [])
        ],
        static_routes=[
            StaticRouteRecord(
                table=item["table"],
                destination_prefix=item["destination_prefix"],
                next_hop=item.get("next_hop"),
                interface=item.get("interface"),
            )
            for item in payload.get("static_routes", [])
        ],
        bgp=BGPSnapshot(
            asn=payload.get("bgp", {}).get("asn"),
            router_id=payload.get("bgp", {}).get("router_id"),
            neighbors=[
                BGPNeighborRecord(
                    peer=item["peer"],
                    enabled=item.get("enabled"),
                    peer_group=item.get("peer_group"),
                    remote_asn=item.get("remote_asn"),
                    description=item.get("description"),
                    update_source=item.get("update_source"),
                )
                for item in payload.get("bgp", {}).get("neighbors", [])
            ],
            network_announcements=list(payload.get("bgp", {}).get("network_announcements", [])),
        ),
        raw_sections=dict(payload.get("raw_sections", {})),
    )
    return build_managed_tnsr_config(snapshot)


def _proposal_summary(existing: dict[str, Any] | None, candidate: dict[str, Any]) -> list[str]:
    current_interfaces = len(existing.get("config", {}).get("interfaces", [])) if existing else 0
    current_routes = len(existing.get("config", {}).get("routing", {}).get("static_routes", [])) if existing else 0
    current_neighbors = len(existing.get("config", {}).get("bgp", {}).get("neighbors", [])) if existing else 0

    candidate_interfaces = len(candidate["config"]["interfaces"])
    candidate_routes = len(candidate["config"]["routing"]["static_routes"])
    candidate_neighbors = len(candidate["config"]["bgp"]["neighbors"])

    return [
        f"Managed file: {'update' if existing else 'create'}",
        f"Interfaces: {current_interfaces} -> {candidate_interfaces}",
        f"Static routes: {current_routes} -> {candidate_routes}",
        f"BGP neighbors: {current_neighbors} -> {candidate_neighbors}",
    ]


def build_tnsr_proposal_artifacts(
    *,
    managed_path: Path,
    candidate_config: dict[str, Any],
) -> tuple[str, str]:
    """Return a proposal markdown document and the candidate JSON text."""

    existing = _load_json(managed_path)
    current_text = _render_json(existing) if existing is not None else ""
    candidate_text = _render_json(candidate_config)
    diff_lines = list(
        unified_diff(
            current_text.splitlines(),
            candidate_text.splitlines(),
            fromfile=str(managed_path),
            tofile=f"{managed_path} (proposed)",
            lineterm="",
        )
    )
    diff_text = "\n".join(diff_lines) if diff_lines else "No changes."

    summary = _proposal_summary(existing, candidate_config)
    proposal_lines = [
        "# TNSR Managed Config Proposal",
        "",
        f"Target file: `{managed_path}`",
        "",
        "## Summary",
        "",
    ]
    proposal_lines.extend(f"- {line}" for line in summary)
    proposal_lines.extend(
        [
            "",
            "## Diff",
            "",
            "```diff",
            diff_text,
            "```",
            "",
        ]
    )
    return "\n".join(proposal_lines), candidate_text
