from __future__ import annotations

from netconf_mcp.vendors.arista import (
    AristaCollector,
    ARISTA_NAMESPACES,
    BGPRecord,
    InterfaceRecord,
    LAGRecord,
    LLDPNeighborRecord,
    StaticRouteRecord,
    SystemInfoRecord,
    VLANRecord,
    VRFRecord,
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
