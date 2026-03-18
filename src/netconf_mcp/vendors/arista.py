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
    # Additional namespaces for new domains
    "oc-acl": "http://openconfig.net/yang/acl",
    "oc-def-sets": "http://openconfig.net/yang/defined-sets",
    "oc-mlag": "http://arista.com/yang/openconfig/mlag",
    "oc-vxlan": "http://arista.com/yang/openconfig/vxlan",
    "oc-evpn": "http://openconfig.net/yang/evpn",
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


# Routing Policy domain dataclasses
@dataclass
class PrefixSetEntryRecord:
    prefix: str | None = None
    masklength_range: str | None = None


@dataclass
class PrefixSetRecord:
    name: str
    prefixes: list[PrefixSetEntryRecord] = field(default_factory=list)


@dataclass
class RoutingPolicyStatementRecord:
    sequence: str | None = None
    conditions: dict[str, Any] = field(default_factory=dict)
    actions: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingPolicyRecord:
    name: str
    statements: list[RoutingPolicyStatementRecord] = field(default_factory=list)


# ACL domain dataclasses
@dataclass
class ACLEntryRecord:
    sequence: str | None = None
    match_conditions: dict[str, Any] = field(default_factory=dict)
    action: str | None = None
    description: str | None = None


@dataclass
class ACLSetRecord:
    name: str
    type: str | None = None
    entries: list[ACLEntryRecord] = field(default_factory=list)


@dataclass
class ACLInterfaceBindingRecord:
    interface: str | None = None
    acl_set: str | None = None
    direction: str | None = None


# MLAG domain dataclasses
@dataclass
class MLAGRecord:
    enabled: bool | None = None
    domain_id: str | None = None
    local_interface: str | None = None
    peer_address: str | None = None
    peer_link: str | None = None
    state: dict[str, Any] = field(default_factory=dict)


@dataclass
class MLAGInterfaceRecord:
    interface: str | None = None
    mlag_id: int | None = None
    status: str | None = None


# EVPN/VXLAN domain dataclasses
@dataclass
class EvpnInstanceRecord:
    name: str | None = None
    vni: int | None = None
    route_target_import: list[str] = field(default_factory=list)
    route_target_export: list[str] = field(default_factory=list)
    rd: str | None = None


