from __future__ import annotations

from netconf_mcp.vendors.arista import (
    ACLInterfaceBindingRecord,
    ACLSetRecord,
    AristaCollector,
    ARISTA_NAMESPACES,
    BGPRecord,
    EvpnInstanceRecord,
    InterfaceRecord,
    LAGRecord,
    LLDPNeighborRecord,
    MLAGInterfaceRecord,
    MLAGRecord,
    PrefixSetRecord,
    RoutingPolicyRecord,
    StaticRouteRecord,
    SystemInfoRecord,
    VLANRecord,
    VRFRecord,
    VxlanMappingRecord,
)


class FakeSession:
    server_capabilities = [
        "urn:ietf:params:netconf:base:1.1",
        "http://openconfig.net/yang/interfaces?module=openconfig-interfaces&revision=2024-12-05",
    ]


class FakeClient:
    def open_session(self, target, *, hostkey_policy="strict", framing="auto", connect_timeout_ms=None):
        del target, hostkey_policy, framing, connect_timeout_ms
        return FakeSession()

    def get_yang_library(self, target, session):
        del target, session
        return {
            "module_set": [{"module": "openconfig-interfaces", "revision": "2024-12-05"}],
        }

    def datastore_get(self, target, session, *, datastore="running", xpath=None):
        del target, session, datastore, xpath
        return {"value": {}}


def test_arista_collector_initialization():
    collector = AristaCollector()
    assert collector.client is not None


def test_arista_collector_with_custom_client():
    client = FakeClient()
    collector = AristaCollector(client=client)
    assert collector.client is client


def test_arista_namespaces_defined():
    assert "oc-if" in ARISTA_NAMESPACES
    assert "oc-vlan" in ARISTA_NAMESPACES
    assert "oc-ni" in ARISTA_NAMESPACES
    assert ARISTA_NAMESPACES["oc-if"] == "http://openconfig.net/yang/interfaces"


def test_arista_collector_collects_interfaces():
    class InterfaceClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "oc-if:interfaces" in xpath:
                # Return the list directly as the value (not wrapped in "interface" key)
                return {
                    "value": [
                            {
                                "name": "Ethernet1",
                                "config": {
                                    "enabled": "true",
                                    "description": "Uplink to core",
                                    "type": "ethernetCsmacd",
                                    "mtu": "9000",
                                },
                                "ipv4": {
                                    "config": {
                                        "ip": "10.0.1.1",
                                        "prefix-length": "24",
                                    }
                                },
                            },
                            {
                                "name": "Management1",
                                "config": {
                                    "enabled": "true",
                                    "description": "Management",
                                },
                                "ipv4": {
                                    "config": {
                                        "ip": "192.168.1.1",
                                        "prefix-length": "24",
                                    }
                                },
                            },
                        ]
                }
            return {"value": {}}

    collector = AristaCollector(client=InterfaceClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
            "host": "arista.example.net",
            "site": "lab",
            "role": ["edge"],
        }
    )

    payload = snapshot.to_dict()
    assert payload["snapshot_type"] == "arista-normalized-config-v1"
    assert payload["device"]["vendor"] == "arista"
    assert len(payload["interfaces"]) == 2
    assert payload["interfaces"][0]["name"] == "Ethernet1"
    assert payload["interfaces"][0]["enabled"] is True
    assert payload["interfaces"][0]["description"] == "Uplink to core"
    assert payload["interfaces"][0]["mtu"] == 9000
    assert payload["interfaces"][1]["name"] == "Management1"


