from __future__ import annotations

from netconf_mcp.vendors.arista_views import build_arista_domain_view, DOMAIN_CHOICES


def _sample_snapshot() -> dict:
    return {
        "interfaces": [
            {
                "name": "Ethernet1",
                "enabled": True,
                "description": "Uplink to core",
                "type": "ethernetCsmacd",
                "ipv4_addresses": ["10.0.1.1/24"],
                "ipv6_addresses": [],
                "mtu": 9000,
            },
            {
                "name": "Ethernet2",
                "enabled": True,
                "description": "Downlink to access",
                "type": "ethernetCsmacd",
                "ipv4_addresses": [],
                "ipv6_addresses": [],
                "mtu": 1500,
            },
            {
                "name": "Management1",
                "enabled": True,
                "description": "Management interface",
                "type": "ethernetCsmacd",
                "ipv4_addresses": ["192.168.1.100/24"],
                "ipv6_addresses": [],
                "mtu": 1500,
            },
        ],
        "lags": [
            {
                "name": "Port-Channel1",
                "enabled": True,
                "lag_type": "LACP",
                "members": ["Ethernet1", "Ethernet2"],
            },
        ],
        "vlans": [
            {"vlan_id": 10, "name": "DATA", "enabled": True},
            {"vlan_id": 20, "name": "VOICE", "enabled": True},
            {"vlan_id": 99, "name": "MGMT", "enabled": False},
        ],
        "vrfs": [
            {"name": "default", "vrf_id": None, "description": "Default VRF", "enabled": True},
            {"name": "CUSTOMER_A", "vrf_id": 100, "description": "Customer A VRF", "enabled": True},
        ],
        "static_routes": [
            {"vrf": "default", "destination_prefix": "0.0.0.0/0", "next_hop": "10.0.1.254", "interface": "Ethernet1", "metric": 1},
            {"vrf": "default", "destination_prefix": "10.100.0.0/16", "next_hop": "10.0.1.1", "interface": None, "metric": 10},
            {"vrf": "CUSTOMER_A", "destination_prefix": "172.16.0.0/12", "next_hop": "192.168.1.1", "interface": "Management1", "metric": 100},
        ],
        "bgp": {
            "enabled": True,
            "asn": "65001",
            "router_id": "10.0.1.1",
        },
        "lldp_neighbors": [
            {
                "interface": "Ethernet1",
                "neighbor_id": "00:1c:73:00:00:01",
                "neighbor_port": "Ethernet1",
                "capability": ["Router", "Bridge"],
            },
            {
                "interface": "Ethernet2",
                "neighbor_id": "00:1c:73:00:00:02",
                "neighbor_port": "Ethernet1",
                "capability": ["Router"],
            },
        ],
        "system": {
            "hostname": "arista-spine-01",
            "version": "4.30.1M",
            "platform": "vEOS",
        },
    }


def test_domain_choices_includes_all_domains():
    assert "interfaces" in DOMAIN_CHOICES
    assert "vlans" in DOMAIN_CHOICES
    assert "vrfs" in DOMAIN_CHOICES
    assert "lags" in DOMAIN_CHOICES
    assert "bgp" in DOMAIN_CHOICES
    assert "lldp" in DOMAIN_CHOICES
    assert "system" in DOMAIN_CHOICES
    assert "routing" in DOMAIN_CHOICES


def test_interfaces_view_summarizes_interface_counts():
    view = build_arista_domain_view(_sample_snapshot(), "interfaces")

    assert view["domain"] == "interfaces"
    assert view["summary"]["interface_count"] == 3
    assert view["summary"]["enabled_count"] == 3
    assert view["summary"]["with_ipv4"] == 2
    assert view["summary"]["with_ipv6"] == 0
    assert "Ethernet1" in view["summary"]["interface_names"]
    assert "Management1" in view["summary"]["interface_names"]
    assert len(view["interfaces"]) == 3


def test_interfaces_view_warns_about_l2_interfaces():
    snapshot = _sample_snapshot()
    view = build_arista_domain_view(snapshot, "interfaces")

    # Ethernet2 has no IP addresses - should be flagged
    assert len(view["analysis_warnings"]) == 1
    assert view["analysis_warnings"][0]["code"] == "POSSIBLE_L2_INTERFACES"


def test_vlans_view_summarizes_vlan_counts():
    view = build_arista_domain_view(_sample_snapshot(), "vlans")

    assert view["domain"] == "vlans"
    assert view["summary"]["vlan_count"] == 3
    assert view["summary"]["enabled_count"] == 2
    assert view["summary"]["vlan_ids"] == [10, 20, 99]
    assert view["summary"]["vlan_names"]["10"] == "DATA"
    assert view["summary"]["vlan_names"]["20"] == "VOICE"


