"""Agent-friendly domain views over normalized Arista EOS snapshots."""

from __future__ import annotations

from typing import Any


DOMAIN_CHOICES = (
    "interfaces",
    "vlans",
    "vrfs",
    "lags",
    "bgp",
    "lldp",
    "system",
    "routing",
    "routing-policy",
    "acls",
    "mlag",
    "evpn-vxlan",
)


def build_arista_domain_view(snapshot: dict[str, Any], domain: str) -> dict[str, Any]:
    if domain == "interfaces":
        return _interfaces_view(snapshot)
    if domain == "vlans":
        return _vlans_view(snapshot)
    if domain == "vrfs":
        return _vrfs_view(snapshot)
    if domain == "lags":
        return _lags_view(snapshot)
    if domain == "bgp":
        return _bgp_view(snapshot)
    if domain == "lldp":
        return _lldp_view(snapshot)
    if domain == "system":
        return _system_view(snapshot)
    if domain == "routing":
        return _routing_view(snapshot)
    if domain == "routing-policy":
        return _build_routing_policy_view(snapshot)
    if domain == "acls":
        return _build_acls_view(snapshot)
    if domain == "mlag":
        return _build_mlag_view(snapshot)
    if domain == "evpn-vxlan":
        return _build_evpn_vxlan_view(snapshot)
    raise ValueError(f"Unsupported Arista EOS domain: {domain}")


def _interfaces_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    interfaces = list(snapshot.get("interfaces", []))
    warnings = []

    # Check for interfaces without addresses that might be L2
    l2_interfaces = [
        iface.get("name")
        for iface in interfaces
        if not iface.get("ipv4_addresses") and not iface.get("ipv6_addresses")
    ]
    if l2_interfaces:
        warnings.append(
            {
                "code": "POSSIBLE_L2_INTERFACES",
                "message": f"Found {len(l2_interfaces)} interfaces without IP addresses; these may be L2 switchports",
            }
        )

    return {
        "domain": "interfaces",
        "summary": {
            "interface_count": len(interfaces),
            "enabled_count": sum(1 for item in interfaces if item.get("enabled") is True),
            "with_ipv4": sum(1 for item in interfaces if item.get("ipv4_addresses")),
            "with_ipv6": sum(1 for item in interfaces if item.get("ipv6_addresses")),
            "interface_names": sorted(item.get("name") for item in interfaces if item.get("name")),
        },
        "interfaces": interfaces,
        "analysis_warnings": warnings,
    }


def _vlans_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    vlans = list(snapshot.get("vlans", []))
    return {
        "domain": "vlans",
        "summary": {
            "vlan_count": len(vlans),
            "enabled_count": sum(1 for item in vlans if item.get("enabled") is True),
            "vlan_ids": sorted(item.get("vlan_id") for item in vlans if item.get("vlan_id")),
            "vlan_names": {str(item.get("vlan_id")): item.get("name") for item in vlans if item.get("vlan_id")},
        },
        "vlans": vlans,
    }


def _vrfs_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    vrfs = list(snapshot.get("vrfs", []))
    return {
        "domain": "vrfs",
        "summary": {
            "vrf_count": len(vrfs),
            "enabled_count": sum(1 for item in vrfs if item.get("enabled") is True),
            "vrf_names": sorted(item.get("name") for item in vrfs if item.get("name")),
        },
        "vrfs": vrfs,
    }


def _lags_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    lags = list(snapshot.get("lags", []))
    return {
        "domain": "lags",
        "summary": {
            "lag_count": len(lags),
            "enabled_count": sum(1 for item in lags if item.get("enabled") is True),
            "lacp_count": sum(1 for item in lags if item.get("lag_type") == "LACP"),
            "lag_names": sorted(item.get("name") for item in lags if item.get("name")),
        },
        "lags": lags,
    }