def test_arista_collector_collects_vlans():
    class VLANClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "oc-vlan:vlans" in xpath:
                return {
                    "value": [
                            {
                                "vlan-id": "10",
                                "config": {
                                    "name": "DATA",
                                    "enabled": "true",
                                },
                            },
                            {
                                "vlan-id": "20",
                                "config": {
                                    "name": "VOICE",
                                    "enabled": "true",
                                },
                            },
                            {
                                "vlan-id": "99",
                                "config": {
                                    "name": "MGMT",
                                    "enabled": "false",
                                },
                            },
                        ]
                }
            return {"value": {}}

    collector = AristaCollector(client=VLANClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert len(payload["vlans"]) == 3
    assert payload["vlans"][0]["vlan_id"] == 10
    assert payload["vlans"][0]["name"] == "DATA"
    assert payload["vlans"][0]["enabled"] is True
    assert payload["vlans"][2]["vlan_id"] == 99
    assert payload["vlans"][2]["enabled"] is False


def test_arista_collector_collects_vrfs():
    class VRFClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "oc-ni:network-instances" in xpath:
                # Return different structures for different queries
                if "static-routes" in xpath:
                    # Static routes query expects a dict with network-instance key
                    return {
                        "value": {
                            "network-instance": [
                                {
                                    "name": "default",
                                    "static-routes": {"static": []}
                                }
                            ]
                        }
                    }
                else:
                    # VRF query expects a list directly in value
                    return {
                        "value": [
                            {
                                "name": "default",
                                "config": {
                                    "enabled": "true",
                                    "vrf-id": "0",
                                    "description": "Default VRF",
                                },
                            },
                            {
                                "name": "CUSTOMER_A",
                                "config": {
                                    "enabled": "true",
                                    "vrf-id": "100",
                                    "description": "Customer A VRF",
                                },
                            },
                        ]
                    }
            return {"value": {}}

    collector = AristaCollector(client=VRFClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert len(payload["vrfs"]) == 2
    assert payload["vrfs"][0]["name"] == "default"
    assert payload["vrfs"][0]["vrf_id"] == 0
    assert payload["vrfs"][1]["name"] == "CUSTOMER_A"
    assert payload["vrfs"][1]["vrf_id"] == 100


def test_arista_collector_collects_static_routes():
    class StaticRouteClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "static-routes" in xpath:
                return {
                    "value": {
                        "network-instance": [
                            {
                                "name": "default",
                                "static-routes": {
                                    "static": [
                                        {
                                            "prefix": "0.0.0.0/0",
                                            "next-hop": {
                                                "next-hop": [
                                                    {
                                                        "config": {
                                                            "next-hop-address": "192.0.2.1",
                                                            "outgoing-interface": "Ethernet1",
                                                            "metric": "10",
                                                        }
                                                    }
                                                ]
                                            }
                                        },
                                        {
                                            "prefix": "10.0.0.0/8",
                                            "next-hop": {
                                                "next-hop": [
                                                    {
                                                        "config": {
                                                            "next-hop-address": "10.0.0.1",
                                                        }
                                                    }
                                                ]
                                            }
                                        },
                                    ]
                                }
                            }
                        ]
                    }
                }
            return {"value": {}}

    collector = AristaCollector(client=StaticRouteClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert len(payload["static_routes"]) == 2
    assert payload["static_routes"][0]["vrf"] == "default"
    assert payload["static_routes"][0]["destination_prefix"] == "0.0.0.0/0"
    assert payload["static_routes"][0]["next_hop"] == "192.0.2.1"
    assert payload["static_routes"][0]["interface"] == "Ethernet1"
    assert payload["static_routes"][0]["metric"] == 10
    assert payload["static_routes"][1]["destination_prefix"] == "10.0.0.0/8"


def test_arista_collector_collects_bgp():
    class BGPClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "protocol/bgp" in xpath:
                return {
                    "value": {
                        "network-instance": [
                            {
                                "name": "default",
                                "protocols": {
                                    "protocol": [
                                        {
                                            "identifier": "BGP",
                                            "bgp": {
                                                "global": {
                                                    "config": {
                                                        "enabled": "true",
                                                        "as": "65001",
                                                        "router-id": "10.0.0.1",
                                                    }
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            return {"value": {}}

    collector = AristaCollector(client=BGPClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert payload["bgp"]["enabled"] is True
    assert payload["bgp"]["asn"] == "65001"
    assert payload["bgp"]["router_id"] == "10.0.0.1"


def test_arista_collector_collects_system_info():
    class SystemClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "oc-sys:system" in xpath:
                # Return config directly in value
                return {
                    "value": {
                        "hostname": "ceos-lab",
                        "version": "4.35.2F",
                        "platform-id": "ceos",
                    }
                }
            return {"value": {}}

    collector = AristaCollector(client=SystemClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert payload["system"]["hostname"] == "ceos-lab"
    assert payload["system"]["version"] == "4.35.2F"
    assert payload["system"]["platform"] == "ceos"


def test_arista_collector_handles_missing_data_gracefully():
    collector = AristaCollector(client=FakeClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    # All fields should have defaults - missing data returns empty collections
    assert payload["interfaces"] == []
    assert payload["lags"] == []
    assert payload["vlans"] == []
    assert payload["vrfs"] == []
    assert payload["static_routes"] == []
    assert payload["bgp"]["enabled"] is None
    assert payload["system"]["hostname"] is None
    # No warnings when data is simply not present (empty collections)
    assert payload["warnings"] == []


def test_arista_collector_includes_target_info():
    class TestClient(FakeClient):
        pass

    collector = AristaCollector(client=TestClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-ceos",
            "facts": {"vendor": "arista", "os": "eos", "platform": "ceos"},
            "host": "arista.example.net",
            "site": "dc-west",
            "role": ["edge", "spoke"],
        }
    )

    payload = snapshot.to_dict()
    assert payload["target_ref"] == "target://lab/arista"
    assert payload["device"]["name"] == "arista-ceos"
    assert payload["device"]["vendor"] == "arista"
    assert payload["device"]["host"] == "arista.example.net"
    assert payload["device"]["site"] == "dc-west"
    assert payload["device"]["role"] == ["edge", "spoke"]


def test_arista_collector_includes_capabilities():
    class TestClient(FakeClient):
        pass

    collector = AristaCollector(client=TestClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert len(payload["capabilities"]) > 0
    assert "urn:ietf:params:netconf:base:1.1" in payload["capabilities"]


def test_arista_namespaces_includes_new_domains():
    """Verify new namespace prefixes for MLAG, VXLAN, ACL, EVPN are defined."""
    assert "oc-acl" in ARISTA_NAMESPACES
    assert "oc-mlag" in ARISTA_NAMESPACES
    assert "oc-vxlan" in ARISTA_NAMESPACES
    assert "oc-evpn" in ARISTA_NAMESPACES
    assert "oc-def-sets" in ARISTA_NAMESPACES
    # oc-rpol already exists, verify it's still there
    assert "oc-rpol" in ARISTA_NAMESPACES


def test_arista_collector_empty_snapshot_includes_new_fields():
    """Verify empty snapshot includes all new domain fields with correct defaults."""
    collector = AristaCollector(client=FakeClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()

    # Routing Policy fields
    assert payload["prefix_sets"] == []
    assert payload["routing_policies"] == []

    # ACL fields
    assert payload["acl_sets"] == []
    assert payload["acl_bindings"] == []

    # MLAG fields
    assert payload["mlag"] is None
    assert payload["mlag_interfaces"] == []

    # EVPN/VXLAN fields
    assert payload["evpn_instances"] == []
    assert payload["vxlan_mappings"] == []


def test_arista_snapshot_serialization_includes_new_fields():
    """Verify snapshot serialization includes all new domain fields."""
    collector = AristaCollector(client=FakeClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    # Verify to_dict() includes all new fields
    payload = snapshot.to_dict()

    # Check all expected keys exist
    expected_keys = [
        "prefix_sets",
        "routing_policies",
        "acl_sets",
        "acl_bindings",
        "mlag",
        "mlag_interfaces",
        "evpn_instances",
        "vxlan_mappings",
    ]
    for key in expected_keys:
        assert key in payload, f"Missing expected key: {key}"


def test_arista_collector_collects_prefix_sets():
    """Verify prefix sets are collected from openconfig-defined-sets."""

    class PrefixSetClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "oc-def-sets:defined-sets" in xpath:
                return {
                    "value": [
                        {
                            "name": "PL-LOOPBACKS",
                            "config": {"name": "PL-LOOPBACKS"},
                            "prefixes": {
                                "prefix": [
                                    {
                                        "ip-prefix": "10.0.0.0/24",
                                        "masklength-range": "24..32",
                                        "config": {
                                            "ip-prefix": "10.0.0.0/24",
                                            "masklength-range": "24..32",
                                        },
                                    }
                                ]
                            },
                        },
                        {
                            "name": "PL-CONNECTED",
                            "config": {"name": "PL-CONNECTED"},
                            "prefixes": {
                                "prefix": [
                                    {
                                        "ip-prefix": "172.16.0.0/16",
                                        "masklength-range": "16..32",
                                        "config": {
                                            "ip-prefix": "172.16.0.0/16",
                                            "masklength-range": "16..32",
                                        },
                                    }
                                ]
                            },
                        },
                        {
                            "name": "PL-DEFAULT",
                            "config": {"name": "PL-DEFAULT"},
                            "prefixes": {
                                "prefix": [
                                    {
                                        "ip-prefix": "0.0.0.0/0",
                                        "masklength-range": "0..0",
                                        "config": {
                                            "ip-prefix": "0.0.0.0/0",
                                            "masklength-range": "0..0",
                                        },
                                    }
                                ]
                            },
                        },
                    ]
                }
            return {"value": {}}

    collector = AristaCollector(client=PrefixSetClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert len(payload["prefix_sets"]) == 3

    # Check first prefix-set
    ps1 = payload["prefix_sets"][0]
    assert ps1["name"] == "PL-LOOPBACKS"
    assert len(ps1["prefixes"]) == 1
    assert ps1["prefixes"][0]["prefix"] == "10.0.0.0/24"
    assert ps1["prefixes"][0]["masklength_range"] == "24..32"

    # Check second prefix-set
    ps2 = payload["prefix_sets"][1]
    assert ps2["name"] == "PL-CONNECTED"
    assert ps2["prefixes"][0]["prefix"] == "172.16.0.0/16"

    # Check default route prefix-set
    ps3 = payload["prefix_sets"][2]
    assert ps3["name"] == "PL-DEFAULT"
    assert ps3["prefixes"][0]["prefix"] == "0.0.0.0/0"


def test_arista_collector_collects_routing_policies():
    """Verify routing policies are collected from openconfig-routing-policy."""

    class RoutingPolicyClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "oc-rpol:routing-policy" in xpath:
                return {
                    "value": [
                        {
                            "name": "RM-BGP-OUT",
                            "config": {"name": "RM-BGP-OUT"},
                            "statements": {
                                "statement": [
                                    {
                                        "name": "10",
                                        "conditions": {
                                            "match-prefix-set": {
                                                "config": {"prefix-set": "PL-LOOPBACKS"}
                                            }
                                        },
                                        "actions": {
                                            "config": {"policy-result": "ACCEPT_ROUTE"},
                                            "bgp-actions": {
                                                "set-community": {
                                                    "config": {
                                                        "communities": ["65001:100"]
                                                    }
                                                }
                                            },
                                        },
                                    },
                                    {
                                        "name": "20",
                                        "conditions": {
                                            "match-prefix-set": {
                                                "config": {"prefix-set": "PL-CONNECTED"}
                                            }
                                        },
                                        "actions": {
                                            "config": {"policy-result": "ACCEPT_ROUTE"},
                                        },
                                    },
                                ]
                            },
                        },
                        {
                            "name": "RM-BGP-IN",
                            "config": {"name": "RM-BGP-IN"},
                            "statements": {
                                "statement": [
                                    {
                                        "name": "10",
                                        "conditions": {},
                                        "actions": {
                                            "config": {"policy-result": "ACCEPT_ROUTE"},
                                            "bgp-actions": {
                                                "set-local-pref": {
                                                    "config": {"local-pref": "200"}
                                                }
                                            },
                                        },
                                    },
                                ]
                            },
                        },
                    ]
                }
            return {"value": {}}

    collector = AristaCollector(client=RoutingPolicyClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert len(payload["routing_policies"]) == 2

    # Check first policy
    p1 = payload["routing_policies"][0]
    assert p1["name"] == "RM-BGP-OUT"
    assert len(p1["statements"]) == 2

    # Check first statement
    stmt1 = p1["statements"][0]
    assert stmt1["sequence"] == "10"
    assert stmt1["conditions"]["match_prefix_set"] == "PL-LOOPBACKS"
    assert stmt1["actions"]["policy_result"] == "ACCEPT_ROUTE"
    assert stmt1["actions"]["set_community"] == ["65001:100"]

    # Check second statement
    stmt2 = p1["statements"][1]
    assert stmt2["sequence"] == "20"
    assert stmt2["conditions"]["match_prefix_set"] == "PL-CONNECTED"

    # Check second policy
    p2 = payload["routing_policies"][1]
    assert p2["name"] == "RM-BGP-IN"
    assert len(p2["statements"]) == 1
    assert p2["statements"][0]["actions"]["set_local_pref"] == "200"


def test_arista_collector_collects_empty_routing_policy_data():
    """Verify empty routing policy data returns empty lists without warnings."""
    collector = AristaCollector(client=FakeClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert payload["prefix_sets"] == []
    assert payload["routing_policies"] == []
    # No warnings for simply missing data
    assert payload["warnings"] == []


def test_arista_collector_handles_routing_policy_errors():
    """Verify routing policy collection handles errors gracefully."""

    class ErrorClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "oc-def-sets" in xpath:
                raise Exception("NETCONF error: resource not found")
            if xpath and "oc-rpol" in xpath:
                raise Exception("NETCONF error: timeout")
            return {"value": {}}

    collector = AristaCollector(client=ErrorClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert payload["prefix_sets"] == []
    assert payload["routing_policies"] == []
    # Should have warnings about the errors
    assert len(payload["warnings"]) == 2
    assert any("Could not collect prefix sets" in w for w in payload["warnings"])
    assert any("Could not collect routing policies" in w for w in payload["warnings"])


def test_arista_collector_collects_acl_sets():
    """Verify ACL sets are collected from openconfig-acl."""

    class ACLClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "oc-acl:acl" in xpath and "acl-sets" in xpath:
                return {
                    "value": [
                        {
                            "name": "ACL-BLOCK-ADMIN",
                            "type": "ACL_IPV4",
                            "config": {
                                "name": "ACL-BLOCK-ADMIN",
                                "type": "ACL_IPV4",
                            },
                            "acl-entries": {
                                "acl-entry": [
                                    {
                                        "sequence-id": "10",
                                        "config": {
                                            "sequence-id": "10",
                                        },
                                        "ipv4": {
                                            "config": {
                                                "source-address": "192.168.1.0/24",
                                            }
                                        },
                                        "actions": {
                                            "config": {
                                                "forwarding-action": "DROP",
                                                "description": "Block admin subnet",
                                            }
                                        },
                                    },
                                    {
                                        "sequence-id": "20",
                                        "config": {
                                            "sequence-id": "20",
                                        },
                                        "actions": {
                                            "config": {
                                                "forwarding-action": "ACCEPT",
                                            }
                                        },
                                    },
                                ]
                            },
                        },
                        {
                            "name": "ACL-ALLOW-WEB",
                            "type": "ACL_IPV4",
                            "config": {
                                "name": "ACL-ALLOW-WEB",
                                "type": "ACL_IPV4",
                            },
                            "acl-entries": {
                                "acl-entry": [
                                    {
                                        "sequence-id": "10",
                                        "config": {
                                            "sequence-id": "10",
                                        },
                                        "ipv4": {
                                            "config": {
                                                "source-address": "0.0.0.0/0",
                                                "destination-address": "0.0.0.0/0",
                                            }
                                        },
                                        "transport": {
                                            "config": {
                                                "protocol": "6",
                                                "destination-port": "80",
                                            }
                                        },
                                        "actions": {
                                            "config": {
                                                "forwarding-action": "ACCEPT",
                                            }
                                        },
                                    },
                                    {
                                        "sequence-id": "20",
                                        "config": {
                                            "sequence-id": "20",
                                        },
                                        "ipv4": {
                                            "config": {
                                                "source-address": "0.0.0.0/0",
                                                "destination-address": "0.0.0.0/0",
                                            }
                                        },
                                        "transport": {
                                            "config": {
                                                "protocol": "6",
                                                "destination-port": "443",
                                            }
                                        },
                                        "actions": {
                                            "config": {
                                                "forwarding-action": "ACCEPT",
                                            }
                                        },
                                    },
                                    {
                                        "sequence-id": "30",
                                        "config": {
                                            "sequence-id": "30",
                                        },
                                        "ipv4": {
                                            "config": {
                                                "source-address": "0.0.0.0/0",
                                                "destination-address": "0.0.0.0/0",
                                            }
                                        },
                                        "actions": {
                                            "config": {
                                                "forwarding-action": "DROP",
                                            }
                                        },
                                    },
                                ]
                            },
                        },
                    ]
                }
            return {"value": {}}

    collector = AristaCollector(client=ACLClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert len(payload["acl_sets"]) == 2

    # Check first ACL set
    acl1 = payload["acl_sets"][0]
    assert acl1["name"] == "ACL-BLOCK-ADMIN"
    assert acl1["type"] == "ACL_IPV4"
    assert len(acl1["entries"]) == 2

    # Check first entry
    entry1 = acl1["entries"][0]
    assert entry1["sequence"] == "10"
    assert entry1["match_conditions"]["source-address"] == "192.168.1.0/24"
    assert entry1["action"] == "DROP"
    assert entry1["description"] == "Block admin subnet"

    # Check second entry (implicit deny)
    entry2 = acl1["entries"][1]
    assert entry2["sequence"] == "20"
    assert entry2["action"] == "ACCEPT"

    # Check second ACL set
    acl2 = payload["acl_sets"][1]
    assert acl2["name"] == "ACL-ALLOW-WEB"
    assert len(acl2["entries"]) == 3

    # Check entry with port matching
    entry3 = acl2["entries"][0]
    assert entry3["sequence"] == "10"
    assert entry3["match_conditions"]["source-address"] == "0.0.0.0/0"
    assert entry3["match_conditions"]["protocol"] == "6"
    assert entry3["match_conditions"]["destination-port"] == "80"
    assert entry3["action"] == "ACCEPT"


def test_arista_collector_collects_acl_bindings():
    """Verify ACL interface bindings are collected from openconfig-acl."""

    class ACLBindingClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "oc-acl:acl" in xpath and "interfaces" in xpath:
                return {
                    "value": [
                        {
                            "id": "Ethernet1",
                            "config": {
                                "id": "Ethernet1",
                                "acl-name": "ACL-ALLOW-WEB",
                                "direction": "INGRESS",
                            },
                        },
                        {
                            "id": "Ethernet2",
                            "config": {
                                "id": "Ethernet2",
                                "acl-name": "ACL-BLOCK-ADMIN",
                                "direction": "INGRESS",
                            },
                        },
                    ]
                }
            return {"value": {}}

    collector = AristaCollector(client=ACLBindingClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert len(payload["acl_bindings"]) == 2

    # Check first binding
    binding1 = payload["acl_bindings"][0]
    assert binding1["interface"] == "Ethernet1"
    assert binding1["acl_set"] == "ACL-ALLOW-WEB"
    assert binding1["direction"] == "INGRESS"

    # Check second binding
    binding2 = payload["acl_bindings"][1]
    assert binding2["interface"] == "Ethernet2"
    assert binding2["acl_set"] == "ACL-BLOCK-ADMIN"
    assert binding2["direction"] == "INGRESS"


def test_arista_collector_collects_ipv6_acl():
    """Verify IPv6 ACL sets are collected correctly."""

    class IPv6ACLClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "oc-acl:acl" in xpath and "acl-sets" in xpath:
                return {
                    "value": [
                        {
                            "name": "ACL-IPV6-ADMIN",
                            "type": "ACL_IPV6",
                            "config": {
                                "name": "ACL-IPV6-ADMIN",
                                "type": "ACL_IPV6",
                            },
                            "acl-entries": {
                                "acl-entry": [
                                    {
                                        "sequence-id": "10",
                                        "config": {
                                            "sequence-id": "10",
                                        },
                                        "ipv6": {
                                            "config": {
                                                "source-address": "2001:db8::/32",
                                            }
                                        },
                                        "actions": {
                                            "config": {
                                                "forwarding-action": "DROP",
                                            }
                                        },
                                    },
                                ]
                            },
                        },
                    ]
                }
            return {"value": {}}

    collector = AristaCollector(client=IPv6ACLClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert len(payload["acl_sets"]) == 1

    acl = payload["acl_sets"][0]
    assert acl["name"] == "ACL-IPV6-ADMIN"
    assert acl["type"] == "ACL_IPV6"
    assert acl["entries"][0]["match_conditions"]["source-address"] == "2001:db8::/32"


def test_arista_collector_collects_empty_acl_data():
    """Verify empty ACL data returns empty lists without warnings."""
    collector = AristaCollector(client=FakeClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert payload["acl_sets"] == []
    assert payload["acl_bindings"] == []
    # No warnings for simply missing data
    assert payload["warnings"] == []


def test_arista_collector_handles_acl_errors():
    """Verify ACL collection handles errors gracefully."""

    class ACLErrorClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "oc-acl:acl" in xpath and "acl-sets" in xpath:
                raise Exception("NETCONF error: resource not found")
            if xpath and "oc-acl:acl" in xpath and "interfaces" in xpath:
                raise Exception("NETCONF error: timeout")
            return {"value": {}}

    collector = AristaCollector(client=ACLErrorClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert payload["acl_sets"] == []
    assert payload["acl_bindings"] == []
    # Should have warnings about the errors
    assert len(payload["warnings"]) == 2
    assert any("Could not collect ACL sets" in w for w in payload["warnings"])
    assert any("Could not collect ACL bindings" in w for w in payload["warnings"])


def test_arista_collector_collects_mlag():
    """Verify MLAG global configuration is collected from Arista EOS."""

    class MLAGClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "oc-mlag:mlag" in xpath:
                return {
                    "value": {
                        "config": {
                            "domain-id": "MLAG-DOMAIN",
                            "local-interface": "Vlan100",
                            "peer-address": "192.168.100.2",
                            "peer-link": "Port-Channel10",
                        },
                        "state": {
                            "status": "active",
                            "peer-link-status": "up",
                        },
                    }
                }
            return {"value": {}}

    collector = AristaCollector(client=MLAGClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert payload["mlag"] is not None
    assert payload["mlag"]["enabled"] is True
    assert payload["mlag"]["domain_id"] == "MLAG-DOMAIN"
    assert payload["mlag"]["local_interface"] == "Vlan100"
    assert payload["mlag"]["peer_address"] == "192.168.100.2"
    assert payload["mlag"]["peer_link"] == "Port-Channel10"
    assert payload["mlag"]["state"]["status"] == "active"
    assert payload["mlag"]["state"]["peer_link_status"] == "up"


def test_arista_collector_collects_mlag_interfaces():
    """Verify MLAG interface memberships are collected from Arista EOS."""

    class MLAGInterfaceClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "oc-if:interfaces" in xpath:
                return {
                    "value": [
                        {
                            "name": "Port-Channel20",
                            "config": {
                                "enabled": True,
                                "mlag-id": "20",
                            },
                            "state": {
                                "mlag": {
                                    "status": "active",
                                },
                            },
                        },
                        {
                            "name": "Port-Channel30",
                            "config": {
                                "enabled": True,
                                "mlag-id": "30",
                            },
                            "state": {
                                "mlag": {
                                    "status": "inactive",
                                },
                            },
                        },
                        {
                            "name": "Ethernet1",
                            "config": {
                                "enabled": True,
                            },
                        },
                    ]
                }
            return {"value": {}}

    collector = AristaCollector(client=MLAGInterfaceClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert len(payload["mlag_interfaces"]) == 2

    # Check first MLAG interface
    iface1 = payload["mlag_interfaces"][0]
    assert iface1["interface"] == "Port-Channel20"
    assert iface1["mlag_id"] == 20
    assert iface1["status"] == "active"

    # Check second MLAG interface
    iface2 = payload["mlag_interfaces"][1]
    assert iface2["interface"] == "Port-Channel30"
    assert iface2["mlag_id"] == 30
    assert iface2["status"] == "inactive"


def test_arista_collector_mlag_not_configured():
    """Verify MLAG returns None when not configured."""
    collector = AristaCollector(client=FakeClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    # MLAG not configured should return None
    assert payload["mlag"] is None
    assert payload["mlag_interfaces"] == []


def test_arista_collector_mlag_empty_config():
    """Verify MLAG returns None when config exists but domain-id is empty."""

    class EmptyMLAGClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "oc-mlag:mlag" in xpath:
                # MLAG container exists but no domain-id configured
                return {
                    "value": {
                        "config": {},
                        "state": {},
                    }
                }
            return {"value": {}}

    collector = AristaCollector(client=EmptyMLAGClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    # No domain-id means MLAG not configured
    assert payload["mlag"] is None


def test_arista_collector_mlag_error_handling():
    """Verify MLAG collection handles errors gracefully."""
    call_count = [0]

    class MLAGErrorClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            call_count[0] += 1
            # Only fail MLAG-related queries
            if xpath and "oc-mlag:mlag" in xpath:
                raise Exception("NETCONF error: resource not found")
            return {"value": {}}

    collector = AristaCollector(client=MLAGErrorClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert payload["mlag"] is None
    assert payload["mlag_interfaces"] == []
    # Should have warning about MLAG error
    assert any("Could not collect MLAG" in w for w in payload["warnings"])


def test_arista_collector_collects_evpn_instances():
    """Verify EVPN instances are collected from OpenConfig network-instance EVPN data."""

    class EVPNClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "static-routes" in xpath:
                # Return proper structure for static routes query
                return {
                    "value": {
                        "network-instance": [
                            {
                                "name": "default",
                                "static-routes": {"static": []}
                            }
                        ]
                    }
                }
            if xpath and "oc-ni:network-instances" in xpath:
                return {
                    "value": [
                        {
                            "name": "VLAN10",
                            "config": {"type": "L2VSI"},
                            "evpn": {
                                "config": {
                                    "route-distinguisher": "65001:1001",
                                },
                                "route-targets": {
                                    "route-target": [
                                        {"type": "IMPORT", "value": "65001:1001"},
                                        {"type": "EXPORT", "value": "65001:1001"},
                                    ]
                                },
                            },
                            "vlans": {
                                "vlan": [
                                    {
                                        "vlan-id": "10",
                                        "config": {"vni": "1001"},
                                    }
                                ]
                            },
                        },
                        {
                            "name": "VLAN20",
                            "config": {"type": "L2VSI"},
                            "evpn": {
                                "config": {
                                    "route-distinguisher": "65001:1002",
                                },
                                "route-targets": {
                                    "route-target": [
                                        {"type": "IMPORT", "value": "65001:1002"},
                                        {"type": "EXPORT", "value": "65001:1002"},
                                    ]
                                },
                            },
                            "vlans": {
                                "vlan": [
                                    {
                                        "vlan-id": "20",
                                        "config": {"vni": "1002"},
                                    }
                                ]
                            },
                        },
                        {
                            "name": "prod",
                            "config": {"type": "L3VRF"},
                            "evpn": {
                                "config": {
                                    "route-distinguisher": "65001:2001",
                                },
                                "route-targets": {
                                    "route-target": [
                                        {"type": "IMPORT", "value": "65001:2001"},
                                        {"type": "EXPORT", "value": "65001:2001"},
                                    ]
                                },
                            },
                            "vrf": {
                                "config": {"vni": "2001"},
                            },
                        },
                    ]
                }
            return {"value": {}}

    collector = AristaCollector(client=EVPNClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert len(payload["evpn_instances"]) == 3

    # Check L2 EVPN instances (VLAN10)
    vlan10 = payload["evpn_instances"][0]
    assert vlan10["name"] == "VLAN10"
    assert vlan10["vni"] == 1001
    assert vlan10["rd"] == "65001:1001"
    assert vlan10["route_target_import"] == ["65001:1001"]
    assert vlan10["route_target_export"] == ["65001:1001"]

    # Check L2 EVPN instances (VLAN20)
    vlan20 = payload["evpn_instances"][1]
    assert vlan20["name"] == "VLAN20"
    assert vlan20["vni"] == 1002

    # Check L3 EVPN instance (prod VRF)
    prod = payload["evpn_instances"][2]
    assert prod["name"] == "prod"
    assert prod["vni"] == 2001
    assert prod["rd"] == "65001:2001"


def test_arista_collector_collects_vxlan_mappings():
    """Verify VXLAN VNI mappings are collected from Arista VXLAN model."""

    class VXLANClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "Vxlan1" in xpath:
                return {
                    "value": [
                        {
                            "name": "Vxlan1",
                            "vxlan": {
                                "config": {
                                    "source-interface": "Loopback0",
                                    "udp-port": "4789",
                                },
                                "vlan-vni-mappings": {
                                    "vlan-vni-mapping": [
                                        {"vlan-id": "10", "vni": "1001"},
                                        {"vlan-id": "20", "vni": "1002"},
                                    ]
                                },
                                "vrf-vni-mappings": {
                                    "vrf-vni-mapping": [
                                        {"vrf-name": "prod", "vni": "2001"},
                                    ]
                                },
                            },
                        }
                    ]
                }
            return {"value": {}}

    collector = AristaCollector(client=VXLANClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert len(payload["vxlan_mappings"]) == 3

    # Check VLAN-VNI mappings
    vlan10 = payload["vxlan_mappings"][0]
    assert vlan10["vni"] == 1001
    assert vlan10["vlan_id"] == 10
    assert vlan10["vrf_name"] is None
    assert vlan10["source_interface"] == "Loopback0"

    vlan20 = payload["vxlan_mappings"][1]
    assert vlan20["vni"] == 1002
    assert vlan20["vlan_id"] == 20

    # Check VRF-VNI mapping
    vrf_vni = payload["vxlan_mappings"][2]
    assert vrf_vni["vni"] == 2001
    assert vrf_vni["vlan_id"] is None
    assert vrf_vni["vrf_name"] == "prod"


def test_arista_collector_collects_empty_evpn_vxlan_data():
    """Verify empty EVPN/VXLAN data returns empty lists without warnings."""
    collector = AristaCollector(client=FakeClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert payload["evpn_instances"] == []
    assert payload["vxlan_mappings"] == []
    # No warnings for simply missing data
    assert payload["warnings"] == []


def test_arista_collector_handles_evpn_vxlan_errors():
    """Verify EVPN/VXLAN collection handles errors gracefully."""

    class ErrorClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "static-routes" in xpath:
                # Return proper structure for static routes query
                return {
                    "value": {
                        "network-instance": [
                            {
                                "name": "default",
                                "static-routes": {"static": []}
                            }
                        ]
                    }
                }
            if xpath and "oc-ni:network-instances" in xpath:
                raise Exception("NETCONF error: resource not found")
            if xpath and "Vxlan1" in xpath:
                raise Exception("NETCONF error: timeout")
            if xpath and "oc-vxlan:vxlan" in xpath:
                raise Exception("NETCONF error: timeout")
            return {"value": {}}

    collector = AristaCollector(client=ErrorClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()
    assert payload["evpn_instances"] == []
    assert payload["vxlan_mappings"] == []
    # Should have warnings about the errors
    assert any("Could not collect EVPN instances" in w for w in payload["warnings"])
    assert any("Could not collect VXLAN mappings" in w for w in payload["warnings"])


def test_arista_collector_evpn_vxlan_mixed_l2_l3():
    """Verify EVPN/VXLAN correctly distinguishes L2 and L3 instances."""

    class MixedClient(FakeClient):
        def datastore_get(self, target, session, *, datastore="running", xpath=None):
            if xpath and "static-routes" in xpath:
                # Return proper structure for static routes query
                return {
                    "value": {
                        "network-instance": [
                            {
                                "name": "default",
                                "static-routes": {"static": []}
                            }
                        ]
                    }
                }
            if xpath and "oc-ni:network-instances" in xpath:
                return {
                    "value": [
                        {
                            "name": "VLAN100",
                            "config": {"type": "L2VSI"},
                            "evpn": {
                                "config": {"route-distinguisher": "65001:1100"},
                            },
                            "vlans": {
                                "vlan": [
                                    {"vlan-id": "100", "config": {"vni": "1100"}}
                                ]
                            },
                        },
                        {
                            "name": "CUSTOMER_VRF",
                            "config": {"type": "L3VRF"},
                            "evpn": {
                                "config": {"route-distinguisher": "65001:3000"},
                            },
                            "vrf": {
                                "config": {"vni": "3000"},
                            },
                        },
                    ]
                }
            if xpath and "Vxlan1" in xpath:
                return {
                    "value": [
                        {
                            "name": "Vxlan1",
                            "vxlan": {
                                "config": {"source-interface": "Loopback0"},
                                "vlan-vni-mappings": {
                                    "vlan-vni-mapping": [
                                        {"vlan-id": "100", "vni": "1100"},
                                    ]
                                },
                                "vrf-vni-mappings": {
                                    "vrf-vni-mapping": [
                                        {"vrf-name": "CUSTOMER_VRF", "vni": "3000"},
                                    ]
                                },
                            },
                        }
                    ]
                }
            return {"value": {}}

    collector = AristaCollector(client=MixedClient())
    snapshot = collector.collect_snapshot(
        {
            "target_ref": "target://lab/arista",
            "name": "arista-test",
            "facts": {"vendor": "arista", "os": "eos"},
        }
    )

    payload = snapshot.to_dict()

    # Check EVPN instances
    assert len(payload["evpn_instances"]) == 2
    vlan100 = payload["evpn_instances"][0]
    assert vlan100["name"] == "VLAN100"
    assert vlan100["vni"] == 1100

    customer = payload["evpn_instances"][1]
    assert customer["name"] == "CUSTOMER_VRF"
    assert customer["vni"] == 3000

    # Check VXLAN mappings
    assert len(payload["vxlan_mappings"]) == 2
    l2_mapping = payload["vxlan_mappings"][0]
    assert l2_mapping["vni"] == 1100
    assert l2_mapping["vlan_id"] == 100

    l3_mapping = payload["vxlan_mappings"][1]
    assert l3_mapping["vni"] == 3000
    assert l3_mapping["vrf_name"] == "CUSTOMER_VRF"
