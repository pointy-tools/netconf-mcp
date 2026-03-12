"""Agent-friendly domain views over normalized TNSR snapshots."""

from __future__ import annotations

from typing import Any


DOMAIN_CHOICES = (
    "interfaces",
    "routing",
    "bgp",
    "prefix-lists",
    "route-maps",
    "bfd",
    "nat",
    "filters",
    "nacm",
    "management",
    "platform",
)


def build_tnsr_domain_view(snapshot: dict[str, Any], domain: str) -> dict[str, Any]:
    if domain == "interfaces":
        return _interfaces_view(snapshot)
    if domain == "routing":
        return _routing_view(snapshot)
    if domain == "bgp":
        return _bgp_view(snapshot)
    if domain == "prefix-lists":
        return _prefix_lists_view(snapshot)
    if domain == "route-maps":
        return _route_maps_view(snapshot)
    if domain == "bfd":
        return _bfd_view(snapshot)
    if domain == "nat":
        return _nat_view(snapshot)
    if domain == "filters":
        return _filters_view(snapshot)
    if domain == "nacm":
        return _nacm_view(snapshot)
    if domain == "management":
        return _management_view(snapshot)
    if domain == "platform":
        return _platform_view(snapshot)
    raise ValueError(f"Unsupported TNSR domain: {domain}")


def _interfaces_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    interfaces = list(snapshot.get("interfaces", []))
    host_interfaces = list(snapshot.get("host_interfaces", []))
    return {
        "domain": "interfaces",
        "summary": {
            "dataplane_interface_count": sum(1 for item in interfaces if item.get("kind") == "dataplane"),
            "host_interface_count": len(host_interfaces),
        },
        "interfaces": interfaces,
        "host_interfaces": host_interfaces,
    }


def _routing_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    static_routes = list(snapshot.get("static_routes", []))
    return {
        "domain": "routing",
        "summary": {
            "static_route_count": len(static_routes),
            "route_tables": sorted({item.get("table", "default") for item in static_routes}),
        },
        "static_routes": static_routes,
    }


def _bgp_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    bgp = dict(snapshot.get("bgp", {}))
    neighbors = list(bgp.get("neighbors", []))
    return {
        "domain": "bgp",
        "summary": {
            "asn": bgp.get("asn"),
            "router_id": bgp.get("router_id"),
            "neighbor_count": len(neighbors),
            "peer_groups": sorted({item.get("peer_group") for item in neighbors if item.get("peer_group")}),
            "route_map_in_neighbors": sorted(
                item.get("peer") for item in neighbors if item.get("route_map_in")
            ),
            "route_map_out_neighbors": sorted(
                item.get("peer") for item in neighbors if item.get("route_map_out")
            ),
        },
        "bgp": bgp,
    }


def _prefix_lists_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    prefix_lists = list(snapshot.get("prefix_lists", []))
    return {
        "domain": "prefix-lists",
        "summary": {
            "prefix_list_count": len(prefix_lists),
            "names": [item.get("name") for item in prefix_lists],
            "rule_counts": {item.get("name"): len(item.get("rules", [])) for item in prefix_lists},
        },
        "prefix_lists": prefix_lists,
    }


def _route_maps_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    route_maps = list(snapshot.get("route_maps", []))
    return {
        "domain": "route-maps",
        "summary": {
            "route_map_count": len(route_maps),
            "names": [item.get("name") for item in route_maps],
            "rule_counts": {item.get("name"): len(item.get("rules", [])) for item in route_maps},
        },
        "route_maps": route_maps,
    }


def _bfd_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    sessions = list(snapshot.get("bfd_sessions", []))
    return {
        "domain": "bfd",
        "summary": {
            "session_count": len(sessions),
            "enabled_session_count": sum(1 for item in sessions if item.get("enabled") is True),
        },
        "bfd_sessions": sessions,
    }


def _nat_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    rulesets = list(snapshot.get("nat_rulesets", []))
    return {
        "domain": "nat",
        "summary": {
            "ruleset_count": len(rulesets),
            "rule_count": sum(len(item.get("rules", [])) for item in rulesets),
            "names": [item.get("name") for item in rulesets],
        },
        "nat_rulesets": rulesets,
    }


def _filters_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    rulesets = list(snapshot.get("acl_rulesets", []))
    bindings = list(snapshot.get("interface_policy_bindings", []))
    return {
        "domain": "filters",
        "summary": {
            "ruleset_count": len(rulesets),
            "interface_binding_count": len(bindings),
            "names": [item.get("name") for item in rulesets],
        },
        "acl_rulesets": rulesets,
        "interface_policy_bindings": bindings,
    }


def _nacm_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    nacm = dict(snapshot.get("nacm", {}))
    groups = list(nacm.get("groups", []))
    rule_lists = list(nacm.get("rule_lists", []))
    return {
        "domain": "nacm",
        "summary": {
            "enabled": nacm.get("enabled"),
            "group_count": len(groups),
            "rule_list_count": len(rule_lists),
        },
        "nacm": nacm,
    }


def _management_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain": "management",
        "summary": {
            "host_interface_count": len(snapshot.get("host_interfaces", [])),
            "logging_server_count": len(snapshot.get("logging", {}).get("remote_servers", [])),
            "netconf_enabled": snapshot.get("ssh_server", {}).get("netconf_enabled"),
        },
        "ssh_server": snapshot.get("ssh_server", {}),
        "host_interfaces": snapshot.get("host_interfaces", []),
        "logging": snapshot.get("logging", {}),
        "prometheus_exporter": snapshot.get("prometheus_exporter", {}),
    }


def _platform_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    dataplane = dict(snapshot.get("dataplane", {}))
    return {
        "domain": "platform",
        "summary": {
            "cpu_workers": dataplane.get("cpu_workers"),
            "dpdk_device_count": len(dataplane.get("dpdk_devices", [])),
            "sysctl_count": len(snapshot.get("sysctl", [])),
            "kernel_module_count": len(snapshot.get("system", {}).get("kernel_modules", [])),
        },
        "dataplane": dataplane,
        "sysctl": snapshot.get("sysctl", []),
        "system": snapshot.get("system", {}),
    }
