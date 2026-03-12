"""TNSR-specific read collectors and snapshot normalization."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from netconf_mcp.transport.live import LiveNetconfSSHClient


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


@dataclass
class InterfaceRecord:
    name: str
    kind: str
    enabled: bool | None = None
    description: str | None = None
    ipv4_addresses: list[str] = field(default_factory=list)


@dataclass
class StaticRouteRecord:
    table: str
    destination_prefix: str
    next_hop: str | None = None
    interface: str | None = None


@dataclass
class BGPNeighborRecord:
    peer: str
    enabled: bool | None = None
    peer_group: str | None = None
    remote_asn: str | None = None
    description: str | None = None
    update_source: str | None = None


@dataclass
class BGPSnapshot:
    asn: str | None = None
    router_id: str | None = None
    neighbors: list[BGPNeighborRecord] = field(default_factory=list)
    network_announcements: list[str] = field(default_factory=list)


@dataclass
class TNSRSnapshot:
    snapshot_type: str
    collected_at_utc: str
    target_ref: str
    device: dict[str, Any]
    capabilities: list[str]
    module_inventory: list[dict[str, Any]]
    interfaces: list[InterfaceRecord]
    static_routes: list[StaticRouteRecord]
    bgp: BGPSnapshot
    raw_sections: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TNSRCollector:
    """Collect a normalized read-only snapshot from a live TNSR target."""

    def __init__(self, client: LiveNetconfSSHClient | None = None):
        self.client = client or LiveNetconfSSHClient()

    def collect(self, target: dict[str, Any], *, hostkey_policy: str = "strict") -> TNSRSnapshot:
        session = self.client.open_session(target, hostkey_policy=hostkey_policy)
        yang_library = self.client.get_yang_library(target, session)
        config_payload = self.client.datastore_get(
            target,
            session,
            datastore="running",
            strict_config=True,
        )
        config = config_payload["value"]

        monitoring = self.client.get_monitoring(target, session, scope="all")
        interfaces = self._collect_interfaces(config)
        static_routes = self._collect_static_routes(config)
        bgp = self._collect_bgp(config)

        return TNSRSnapshot(
            snapshot_type="tnsr-normalized-config-v1",
            collected_at_utc=datetime.now(timezone.utc).isoformat(),
            target_ref=target["target_ref"],
            device={
                "name": target.get("name"),
                "vendor": target.get("facts", {}).get("vendor", "netgate"),
                "os": target.get("facts", {}).get("os", "tnsr"),
                "host": target.get("host") or target.get("ssh_config_host"),
                "site": target.get("site"),
                "role": target.get("role", []),
            },
            capabilities=session.server_capabilities,
            module_inventory=yang_library.get("module_set", []),
            interfaces=interfaces,
            static_routes=static_routes,
            bgp=bgp,
            raw_sections={
                "config_root_keys": sorted(config.keys()) if isinstance(config, dict) else [],
                "monitoring_sessions": monitoring.get("sessions", []),
            },
        )

    def _collect_interfaces(self, config: dict[str, Any]) -> list[InterfaceRecord]:
        interfaces: list[InterfaceRecord] = []

        host_if = config.get("host-if-config", {}).get("interface")
        for item in _as_list(host_if):
            if not isinstance(item, dict):
                continue
            interfaces.append(
                InterfaceRecord(
                    name=str(item.get("name")),
                    kind="host",
                    enabled=_to_bool(item.get("enabled")),
                    ipv4_addresses=self._extract_host_ipv4(item),
                )
            )

        routed_if = config.get("interfaces-config", {}).get("interface")
        for item in _as_list(routed_if):
            if not isinstance(item, dict):
                continue
            interfaces.append(
                InterfaceRecord(
                    name=str(item.get("name")),
                    kind="dataplane",
                    enabled=_to_bool(item.get("enabled")),
                    description=item.get("description"),
                    ipv4_addresses=self._extract_ipv4_addresses(item),
                )
            )

        return interfaces

    def _collect_static_routes(self, config: dict[str, Any]) -> list[StaticRouteRecord]:
        routes: list[StaticRouteRecord] = []
        route_tables = config.get("route-table-config", {}).get("static-routes", {}).get("route-table")
        for table in _as_list(route_tables):
            if not isinstance(table, dict):
                continue
            table_name = str(table.get("name", "default"))
            route_items = table.get("ipv4-routes", {}).get("route")
            for route in _as_list(route_items):
                if not isinstance(route, dict):
                    continue
                hop = route.get("next-hop", {}).get("hop", {})
                routes.append(
                    StaticRouteRecord(
                        table=table_name,
                        destination_prefix=str(route.get("destination-prefix")),
                        next_hop=hop.get("ipv4-address"),
                        interface=hop.get("if-name"),
                    )
                )
        return routes

    def _collect_bgp(self, config: dict[str, Any]) -> BGPSnapshot:
        router = config.get("route-config", {}).get("dynamic", {}).get("bgp", {}).get("routers", {}).get("router", {})
        if not isinstance(router, dict):
            return BGPSnapshot()

        neighbors = []
        neighbor_items = router.get("neighbors", {}).get("neighbor")
        for item in _as_list(neighbor_items):
            if not isinstance(item, dict):
                continue
            neighbors.append(
                BGPNeighborRecord(
                    peer=str(item.get("peer")),
                    enabled=_to_bool(item.get("enable")),
                    peer_group=item.get("peer-group-name"),
                    remote_asn=item.get("remote-asn"),
                    description=item.get("description"),
                    update_source=item.get("update-source"),
                )
            )

        announcements = []
        announcement_items = (
            router.get("address-families", {})
            .get("ipv4", {})
            .get("unicast", {})
            .get("network-announcements", {})
            .get("network")
        )
        for item in _as_list(announcement_items):
            if isinstance(item, dict) and item.get("ip-prefix"):
                announcements.append(str(item["ip-prefix"]))

        return BGPSnapshot(
            asn=router.get("asn"),
            router_id=router.get("router-id"),
            neighbors=neighbors,
            network_announcements=announcements,
        )

    @staticmethod
    def _extract_ipv4_addresses(interface: dict[str, Any]) -> list[str]:
        values = []
        addresses = interface.get("ipv4", {}).get("address")
        for item in _as_list(addresses):
            if isinstance(item, dict) and item.get("ip"):
                values.append(str(item["ip"]))
        return values

    @staticmethod
    def _extract_host_ipv4(interface: dict[str, Any]) -> list[str]:
        addresses = []
        ipv4 = interface.get("ipv4", {})
        for key in ("address", "addresses"):
            for item in _as_list(ipv4.get(key)):
                if isinstance(item, dict) and item.get("ip"):
                    addresses.append(str(item["ip"]))
        return addresses