def _bgp_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    bgp = dict(snapshot.get("bgp", {}))
    warnings = []

    if not bgp.get("enabled") and bgp.get("asn"):
        warnings.append(
            {
                "code": "BGP_DISABLED_WITH_ASN",
                "message": "BGP is configured with an ASN but not enabled",
            }
        )

    return {
        "domain": "bgp",
        "summary": {
            "enabled": bgp.get("enabled"),
            "asn": bgp.get("asn"),
            "router_id": bgp.get("router_id"),
        },
        "bgp": bgp,
        "analysis_warnings": warnings,
    }


def _lldp_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    neighbors = list(snapshot.get("lldp_neighbors", []))
    interfaces_with_neighbors = {item.get("interface") for item in neighbors if item.get("interface")}
    return {
        "domain": "lldp",
        "summary": {
            "neighbor_count": len(neighbors),
            "interfaces_with_neighbors": sorted(interfaces_with_neighbors),
            "unique_neighbors": sorted(
                {item.get("neighbor_id") for item in neighbors if item.get("neighbor_id")}
            ),
        },
        "lldp_neighbors": neighbors,
    }


def _system_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    system = dict(snapshot.get("system", {}))
    return {
        "domain": "system",
        "summary": {
            "hostname": system.get("hostname"),
            "version": system.get("version"),
            "platform": system.get("platform"),
        },
        "system": system,
    }


def _routing_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    static_routes = list(snapshot.get("static_routes", []))
    vrfs_with_routes = {item.get("vrf") for item in static_routes if item.get("vrf")}
    return {
        "domain": "routing",
        "summary": {
            "static_route_count": len(static_routes),
            "vrfs_with_routes": sorted(vrfs_with_routes),
            "default_routes": [
                item.get("destination_prefix")
                for item in static_routes
                if item.get("destination_prefix") in ("0.0.0.0/0", "::/0")
            ],
        },
        "static_routes": static_routes,
    }


