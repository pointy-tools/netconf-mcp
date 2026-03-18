"""Arista EOS-specific read collectors and snapshot normalization."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from netconf_mcp.transport.live import LiveNetconfSession, LiveNetconfSSHClient


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
    return None


def _to_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


# OpenConfig namespace prefixes for Arista EOS
ARISTA_NAMESPACES = {
    "oc-if": "http://openconfig.net/yang/interfaces",
    "oc-eth": "http://openconfig.net/yang/interfaces/ethernet",
    "oc-ip": "http://openconfig.net/yang/interfaces/ip",
    "oc-lacp": "http://openconfig.net/yang/lacp",
    "oc-vlan": "http://openconfig.net/yang/vlan",
    "oc-ni": "http://openconfig.net/yang/network-instance",
    "oc-lldp": "http://openconfig.net/yang/lldp",
    "oc-sys": "http://openconfig.net/yang/system",
    "oc-bgp": "http://openconfig.net/yang/bgp",
    "oc-rpol": "http://openconfig.net/yang/routing-policy",
    "oc-local-routing": "http://openconfig.net/yang/local-routing",
    "oc-aaa": "http://openconfig.net/yang/aaa",
}


@dataclass
class InterfaceRecord:
    name: str
    enabled: bool | None = None
    description: str | None = None
    type: str | None = None
    ipv4_addresses: list[str] = field(default_factory=list)
    ipv6_addresses: list[str] = field(default_factory=list)
    mtu: int | None = None


@dataclass
class LAGRecord:
    name: str
    enabled: bool | None = None
    lag_type: str | None = None
    members: list[str] = field(default_factory=list)


@dataclass
class VLANRecord:
    vlan_id: int | None = None
    name: str | None = None
    enabled: bool | None = None


@dataclass
class VRFRecord:
    name: str
    vrf_id: int | None = None
    description: str | None = None
    enabled: bool | None = None


@dataclass
class StaticRouteRecord:
    vrf: str
    destination_prefix: str
    next_hop: str | None = None
    interface: str | None = None
    metric: int | None = None


@dataclass
class BGPRecord:
    enabled: bool | None = None
    asn: str | None = None
    router_id: str | None = None


@dataclass
class LLDPNeighborRecord:
    interface: str | None = None
    neighbor_id: str | None = None
    neighbor_port: str | None = None
    capability: list[str] = field(default_factory=list)


@dataclass
class SystemInfoRecord:
    hostname: str | None = None
    version: str | None = None
    platform: str | None = None


@dataclass
class AristaSnapshot:
    snapshot_type: str
    collected_at_utc: str
    target_ref: str
    device: dict[str, Any]
    capabilities: list[str]
    module_inventory: list[dict[str, Any]]
    interfaces: list[InterfaceRecord]
    lags: list[LAGRecord]
    vlans: list[VLANRecord]
    vrfs: list[VRFRecord]
    static_routes: list[StaticRouteRecord]
    bgp: BGPRecord
    lldp_neighbors: list[LLDPNeighborRecord]
    system: SystemInfoRecord
    raw_sections: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AristaCollector:
    """Collect a normalized read-only snapshot from a live Arista EOS target."""

    def __init__(self, client: LiveNetconfSSHClient | None = None):
        self.client = client or LiveNetconfSSHClient()

    def collect_snapshot(
        self,
        target: dict[str, Any],
        *,
        hostkey_policy: str = "strict",
    ) -> AristaSnapshot:
        """Collect a normalized snapshot from an Arista EOS device using OpenConfig models."""
        # Add namespace map to target for OpenConfig queries
        target_with_ns = dict(target)
        target_with_ns["namespace_map"] = ARISTA_NAMESPACES

        session = self.client.open_session(target_with_ns, hostkey_policy=hostkey_policy)
        yang_library = self.client.get_yang_library(target_with_ns, session)

        warnings: list[str] = []

        # Collect various data sections with graceful error handling
        interfaces, if_warnings = self._collect_interfaces(target_with_ns, session)
        warnings.extend(if_warnings)

        lags, lag_warnings = self._collect_lags(target_with_ns, session)
        warnings.extend(lag_warnings)

        vlans, vlan_warnings = self._collect_vlans(target_with_ns, session)
        warnings.extend(vlan_warnings)

        vrfs, vrf_warnings = self._collect_vrfs(target_with_ns, session)
        warnings.extend(vrf_warnings)

        static_routes, sr_warnings = self._collect_static_routes(target_with_ns, session)
        warnings.extend(sr_warnings)

        bgp = self._collect_bgp(target_with_ns, session)

        lldp_neighbors, lldp_warnings = self._collect_lldp(target_with_ns, session)
        warnings.extend(lldp_warnings)

        system = self._collect_system(target_with_ns, session)

        return AristaSnapshot(
            snapshot_type="arista-normalized-config-v1",
            collected_at_utc=datetime.now(timezone.utc).isoformat(),
            target_ref=target["target_ref"],
            device={
                "name": target.get("name"),
                "vendor": target.get("facts", {}).get("vendor", "arista"),
                "os": target.get("facts", {}).get("os", "eos"),
                "host": target.get("host") or target.get("ssh_config_host"),
                "site": target.get("site"),
                "role": target.get("role", []),
            },
            capabilities=session.server_capabilities,
            module_inventory=yang_library.get("module_set", []),
            interfaces=interfaces,
            lags=lags,
            vlans=vlans,
            vrfs=vrfs,
            static_routes=static_routes,
            bgp=bgp,
            lldp_neighbors=lldp_neighbors,
            system=system,
            raw_sections={
                "yang_library_completeness": yang_library.get("completeness", "unknown"),
            },
            warnings=warnings,
        )

    def _collect_interfaces(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> tuple[list[InterfaceRecord], list[str]]:
        interfaces: list[InterfaceRecord] = []
        warnings: list[str] = []

        try:
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-if:interfaces/interface",
            )
            config = payload.get("value", {})
        except Exception as e:
            warnings.append(f"Could not collect interfaces: {e}")
            return interfaces, warnings

        for item in _as_list(config):
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            if not name:
                continue

            # Extract IPv4 addresses
            ipv4_addresses = []
            ipv4_config = item.get("ipv4", {})
            if isinstance(ipv4_config, dict):
                for addr_key, addr_val in ipv4_config.items():
                    if addr_key == "config":
                        ip_addr = addr_val.get("ip") if isinstance(addr_val, dict) else None
                        if ip_addr:
                            prefix_len = addr_val.get("prefix-length", "")
                            ipv4_addresses.append(f"{ip_addr}/{prefix_len}" if prefix_len else ip_addr)

            # Extract IPv6 addresses
            ipv6_addresses = []
            ipv6_config = item.get("ipv6", {})
            if isinstance(ipv6_config, dict):
                for addr_key, addr_val in ipv6_config.items():
                    if addr_key == "config":
                        ip_addr = addr_val.get("ip") if isinstance(addr_val, dict) else None
                        if ip_addr:
                            prefix_len = addr_val.get("prefix-length", "")
                            ipv6_addresses.append(f"{ip_addr}/{prefix_len}" if prefix_len else ip_addr)

            interfaces.append(
                InterfaceRecord(
                    name=str(name),
                    enabled=_to_bool(item.get("config", {}).get("enabled")),
                    description=item.get("config", {}).get("description"),
                    type=item.get("config", {}).get("type"),
                    ipv4_addresses=ipv4_addresses,
                    ipv6_addresses=ipv6_addresses,
                    mtu=_to_int(item.get("config", {}).get("mtu")),
                )
            )

        return interfaces, warnings

    def _collect_lags(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> tuple[list[LAGRecord], list[str]]:
        lags: list[LAGRecord] = []
        warnings: list[str] = []

        try:
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-if:interfaces/interface[oc-eth:ethernet]",
            )
            config = payload.get("value", {})
        except Exception as e:
            warnings.append(f"Could not collect LAGs: {e}")
            return lags, warnings

        # Look for aggregate interfaces
        for item in _as_list(config):
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            if not name:
                continue

            eth_config = item.get("ethernet", {})
            if isinstance(eth_config, dict):
                agg_config = eth_config.get("aggregate-id", {})
                if isinstance(agg_config, dict):
                    agg_id = agg_config.get("config", {}).get("aggregate-id")
                    if agg_id:
                        lags.append(
                            LAGRecord(
                                name=str(name),
                                enabled=_to_bool(item.get("config", {}).get("enabled")),
                                lag_type="LACP",
                                members=[str(agg_id)],
                            )
                        )

        return lags, warnings

    def _collect_vlans(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> tuple[list[VLANRecord], list[str]]:
        vlans: list[VLANRecord] = []
        warnings: list[str] = []

        try:
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-vlan:vlans/vlan",
            )
            config = payload.get("value", {})
        except Exception as e:
            warnings.append(f"Could not collect VLANs: {e}")
            return vlans, warnings

        for item in _as_list(config):
            if not isinstance(item, dict):
                continue

            vlan_id = item.get("vlan-id")
            if vlan_id is None:
                continue

            vlans.append(
                VLANRecord(
                    vlan_id=_to_int(vlan_id),
                    name=item.get("config", {}).get("name"),
                    enabled=_to_bool(item.get("config", {}).get("enabled")),
                )
            )

        return vlans, warnings

    def _collect_vrfs(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> tuple[list[VRFRecord], list[str]]:
        vrfs: list[VRFRecord] = []
        warnings: list[str] = []

        try:
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-ni:network-instances/network-instance",
            )
            config = payload.get("value", {})
        except Exception as e:
            warnings.append(f"Could not collect VRFs: {e}")
            return vrfs, warnings

        for item in _as_list(config):
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            if not name:
                continue

            vrfs.append(
                VRFRecord(
                    name=str(name),
                    vrf_id=_to_int(item.get("config", {}).get("vrf-id")),
                    description=item.get("config", {}).get("description"),
                    enabled=_to_bool(item.get("config", {}).get("enabled")),
                )
            )

        return vrfs, warnings

    def _collect_static_routes(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> tuple[list[StaticRouteRecord], list[str]]:
        routes: list[StaticRouteRecord] = []
        warnings: list[str] = []

        try:
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-ni:network-instances/network-instance/static-routes",
            )
            config = payload.get("value", {})
        except Exception as e:
            warnings.append(f"Could not collect static routes: {e}")
            return routes, warnings

        # Navigate through network-instances to find static routes
        ni_list = _as_list(config.get("network-instance"))
        for ni in ni_list:
            if not isinstance(ni, dict):
                continue

            vrf_name = ni.get("name", "default")
            sr_config = ni.get("static-routes", {})
            if not isinstance(sr_config, dict):
                continue

            # Handle both static and config structures
            static_list = _as_list(sr_config.get("static")) + _as_list(sr_config.get("config", {}).get("static"))

            for static in static_list:
                if not isinstance(static, dict):
                    continue

                prefix = static.get("prefix")
                if not prefix:
                    continue

                # Extract next-hops
                next_hops = static.get("next-hop", {})
                if isinstance(next_hops, dict):
                    hop_list = _as_list(next_hops.get("next-hop"))
                    for hop in hop_list:
                        if not isinstance(hop, dict):
                            continue

                        routes.append(
                            StaticRouteRecord(
                                vrf=vrf_name,
                                destination_prefix=str(prefix),
                                next_hop=hop.get("config", {}).get("next-hop-address"),
                                interface=hop.get("config", {}).get("outgoing-interface"),
                                metric=_to_int(hop.get("config", {}).get("metric")),
                            )
                        )

        return routes, warnings

    def _collect_bgp(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> BGPRecord:
        try:
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-ni:network-instances/network-instance/protocols/protocol/bgp",
            )
            config = payload.get("value", {})

            # Navigate to BGP config
            for ni in _as_list(config.get("network-instance")):
                if not isinstance(ni, dict):
                    continue

                protocols = ni.get("protocols", {})
                if not isinstance(protocols, dict):
                    continue

                for proto in _as_list(protocols.get("protocol")):
                    if not isinstance(proto, dict):
                        continue

                    if proto.get("identifier") != "BGP":
                        continue

                    bgp = proto.get("bgp", {})
                    if not isinstance(bgp, dict):
                        continue

                    global_bgp = bgp.get("global", {})
                    if not isinstance(global_bgp, dict):
                        continue

                    conf = global_bgp.get("config", {})
                    if isinstance(conf, dict):
                        return BGPRecord(
                            enabled=_to_bool(conf.get("enabled")),
                            asn=str(conf.get("as")) if conf.get("as") else None,
                            router_id=conf.get("router-id"),
                        )
        except Exception:
            pass

        return BGPRecord()

    def _collect_lldp(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> tuple[list[LLDPNeighborRecord], list[str]]:
        neighbors: list[LLDPNeighborRecord] = []
        warnings: list[str] = []

        try:
            payload = self.client.datastore_get(
                target,
                session,
                datastore="operational",
                xpath="/oc-lldp:lldp/interfaces/interface",
            )
            config = payload.get("value", {})
        except Exception as e:
            warnings.append(f"Could not collect LLDP neighbors: {e}")
            return neighbors, warnings

        for item in _as_list(config):
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            neighbors_list = item.get("neighbors", {})
            if not isinstance(neighbors_list, dict):
                continue

            for neighbor in _as_list(neighbors_list.get("neighbor")):
                if not isinstance(neighbor, dict):
                    continue

                neighbors.append(
                    LLDPNeighborRecord(
                        interface=str(name) if name else None,
                        neighbor_id=neighbor.get("config", {}).get("neighbor-id"),
                        neighbor_port=neighbor.get("config", {}).get("port"),
                        capability=_as_list(neighbor.get("config", {}).get("system-capabilities")),
                    )
                )

        return neighbors, warnings

    def _collect_system(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> SystemInfoRecord:
        try:
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-sys:system/config",
            )
            config = payload.get("value", {})
        except Exception:
            # Try operational datastore as fallback
            try:
                payload = self.client.datastore_get(
                    target,
                    session,
                    datastore="operational",
                    xpath="/oc-sys:system",
                )
                config = payload.get("value", {})
            except Exception:
                return SystemInfoRecord()

        if not isinstance(config, dict):
            return SystemInfoRecord()

        return SystemInfoRecord(
            hostname=config.get("hostname"),
            version=config.get("version"),
            platform=config.get("platform-id"),
        )


def get_domain_view(snapshot: dict[str, Any], domain: str) -> dict[str, Any]:
    """Build a domain view from an Arista EOS snapshot.

    Args:
        snapshot: A normalized Arista EOS snapshot dict (from AristaSnapshot.to_dict())
        domain: The domain to view (interfaces, vlans, vrfs, lags, bgp, lldp, system, routing)

    Returns:
        A compact, agent-friendly domain view dict

    Raises:
        ValueError: If the domain is not supported
    """
    from netconf_mcp.vendors.arista_views import build_arista_domain_view

    return build_arista_domain_view(snapshot, domain)