def test_vrfs_view_summarizes_vrf_counts():
    view = build_arista_domain_view(_sample_snapshot(), "vrfs")

    assert view["domain"] == "vrfs"
    assert view["summary"]["vrf_count"] == 2
    assert view["summary"]["enabled_count"] == 2
    assert view["summary"]["vrf_names"] == ["CUSTOMER_A", "default"]


def test_lags_view_summarizes_lag_counts():
    view = build_arista_domain_view(_sample_snapshot(), "lags")

    assert view["domain"] == "lags"
    assert view["summary"]["lag_count"] == 1
    assert view["summary"]["enabled_count"] == 1
    assert view["summary"]["lacp_count"] == 1
    assert view["summary"]["lag_names"] == ["Port-Channel1"]
    assert view["lags"][0]["members"] == ["Ethernet1", "Ethernet2"]


def test_bgp_view_summarizes_bgp_config():
    view = build_arista_domain_view(_sample_snapshot(), "bgp")

    assert view["domain"] == "bgp"
    assert view["summary"]["enabled"] is True
    assert view["summary"]["asn"] == "65001"
    assert view["summary"]["router_id"] == "10.0.1.1"


def test_bgp_view_warns_when_disabled_with_asn():
    snapshot = _sample_snapshot()
    snapshot["bgp"] = {"enabled": False, "asn": "65001", "router_id": "10.0.1.1"}
    view = build_arista_domain_view(snapshot, "bgp")

    assert len(view["analysis_warnings"]) == 1
    assert view["analysis_warnings"][0]["code"] == "BGP_DISABLED_WITH_ASN"


def test_lldp_view_summarizes_neighbors():
    view = build_arista_domain_view(_sample_snapshot(), "lldp")

    assert view["domain"] == "lldp"
    assert view["summary"]["neighbor_count"] == 2
    assert view["summary"]["interfaces_with_neighbors"] == ["Ethernet1", "Ethernet2"]
    assert len(view["summary"]["unique_neighbors"]) == 2


def test_system_view_summarizes_system_info():
    view = build_arista_domain_view(_sample_snapshot(), "system")

    assert view["domain"] == "system"
    assert view["summary"]["hostname"] == "arista-spine-01"
    assert view["summary"]["version"] == "4.30.1M"
    assert view["summary"]["platform"] == "vEOS"


def test_routing_view_summarizes_static_routes():
    view = build_arista_domain_view(_sample_snapshot(), "routing")

    assert view["domain"] == "routing"
    assert view["summary"]["static_route_count"] == 3
    assert view["summary"]["vrfs_with_routes"] == ["CUSTOMER_A", "default"]
    assert view["summary"]["default_routes"] == ["0.0.0.0/0"]


def test_unsupported_domain_raises_error():
    try:
        build_arista_domain_view({}, "unsupported")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unsupported Arista EOS domain" in str(e)


def test_empty_snapshot_returns_empty_views():
    snapshot = {}

    view = build_arista_domain_view(snapshot, "interfaces")
    assert view["summary"]["interface_count"] == 0

    view = build_arista_domain_view(snapshot, "vlans")
    assert view["summary"]["vlan_count"] == 0

    view = build_arista_domain_view(snapshot, "vrfs")
    assert view["summary"]["vrf_count"] == 0

    view = build_arista_domain_view(snapshot, "lags")
    assert view["summary"]["lag_count"] == 0

    view = build_arista_domain_view(snapshot, "bgp")
    assert view["summary"].get("asn") is None

    view = build_arista_domain_view(snapshot, "lldp")
    assert view["summary"]["neighbor_count"] == 0

    view = build_arista_domain_view(snapshot, "system")
    assert view["summary"].get("hostname") is None

    view = build_arista_domain_view(snapshot, "routing")
    assert view["summary"]["static_route_count"] == 0

    view = build_arista_domain_view(snapshot, "routing-policy")
    assert view["summary"]["policy_count"] == 0
    assert view["summary"]["prefix_set_count"] == 0


def test_routing_policy_domain_in_choices():
    """Verify routing-policy is in DOMAIN_CHOICES."""
    assert "routing-policy" in DOMAIN_CHOICES