def _build_routing_policy_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Build a routing policy domain view with prefix-sets and policies."""
    prefix_sets = list(snapshot.get("prefix_sets", []))
    routing_policies = list(snapshot.get("routing_policies", []))
    warnings: list[dict[str, Any]] = []

    # Calculate summary statistics
    total_prefixes = sum(len(ps.get("prefixes", [])) for ps in prefix_sets)
    total_statements = sum(len(p.get("statements", [])) for p in routing_policies)

    # Find policies that reference prefix-sets
    policies_with_prefix_refs = []
    for policy in routing_policies:
        for stmt in policy.get("statements", []):
            conditions = stmt.get("conditions", {})
            if conditions.get("match_prefix_set"):
                policies_with_prefix_refs.append(policy.get("name"))
                break

    # Build prefix-sets detail view
    prefix_sets_detail = []
    for ps in prefix_sets:
        prefixes_detail = []
        for prefix_entry in ps.get("prefixes", []):
            prefixes_detail.append({
                "prefix": prefix_entry.get("prefix"),
                "masklength_range": prefix_entry.get("masklength_range"),
            })
        prefix_sets_detail.append({
            "name": ps.get("name"),
            "prefix_count": len(prefixes_detail),
            "prefixes": prefixes_detail,
        })

    # Build routing policies detail view
    policies_detail = []
    for policy in routing_policies:
        statements_detail = []
        for stmt in policy.get("statements", []):
            conditions = stmt.get("conditions", {})
            actions = stmt.get("actions", {})

            # Build conditions summary
            conditions_summary = []
            if conditions.get("match_prefix_set"):
                conditions_summary.append(f"prefix-set:{conditions['match_prefix_set']}")
            if conditions.get("match_community"):
                conditions_summary.append(f"community:{conditions['match_community']}")
            if conditions.get("match_as_path_set"):
                conditions_summary.append(f"as-path:{conditions['match_as_path_set']}")

            # Build actions summary
            actions_summary = []
            policy_result = actions.get("policy_result")
            if policy_result:
                actions_summary.append(policy_result)
            if actions.get("set_community"):
                actions_summary.append(f"set-community:{len(actions['set_community'])} communities")
            if actions.get("set_local_pref"):
                actions_summary.append(f"set-local-pref:{actions['set_local_pref']}")
            if actions.get("set_med"):
                actions_summary.append(f"set-med:{actions['set_med']}")
            if actions.get("set_next_hop"):
                actions_summary.append(f"set-next-hop:{actions['set_next_hop']}")

            statements_detail.append({
                "sequence": stmt.get("sequence"),
                "conditions_summary": conditions_summary,
                "actions_summary": actions_summary,
            })

        policies_detail.append({
            "name": policy.get("name"),
            "statement_count": len(statements_detail),
            "statements": statements_detail,
        })

    # Check for warnings
    if prefix_sets and not routing_policies:
        warnings.append({
            "code": "PREFIX_SETS_WITHOUT_POLICIES",
            "message": f"Found {len(prefix_sets)} prefix-sets but no routing policies that reference them",
        })

    if routing_policies and not prefix_sets:
        warnings.append({
            "code": "POLICIES_WITHOUT_PREFIX_SETS",
            "message": f"Found {len(routing_policies)} routing policies but no prefix-sets defined",
        })

    return {
        "domain": "routing-policy",
        "summary": {
            "policy_count": len(routing_policies),
            "prefix_set_count": len(prefix_sets),
            "total_statements": total_statements,
            "total_prefixes": total_prefixes,
            "policies_with_prefix_refs": sorted(set(policies_with_prefix_refs)),
        },
        "prefix_sets": prefix_sets_detail,
        "routing_policies": policies_detail,
        "analysis_warnings": warnings,
    }


def _build_acls_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Build an ACL domain view with ACL sets and interface bindings."""
    acl_sets = list(snapshot.get("acl_sets", []))
    acl_bindings = list(snapshot.get("acl_bindings", []))
    warnings: list[dict[str, Any]] = []

    # Calculate summary statistics
    total_entries = sum(len(acl_set.get("entries", [])) for acl_set in acl_sets)
    acl_types = sorted(set(acl_set.get("type") for acl_set in acl_sets if acl_set.get("type")))

    # Get interfaces with ACLs
    interfaces_with_acls = sorted(set(binding.get("interface") for binding in acl_bindings if binding.get("interface")))

    # Build ACL sets detail view
    acl_sets_detail = []
    for acl_set in acl_sets:
        entries_detail = []
        for entry in acl_set.get("entries", []):
            # Build compact match summary
            match_conditions = entry.get("match_conditions", {})
            match_summary_parts = []
            for key, value in match_conditions.items():
                if key == "source-address":
                    match_summary_parts.append(f"src={value}")
                elif key == "destination-address":
                    match_summary_parts.append(f"dst={value}")
                elif key == "protocol":
                    match_summary_parts.append(f"proto={value}")
                elif key == "source-port":
                    match_summary_parts.append(f"sport={value}")
                elif key == "destination-port":
                    match_summary_parts.append(f"dport={value}")
                else:
                    match_summary_parts.append(f"{key}={value}")

            match_summary = ", ".join(match_summary_parts) if match_summary_parts else "any"

            entries_detail.append({
                "sequence": entry.get("sequence"),
                "match_summary": match_summary,
                "action": entry.get("action"),
                "description": entry.get("description"),
            })

        acl_sets_detail.append({
            "name": acl_set.get("name"),
            "type": acl_set.get("type"),
            "entry_count": len(entries_detail),
            "entries": entries_detail,
        })

    # Build ACL bindings detail view
    bindings_detail = []
    for binding in acl_bindings:
        bindings_detail.append({
            "interface": binding.get("interface"),
            "acl_set": binding.get("acl_set"),
            "direction": binding.get("direction"),
        })

    # Check for orphaned ACLs (defined but not bound to any interface)
    bound_acl_names = set(binding.get("acl_set") for binding in acl_bindings if binding.get("acl_set"))
    for acl_set in acl_sets:
        acl_name = acl_set.get("name")
        if acl_name and acl_name not in bound_acl_names:
            warnings.append({
                "code": "ORPHANED_ACL",
                "message": f"ACL '{acl_name}' is defined but not bound to any interface",
            })

    # Check for invalid bindings (references nonexistent ACL)
    defined_acl_names = set(acl_set.get("name") for acl_set in acl_sets if acl_set.get("name"))
    for binding in acl_bindings:
        acl_name = binding.get("acl_set")
        if acl_name and acl_name not in defined_acl_names:
            warnings.append({
                "code": "INVALID_ACL_BINDING",
                "message": f"Interface '{binding.get('interface')}' references nonexistent ACL '{acl_name}'",
            })

    return {
        "domain": "acls",
        "summary": {
            "acl_count": len(acl_sets),
            "total_entries": total_entries,
            "binding_count": len(acl_bindings),
            "acl_types": acl_types,
            "interfaces_with_acls": interfaces_with_acls,
        },
        "acl_sets": acl_sets_detail,
        "acl_bindings": bindings_detail,
        "analysis_warnings": warnings,
    }