@dataclass
class VxlanMappingRecord:
    vni: int | None = None
    vlan_id: int | None = None
    vrf_name: str | None = None
    flood_vteps: list[str] = field(default_factory=list)
    source_interface: str | None = None


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
    # Routing Policy domain fields
    prefix_sets: list[PrefixSetRecord] = field(default_factory=list)
    routing_policies: list[RoutingPolicyRecord] = field(default_factory=list)
    # ACL domain fields
    acl_sets: list[ACLSetRecord] = field(default_factory=list)
    acl_bindings: list[ACLInterfaceBindingRecord] = field(default_factory=list)
    # MLAG domain fields
    mlag: MLAGRecord | None = None
    mlag_interfaces: list[MLAGInterfaceRecord] = field(default_factory=list)
    # EVPN/VXLAN domain fields
    evpn_instances: list[EvpnInstanceRecord] = field(default_factory=list)
    vxlan_mappings: list[VxlanMappingRecord] = field(default_factory=list)
    # Metadata fields
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

        # Routing Policy domain fields
        prefix_sets, ps_warnings = self._collect_prefix_sets(target_with_ns, session)
        warnings.extend(ps_warnings)

        routing_policies, rp_warnings = self._collect_routing_policies(target_with_ns, session)
        warnings.extend(rp_warnings)

        # ACL domain fields
        acl_sets, acl_warnings = self._collect_acl_sets(target_with_ns, session)
        warnings.extend(acl_warnings)

        acl_bindings, binding_warnings = self._collect_acl_bindings(target_with_ns, session)
        warnings.extend(binding_warnings)

        # MLAG domain fields
        mlag, mlag_warnings = self._collect_mlag(target_with_ns, session)
        warnings.extend(mlag_warnings)

        mlag_interfaces, mlag_if_warnings = self._collect_mlag_interfaces(target_with_ns, session)
        warnings.extend(mlag_if_warnings)

        # EVPN/VXLAN domain fields
        evpn_instances, evpn_warnings = self._collect_evpn_instances(target_with_ns, session)
        warnings.extend(evpn_warnings)

        vxlan_mappings, vxlan_warnings = self._collect_vxlan_mappings(target_with_ns, session)
        warnings.extend(vxlan_warnings)

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
            prefix_sets=prefix_sets,
            routing_policies=routing_policies,
            acl_sets=acl_sets,
            acl_bindings=acl_bindings,
            mlag=mlag,
            mlag_interfaces=mlag_interfaces,
            evpn_instances=evpn_instances,
            vxlan_mappings=vxlan_mappings,
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

    def _collect_prefix_sets(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> tuple[list[PrefixSetRecord], list[str]]:
        """Collect prefix sets from openconfig-defined-sets."""
        prefix_sets: list[PrefixSetRecord] = []
        warnings: list[str] = []

        try:
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-def-sets:defined-sets/oc-def-sets:prefix-sets/oc-def-sets:prefix-set",
            )
            config = payload.get("value", {})
        except Exception as e:
            warnings.append(f"Could not collect prefix sets: {e}")
            return prefix_sets, warnings

        for item in _as_list(config):
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            if not name:
                continue

            # Extract prefixes from the prefix-set
            prefixes: list[PrefixSetEntryRecord] = []
            prefixes_container = item.get("prefixes", {})
            if isinstance(prefixes_container, dict):
                prefix_list = _as_list(prefixes_container.get("prefix"))
                for prefix_item in prefix_list:
                    if not isinstance(prefix_item, dict):
                        continue

                    prefixes.append(
                        PrefixSetEntryRecord(
                            prefix=prefix_item.get("ip-prefix"),
                            masklength_range=prefix_item.get("masklength-range"),
                        )
                    )

            prefix_sets.append(
                PrefixSetRecord(
                    name=str(name),
                    prefixes=prefixes,
                )
            )

        return prefix_sets, warnings

    def _collect_routing_policies(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> tuple[list[RoutingPolicyRecord], list[str]]:
        """Collect routing policies from openconfig-routing-policy."""
        policies: list[RoutingPolicyRecord] = []
        warnings: list[str] = []

        try:
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-rpol:routing-policy/oc-rpol:policy-definitions/oc-rpol:policy-definition",
            )
            config = payload.get("value", {})
        except Exception as e:
            warnings.append(f"Could not collect routing policies: {e}")
            return policies, warnings

        for item in _as_list(config):
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            if not name:
                continue

            # Extract statements from the policy-definition
            statements: list[RoutingPolicyStatementRecord] = []
            statements_container = item.get("statements", {})
            if isinstance(statements_container, dict):
                statement_list = _as_list(statements_container.get("statement"))
                for stmt in statement_list:
                    if not isinstance(stmt, dict):
                        continue

                    # Extract conditions
                    conditions: dict[str, Any] = {}
                    conditions_container = stmt.get("conditions", {})
                    if isinstance(conditions_container, dict):
                        # Check for prefix-set match
                        match_prefix = conditions_container.get("match-prefix-set", {})
                        if isinstance(match_prefix, dict):
                            prefix_set_ref = match_prefix.get("config", {}).get("prefix-set")
                            if prefix_set_ref:
                                conditions["match_prefix_set"] = prefix_set_ref

                        # Check for community match
                        match_comm = conditions_container.get("match-community", {})
                        if isinstance(match_comm, dict):
                            community_config = match_comm.get("config", {})
                            if community_config:
                                conditions["match_community"] = community_config.get("community-set")

                        # Check for as-path match
                        match_as_path = conditions_container.get("match-as-path-set", {})
                        if isinstance(match_as_path, dict):
                            as_path_config = match_as_path.get("config", {})
                            if as_path_config:
                                conditions["match_as_path_set"] = as_path_config.get("as-path-set")

                    # Extract actions
                    actions: dict[str, Any] = {}
                    actions_container = stmt.get("actions", {})
                    if isinstance(actions_container, dict):
                        # Get policy result (ACCEPT_ROUTE, REJECT_ROUTE)
                        config_actions = actions_container.get("config", {})
                        if isinstance(config_actions, dict):
                            policy_result = config_actions.get("policy-result")
                            if policy_result:
                                actions["policy_result"] = policy_result

                        # Check for BGP actions
                        bgp_actions = actions_container.get("bgp-actions", {})
                        if isinstance(bgp_actions, dict):
                            # Set community
                            set_community = bgp_actions.get("set-community", {})
                            if isinstance(set_community, dict):
                                comm_config = set_community.get("config", {})
                                if comm_config:
                                    actions["set_community"] = comm_config.get("communities")

                            # Set local preference
                            set_local_pref = bgp_actions.get("set-local-pref", {})
                            if isinstance(set_local_pref, dict):
                                lp_config = set_local_pref.get("config", {})
                                if lp_config:
                                    actions["set_local_pref"] = lp_config.get("local-pref")

                            # Set med
                            set_med = bgp_actions.get("set-med", {})
                            if isinstance(set_med, dict):
                                med_config = set_med.get("config", {})
                                if med_config:
                                    actions["set_med"] = med_config.get("med")

                            # Set next-hop
                            set_next_hop = bgp_actions.get("set-next-hop", {})
                            if isinstance(set_next_hop, dict):
                                nh_config = set_next_hop.get("config", {})
                                if nh_config:
                                    actions["set_next_hop"] = nh_config.get("next-hop")

                    statements.append(
                        RoutingPolicyStatementRecord(
                            sequence=stmt.get("name"),
                            conditions=conditions,
                            actions=actions,
                        )
                    )

            policies.append(
                RoutingPolicyRecord(
                    name=str(name),
                    statements=statements,
                )
            )

        return policies, warnings

    def _collect_acl_sets(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> tuple[list[ACLSetRecord], list[str]]:
        """Collect ACL sets from openconfig-acl."""
        acl_sets: list[ACLSetRecord] = []
        warnings: list[str] = []

        try:
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-acl:acl/oc-acl:acl-sets/oc-acl:acl-set",
            )
            config = payload.get("value", {})
        except Exception as e:
            warnings.append(f"Could not collect ACL sets: {e}")
            return acl_sets, warnings

        for item in _as_list(config):
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            if not name:
                continue

            acl_type = item.get("type")

            # Extract ACL entries
            entries: list[ACLEntryRecord] = []
            entries_container = item.get("acl-entries", {})
            if isinstance(entries_container, dict):
                entry_list = _as_list(entries_container.get("acl-entry"))
                for entry in entry_list:
                    if not isinstance(entry, dict):
                        continue

                    sequence_id = entry.get("sequence-id")

                    # Extract match conditions
                    match_conditions: dict[str, Any] = {}

                    # IPv4 match conditions
                    ipv4_config = entry.get("ipv4", {})
                    if isinstance(ipv4_config, dict):
                        ipv4_match = ipv4_config.get("config", {})
                        if isinstance(ipv4_match, dict):
                            src_addr = ipv4_match.get("source-address")
                            if src_addr:
                                match_conditions["source-address"] = src_addr
                            dst_addr = ipv4_match.get("destination-address")
                            if dst_addr:
                                match_conditions["destination-address"] = dst_addr

                    # IPv6 match conditions
                    ipv6_config = entry.get("ipv6", {})
                    if isinstance(ipv6_config, dict):
                        ipv6_match = ipv6_config.get("config", {})
                        if isinstance(ipv6_match, dict):
                            src_addr = ipv6_match.get("source-address")
                            if src_addr:
                                match_conditions["source-address"] = src_addr
                            dst_addr = ipv6_match.get("destination-address")
                            if dst_addr:
                                match_conditions["destination-address"] = dst_addr

                    # L4 match conditions (protocol, ports)
                    l4_config = entry.get("transport", {})
                    if isinstance(l4_config, dict):
                        l4_match = l4_config.get("config", {})
                        if isinstance(l4_match, dict):
                            protocol = l4_match.get("protocol")
                            if protocol:
                                match_conditions["protocol"] = protocol
                            src_port = l4_match.get("source-port")
                            if src_port:
                                match_conditions["source-port"] = src_port
                            dst_port = l4_match.get("destination-port")
                            if dst_port:
                                match_conditions["destination-port"] = dst_port

                    # Extract actions
                    action: str | None = None
                    actions_container = entry.get("actions", {})
                    if isinstance(actions_container, dict):
                        action_config = actions_container.get("config", {})
                        if isinstance(action_config, dict):
                            action = action_config.get("forwarding-action")

                    # Extract description
                    description = None
                    if isinstance(actions_container, dict):
                        action_config = actions_container.get("config", {})
                        if isinstance(action_config, dict):
                            description = action_config.get("description")

                    entries.append(
                        ACLEntryRecord(
                            sequence=str(sequence_id) if sequence_id is not None else None,
                            match_conditions=match_conditions,
                            action=action,
                            description=description,
                        )
                    )

            acl_sets.append(
                ACLSetRecord(
                    name=str(name),
                    type=acl_type,
                    entries=entries,
                )
            )

        return acl_sets, warnings

    def _collect_acl_bindings(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> tuple[list[ACLInterfaceBindingRecord], list[str]]:
        """Collect ACL interface bindings from openconfig-acl."""
        bindings: list[ACLInterfaceBindingRecord] = []
        warnings: list[str] = []

        try:
            # Try to get ACL interface bindings from the ACL model
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-acl:acl/oc-acl:interfaces/oc-acl:interface",
            )
            config = payload.get("value", {})
        except Exception as e:
            warnings.append(f"Could not collect ACL bindings: {e}")
            return bindings, warnings

        for item in _as_list(config):
            if not isinstance(item, dict):
                continue

            interface = item.get("id")
            if not interface:
                continue

            # Get the ACL set reference
            interface_config = item.get("config", {})
            if isinstance(interface_config, dict):
                acl_set = interface_config.get("acl-name")
                direction = interface_config.get("direction")

                if acl_set:
                    bindings.append(
                        ACLInterfaceBindingRecord(
                            interface=str(interface),
                            acl_set=str(acl_set),
                            direction=direction,
                        )
                    )

        return bindings, warnings

    def _collect_mlag(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> tuple[MLAGRecord | None, list[str]]:
        """Collect MLAG global configuration from Arista EOS."""
        mlag_record: MLAGRecord | None = None
        warnings: list[str] = []

        try:
            # Try Arista-specific MLAG namespace first
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-mlag:mlag",
            )
            config = payload.get("value", {})
        except Exception as e:
            warnings.append(f"Could not collect MLAG: {e}")
            return mlag_record, warnings

        if not config or not isinstance(config, dict):
            return mlag_record, warnings

        # Extract config section
        config_section = config.get("config", {})
        if not isinstance(config_section, dict):
            config_section = {}

        # Extract state section
        state_section = config.get("state", {})
        if not isinstance(state_section, dict):
            state_section = {}

        # Check if MLAG is configured (domain-id is the key indicator)
        domain_id = config_section.get("domain-id")
        if not domain_id:
            # MLAG not configured
            return mlag_record, warnings

        # Build state dict
        state: dict[str, Any] = {}
        status = state_section.get("status")
        if status:
            state["status"] = status
        peer_link_status = state_section.get("peer-link-status")
        if peer_link_status:
            state["peer_link_status"] = peer_link_status

        mlag_record = MLAGRecord(
            enabled=True,
            domain_id=str(domain_id),
            local_interface=config_section.get("local-interface"),
            peer_address=config_section.get("peer-address"),
            peer_link=config_section.get("peer-link"),
            state=state,
        )

        return mlag_record, warnings

    def _collect_mlag_interfaces(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> tuple[list[MLAGInterfaceRecord], list[str]]:
        """Collect MLAG interface memberships from Arista EOS."""
        interfaces: list[MLAGInterfaceRecord] = []
        warnings: list[str] = []

        try:
            # Query interfaces that might have MLAG IDs
            # Try OpenConfig interfaces first, then look for MLAG augment
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-if:interfaces/interface",
            )
            config = payload.get("value", {})
        except Exception as e:
            warnings.append(f"Could not collect MLAG interfaces: {e}")
            return interfaces, warnings

        for item in _as_list(config):
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            if not name:
                continue

            # Look for MLAG ID in various possible locations
            # Arista augments interface config with mlag-id
            mlag_id = None

            # Check for MLAG in config
            config_data = item.get("config", {})
            if isinstance(config_data, dict):
                mlag_id = config_data.get("mlag-id")

            # Also check state
            if mlag_id is None:
                state_data = item.get("state", {})
                if isinstance(state_data, dict):
                    mlag_id = state_data.get("mlag-id")

            if mlag_id is not None:
                # Determine status from state
                status = None
                state_data = item.get("state", {})
                if isinstance(state_data, dict):
                    # Look for MLAG state info
                    mlag_state = state_data.get("mlag", {})
                    if isinstance(mlag_state, dict):
                        status = mlag_state.get("status")

                interfaces.append(
                    MLAGInterfaceRecord(
                        interface=str(name),
                        mlag_id=_to_int(mlag_id),
                        status=status,
                    )
                )

        return interfaces, warnings

    def _collect_evpn_instances(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> tuple[list[EvpnInstanceRecord], list[str]]:
        """Collect EVPN instances from OpenConfig network-instance EVPN data."""
        instances: list[EvpnInstanceRecord] = []
        warnings: list[str] = []

        try:
            # Query network-instances with EVPN
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-ni:network-instances/network-instance",
            )
            config = payload.get("value", {})
        except Exception as e:
            warnings.append(f"Could not collect EVPN instances: {e}")
            return instances, warnings

        for item in _as_list(config):
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            if not name:
                continue

            # Get the network instance type to determine L2 vs L3
            ni_type = item.get("config", {}).get("type")
            if not ni_type:
                continue

            # Look for EVPN configuration
            evpn_config = item.get("evpn", {})
            if not isinstance(evpn_config, dict):
                continue

            # Extract route distinguisher
            rd = None
            evpn_cfg = evpn_config.get("config", {})
            if isinstance(evpn_cfg, dict):
                rd = evpn_cfg.get("route-distinguisher")

            # Extract route targets
            rt_import: list[str] = []
            rt_export: list[str] = []

            rt_container = evpn_config.get("route-targets", {})
            if isinstance(rt_container, dict):
                rt_list = _as_list(rt_container.get("route-target"))
                for rt in rt_list:
                    if not isinstance(rt, dict):
                        continue
                    rt_type = rt.get("type")
                    rt_value = rt.get("value")
                    if rt_type == "IMPORT" and rt_value:
                        rt_import.append(str(rt_value))
                    elif rt_type == "EXPORT" and rt_value:
                        rt_export.append(str(rt_value))

            # Extract VNI from VLAN or VRF config
            vni: int | None = None

            # Check for VLAN-based VNI (L2VSI)
            vlans_container = item.get("vlans", {})
            if isinstance(vlans_container, dict):
                vlan_list = _as_list(vlans_container.get("vlan"))
                for vlan in vlan_list:
                    if not isinstance(vlan, dict):
                        continue
                    vlan_cfg = vlan.get("config", {})
                    if isinstance(vlan_cfg, dict):
                        vni_val = vlan_cfg.get("vni")
                        if vni_val is not None:
                            vni = _to_int(vni_val)
                            break

            # If no VLAN VNI, check for VRF VNI (L3VRF)
            if vni is None:
                vrf_cfg = item.get("vrf", {})
                if isinstance(vrf_cfg, dict):
                    vrf_cfg_inner = vrf_cfg.get("config", {})
                    if isinstance(vrf_cfg_inner, dict):
                        vni = _to_int(vrf_cfg_inner.get("vni"))

            # Only add if we have EVPN config (RD or RTs) or VNI
            if rd or rt_import or rt_export or vni is not None:
                instances.append(
                    EvpnInstanceRecord(
                        name=str(name),
                        vni=vni,
                        route_target_import=rt_import,
                        route_target_export=rt_export,
                        rd=rd,
                    )
                )

        return instances, warnings

    def _collect_vxlan_mappings(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
    ) -> tuple[list[VxlanMappingRecord], list[str]]:
        """Collect VXLAN VNI mappings from Arista VXLAN model."""
        mappings: list[VxlanMappingRecord] = []
        warnings: list[str] = []

        source_interface: str | None = None

        try:
            # First try Arista VXLAN model on Vxlan1 interface
            payload = self.client.datastore_get(
                target,
                session,
                datastore="running",
                xpath="/oc-if:interfaces/interface[name='Vxlan1']",
            )
            config = payload.get("value", {})
        except Exception:
            # Fall back to trying the VXLAN namespace directly
            try:
                payload = self.client.datastore_get(
                    target,
                    session,
                    datastore="running",
                    xpath="/oc-vxlan:vxlan",
                )
                config = payload.get("value", {})
            except Exception as e:
                warnings.append(f"Could not collect VXLAN mappings: {e}")
                return mappings, warnings

        # Handle both single interface and list of interfaces
        interface_list = _as_list(config)
        if len(interface_list) == 1 and isinstance(interface_list[0], dict):
            # Single interface case - check if it's Vxlan1
            iface = interface_list[0]
            if iface.get("name") != "Vxlan1":
                # Not Vxlan1, try to find Vxlan1 in the list
                for item in interface_list:
                    if isinstance(item, dict) and item.get("name") == "Vxlan1":
                        interface_list = [item]
                        break

        for item in interface_list:
            if not isinstance(item, dict):
                continue

            # Skip non-VXLAN interfaces
            if item.get("name") != "Vxlan1":
                continue

            # Extract source interface from VXLAN config
            vxlan_container = item.get("vxlan", {})
            if not isinstance(vxlan_container, dict):
                vxlan_container = item.get("oc-vxlan:vxlan", {})

            if isinstance(vxlan_container, dict):
                vxlan_cfg = vxlan_container.get("config", {})
                if isinstance(vxlan_cfg, dict):
                    if source_interface is None:
                        source_interface = vxlan_cfg.get("source-interface")

                # Extract VLAN-VNI mappings
                vlan_vni_mappings = vxlan_container.get("vlan-vni-mappings", {})
                if isinstance(vlan_vni_mappings, dict):
                    mapping_list = _as_list(vlan_vni_mappings.get("vlan-vni-mapping"))
                    for mapping in mapping_list:
                        if not isinstance(mapping, dict):
                            continue

                        vni = _to_int(mapping.get("vni"))
                        vlan_id = _to_int(mapping.get("vlan-id"))

                        if vni is not None:
                            mappings.append(
                                VxlanMappingRecord(
                                    vni=vni,
                                    vlan_id=vlan_id,
                                    vrf_name=None,
                                    source_interface=source_interface,
                                    flood_vteps=[],
                                )
                            )

                # Extract VRF-VNI mappings
                vrf_vni_mappings = vxlan_container.get("vrf-vni-mappings", {})
                if isinstance(vrf_vni_mappings, dict):
                    mapping_list = _as_list(vrf_vni_mappings.get("vrf-vni-mapping"))
                    for mapping in mapping_list:
                        if not isinstance(mapping, dict):
                            continue

                        vni = _to_int(mapping.get("vni"))
                        vrf_name = mapping.get("vrf-name")

                        if vni is not None:
                            mappings.append(
                                VxlanMappingRecord(
                                    vni=vni,
                                    vlan_id=None,
                                    vrf_name=vrf_name,
                                    source_interface=source_interface,
                                    flood_vteps=[],
                                )
                            )

        # Add warning if we found VXLAN data from vendor-specific model
        if mappings and source_interface is None:
            warnings.append("VXLAN VNI mappings collected but source-interface not found in Vxlan1 config")

        return mappings, warnings


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
