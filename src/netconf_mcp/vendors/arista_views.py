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