def test_routing_policy_view_with_populated_data():
    """Verify routing-policy view correctly summarizes prefix-sets and policies."""
    snapshot = {
        "prefix_sets": [
            {
                "name": "PL-LOOPBACKS",
                "prefixes": [
                    {"prefix": "10.0.0.0/24", "masklength_range": "24..32"},
                    {"prefix": "10.0.1.0/24", "masklength_range": "24..32"},
                ],
            },
            {
                "name": "PL-CONNECTED",
                "prefixes": [
                    {"prefix": "172.16.0.0/16", "masklength_range": "16..32"},
                ],
            },
            {
                "name": "PL-DEFAULT",
                "prefixes": [
                    {"prefix": "0.0.0.0/0", "masklength_range": "0..0"},
                ],
            },
        ],
        "routing_policies": [
            {
                "name": "RM-BGP-OUT",
                "statements": [
                    {
                        "sequence": "10",
                        "conditions": {"match_prefix_set": "PL-LOOPBACKS"},
                        "actions": {
                            "policy_result": "ACCEPT_ROUTE",
                            "set_community": ["65001:100"],
                        },
                    },
                    {
                        "sequence": "20",
                        "conditions": {"match_prefix_set": "PL-CONNECTED"},
                        "actions": {"policy_result": "ACCEPT_ROUTE"},
                    },
                ],
            },
            {
                "name": "RM-BGP-IN",
                "statements": [
                    {
                        "sequence": "10",
                        "conditions": {},
                        "actions": {
                            "policy_result": "ACCEPT_ROUTE",
                            "set_local_pref": "200",
                        },
                    },
                ],
            },
        ],
    }

    view = build_arista_domain_view(snapshot, "routing-policy")

    # Check summary
    assert view["domain"] == "routing-policy"
    assert view["summary"]["policy_count"] == 2
    assert view["summary"]["prefix_set_count"] == 3
    assert view["summary"]["total_statements"] == 3
    assert view["summary"]["total_prefixes"] == 4
    assert view["summary"]["policies_with_prefix_refs"] == ["RM-BGP-OUT"]

    # Check prefix-sets detail
    assert len(view["prefix_sets"]) == 3
    ps1 = view["prefix_sets"][0]
    assert ps1["name"] == "PL-LOOPBACKS"
    assert ps1["prefix_count"] == 2

    # Check policies detail
    assert len(view["routing_policies"]) == 2
    p1 = view["routing_policies"][0]
    assert p1["name"] == "RM-BGP-OUT"
    assert p1["statement_count"] == 2
    assert p1["statements"][0]["sequence"] == "10"
    assert "prefix-set:PL-LOOPBACKS" in p1["statements"][0]["conditions_summary"]
    assert "ACCEPT_ROUTE" in p1["statements"][0]["actions_summary"]
    assert "set-community:1 communities" in p1["statements"][0]["actions_summary"]


def test_routing_policy_view_empty_data():
    """Verify routing-policy view handles empty data correctly."""
    snapshot = {
        "prefix_sets": [],
        "routing_policies": [],
    }

    view = build_arista_domain_view(snapshot, "routing-policy")

    assert view["domain"] == "routing-policy"
    assert view["summary"]["policy_count"] == 0
    assert view["summary"]["prefix_set_count"] == 0
    assert view["summary"]["total_statements"] == 0
    assert view["summary"]["total_prefixes"] == 0
    assert view["summary"]["policies_with_prefix_refs"] == []
    assert view["prefix_sets"] == []
    assert view["routing_policies"] == []
    assert view["analysis_warnings"] == []


def test_routing_policy_view_cross_references():
    """Verify routing-policy view shows cross-references between policies and prefix-sets."""
    snapshot = {
        "prefix_sets": [
            {
                "name": "PL-LOOPBACKS",
                "prefixes": [
                    {"prefix": "10.0.0.0/24", "masklength_range": "24..32"},
                ],
            },
            {
                "name": "PL-NETWORKS",
                "prefixes": [
                    {"prefix": "192.168.0.0/16", "masklength_range": "16..24"},
                ],
            },
        ],
        "routing_policies": [
            {
                "name": "RM-EXPORT",
                "statements": [
                    {
                        "sequence": "10",
                        "conditions": {"match_prefix_set": "PL-LOOPBACKS"},
                        "actions": {"policy_result": "ACCEPT_ROUTE"},
                    },
                    {
                        "sequence": "20",
                        "conditions": {"match_prefix_set": "PL-NETWORKS"},
                        "actions": {"policy_result": "ACCEPT_ROUTE"},
                    },
                ],
            },
            {
                "name": "RM-IMPORT",
                "statements": [
                    {
                        "sequence": "10",
                        "conditions": {"match_prefix_set": "PL-LOOPBACKS"},
                        "actions": {"policy_result": "ACCEPT_ROUTE", "set_local_pref": "100"},
                    },
                ],
            },
        ],
    }

    view = build_arista_domain_view(snapshot, "routing-policy")

    # Both policies reference prefix-sets
    assert view["summary"]["policies_with_prefix_refs"] == ["RM-EXPORT", "RM-IMPORT"]

    # Check that conditions_summary shows the prefix-set references
    rm_export = view["routing_policies"][0]
    assert "prefix-set:PL-LOOPBACKS" in rm_export["statements"][0]["conditions_summary"]
    assert "prefix-set:PL-NETWORKS" in rm_export["statements"][1]["conditions_summary"]

    rm_import = view["routing_policies"][1]
    assert "prefix-set:PL-LOOPBACKS" in rm_import["statements"][0]["conditions_summary"]


