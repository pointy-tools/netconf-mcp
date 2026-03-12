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
                        "ipv4": {"dhcp-client": {"enabled": "true"}},
                        "ipv6": {"dhcp-client": {"enabled": "false"}},
                    }
                },
                "ssh-server-config": {
                    "host": {
                        "netconf-subsystem": {
                            "enable": "true",
                            "port": "830",
                        }
                    }
                },
                "dataplane-config": {
                    "buffers-per-numa": "131070",
                    "cpu": {
                        "main-core": "1",
                        "skip-cores": "1",
                        "workers": "6",
                    },
                    "dpdk": {
                        "uio-driver": "vfio-pci",
                        "dev": [
                            {
                                "name": "WAN",
                                "id": "0000:28:00.0",
                                "num-rx-queues": "6",
                                "devargs": "llq_policy=1",
                            },
                            {
                                "name": "LAN",
                                "id": "0000:29:00.0",
                                "num-rx-queues": "6",
                                "devargs": "llq_policy=1",
                            },
                        ],
                    },
                    "memory": {"main-heap-size": "8g"},
                    "statseg": {"heap-size": "2g"},
                },
                "sysctl-config": {
                    "kernel": {"shmmax": "2147483648"},
                    "vm": {"max_map_count": "65530"},
                },
                "system": {
                    "kernel": {
                        "modules": {
                            "vfio": {
                                "noiommu": "true",
                            }
                        }
                    }
                },
                "logging-config": {
                    "remote-servers": {
                        "remote-server": {
                            "name": "localhost",
                            "address": "127.0.0.1",
                            "port": "10010",
                            "transport-protocol": "udp",
                            "filter": {
                                "facility": "all",
                                "priority": "warning",
                            },
                        }
                    }
                },
                "prometheus-exporter": {
                    "host-space": {
                        "filters": {
                            "filter": "v2 ^/sys/heartbeat ^/interfaces/",
                        }
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
                "bfd-config": {
                    "bfd-table": {
                        "bfd-session": {
                            "name": "transit-bfd",
                            "enable": "true",
                            "interface": "LAN",
                            "local-ip-address": "10.0.0.1",
                            "peer-ip-address": "192.0.2.2",
                            "desired-min-tx": "500000",
                            "required-min-rx": "500000",
                            "detect-multiplier": "3",
                        }
                    }
                },
                "vpf-config": {
                    "filter-rulesets": {
                        "ruleset": {
                            "name": "LAN-filter",
                            "description": "Filter rules for LAN",
                            "rules": {
                                "rule": {
                                    "sequence": "10",
                                    "description": "Permit RFC1918 egress",
                                    "direction": "out",
                                    "ip-version": "ipv4",
                                    "pass": "true",
                                    "stateful": "true",
                                    "filter": {"to": {"ipv4-prefix": "10.0.0.0/8"}},
                                }
                            },
                        }
                    },
                    "nat-rulesets": {
                        "ruleset": {
                            "name": "WAN-nat",
                            "description": "NAT for WAN",
                            "rules": {
                                "rule": {
                                    "sequence": "1000",
                                    "description": "Dynamic NAT from RFC1918",
                                    "direction": "out",
                                    "dynamic": "true",
                                    "algorithm": "ip-hash",
                                    "match": {"from": {"ipv4-prefix": "10.0.0.0/8"}},
                                    "translation": {"if-name": "WAN"},
                                }
                            },
                        }
                    },
                    "options": {
                        "interfaces": {
                            "interface": [
                                {"if-name": "LAN", "filter-ruleset": "LAN-filter"},
                                {"if-name": "WAN", "nat-ruleset": "WAN-nat", "filter-ruleset": "WAN-filter"},
                            ]
                        }
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
    assert payload["host_interfaces"][0]["name"] == "eth0"
    assert payload["host_interfaces"][0]["ipv4_dhcp_client_enabled"] is True
    assert payload["host_interfaces"][0]["ipv6_dhcp_client_enabled"] is False
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
    assert payload["bfd_sessions"][0]["name"] == "transit-bfd"
    assert payload["bfd_sessions"][0]["enabled"] is True
    assert payload["bfd_sessions"][0]["detect_multiplier"] == 3
    assert payload["nat_rulesets"][0]["name"] == "WAN-nat"
    assert payload["nat_rulesets"][0]["rules"][0]["match_from_prefix"] == "10.0.0.0/8"
    assert payload["acl_rulesets"][0]["name"] == "LAN-filter"
    assert payload["acl_rulesets"][0]["rules"][0]["to_prefix"] == "10.0.0.0/8"
    assert payload["interface_policy_bindings"][0]["interface"] == "LAN"
    assert payload["ssh_server"]["netconf_enabled"] is True
    assert payload["ssh_server"]["netconf_port"] == 830
    assert payload["dataplane"]["cpu_workers"] == 6
    assert payload["dataplane"]["dpdk_devices"][0]["name"] == "WAN"
    assert payload["sysctl"][0]["name"] == "kernel.shmmax"
    assert payload["system"]["kernel_modules"][0]["module"] == "vfio"
    assert payload["system"]["kernel_modules"][0]["attributes"]["noiommu"] == "true"
    assert payload["logging"]["remote_servers"][0]["name"] == "localhost"
    assert payload["logging"]["remote_servers"][0]["port"] == 10010
    assert payload["prometheus_exporter"]["host_space_filter"] == "v2 ^/sys/heartbeat ^/interfaces/"
