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