def test_routing_policy_view_warnings():
    """Verify routing-policy view generates appropriate warnings."""
    # Prefix-sets without policies
    snapshot1 = {
        "prefix_sets": [
            {"name": "PL-LOOPBACKS", "prefixes": [{"prefix": "10.0.0.0/24", "masklength_range": "24..32"}]},
        ],
        "routing_policies": [],
    }

    view1 = build_arista_domain_view(snapshot1, "routing-policy")
    assert len(view1["analysis_warnings"]) == 1
    assert view1["analysis_warnings"][0]["code"] == "PREFIX_SETS_WITHOUT_POLICIES"

    # Policies without prefix-sets
    snapshot2 = {
        "prefix_sets": [],
        "routing_policies": [
            {
                "name": "RM-TEST",
                "statements": [
                    {"sequence": "10", "conditions": {}, "actions": {"policy_result": "ACCEPT_ROUTE"}},
                ],
            },
        ],
    }

    view2 = build_arista_domain_view(snapshot2, "routing-policy")
    assert len(view2["analysis_warnings"]) == 1
    assert view2["analysis_warnings"][0]["code"] == "POLICIES_WITHOUT_PREFIX_SETS"

    # Both present - no warnings
    snapshot3 = {
        "prefix_sets": [
            {"name": "PL-LOOPBACKS", "prefixes": [{"prefix": "10.0.0.0/24", "masklength_range": "24..32"}]},
        ],
        "routing_policies": [
            {
                "name": "RM-TEST",
                "statements": [
                    {
                        "sequence": "10",
                        "conditions": {"match_prefix_set": "PL-LOOPBACKS"},
                        "actions": {"policy_result": "ACCEPT_ROUTE"},
                    },
                ],
            },
        ],
    }

    view3 = build_arista_domain_view(snapshot3, "routing-policy")
    assert view3["analysis_warnings"] == []


def test_acls_domain_in_choices():
    """Verify acls is in DOMAIN_CHOICES."""
    assert "acls" in DOMAIN_CHOICES


def test_acls_view_with_populated_data():
    """Verify acls view correctly summarizes ACL sets and bindings."""
    snapshot = {
        "acl_sets": [
            {
                "name": "ACL-BLOCK-ADMIN",
                "type": "ACL_IPV4",
                "entries": [
                    {
                        "sequence": "10",
                        "match_conditions": {"source-address": "192.168.1.0/24"},
                        "action": "DROP",
                        "description": "Block admin subnet",
                    },
                    {
                        "sequence": "20",
                        "match_conditions": {},
                        "action": "ACCEPT",
                        "description": None,
                    },
                ],
            },
            {
                "name": "ACL-ALLOW-WEB",
                "type": "ACL_IPV4",
                "entries": [
                    {
                        "sequence": "10",
                        "match_conditions": {
                            "source-address": "0.0.0.0/0",
                            "protocol": "6",
                            "destination-port": "80",
                        },
                        "action": "ACCEPT",
                        "description": None,
                    },
                    {
                        "sequence": "20",
                        "match_conditions": {
                            "source-address": "0.0.0.0/0",
                            "protocol": "6",
                            "destination-port": "443",
                        },
                        "action": "ACCEPT",
                        "description": None,
                    },
                    {
                        "sequence": "30",
                        "match_conditions": {"source-address": "0.0.0.0/0"},
                        "action": "DROP",
                        "description": None,
                    },
                ],
            },
        ],
        "acl_bindings": [
            {
                "interface": "Ethernet1",
                "acl_set": "ACL-ALLOW-WEB",
                "direction": "INGRESS",
            },
            {
                "interface": "Ethernet2",
                "acl_set": "ACL-BLOCK-ADMIN",
                "direction": "INGRESS",
            },
        ],
    }

    view = build_arista_domain_view(snapshot, "acls")

    # Check summary
    assert view["domain"] == "acls"
    assert view["summary"]["acl_count"] == 2
    assert view["summary"]["total_entries"] == 5
    assert view["summary"]["binding_count"] == 2
    assert view["summary"]["acl_types"] == ["ACL_IPV4"]
    assert view["summary"]["interfaces_with_acls"] == ["Ethernet1", "Ethernet2"]

    # Check ACL sets detail
    assert len(view["acl_sets"]) == 2
    acl1 = view["acl_sets"][0]
    assert acl1["name"] == "ACL-BLOCK-ADMIN"
    assert acl1["type"] == "ACL_IPV4"
    assert acl1["entry_count"] == 2

    # Check entry detail with match_summary
    entry1 = acl1["entries"][0]
    assert entry1["sequence"] == "10"
    assert entry1["match_summary"] == "src=192.168.1.0/24"
    assert entry1["action"] == "DROP"
    assert entry1["description"] == "Block admin subnet"

    # Check second ACL
    acl2 = view["acl_sets"][1]
    assert acl2["name"] == "ACL-ALLOW-WEB"
    assert acl2["entry_count"] == 3

    # Check entry with multiple match conditions
    entry2 = acl2["entries"][0]
    assert entry2["match_summary"] == "src=0.0.0.0/0, proto=6, dport=80"

    # Check bindings detail
    assert len(view["acl_bindings"]) == 2
    binding1 = view["acl_bindings"][0]
    assert binding1["interface"] == "Ethernet1"
    assert binding1["acl_set"] == "ACL-ALLOW-WEB"
    assert binding1["direction"] == "INGRESS"


