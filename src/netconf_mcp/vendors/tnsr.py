"""TNSR-specific read collectors and snapshot normalization."""

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
    bfd: bool | None = None
    peer_group: str | None = None
    remote_asn: str | None = None
    description: str | None = None
    update_source: str | None = None
    ebgp_multihop_max_hops: int | None = None


@dataclass
class PrefixListRuleRecord:
    sequence: str
    action: str | None = None
    prefix: str | None = None


@dataclass
class PrefixListRecord:
    name: str
    rules: list[PrefixListRuleRecord] = field(default_factory=list)


@dataclass
class RouteMapRuleRecord:
    sequence: str
    policy: str | None = None
    match_ip_prefix_list: str | None = None
    set_as_path_prepend: str | None = None


@dataclass
class RouteMapRecord:
    name: str
    rules: list[RouteMapRuleRecord] = field(default_factory=list)


@dataclass
class BFDSessionRecord:
    name: str
    enabled: bool | None = None
    interface: str | None = None
    local_ip_address: str | None = None
    peer_ip_address: str | None = None
    desired_min_tx: int | None = None
    required_min_rx: int | None = None
    detect_multiplier: int | None = None


@dataclass
class NATRuleRecord:
    sequence: str
    description: str | None = None
    direction: str | None = None
    dynamic: bool | None = None
    algorithm: str | None = None
    match_from_prefix: str | None = None
    translation_interface: str | None = None


@dataclass
class NATRulesetRecord:
    name: str
    description: str | None = None
    rules: list[NATRuleRecord] = field(default_factory=list)


@dataclass
class ACLRuleRecord:
    sequence: str
    description: str | None = None
    direction: str | None = None
    ip_version: str | None = None
    pass_action: bool | None = None
    stateful: bool | None = None
    protocol_set: str | None = None
    from_prefix: str | None = None
    to_prefix: str | None = None


@dataclass
class ACLRulesetRecord:
    name: str
    description: str | None = None
    rules: list[ACLRuleRecord] = field(default_factory=list)


@dataclass
class InterfacePolicyBindingRecord:
    interface: str
    nat_ruleset: str | None = None
    filter_ruleset: str | None = None


