"""Generate source-of-truth proposals from normalized TNSR snapshots."""

from __future__ import annotations

from difflib import unified_diff
import json
from pathlib import Path
from typing import Any

from netconf_mcp.vendors.tnsr import (
    ACLRuleRecord,
    ACLRulesetRecord,
    BFDSessionRecord,
    BGPNeighborRecord,
    BGPSnapshot,
    InterfaceRecord,
    InterfacePolicyBindingRecord,
    NATRuleRecord,
    NATRulesetRecord,
    PrefixListRecord,
    PrefixListRuleRecord,
    RouteMapRecord,
    RouteMapRuleRecord,
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
                "bfd": item.bfd,
                "peer_group": item.peer_group,
                "remote_asn": item.remote_asn,
                "description": item.description,
                "update_source": item.update_source,
                "ebgp_multihop_max_hops": item.ebgp_multihop_max_hops,
            }
            for item in snapshot.bgp.neighbors
        ),
        key=lambda item: item["peer"],
    )

    prefix_lists = sorted(
        (
            {
                "name": item.name,
                "rules": [
                    {
                        "sequence": rule.sequence,
                        "action": rule.action,
                        "prefix": rule.prefix,
                    }
                    for rule in sorted(item.rules, key=lambda rule: int(rule.sequence) if rule.sequence.isdigit() else rule.sequence)
                ],
            }
            for item in snapshot.prefix_lists
        ),
        key=lambda item: item["name"],
    )

    route_maps = sorted(
        (
            {
                "name": item.name,
                "rules": [
                    {
                        "sequence": rule.sequence,
                        "policy": rule.policy,
                        "match_ip_prefix_list": rule.match_ip_prefix_list,
                        "set_as_path_prepend": rule.set_as_path_prepend,
                    }
                    for rule in sorted(item.rules, key=lambda rule: int(rule.sequence) if rule.sequence.isdigit() else rule.sequence)
                ],
            }
            for item in snapshot.route_maps
        ),
        key=lambda item: item["name"],
    )

    bfd_sessions = sorted(
        (
            {
                "name": item.name,
                "enabled": item.enabled,
                "interface": item.interface,
                "local_ip_address": item.local_ip_address,
                "peer_ip_address": item.peer_ip_address,
                "desired_min_tx": item.desired_min_tx,
                "required_min_rx": item.required_min_rx,
                "detect_multiplier": item.detect_multiplier,
            }
            for item in snapshot.bfd_sessions
        ),
        key=lambda item: item["name"],
    )

    nat_rulesets = sorted(
        (
            {
                "name": item.name,
                "description": item.description,
                "rules": [
                    {
                        "sequence": rule.sequence,
                        "description": rule.description,
                        "direction": rule.direction,
                        "dynamic": rule.dynamic,
                        "algorithm": rule.algorithm,
                        "match_from_prefix": rule.match_from_prefix,
                        "translation_interface": rule.translation_interface,
                    }
                    for rule in sorted(item.rules, key=lambda rule: int(rule.sequence) if rule.sequence.isdigit() else rule.sequence)
                ],
            }
            for item in snapshot.nat_rulesets
        ),
        key=lambda item: item["name"],
    )

    acl_rulesets = sorted(
        (
            {
                "name": item.name,
                "description": item.description,
                "rules": [
                    {
                        "sequence": rule.sequence,
                        "description": rule.description,
                        "direction": rule.direction,
                        "ip_version": rule.ip_version,
                        "pass_action": rule.pass_action,
                        "stateful": rule.stateful,
                        "protocol_set": rule.protocol_set,
                        "from_prefix": rule.from_prefix,
                        "to_prefix": rule.to_prefix,
                    }
                    for rule in sorted(item.rules, key=lambda rule: int(rule.sequence) if rule.sequence.isdigit() else rule.sequence)
                ],
            }
            for item in snapshot.acl_rulesets
        ),
        key=lambda item: item["name"],
    )

    interface_policy_bindings = sorted(
        (
            {
                "interface": item.interface,
                "nat_ruleset": item.nat_ruleset,
                "filter_ruleset": item.filter_ruleset,
            }
            for item in snapshot.interface_policy_bindings
        ),
        key=lambda item: item["interface"],
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
                "vrf_id": snapshot.bgp.vrf_id,
                "ipv4_unicast_enabled": snapshot.bgp.ipv4_unicast_enabled,
                "ebgp_requires_policy": snapshot.bgp.ebgp_requires_policy,
                "log_neighbor_changes": snapshot.bgp.log_neighbor_changes,
                "network_import_check": snapshot.bgp.network_import_check,
                "keepalive_seconds": snapshot.bgp.keepalive_seconds,
                "hold_time_seconds": snapshot.bgp.hold_time_seconds,
                "neighbors": neighbors,
                "network_announcements": _sorted_unique(snapshot.bgp.network_announcements),
            },
            "routing_policy": {
                "prefix_lists": prefix_lists,
                "route_maps": route_maps,
            },
            "bfd": {
                "sessions": bfd_sessions,
            },
            "nat": {
                "rulesets": nat_rulesets,
            },
            "acl": {
                "rulesets": acl_rulesets,
                "interface_bindings": interface_policy_bindings,
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
            vrf_id=payload.get("bgp", {}).get("vrf_id"),
            ipv4_unicast_enabled=payload.get("bgp", {}).get("ipv4_unicast_enabled"),
            ebgp_requires_policy=payload.get("bgp", {}).get("ebgp_requires_policy"),
            log_neighbor_changes=payload.get("bgp", {}).get("log_neighbor_changes"),
            network_import_check=payload.get("bgp", {}).get("network_import_check"),
            keepalive_seconds=payload.get("bgp", {}).get("keepalive_seconds"),
            hold_time_seconds=payload.get("bgp", {}).get("hold_time_seconds"),
            neighbors=[
                BGPNeighborRecord(
                    peer=item["peer"],
                    enabled=item.get("enabled"),
                    bfd=item.get("bfd"),
                    peer_group=item.get("peer_group"),
                    remote_asn=item.get("remote_asn"),
                    description=item.get("description"),
                    update_source=item.get("update_source"),
                    ebgp_multihop_max_hops=item.get("ebgp_multihop_max_hops"),
                )
                for item in payload.get("bgp", {}).get("neighbors", [])
            ],
            network_announcements=list(payload.get("bgp", {}).get("network_announcements", [])),
        ),
        prefix_lists=[
            PrefixListRecord(
                name=item["name"],
                rules=[
                    PrefixListRuleRecord(
                        sequence=rule["sequence"],
                        action=rule.get("action"),
                        prefix=rule.get("prefix"),
                    )
                    for rule in item.get("rules", [])
                ],
            )
            for item in payload.get("prefix_lists", [])
        ],
        route_maps=[
            RouteMapRecord(
                name=item["name"],
                rules=[
                    RouteMapRuleRecord(
                        sequence=rule["sequence"],
                        policy=rule.get("policy"),
                        match_ip_prefix_list=rule.get("match_ip_prefix_list"),
                        set_as_path_prepend=rule.get("set_as_path_prepend"),
                    )
                    for rule in item.get("rules", [])
                ],
            )
            for item in payload.get("route_maps", [])
        ],
        bfd_sessions=[
            BFDSessionRecord(
                name=item["name"],
                enabled=item.get("enabled"),
                interface=item.get("interface"),
                local_ip_address=item.get("local_ip_address"),
                peer_ip_address=item.get("peer_ip_address"),
                desired_min_tx=item.get("desired_min_tx"),
                required_min_rx=item.get("required_min_rx"),
                detect_multiplier=item.get("detect_multiplier"),
            )
            for item in payload.get("bfd_sessions", [])
        ],
        nat_rulesets=[
            NATRulesetRecord(
                name=item["name"],
                description=item.get("description"),
                rules=[
                    NATRuleRecord(
                        sequence=rule["sequence"],
                        description=rule.get("description"),
                        direction=rule.get("direction"),
                        dynamic=rule.get("dynamic"),
                        algorithm=rule.get("algorithm"),
                        match_from_prefix=rule.get("match_from_prefix"),
                        translation_interface=rule.get("translation_interface"),
                    )
                    for rule in item.get("rules", [])
                ],
            )
            for item in payload.get("nat_rulesets", [])
        ],
        acl_rulesets=[
            ACLRulesetRecord(
                name=item["name"],
                description=item.get("description"),
                rules=[
                    ACLRuleRecord(
                        sequence=rule["sequence"],
                        description=rule.get("description"),
                        direction=rule.get("direction"),
                        ip_version=rule.get("ip_version"),
                        pass_action=rule.get("pass_action"),
                        stateful=rule.get("stateful"),
                        protocol_set=rule.get("protocol_set"),
                        from_prefix=rule.get("from_prefix"),
                        to_prefix=rule.get("to_prefix"),
                    )
                    for rule in item.get("rules", [])
                ],
            )
            for item in payload.get("acl_rulesets", [])
        ],
        interface_policy_bindings=[
            InterfacePolicyBindingRecord(
                interface=item["interface"],
                nat_ruleset=item.get("nat_ruleset"),
                filter_ruleset=item.get("filter_ruleset"),
            )
            for item in payload.get("interface_policy_bindings", [])
        ],
        raw_sections=dict(payload.get("raw_sections", {})),
    )
    return build_managed_tnsr_config(snapshot)