def test_acls_view_empty_data():
    """Verify acls view handles empty data correctly."""
    snapshot = {
        "acl_sets": [],
        "acl_bindings": [],
    }

    view = build_arista_domain_view(snapshot, "acls")

    assert view["domain"] == "acls"
    assert view["summary"]["acl_count"] == 0
    assert view["summary"]["total_entries"] == 0
    assert view["summary"]["binding_count"] == 0
    assert view["summary"]["acl_types"] == []
    assert view["summary"]["interfaces_with_acls"] == []
    assert view["acl_sets"] == []
    assert view["acl_bindings"] == []
    assert view["analysis_warnings"] == []


def test_acls_view_orphaned_acl_detection():
    """Verify acls view detects orphaned ACLs (defined but not bound)."""
    snapshot = {
        "acl_sets": [
            {
                "name": "ACL-UNUSED",
                "type": "ACL_IPV4",
                "entries": [
                    {
                        "sequence": "10",
                        "match_conditions": {"source-address": "10.0.0.0/8"},
                        "action": "DROP",
                        "description": None,
                    },
                ],
            },
            {
                "name": "ACL-IN-USE",
                "type": "ACL_IPV4",
                "entries": [
                    {
                        "sequence": "10",
                        "match_conditions": {},
                        "action": "ACCEPT",
                        "description": None,
                    },
                ],
            },
        ],
        "acl_bindings": [
            {
                "interface": "Ethernet1",
                "acl_set": "ACL-IN-USE",
                "direction": "INGRESS",
            },
        ],
    }

    view = build_arista_domain_view(snapshot, "acls")

    # Should have warning about orphaned ACL
    assert len(view["analysis_warnings"]) == 1
    assert view["analysis_warnings"][0]["code"] == "ORPHANED_ACL"
    assert "ACL-UNUSED" in view["analysis_warnings"][0]["message"]


def test_acls_view_invalid_binding_detection():
    """Verify acls view detects bindings to nonexistent ACLs."""
    snapshot = {
        "acl_sets": [
            {
                "name": "ACL-REAL",
                "type": "ACL_IPV4",
                "entries": [],
            },
        ],
        "acl_bindings": [
            {
                "interface": "Ethernet1",
                "acl_set": "ACL-REAL",
                "direction": "INGRESS",
            },
            {
                "interface": "Ethernet2",
                "acl_set": "ACL-NONEXISTENT",
                "direction": "INGRESS",
            },
        ],
    }

    view = build_arista_domain_view(snapshot, "acls")

    # Should have warning about invalid binding
    assert len(view["analysis_warnings"]) == 1
    assert view["analysis_warnings"][0]["code"] == "INVALID_ACL_BINDING"
    assert "ACL-NONEXISTENT" in view["analysis_warnings"][0]["message"]


def test_acls_view_multiple_acl_types():
    """Verify acls view handles multiple ACL types correctly."""
    snapshot = {
        "acl_sets": [
            {
                "name": "ACL-IPV4-STANDARD",
                "type": "ACL_IPV4",
                "entries": [],
            },
            {
                "name": "ACL-IPV6",
                "type": "ACL_IPV6",
                "entries": [],
            },
            {
                "name": "ACL-L2",
                "type": "ACL_L2",
                "entries": [],
            },
        ],
        "acl_bindings": [],
    }

    view = build_arista_domain_view(snapshot, "acls")

    assert view["summary"]["acl_count"] == 3
    assert sorted(view["summary"]["acl_types"]) == ["ACL_IPV4", "ACL_IPV6", "ACL_L2"]


def test_acls_view_match_summary_formats():
    """Verify acls view formats match_summary correctly for different conditions."""
    snapshot = {
        "acl_sets": [
            {
                "name": "ACL-TEST",
                "type": "ACL_IPV4",
                "entries": [
                    # No match conditions
                    {
                        "sequence": "10",
                        "match_conditions": {},
                        "action": "ACCEPT",
                        "description": None,
                    },
                    # Source only
                    {
                        "sequence": "20",
                        "match_conditions": {"source-address": "192.168.1.0/24"},
                        "action": "DROP",
                        "description": None,
                    },
                    # Destination only
                    {
                        "sequence": "30",
                        "match_conditions": {"destination-address": "10.0.0.0/8"},
                        "action": "ACCEPT",
                        "description": None,
                    },
                    # Protocol only
                    {
                        "sequence": "40",
                        "match_conditions": {"protocol": "6"},
                        "action": "ACCEPT",
                        "description": None,
                    },
                    # All conditions
                    {
                        "sequence": "50",
                        "match_conditions": {
                            "source-address": "0.0.0.0/0",
                            "destination-address": "0.0.0.0/0",
                            "protocol": "6",
                            "source-port": "1024",
                            "destination-port": "443",
                        },
                        "action": "ACCEPT",
                        "description": None,
                    },
                ],
            },
        ],
        "acl_bindings": [],
    }

    view = build_arista_domain_view(snapshot, "acls")

    acl = view["acl_sets"][0]
    entries = acl["entries"]

    # Check each match_summary format
    assert entries[0]["match_summary"] == "any"
    assert entries[1]["match_summary"] == "src=192.168.1.0/24"
    assert entries[2]["match_summary"] == "dst=10.0.0.0/8"
    assert entries[3]["match_summary"] == "proto=6"
    assert entries[4]["match_summary"] == "src=0.0.0.0/0, dst=0.0.0.0/0, proto=6, sport=1024, dport=443"


