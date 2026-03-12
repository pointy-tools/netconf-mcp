from __future__ import annotations

from netconf_mcp.vendors.tnsr import TNSRCollector


class FakeSession:
    server_capabilities = [
        "urn:ietf:params:netconf:base:1.1",
        "urn:ietf:params:netconf:capability:candidate:1.0",
    ]


class FakeClient:
    def open_session(self, target, *, hostkey_policy="strict", framing="auto", connect_timeout_ms=None):
        del target, hostkey_policy, framing, connect_timeout_ms
        return FakeSession()

    def get_yang_library(self, target, session):
        del target, session
        return {
            "module_set": [{"module": "netgate-interface", "revision": "2025-10-02"}],
        }

    def datastore_get(self, target, session, *, datastore="running", strict_config=False):
        del target, session, datastore, strict_config
        return {
            "value": {
                "host-if-config": {
                    "interface": {
                        "name": "eth0",
                        "enabled": "true",
                    }
                },
                "interfaces-config": {
                    "interface": [
                        {
                            "name": "LAN",
                            "enabled": "true",
                            "description": "lan-uplink",
                            "ipv4": {"address": {"ip": "10.0.0.1/24"}},
                        },
                        {
                            "name": "WAN",
                            "enabled": "false",
                            "ipv4": {"address": {"ip": "192.0.2.1/31"}},
                        },
                    ]
                },
                "route-table-config": {
                    "static-routes": {
                        "route-table": {
                            "name": "default",
                            "ipv4-routes": {
                                "route": {
                                    "destination-prefix": "0.0.0.0/0",
                                    "next-hop": {"hop": {"ipv4-address": "192.0.2.0", "if-name": "WAN"}},
                                }
                            },
                        }
                    }
                },
                "route-config": {
                    "dynamic": {
                        "bgp": {
                            "routers": {
                                "router": {
                                    "asn": "65001",
                                    "router-id": "10.0.0.1",
                                    "neighbors": {
                                        "neighbor": [
                                        {
                                            "peer": "192.0.2.2",
                                            "bfd": "true",
                                            "enable": "true",
                                            "peer-group-name": "TRANSIT",
                                            "remote-asn": "64512",
                                            "ebgp-multihop": {"max-hop-count": "4"},
                                        }
                                    ]
                                },
                                "defaults": {"ipv4-unicast-enabled": "false"},
                                "ebgp-requires-policy": "true",
                                "log-neighbor-changes": "true",
                                "network-import-check": "true",
                                "timers": {"keep-alive": "3", "hold-time": "9"},
                                "vrf-id": "default",
                                "address-families": {
                                    "ipv4": {
                                        "unicast": {
                                                "network-announcements": {
                                                    "network": [{"ip-prefix": "10.0.0.0/24"}]
                                                }
                                            }
                                        }
                                    },
                                }
                            }
                        }
                    },
                    "prefix-lists": {
                        "list": {
                            "name": "DEFAULT-OUT",
                            "rules": {"rule": {"sequence": "10", "action": "permit", "prefix": "0.0.0.0/0"}},
                        }
                    },
                    "route-maps": {
                        "map": {
                            "name": "TRANSIT-OUT",
                            "rules": {
                                "rule": {
                                    "sequence": "10",
                                    "policy": "permit",
                                    "match": {"ip-address-prefix-list": "DEFAULT-OUT"},
                                    "set": {"as-path": {"prepend": "65001"}},
                                }
                            }
                        },
                    },
                },
            }
        }

    def get_monitoring(self, target, session, scope="all"):
        del target, session, scope
        return {"sessions": [{"session-id": "1"}]}


def test_tnsr_collector_normalizes_interfaces_routes_and_bgp():
    collector = TNSRCollector(client=FakeClient())
    snapshot = collector.collect(
        {
            "target_ref": "target://lab/tnsr",
            "name": "tnsr-lab",
            "facts": {"vendor": "netgate", "os": "tnsr"},
            "host": "tnsr.example.net",
            "site": "lab",
            "role": ["edge"],
        }
    )

    payload = snapshot.to_dict()
    assert payload["snapshot_type"] == "tnsr-normalized-config-v1"
    assert payload["device"]["vendor"] == "netgate"
    assert [item["name"] for item in payload["interfaces"]] == ["eth0", "LAN", "WAN"]
    assert payload["interfaces"][1]["ipv4_addresses"] == ["10.0.0.1/24"]
    assert payload["static_routes"][0]["destination_prefix"] == "0.0.0.0/0"
    assert payload["static_routes"][0]["interface"] == "WAN"
    assert payload["bgp"]["asn"] == "65001"
    assert payload["bgp"]["router_id"] == "10.0.0.1"
    assert payload["bgp"]["vrf_id"] == "default"
    assert payload["bgp"]["ebgp_requires_policy"] is True
    assert payload["bgp"]["keepalive_seconds"] == 3
    assert payload["bgp"]["neighbors"][0]["peer"] == "192.0.2.2"
    assert payload["bgp"]["neighbors"][0]["bfd"] is True
    assert payload["bgp"]["neighbors"][0]["ebgp_multihop_max_hops"] == 4
    assert payload["bgp"]["network_announcements"] == ["10.0.0.0/24"]
    assert payload["prefix_lists"][0]["name"] == "DEFAULT-OUT"
    assert payload["prefix_lists"][0]["rules"][0]["prefix"] == "0.0.0.0/0"
    assert payload["route_maps"][0]["name"] == "TRANSIT-OUT"
    assert payload["route_maps"][0]["rules"][0]["match_ip_prefix_list"] == "DEFAULT-OUT"