@dataclass
class BGPSnapshot:
    asn: str | None = None
    router_id: str | None = None
    vrf_id: str | None = None
    ipv4_unicast_enabled: bool | None = None
    ebgp_requires_policy: bool | None = None
    log_neighbor_changes: bool | None = None
    network_import_check: bool | None = None
    keepalive_seconds: int | None = None
    hold_time_seconds: int | None = None
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
    prefix_lists: list[PrefixListRecord]
    route_maps: list[RouteMapRecord]
    bfd_sessions: list[BFDSessionRecord]
    nat_rulesets: list[NATRulesetRecord]
    acl_rulesets: list[ACLRulesetRecord]
    interface_policy_bindings: list[InterfacePolicyBindingRecord]
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
        route_config = self._collect_route_config_subtree(target, session, config)

        monitoring = self.client.get_monitoring(target, session, scope="all")
        interfaces = self._collect_interfaces(config)
        static_routes = self._collect_static_routes(config)
        bgp = self._collect_bgp(route_config)
        prefix_lists = self._collect_prefix_lists(route_config)
        route_maps = self._collect_route_maps(route_config)
        bfd_sessions = self._collect_bfd_sessions(config)
        nat_rulesets = self._collect_nat_rulesets(config)
        acl_rulesets = self._collect_acl_rulesets(config)
        interface_policy_bindings = self._collect_interface_policy_bindings(config)

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
            prefix_lists=prefix_lists,
            route_maps=route_maps,
            bfd_sessions=bfd_sessions,
            nat_rulesets=nat_rulesets,
            acl_rulesets=acl_rulesets,
            interface_policy_bindings=interface_policy_bindings,
            raw_sections={
                "config_root_keys": sorted(config.keys()) if isinstance(config, dict) else [],
                "monitoring_sessions": monitoring.get("sessions", []),
            },
        )

    def _collect_route_config_subtree(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        route_config = config.get("route-config")
        if isinstance(route_config, dict) and route_config.get("prefix-lists") and route_config.get("route-maps"):
            return route_config

        try:
            route_payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/route-config",
                strict_config=True,
            )
        except Exception:
            return route_config if isinstance(route_config, dict) else {}

        route_value = route_payload.get("value")
        return route_value if isinstance(route_value, dict) else {}

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

    def _collect_bgp(self, route_config: dict[str, Any]) -> BGPSnapshot:
        router = route_config.get("dynamic", {}).get("bgp", {}).get("routers", {}).get("router", {})
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
                    bfd=_to_bool(item.get("bfd")),
                    peer_group=item.get("peer-group-name"),
                    remote_asn=item.get("remote-asn"),
                    description=item.get("description"),
                    update_source=item.get("update-source"),
                    ebgp_multihop_max_hops=_to_int(item.get("ebgp-multihop", {}).get("max-hop-count")),
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
            vrf_id=router.get("vrf-id"),
            ipv4_unicast_enabled=_to_bool(router.get("defaults", {}).get("ipv4-unicast-enabled")),
            ebgp_requires_policy=_to_bool(router.get("ebgp-requires-policy")),
            log_neighbor_changes=_to_bool(router.get("log-neighbor-changes")),
            network_import_check=_to_bool(router.get("network-import-check")),
            keepalive_seconds=_to_int(router.get("timers", {}).get("keep-alive")),
            hold_time_seconds=_to_int(router.get("timers", {}).get("hold-time")),
            neighbors=neighbors,
            network_announcements=announcements,
        )

    def _collect_prefix_lists(self, route_config: dict[str, Any]) -> list[PrefixListRecord]:
        prefix_lists = []
        prefix_root = route_config.get("prefix-lists")
        if not isinstance(prefix_root, dict):
            prefix_root = route_config.get("dynamic", {}).get("prefix-lists", {})
        items = prefix_root.get("list")
        for item in _as_list(items):
            if not isinstance(item, dict):
                continue
            rules = []
            for rule in _as_list(item.get("rules", {}).get("rule")):
                if not isinstance(rule, dict):
                    continue
                rules.append(
                    PrefixListRuleRecord(
                        sequence=str(rule.get("sequence")),
                        action=rule.get("action"),
                        prefix=rule.get("prefix"),
                    )
                )
            prefix_lists.append(
                PrefixListRecord(
                    name=str(item.get("name")),
                    rules=rules,
                )
            )
        return prefix_lists

    def _collect_route_maps(self, route_config: dict[str, Any]) -> list[RouteMapRecord]:
        route_maps = []
        route_map_root = route_config.get("route-maps")
        if not isinstance(route_map_root, dict):
            route_map_root = route_config.get("dynamic", {}).get("route-maps", {})
        items = route_map_root.get("map")
        for item in _as_list(items):
            if not isinstance(item, dict):
                continue
            rules = []
            for rule in _as_list(item.get("rules", {}).get("rule")):
                if not isinstance(rule, dict):
                    continue
                rules.append(
                    RouteMapRuleRecord(
                        sequence=str(rule.get("sequence")),
                        policy=rule.get("policy"),
                        match_ip_prefix_list=rule.get("match", {}).get("ip-address-prefix-list"),
                        set_as_path_prepend=rule.get("set", {}).get("as-path", {}).get("prepend"),
                    )
                )
            route_maps.append(
                RouteMapRecord(
                    name=str(item.get("name")),
                    rules=rules,
                )
            )
        return route_maps

    def _collect_bfd_sessions(self, config: dict[str, Any]) -> list[BFDSessionRecord]:
        sessions = []
        items = config.get("bfd-config", {}).get("bfd-table", {}).get("bfd-session")
        for item in _as_list(items):
            if not isinstance(item, dict):
                continue
            sessions.append(
                BFDSessionRecord(
                    name=str(item.get("name")),
                    enabled=_to_bool(item.get("enable")),
                    interface=item.get("interface"),
                    local_ip_address=item.get("local-ip-address"),
                    peer_ip_address=item.get("peer-ip-address"),
                    desired_min_tx=_to_int(item.get("desired-min-tx")),
                    required_min_rx=_to_int(item.get("required-min-rx")),
                    detect_multiplier=_to_int(item.get("detect-multiplier")),
                )
            )
        return sessions

    def _collect_nat_rulesets(self, config: dict[str, Any]) -> list[NATRulesetRecord]:
        rulesets = []
        items = config.get("vpf-config", {}).get("nat-rulesets", {}).get("ruleset")
        for item in _as_list(items):
            if not isinstance(item, dict):
                continue
            rules = []
            for rule in _as_list(item.get("rules", {}).get("rule")):
                if not isinstance(rule, dict):
                    continue
                rules.append(
                    NATRuleRecord(
                        sequence=str(rule.get("sequence")),
                        description=rule.get("description"),
                        direction=rule.get("direction"),
                        dynamic=_to_bool(rule.get("dynamic")),
                        algorithm=rule.get("algorithm"),
                        match_from_prefix=rule.get("match", {}).get("from", {}).get("ipv4-prefix"),
                        translation_interface=rule.get("translation", {}).get("if-name"),
                    )
                )
            rulesets.append(
                NATRulesetRecord(
                    name=str(item.get("name")),
                    description=item.get("description"),
                    rules=rules,
                )
            )
        return rulesets

    def _collect_acl_rulesets(self, config: dict[str, Any]) -> list[ACLRulesetRecord]:
        rulesets = []
        items = config.get("vpf-config", {}).get("filter-rulesets", {}).get("ruleset")
        for item in _as_list(items):
            if not isinstance(item, dict):
                continue
            rules = []
            for rule in _as_list(item.get("rules", {}).get("rule")):
                if not isinstance(rule, dict):
                    continue
                rules.append(
                    ACLRuleRecord(
                        sequence=str(rule.get("sequence")),
                        description=rule.get("description"),
                        direction=rule.get("direction"),
                        ip_version=rule.get("ip-version"),
                        pass_action=_to_bool(rule.get("pass")),
                        stateful=_to_bool(rule.get("stateful")),
                        protocol_set=rule.get("filter", {}).get("protocol-set"),
                        from_prefix=rule.get("filter", {}).get("from", {}).get("ipv4-prefix"),
                        to_prefix=rule.get("filter", {}).get("to", {}).get("ipv4-prefix"),
                    )
                )
            rulesets.append(
                ACLRulesetRecord(
                    name=str(item.get("name")),
                    description=item.get("description"),
                    rules=rules,
                )
            )
        return rulesets

    def _collect_interface_policy_bindings(self, config: dict[str, Any]) -> list[InterfacePolicyBindingRecord]:
        bindings = []
        items = config.get("vpf-config", {}).get("options", {}).get("interfaces", {}).get("interface")
        for item in _as_list(items):
            if not isinstance(item, dict):
                continue
            bindings.append(
                InterfacePolicyBindingRecord(
                    interface=str(item.get("if-name")),
                    nat_ruleset=item.get("nat-ruleset"),
                    filter_ruleset=item.get("filter-ruleset"),
                )
            )
        return bindings

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


def _to_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