def test_mlag_domain_in_choices():
    """Verify mlag is in DOMAIN_CHOICES."""
    assert "mlag" in DOMAIN_CHOICES


def test_mlag_view_with_populated_data():
    """Verify mlag view correctly summarizes MLAG global config and member interfaces."""
    snapshot = {
        "mlag": {
            "enabled": True,
            "domain_id": "MLAG-DOMAIN",
            "local_interface": "Vlan100",
            "peer_address": "192.168.100.2",
            "peer_link": "Port-Channel10",
            "state": {
                "status": "active",
                "peer_link_status": "up",
            },
        },
        "mlag_interfaces": [
            {
                "interface": "Port-Channel20",
                "mlag_id": 20,
                "status": "active",
            },
            {
                "interface": "Port-Channel30",
                "mlag_id": 30,
                "status": "active",
            },
            {
                "interface": "Port-Channel40",
                "mlag_id": 40,
                "status": "inactive",
            },
        ],
    }

    view = build_arista_domain_view(snapshot, "mlag")

    # Check summary
    assert view["domain"] == "mlag"
    assert view["summary"]["enabled"] is True
    assert view["summary"]["domain_id"] == "MLAG-DOMAIN"
    assert view["summary"]["peer_address"] == "192.168.100.2"
    assert view["summary"]["peer_link"] == "Port-Channel10"
    assert view["summary"]["member_count"] == 3
    assert view["summary"]["active_member_count"] == 2

    # Check global config
    assert view["global_config"]["domain_id"] == "MLAG-DOMAIN"
    assert view["global_config"]["local_interface"] == "Vlan100"
    assert view["global_config"]["peer_address"] == "192.168.100.2"
    assert view["global_config"]["peer_link"] == "Port-Channel10"
    assert view["global_config"]["status"] == "active"
    assert view["global_config"]["data_source"] == "arista-proprietary"

    # Check member interfaces
    assert len(view["member_interfaces"]) == 3
    assert view["member_interfaces"][0]["interface"] == "Port-Channel20"
    assert view["member_interfaces"][0]["mlag_id"] == 20
    assert view["member_interfaces"][0]["status"] == "active"

    # Check warnings include vendor-specific data source note
    warning_codes = [w["code"] for w in view["analysis_warnings"]]
    assert "VENDOR_SPECIFIC_DATA" in warning_codes


def test_mlag_view_empty_data():
    """Verify mlag view handles empty data correctly."""
    snapshot = {
        "mlag": None,
        "mlag_interfaces": [],
    }

    view = build_arista_domain_view(snapshot, "mlag")

    assert view["domain"] == "mlag"
    assert view["summary"]["enabled"] is False
    assert view["summary"]["domain_id"] is None
    assert view["summary"]["peer_address"] is None
    assert view["summary"]["peer_link"] is None
    assert view["summary"]["member_count"] == 0
    assert view["summary"]["active_member_count"] == 0
    assert view["global_config"] == {}
    assert view["member_interfaces"] == []
    assert view["analysis_warnings"] == []


def test_mlag_view_peer_link_down_warning():
    """Verify mlag view generates warning when peer-link is down."""
    snapshot = {
        "mlag": {
            "enabled": True,
            "domain_id": "MLAG-DOMAIN",
            "local_interface": "Vlan100",
            "peer_address": "192.168.100.2",
            "peer_link": "Port-Channel10",
            "state": {
                "status": "active",
                "peer_link_status": "down",
            },
        },
        "mlag_interfaces": [],
    }

    view = build_arista_domain_view(snapshot, "mlag")

    warning_codes = [w["code"] for w in view["analysis_warnings"]]
    assert "PEER_LINK_DOWN" in warning_codes
    assert any("peer-link status is 'down'" in w["message"] for w in view["analysis_warnings"])


