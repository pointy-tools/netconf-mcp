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
    DataplaneDeviceRecord,
    DataplaneSnapshot,
    HostInterfaceRecord,
    InterfaceRecord,
    InterfacePolicyBindingRecord,
    LoggingRemoteServerRecord,
    LoggingSnapshot,
    NACMGroupRecord,
    NACMRuleListRecord,
    NACMRuleRecord,
    NACMSnapshot,
    NATRuleRecord,
    NATRulesetRecord,
    PrefixListRecord,
    PrefixListRuleRecord,
    PrometheusExporterSnapshot,
    RouteMapRecord,
    RouteMapRuleRecord,
    SSHServerSnapshot,
    StaticRouteRecord,
    SysctlRecord,
    SystemKernelModuleRecord,
    SystemSnapshot,
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


def render_text_diff(*, current_text: str, candidate_text: str, path_label: str) -> str:
    diff_lines = list(
        unified_diff(
            current_text.splitlines(),
            candidate_text.splitlines(),
            fromfile=path_label,
            tofile=f"{path_label} (proposed)",
            lineterm="",
        )
    )
    return "\n".join(diff_lines) if diff_lines else "No changes."


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

    host_interfaces = sorted(
        (
            {
                "name": item.name,
                "enabled": item.enabled,
                "ipv4_addresses": _sorted_unique(item.ipv4_addresses),
                "ipv4_dhcp_client_enabled": item.ipv4_dhcp_client_enabled,
                "ipv6_dhcp_client_enabled": item.ipv6_dhcp_client_enabled,
            }
            for item in snapshot.host_interfaces
        ),
        key=lambda item: item["name"],
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
                "activate": item.activate,
                "route_map_in": item.route_map_in,
                "route_map_out": item.route_map_out,
                "default_originate_route_map": item.default_originate_route_map,
                "send_community_standard": item.send_community_standard,
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

    dataplane_devices = sorted(
        (
            {
                "name": item.name,
                "pci_id": item.pci_id,
                "num_rx_queues": item.num_rx_queues,
                "devargs": item.devargs,
            }
            for item in snapshot.dataplane.dpdk_devices
        ),
        key=lambda item: item["name"],
    )

    sysctl_settings = [
        {
            "name": item.name,
            "value": item.value,
        }
        for item in sorted(snapshot.sysctl, key=lambda item: item.name)
    ]

    kernel_modules = sorted(
        (
            {
                "module": item.module,
                "attributes": dict(sorted(item.attributes.items())),
            }
            for item in snapshot.system.kernel_modules
        ),
        key=lambda item: item["module"],
    )

    logging_remote_servers = sorted(
        (
            {
                "name": item.name,
                "address": item.address,
                "port": item.port,
                "transport_protocol": item.transport_protocol,
                "facility": item.facility,
                "priority": item.priority,
            }
            for item in snapshot.logging.remote_servers
        ),
        key=lambda item: item["name"],
    )

    nacm_groups = sorted(
        (
            {
                "name": item.name,
                "user_names": list(item.user_names),
            }
            for item in snapshot.nacm.groups
        ),
        key=lambda item: item["name"],
    )

    nacm_rule_lists = sorted(
        (
            {
                "name": item.name,
                "group": item.group,
                "rules": [
                    {
                        "name": rule.name,
                        "module_name": rule.module_name,
                        "access_operations": rule.access_operations,
                        "action": rule.action,
                    }
                    for rule in item.rules
                ],
            }
            for item in snapshot.nacm.rule_lists
        ),
        key=lambda item: item["name"],
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
            "management": {
                "ssh_server": {
                    "netconf_enabled": snapshot.ssh_server.netconf_enabled,
                    "netconf_port": snapshot.ssh_server.netconf_port,
                },
                "host_interfaces": host_interfaces,
                "logging": {
                    "remote_servers": logging_remote_servers,
                },
                "prometheus_exporter": {
                    "host_space_filter": snapshot.prometheus_exporter.host_space_filter,
                },
            },
            "platform": {
                "dataplane": {
                    "buffers_per_numa": snapshot.dataplane.buffers_per_numa,
                    "cpu_main_core": snapshot.dataplane.cpu_main_core,
                    "cpu_skip_cores": snapshot.dataplane.cpu_skip_cores,
                    "cpu_workers": snapshot.dataplane.cpu_workers,
                    "dpdk_uio_driver": snapshot.dataplane.dpdk_uio_driver,
                    "dpdk_devices": dataplane_devices,
                    "main_heap_size": snapshot.dataplane.main_heap_size,
                    "statseg_heap_size": snapshot.dataplane.statseg_heap_size,
                },
                "sysctl": sysctl_settings,
                "system": {
                    "kernel_modules": kernel_modules,
                },
            },
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
                "ipv4_unicast_multipath": snapshot.bgp.ipv4_unicast_multipath,
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
            "nacm": {
                "enabled": snapshot.nacm.enabled,
                "read_default": snapshot.nacm.read_default,
                "write_default": snapshot.nacm.write_default,
                "exec_default": snapshot.nacm.exec_default,
                "groups": nacm_groups,
                "rule_lists": nacm_rule_lists,
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


def build_split_managed_tnsr_files(
    candidate_config: dict[str, Any],
    *,
    include_observed_state: bool = False,
) -> dict[str, str]:
    """Project the managed config into smaller repo-facing files by domain."""

    files: dict[str, dict[str, Any]] = {
        "device.json": {
            "schema_version": candidate_config["schema_version"],
            "device": candidate_config["device"],
            "metadata": candidate_config["metadata"],
        },
        "interfaces.json": {
            "interfaces": candidate_config["config"]["interfaces"],
        },
        "management/ssh-server.json": {
            "ssh_server": candidate_config["config"]["management"]["ssh_server"],
        },
        "management/host-interfaces.json": {
            "host_interfaces": candidate_config["config"]["management"]["host_interfaces"],
        },
        "management/logging.json": {
            "logging": candidate_config["config"]["management"]["logging"],
        },
        "management/prometheus-exporter.json": {
            "prometheus_exporter": candidate_config["config"]["management"]["prometheus_exporter"],
        },
        "platform/dataplane.json": {
            "dataplane": candidate_config["config"]["platform"]["dataplane"],
        },
        "platform/sysctl.json": {
            "sysctl": candidate_config["config"]["platform"]["sysctl"],
        },
        "platform/system.json": {
            "system": candidate_config["config"]["platform"]["system"],
        },
        "routing/static-routes.json": {
            "static_routes": candidate_config["config"]["routing"]["static_routes"],
        },
        "routing/bgp.json": {
            "bgp": candidate_config["config"]["bgp"],
        },
        "routing/prefix-lists.json": {
            "prefix_lists": candidate_config["config"]["routing_policy"]["prefix_lists"],
        },
        "routing/route-maps.json": {
            "route_maps": candidate_config["config"]["routing_policy"]["route_maps"],
        },
        "services/bfd.json": {
            "bfd": candidate_config["config"]["bfd"],
        },
        "security/nat-rulesets.json": {
            "nat": candidate_config["config"]["nat"],
        },
        "security/acl-rulesets.json": {
            "acl_rulesets": candidate_config["config"]["acl"]["rulesets"],
        },
        "security/interface-policy-bindings.json": {
            "interface_bindings": candidate_config["config"]["acl"]["interface_bindings"],
        },
        "security/nacm.json": {
            "nacm": candidate_config["config"]["nacm"],
        },
    }
    if include_observed_state:
        files["observed-state.json"] = {
            "observed_state": candidate_config["observed_state"],
        }
    return {path: _render_json(payload) for path, payload in files.items()}


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
        host_interfaces=[
            HostInterfaceRecord(
                name=item["name"],
                enabled=item.get("enabled"),
                ipv4_addresses=list(item.get("ipv4_addresses", [])),
                ipv4_dhcp_client_enabled=item.get("ipv4_dhcp_client_enabled"),
                ipv6_dhcp_client_enabled=item.get("ipv6_dhcp_client_enabled"),
            )
            for item in payload.get("host_interfaces", [])
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
            ipv4_unicast_multipath=payload.get("bgp", {}).get("ipv4_unicast_multipath"),
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
                    activate=item.get("activate"),
                    route_map_in=item.get("route_map_in"),
                    route_map_out=item.get("route_map_out"),
                    default_originate_route_map=item.get("default_originate_route_map"),
                    send_community_standard=item.get("send_community_standard"),
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
        ssh_server=SSHServerSnapshot(
            netconf_enabled=payload.get("ssh_server", {}).get("netconf_enabled"),
            netconf_port=payload.get("ssh_server", {}).get("netconf_port"),
        ),
        dataplane=DataplaneSnapshot(
            buffers_per_numa=payload.get("dataplane", {}).get("buffers_per_numa"),
            cpu_main_core=payload.get("dataplane", {}).get("cpu_main_core"),
            cpu_skip_cores=payload.get("dataplane", {}).get("cpu_skip_cores"),
            cpu_workers=payload.get("dataplane", {}).get("cpu_workers"),
            dpdk_uio_driver=payload.get("dataplane", {}).get("dpdk_uio_driver"),
            dpdk_devices=[
                DataplaneDeviceRecord(
                    name=item["name"],
                    pci_id=item.get("pci_id"),
                    num_rx_queues=item.get("num_rx_queues"),
                    devargs=item.get("devargs"),
                )
                for item in payload.get("dataplane", {}).get("dpdk_devices", [])
            ],
            main_heap_size=payload.get("dataplane", {}).get("main_heap_size"),
            statseg_heap_size=payload.get("dataplane", {}).get("statseg_heap_size"),
        ),
        sysctl=[
            SysctlRecord(
                name=item["name"],
                value=item["value"],
            )
            for item in payload.get("sysctl", [])
        ],
        system=SystemSnapshot(
            kernel_modules=[
                SystemKernelModuleRecord(
                    module=item["module"],
                    attributes=dict(item.get("attributes", {})),
                )
                for item in payload.get("system", {}).get("kernel_modules", [])
            ],
        ),
        logging=LoggingSnapshot(
            remote_servers=[
                LoggingRemoteServerRecord(
                    name=item["name"],
                    address=item.get("address"),
                    port=item.get("port"),
                    transport_protocol=item.get("transport_protocol"),
                    facility=item.get("facility"),
                    priority=item.get("priority"),
                )
                for item in payload.get("logging", {}).get("remote_servers", [])
            ],
        ),
        prometheus_exporter=PrometheusExporterSnapshot(
            host_space_filter=payload.get("prometheus_exporter", {}).get("host_space_filter"),
        ),
        nacm=NACMSnapshot(
            enabled=payload.get("nacm", {}).get("enabled"),
            read_default=payload.get("nacm", {}).get("read_default"),
            write_default=payload.get("nacm", {}).get("write_default"),
            exec_default=payload.get("nacm", {}).get("exec_default"),
            groups=[
                NACMGroupRecord(
                    name=item["name"],
                    user_names=list(item.get("user_names", [])),
                )
                for item in payload.get("nacm", {}).get("groups", [])
            ],
            rule_lists=[
                NACMRuleListRecord(
                    name=item["name"],
                    group=item.get("group"),
                    rules=[
                        NACMRuleRecord(
                            name=rule["name"],
                            module_name=rule.get("module_name"),
                            access_operations=rule.get("access_operations"),
                            action=rule.get("action"),
                        )
                        for rule in item.get("rules", [])
                    ],
                )
                for item in payload.get("nacm", {}).get("rule_lists", [])
            ],
        ),
        raw_sections=dict(payload.get("raw_sections", {})),
    )
    return build_managed_tnsr_config(snapshot)


def _proposal_summary(existing: dict[str, Any] | None, candidate: dict[str, Any]) -> list[str]:
    current_interfaces = len(existing.get("config", {}).get("interfaces", [])) if existing else 0
    current_host_interfaces = len(existing.get("config", {}).get("management", {}).get("host_interfaces", [])) if existing else 0
    current_routes = len(existing.get("config", {}).get("routing", {}).get("static_routes", [])) if existing else 0
    current_neighbors = len(existing.get("config", {}).get("bgp", {}).get("neighbors", [])) if existing else 0
    current_prefix_lists = len(existing.get("config", {}).get("routing_policy", {}).get("prefix_lists", [])) if existing else 0
    current_route_maps = len(existing.get("config", {}).get("routing_policy", {}).get("route_maps", [])) if existing else 0
    current_bfd_sessions = len(existing.get("config", {}).get("bfd", {}).get("sessions", [])) if existing else 0
    current_nat_rulesets = len(existing.get("config", {}).get("nat", {}).get("rulesets", [])) if existing else 0
    current_acl_rulesets = len(existing.get("config", {}).get("acl", {}).get("rulesets", [])) if existing else 0
    current_nacm_rule_lists = len(existing.get("config", {}).get("nacm", {}).get("rule_lists", [])) if existing else 0
    current_sysctl = len(existing.get("config", {}).get("platform", {}).get("sysctl", [])) if existing else 0
    current_kernel_modules = len(existing.get("config", {}).get("platform", {}).get("system", {}).get("kernel_modules", [])) if existing else 0
    current_logging_servers = len(existing.get("config", {}).get("management", {}).get("logging", {}).get("remote_servers", [])) if existing else 0

    candidate_interfaces = len(candidate["config"]["interfaces"])
    candidate_host_interfaces = len(candidate["config"]["management"]["host_interfaces"])
    candidate_routes = len(candidate["config"]["routing"]["static_routes"])
    candidate_neighbors = len(candidate["config"]["bgp"]["neighbors"])
    candidate_prefix_lists = len(candidate["config"]["routing_policy"]["prefix_lists"])
    candidate_route_maps = len(candidate["config"]["routing_policy"]["route_maps"])
    candidate_bfd_sessions = len(candidate["config"]["bfd"]["sessions"])
    candidate_nat_rulesets = len(candidate["config"]["nat"]["rulesets"])
    candidate_acl_rulesets = len(candidate["config"]["acl"]["rulesets"])
    candidate_nacm_rule_lists = len(candidate["config"]["nacm"]["rule_lists"])
    candidate_sysctl = len(candidate["config"]["platform"]["sysctl"])
    candidate_kernel_modules = len(candidate["config"]["platform"]["system"]["kernel_modules"])
    candidate_logging_servers = len(candidate["config"]["management"]["logging"]["remote_servers"])

    return [
        f"Managed file: {'update' if existing else 'create'}",
        f"Interfaces: {current_interfaces} -> {candidate_interfaces}",
        f"Host interfaces: {current_host_interfaces} -> {candidate_host_interfaces}",
        f"Static routes: {current_routes} -> {candidate_routes}",
        f"BGP neighbors: {current_neighbors} -> {candidate_neighbors}",
        f"Prefix lists: {current_prefix_lists} -> {candidate_prefix_lists}",
        f"Route maps: {current_route_maps} -> {candidate_route_maps}",
        f"BFD sessions: {current_bfd_sessions} -> {candidate_bfd_sessions}",
        f"NAT rulesets: {current_nat_rulesets} -> {candidate_nat_rulesets}",
        f"ACL rulesets: {current_acl_rulesets} -> {candidate_acl_rulesets}",
        f"NACM rule lists: {current_nacm_rule_lists} -> {candidate_nacm_rule_lists}",
        f"Sysctl settings: {current_sysctl} -> {candidate_sysctl}",
        f"Kernel modules: {current_kernel_modules} -> {candidate_kernel_modules}",
        f"Logging servers: {current_logging_servers} -> {candidate_logging_servers}",
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
    diff_text = render_text_diff(
        current_text=current_text,
        candidate_text=candidate_text,
        path_label=str(managed_path),
    )

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


def build_split_tnsr_proposal_index(
    *,
    managed_root: Path,
    file_map: dict[str, str],
) -> str:
    lines = [
        "# TNSR Split Managed Config Proposal",
        "",
        f"Managed root: `{managed_root}`",
        "",
        "## Files",
        "",
    ]

    for rel_path in sorted(file_map):
        output_path = managed_root / rel_path
        current_text = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
        candidate_text = file_map[rel_path]
        status = "update" if output_path.exists() else "create"
        diff_text = render_text_diff(
            current_text=current_text,
            candidate_text=candidate_text,
            path_label=str(output_path),
        )
        lines.extend(
            [
                f"### `{output_path}`",
                "",
                f"- Action: `{status}`",
                "",
                "```diff",
                diff_text,
                "```",
                "",
            ]
        )

    return "\n".join(lines)