def _build_mlag_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Build an MLAG domain view with global config and member interfaces."""
    mlag = snapshot.get("mlag")
    mlag_interfaces = list(snapshot.get("mlag_interfaces", []))
    warnings: list[dict[str, Any]] = []

    # Determine if MLAG is enabled
    enabled = mlag.get("enabled") is True if mlag else False

    # Calculate member counts
    member_count = len(mlag_interfaces)
    active_member_count = sum(
        1 for iface in mlag_interfaces if iface.get("status") == "active"
    )

    # Build global config with data source indicator
    global_config: dict[str, Any] = {}
    if mlag:
        global_config = {
            "domain_id": mlag.get("domain_id"),
            "local_interface": mlag.get("local_interface"),
            "peer_address": mlag.get("peer_address"),
            "peer_link": mlag.get("peer_link"),
            "status": mlag.get("state", {}).get("status") if mlag.get("state") else None,
            "data_source": "arista-proprietary",
        }

    # Build member interfaces detail
    member_interfaces = []
    for iface in mlag_interfaces:
        member_interfaces.append({
            "interface": iface.get("interface"),
            "mlag_id": iface.get("mlag_id"),
            "status": iface.get("status"),
        })

    # Check for operational warnings
    if mlag:
        state = mlag.get("state", {})
        if state:
            peer_link_status = state.get("peer_link_status")
            if peer_link_status and peer_link_status != "up":
                warnings.append({
                    "code": "PEER_LINK_DOWN",
                    "message": f"MLAG peer-link status is '{peer_link_status}'",
                })

            status = state.get("status")
            if status and status != "active":
                warnings.append({
                    "code": "MLAG_NOT_ACTIVE",
                    "message": f"MLAG status is '{status}', not active",
                })

    # Add vendor-specific data source warning
    if mlag:
        warnings.append({
            "code": "VENDOR_SPECIFIC_DATA",
            "message": "MLAG data is sourced from Arista-proprietary YANG model (not OpenConfig ethernet-segments)",
        })

    return {
        "domain": "mlag",
        "summary": {
            "enabled": enabled,
            "domain_id": mlag.get("domain_id") if mlag else None,
            "peer_address": mlag.get("peer_address") if mlag else None,
            "peer_link": mlag.get("peer_link") if mlag else None,
            "member_count": member_count,
            "active_member_count": active_member_count,
        },
        "global_config": global_config,
        "member_interfaces": member_interfaces,
        "analysis_warnings": warnings,
    }


def _build_evpn_vxlan_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Build an EVPN/VXLAN domain view with EVPN instances and VXLAN mappings."""
    evpn_instances = list(snapshot.get("evpn_instances", []))
    vxlan_mappings = list(snapshot.get("vxlan_mappings", []))
    warnings: list[dict[str, Any]] = []

    # Determine if EVPN is enabled
    evpn_enabled = len(evpn_instances) > 0 or len(vxlan_mappings) > 0

    # Calculate VNI counts - use VXLAN mappings as primary source (data plane)
    l2vni_count = 0
    l3vni_count = 0
    vlan_count = 0
    vrf_count = 0

    # Track VNIs to detect conflicts
    vni_to_services: dict[int, list[str]] = {}

    # Count from VXLAN mappings (primary - data plane)
    source_interface: str | None = None
    for mapping in vxlan_mappings:
        vni = mapping.get("vni")
        if vni is not None:
            if vni not in vni_to_services:
                vni_to_services[vni] = []
            vni_to_services[vni].append(f"vxlan:vlan{mapping.get('vlan_id', '?')}" if mapping.get("vlan_id") else f"vxlan:vrf{mapping.get('vrf_name', '?')}")

            if mapping.get("vlan_id") is not None:
                l2vni_count += 1
                vlan_count += 1
            elif mapping.get("vrf_name") is not None:
                l3vni_count += 1
                vrf_count += 1

        if source_interface is None:
            source_interface = mapping.get("source_interface")

    # Also check EVPN instances for additional VNIs not in VXLAN mappings
    for instance in evpn_instances:
        vni = instance.get("vni")
        if vni is not None:
            # Track for conflict detection
            if vni not in vni_to_services:
                vni_to_services[vni] = []
            vni_to_services[vni].append(f"evpn:{instance.get('name')}")

            # Only count if not already counted from VXLAN mappings
            if vni not in [m.get("vni") for m in vxlan_mappings if m.get("vni")]:
                # Infer type from name
                name_lower = instance.get("name", "").lower()
                if "vlan" in name_lower or "vsi" in name_lower:
                    l2vni_count += 1
                    vlan_count += 1
                elif "vrf" in name_lower or "prod" in name_lower or "customer" in name_lower or "dev" in name_lower:
                    l3vni_count += 1
                    vrf_count += 1

    # Detect VNI conflicts
    for vni, services in vni_to_services.items():
        if len(services) > 1:
            warnings.append({
                "code": "VNI_CONFLICT",
                "message": f"VNI {vni} is used by multiple services: {', '.join(services)}",
            })

    # Check for missing source interface
    if evpn_enabled and source_interface is None:
        warnings.append({
            "code": "MISSING_VXLAN_SOURCE_INTERFACE",
            "message": "EVPN/VXLAN is enabled but source-interface not found in Vxlan1 config",
        })

    # Build EVPN instances detail
    evpn_instances_detail = []
    for instance in evpn_instances:
        # Determine type based on name
        name_lower = instance.get("name", "").lower()
        if "vlan" in name_lower or "vsi" in name_lower:
            inst_type = "L2"
        elif "vrf" in name_lower or "prod" in name_lower or "customer" in name_lower or "dev" in name_lower:
            inst_type = "L3"
        else:
            inst_type = "L2"  # Default to L2

        evpn_instances_detail.append({
            "name": instance.get("name"),
            "vni": instance.get("vni"),
            "rd": instance.get("rd"),
            "rt_import": instance.get("route_target_import", []),
            "rt_export": instance.get("route_target_export", []),
            "type": inst_type,
        })

    # Build VXLAN mappings detail
    vxlan_mappings_detail = []
    for mapping in vxlan_mappings:
        vxlan_mappings_detail.append({
            "vni": mapping.get("vni"),
            "vlan_id": mapping.get("vlan_id"),
            "vrf_name": mapping.get("vrf_name"),
            "source_interface": mapping.get("source_interface"),
            "data_source": "arista-proprietary" if mapping.get("source_interface") else "openconfig",
        })

    # Add vendor-specific data source warning
    if vxlan_mappings:
        warnings.append({
            "code": "VENDOR_SPECIFIC_DATA",
            "message": "VXLAN VNI mappings sourced from Arista-proprietary YANG model (not OpenConfig vxlan)",
        })

    return {
        "domain": "evpn-vxlan",
        "summary": {
            "evpn_enabled": evpn_enabled,
            "total_vni_count": l2vni_count + l3vni_count,
            "l2vni_count": l2vni_count,
            "l3vni_count": l3vni_count,
            "vlan_count": vlan_count,
            "vrf_count": vrf_count,
            "source_interface": source_interface,
        },
        "evpn_instances": evpn_instances_detail,
        "vxlan_mappings": vxlan_mappings_detail,
        "analysis_warnings": warnings,
    }