def test_mlag_view_mlag_not_active_warning():
    """Verify mlag view generates warning when MLAG status is not active."""
    snapshot = {
        "mlag": {
            "enabled": True,
            "domain_id": "MLAG-DOMAIN",
            "local_interface": "Vlan100",
            "peer_address": "192.168.100.2",
            "peer_link": "Port-Channel10",
            "state": {
                "status": "inactive",
                "peer_link_status": "up",
            },
        },
        "mlag_interfaces": [],
    }

    view = build_arista_domain_view(snapshot, "mlag")

    warning_codes = [w["code"] for w in view["analysis_warnings"]]
    assert "MLAG_NOT_ACTIVE" in warning_codes
    assert any("status is 'inactive'" in w["message"] for w in view["analysis_warnings"])


def test_mlag_view_missing_mlag_key():
    """Verify mlag view handles missing mlag key gracefully."""
    snapshot = {}

    view = build_arista_domain_view(snapshot, "mlag")

    assert view["domain"] == "mlag"
    assert view["summary"]["enabled"] is False
    assert view["summary"]["member_count"] == 0
    assert view["global_config"] == {}
    assert view["member_interfaces"] == []
    assert view["analysis_warnings"] == []


def test_evpn_vxlan_domain_in_choices():
    """Verify evpn-vxlan is in DOMAIN_CHOICES."""
    assert "evpn-vxlan" in DOMAIN_CHOICES


def test_evpn_vxlan_view_with_populated_data():
    """Verify evpn-vxlan view correctly summarizes EVPN instances and VXLAN mappings."""
    snapshot = {
        "evpn_instances": [
            {
                "name": "VLAN10",
                "vni": 1001,
                "rd": "65001:1001",
                "route_target_import": ["65001:1001"],
                "route_target_export": ["65001:1001"],
            },
            {
                "name": "VLAN20",
                "vni": 1002,
                "rd": "65001:1002",
                "route_target_import": ["65001:1002"],
                "route_target_export": ["65001:1002"],
            },
            {
                "name": "prod",
                "vni": 2001,
                "rd": "65001:2001",
                "route_target_import": ["65001:2001"],
                "route_target_export": ["65001:2001"],
            },
        ],
        "vxlan_mappings": [
            {
                "vni": 1001,
                "vlan_id": 10,
                "vrf_name": None,
                "source_interface": "Loopback0",
                "flood_vteps": [],
            },
            {
                "vni": 1002,
                "vlan_id": 20,
                "vrf_name": None,
                "source_interface": "Loopback0",
                "flood_vteps": [],
            },
            {
                "vni": 2001,
                "vlan_id": None,
                "vrf_name": "prod",
                "source_interface": "Loopback0",
                "flood_vteps": [],
            },
        ],
    }

    view = build_arista_domain_view(snapshot, "evpn-vxlan")

    # Check summary
    assert view["domain"] == "evpn-vxlan"
    assert view["summary"]["evpn_enabled"] is True
    assert view["summary"]["total_vni_count"] == 3
    assert view["summary"]["l2vni_count"] == 2
    assert view["summary"]["l3vni_count"] == 1
    assert view["summary"]["vlan_count"] == 2
    assert view["summary"]["vrf_count"] == 1
    assert view["summary"]["source_interface"] == "Loopback0"

    # Check EVPN instances detail
    assert len(view["evpn_instances"]) == 3
    vlan10 = view["evpn_instances"][0]
    assert vlan10["name"] == "VLAN10"
    assert vlan10["vni"] == 1001
    assert vlan10["rd"] == "65001:1001"
    assert vlan10["rt_import"] == ["65001:1001"]
    assert vlan10["rt_export"] == ["65001:1001"]
    assert vlan10["type"] == "L2"

    prod = view["evpn_instances"][2]
    assert prod["name"] == "prod"
    assert prod["vni"] == 2001
    assert prod["type"] == "L3"

    # Check VXLAN mappings detail
    assert len(view["vxlan_mappings"]) == 3
    vxlan1 = view["vxlan_mappings"][0]
    assert vxlan1["vni"] == 1001
    assert vxlan1["vlan_id"] == 10
    assert vxlan1["source_interface"] == "Loopback0"
    assert vxlan1["data_source"] == "arista-proprietary"

    # Check warnings include vendor-specific data source note
    warning_codes = [w["code"] for w in view["analysis_warnings"]]
    assert "VENDOR_SPECIFIC_DATA" in warning_codes


def test_evpn_vxlan_view_empty_data():
    """Verify evpn-vxlan view handles empty data correctly."""
    snapshot = {
        "evpn_instances": [],
        "vxlan_mappings": [],
    }

    view = build_arista_domain_view(snapshot, "evpn-vxlan")

    assert view["domain"] == "evpn-vxlan"
    assert view["summary"]["evpn_enabled"] is False
    assert view["summary"]["total_vni_count"] == 0
    assert view["summary"]["l2vni_count"] == 0
    assert view["summary"]["l3vni_count"] == 0
    assert view["summary"]["vlan_count"] == 0
    assert view["summary"]["vrf_count"] == 0
    assert view["summary"]["source_interface"] is None
    assert view["evpn_instances"] == []
    assert view["vxlan_mappings"] == []
    assert view["analysis_warnings"] == []


