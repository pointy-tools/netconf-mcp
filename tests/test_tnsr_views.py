from __future__ import annotations

from netconf_mcp.vendors.tnsr_views import build_tnsr_domain_view


def _sample_snapshot() -> dict:
    return {
        "interfaces": [
            {"name": "LAN", "kind": "dataplane", "enabled": True, "ipv4_addresses": ["10.0.0.1/24"]},
            {"name": "eth0", "kind": "host", "enabled": True, "ipv4_addresses": []},
        ],
        "host_interfaces": [
            {"name": "eth0", "enabled": True, "ipv4_addresses": [], "ipv4_dhcp_client_enabled": True, "ipv6_dhcp_client_enabled": True}
        ],
        "static_routes": [{"table": "default", "destination_prefix": "0.0.0.0/0", "next_hop": "192.0.2.1", "interface": "WAN"}],
        "bgp": {
            "asn": "65001",
            "router_id": "10.0.0.1",
            "neighbors": [
                {
                    "peer": "TRANSIT",
                    "peer_group": "TRANSIT",
                    "bfd": True,
                    "ebgp_multihop_max_hops": 6,
                    "route_map_in": "TRANSIT-IN",
                    "route_map_out": "TRANSIT-OUT",
                },
                {
                    "peer": "192.0.2.2",
                    "peer_group": "TRANSIT",
                    "route_map_in": "TRANSIT-IN",
                    "route_map_out": "TRANSIT-OUT",
                },
            ],
        },
        "prefix_lists": [
            {"name": "AWS-PUBLIC-ANNOUNCE", "rules": [{"sequence": "1", "action": "permit", "prefix": "16.15.176.0/20"}]},
            {"name": "DEFAULT-OUT", "rules": [{"sequence": "10", "action": "permit", "prefix": "0.0.0.0/0"}]},
        ],
        "route_maps": [{"name": "TRANSIT-OUT", "rules": [{"sequence": "10", "policy": "permit"}]}],
        "bfd_sessions": [{"name": "transit-bfd", "enabled": True}],
        "nat_rulesets": [{"name": "WAN-nat", "rules": [{"sequence": "1000"}]}],
        "acl_rulesets": [{"name": "LAN-filter", "rules": [{"sequence": "10"}]}],
        "interface_policy_bindings": [{"interface": "WAN", "nat_ruleset": "WAN-nat", "filter_ruleset": "WAN-filter"}],
        "nacm": {
            "enabled": True,
            "groups": [{"name": "admin", "user_names": ["ansible", "root", "tnsr"]}],
            "rule_lists": [{"name": "admin-rules", "group": "admin", "rules": [{"name": "permit-all", "action": "permit"}]}],
        },
        "ssh_server": {"netconf_enabled": True, "netconf_port": 830},
        "logging": {"remote_servers": [{"name": "localhost", "address": "127.0.0.1"}]},
        "prometheus_exporter": {"host_space_filter": "v2 ^/sys/heartbeat"},
        "dataplane": {"cpu_workers": 6, "dpdk_devices": [{"name": "WAN"}, {"name": "LAN"}]},
        "sysctl": [{"name": "kernel.shmmax", "value": "2147483648"}],
        "system": {"kernel_modules": [{"module": "vfio", "attributes": {"noiommu": "true"}}]},
    }


def test_prefix_lists_view_summarizes_names_and_rule_counts():
    view = build_tnsr_domain_view(_sample_snapshot(), "prefix-lists")

    assert view["summary"]["prefix_list_count"] == 2
    assert view["summary"]["names"] == ["AWS-PUBLIC-ANNOUNCE", "DEFAULT-OUT"]
    assert view["summary"]["rule_counts"]["AWS-PUBLIC-ANNOUNCE"] == 1
    assert view["prefix_lists"][1]["rules"][0]["prefix"] == "0.0.0.0/0"


def test_route_maps_view_summarizes_policy_shape():
    snapshot = _sample_snapshot()
    snapshot["route_maps"] = [
        {"name": "TRANSIT-IN", "rules": [{"sequence": "10", "policy": "permit", "match_ip_prefix_list": "AWS-PUBLIC-ANNOUNCE"}]},
        {"name": "TRANSIT-OUT", "rules": [{"sequence": "10", "policy": "permit", "set_as_path_prepend": "65001"}, {"sequence": "100", "policy": "deny"}]},
    ]

    view = build_tnsr_domain_view(snapshot, "route-maps")

    assert view["summary"]["route_map_count"] == 2
    assert view["summary"]["prefix_list_refs"] == ["AWS-PUBLIC-ANNOUNCE"]
    assert view["summary"]["deny_rule_counts"]["TRANSIT-OUT"] == 1
    assert view["summary"]["as_path_prepends"]["TRANSIT-OUT"] == ["65001"]


def test_nacm_view_summarizes_groups_and_rule_lists():
    view = build_tnsr_domain_view(_sample_snapshot(), "nacm")

    assert view["summary"]["enabled"] is True
    assert view["summary"]["group_count"] == 1
    assert view["nacm"]["groups"][0]["user_names"] == ["ansible", "root", "tnsr"]
    assert view["nacm"]["rule_lists"][0]["rules"][0]["action"] == "permit"


def test_bgp_view_summarizes_policy_attachments():
    view = build_tnsr_domain_view(_sample_snapshot(), "bgp")

    assert view["summary"]["neighbor_count"] == 2
    assert view["summary"]["peer_group_template_count"] == 1
    assert view["summary"]["peer_member_count"] == 1
    assert view["summary"]["route_map_in_neighbors"] == ["192.0.2.2", "TRANSIT"]
    assert view["summary"]["route_map_out_neighbors"] == ["192.0.2.2", "TRANSIT"]
    assert view["summary"]["configured_bfd_peer_groups"] == ["TRANSIT"]
    assert view["peer_group_members"]["TRANSIT"] == ["192.0.2.2"]
    assert view["analysis_warnings"][0]["code"] == "TNSR_MULTIHOP_BFD_CONFIGURED"


def test_nat_and_filter_views_summarize_interfaces_and_protocol_sets():
    view_nat = build_tnsr_domain_view(_sample_snapshot(), "nat")
    view_filters = build_tnsr_domain_view(_sample_snapshot(), "filters")

    assert view_nat["summary"]["translation_interfaces"] == []
    assert view_filters["summary"]["protocol_sets"] == []

    snapshot = _sample_snapshot()
    snapshot["nat_rulesets"] = [{"name": "WAN-nat", "rules": [{"sequence": "1000", "translation_interface": "WAN"}]}]
    snapshot["acl_rulesets"] = [{"name": "WAN-filter", "rules": [{"sequence": "30", "direction": "in", "protocol_set": "icmp"}]}]
    view_nat = build_tnsr_domain_view(snapshot, "nat")
    view_filters = build_tnsr_domain_view(snapshot, "filters")

    assert view_nat["summary"]["translation_interfaces"] == ["WAN"]
    assert view_filters["summary"]["protocol_sets"] == ["icmp"]
    assert view_filters["summary"]["direction_counts"]["WAN-filter"]["in"] == 1


def test_platform_view_summarizes_counts():
    view = build_tnsr_domain_view(_sample_snapshot(), "platform")

    assert view["summary"]["cpu_workers"] == 6
    assert view["summary"]["dpdk_device_count"] == 2
    assert view["summary"]["kernel_module_count"] == 1