def _proposal_summary(existing: dict[str, Any] | None, candidate: dict[str, Any]) -> list[str]:
    current_interfaces = len(existing.get("config", {}).get("interfaces", [])) if existing else 0
    current_routes = len(existing.get("config", {}).get("routing", {}).get("static_routes", [])) if existing else 0
    current_neighbors = len(existing.get("config", {}).get("bgp", {}).get("neighbors", [])) if existing else 0
    current_prefix_lists = len(existing.get("config", {}).get("routing_policy", {}).get("prefix_lists", [])) if existing else 0
    current_route_maps = len(existing.get("config", {}).get("routing_policy", {}).get("route_maps", [])) if existing else 0
    current_bfd_sessions = len(existing.get("config", {}).get("bfd", {}).get("sessions", [])) if existing else 0
    current_nat_rulesets = len(existing.get("config", {}).get("nat", {}).get("rulesets", [])) if existing else 0
    current_acl_rulesets = len(existing.get("config", {}).get("acl", {}).get("rulesets", [])) if existing else 0

    candidate_interfaces = len(candidate["config"]["interfaces"])
    candidate_routes = len(candidate["config"]["routing"]["static_routes"])
    candidate_neighbors = len(candidate["config"]["bgp"]["neighbors"])
    candidate_prefix_lists = len(candidate["config"]["routing_policy"]["prefix_lists"])
    candidate_route_maps = len(candidate["config"]["routing_policy"]["route_maps"])
    candidate_bfd_sessions = len(candidate["config"]["bfd"]["sessions"])
    candidate_nat_rulesets = len(candidate["config"]["nat"]["rulesets"])
    candidate_acl_rulesets = len(candidate["config"]["acl"]["rulesets"])

    return [
        f"Managed file: {'update' if existing else 'create'}",
        f"Interfaces: {current_interfaces} -> {candidate_interfaces}",
        f"Static routes: {current_routes} -> {candidate_routes}",
        f"BGP neighbors: {current_neighbors} -> {candidate_neighbors}",
        f"Prefix lists: {current_prefix_lists} -> {candidate_prefix_lists}",
        f"Route maps: {current_route_maps} -> {candidate_route_maps}",
        f"BFD sessions: {current_bfd_sessions} -> {candidate_bfd_sessions}",
        f"NAT rulesets: {current_nat_rulesets} -> {candidate_nat_rulesets}",
        f"ACL rulesets: {current_acl_rulesets} -> {candidate_acl_rulesets}",
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