def test_evpn_vxlan_view_vni_conflict_detection():
    """Verify evpn-vxlan view detects VNI conflicts."""
    snapshot = {
        "evpn_instances": [
            {
                "name": "VLAN10",
                "vni": 1001,
                "rd": "65001:1001",
                "route_target_import": ["65001:1001"],
                "route_target_export": ["65001:1001"],
            },
        ],
        "vxlan_mappings": [
            {
                "vni": 1001,  # Same VNI as EVPN instance
                "vlan_id": 50,  # Different VLAN
                "vrf_name": None,
                "source_interface": "Loopback0",
                "flood_vteps": [],
            },
        ],
    }

    view = build_arista_domain_view(snapshot, "evpn-vxlan")

    # Should have warning about VNI conflict
    warning_codes = [w["code"] for w in view["analysis_warnings"]]
    assert "VNI_CONFLICT" in warning_codes
    assert any("VNI 1001" in w["message"] for w in view["analysis_warnings"])


def test_evpn_vxlan_view_missing_source_interface():
    """Verify evpn-vxlan view generates warning when source interface is missing."""
    snapshot = {
        "evpn_instances": [
            {
                "name": "VLAN10",
                "vni": 1001,
                "rd": "65001:1001",
                "route_target_import": ["65001:1001"],
                "route_target_export": ["65001:1001"],
            },
        ],
        "vxlan_mappings": [
            {
                "vni": 1001,
                "vlan_id": 10,
                "vrf_name": None,
                "source_interface": None,  # No source interface
                "flood_vteps": [],
            },
        ],
    }

    view = build_arista_domain_view(snapshot, "evpn-vxlan")

    # Should have warning about missing source interface
    warning_codes = [w["code"] for w in view["analysis_warnings"]]
    assert "MISSING_VXLAN_SOURCE_INTERFACE" in warning_codes


def test_evpn_vxlan_view_missing_keys():
    """Verify evpn-vxlan view handles missing keys gracefully."""
    snapshot = {}

    view = build_arista_domain_view(snapshot, "evpn-vxlan")

    assert view["domain"] == "evpn-vxlan"
    assert view["summary"]["evpn_enabled"] is False
    assert view["summary"]["total_vni_count"] == 0
    assert view["evpn_instances"] == []
    assert view["vxlan_mappings"] == []


def test_evpn_vxlan_view_l2_only():
    """Verify evpn-vxlan view handles L2-only EVPN correctly."""
    snapshot = {
        "evpn_instances": [
            {
                "name": "VLAN10",
                "vni": 1001,
                "rd": "65001:1001",
                "route_target_import": ["65001:1001"],
                "route_target_export": ["65001:1001"],
            },
            {
                "name": "VLAN20",
                "vni": 1002,
                "rd": "65001:1002",
                "route_target_import": ["65001:1002"],
                "route_target_export": ["65001:1002"],
            },
        ],
        "vxlan_mappings": [
            {
                "vni": 1001,
                "vlan_id": 10,
                "vrf_name": None,
                "source_interface": "Loopback0",
                "flood_vteps": [],
            },
            {
                "vni": 1002,
                "vlan_id": 20,
                "vrf_name": None,
                "source_interface": "Loopback0",
                "flood_vteps": [],
            },
        ],
    }

    view = build_arista_domain_view(snapshot, "evpn-vxlan")

    assert view["summary"]["l2vni_count"] == 2
    assert view["summary"]["l3vni_count"] == 0
    assert view["summary"]["vlan_count"] == 2
    assert view["summary"]["vrf_count"] == 0


def test_evpn_vxlan_view_l3_only():
    """Verify evpn-vxlan view handles L3-only EVPN correctly."""
    snapshot = {
        "evpn_instances": [
            {
                "name": "prod",
                "vni": 2001,
                "rd": "65001:2001",
                "route_target_import": ["65001:2001"],
                "route_target_export": ["65001:2001"],
            },
            {
                "name": "dev",
                "vni": 2002,
                "rd": "65001:2002",
                "route_target_import": ["65001:2002"],
                "route_target_export": ["65001:2002"],
            },
        ],
        "vxlan_mappings": [
            {
                "vni": 2001,
                "vlan_id": None,
                "vrf_name": "prod",
                "source_interface": "Loopback0",
                "flood_vteps": [],
            },
            {
                "vni": 2002,
                "vlan_id": None,
                "vrf_name": "dev",
                "source_interface": "Loopback0",
                "flood_vteps": [],
            },
        ],
    }

    view = build_arista_domain_view(snapshot, "evpn-vxlan")

    assert view["summary"]["l2vni_count"] == 0
    assert view["summary"]["l3vni_count"] == 2
    assert view["summary"]["vlan_count"] == 0
    assert view["summary"]["vrf_count"] == 2
