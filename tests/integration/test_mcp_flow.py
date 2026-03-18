from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from netconf_mcp.mcp.server import create_server


FIXTURES = Path("tests/fixtures")


class DummyLiveClient:
    def open_session(self, target, *, framing="auto", hostkey_policy="strict", connect_timeout_ms=None):
        del hostkey_policy, connect_timeout_ms
        selected = "base:1.0" if framing == "auto" else framing
        facts = target.get("facts", {})
        os_type = facts.get("os", "tnsr")
        return type(
            "LiveSession",
            (),
            {
                "session_id": "901",
                "framing": selected,
                "server_capabilities": [
                    "urn:ietf:params:netconf:base:1.0",
                    "urn:ietf:params:netconf:capability:with-defaults:1.0",
                ],
                "transport": {"protocol": "ssh", "framing": selected},
                "target_os": os_type,
            },
        )()

    def get_yang_library(self, target, session):
        del target, session
        return {
            "module_set": [{"module": "ietf-interfaces", "revision": "2018-02-20"}],
            "yang_hashes": {},
            "provenance": "live-netconf",
            "completeness": "complete",
            "feature_matrix": {},
            "raw_xml": "<rpc-reply/>",
        }

    def get_monitoring(self, target, session, scope="all"):
        del target, session
        return {
            "scope": scope,
            "sessions": [{"session-id": "901"}],
            "locks": [],
            "datastore_health": {},
            "transport_stats": {},
            "raw_xml": "<rpc-reply/>",
        }

    def datastore_get(self, target, session, *, datastore="running", xpath=None, subtree=None, with_defaults="explicit", strict_config=False):
        del target, subtree, with_defaults
        # Check target OS from session
        target_os = getattr(session, "target_os", "tnsr")

        # Handle Arista EOS xpaths
        if target_os == "eos":
            if xpath and "oc-if:interfaces" in xpath:
                return {
                    "resource": {"datastore": datastore, "filter": xpath},
                    "nacm_visibility": "unknown",
                    "value": [
                        {
                            "name": "Ethernet1",
                            "config": {"enabled": True, "description": "Uplink", "type": "ethernetCsmacd", "mtu": 9000},
                            "ipv4": {
                                "config": {"ip": "10.0.1.1", "prefix-length": "24"},
                            },
                        }
                    ],
                    "source_metadata": {"mode": "live-netconf", "host": "arista-ceos", "strict_config": strict_config},
                    "raw_xml": "<rpc-reply/>",
                }
            elif xpath and "oc-vlan:vlans" in xpath:
                return {
                    "resource": {"datastore": datastore, "filter": xpath},
                    "nacm_visibility": "unknown",
                    "value": [
                        {"vlan-id": 10, "config": {"name": "DATA", "enabled": True}},
                        {"vlan-id": 20, "config": {"name": "VOICE", "enabled": True}},
                    ],
                    "source_metadata": {"mode": "live-netconf", "host": "arista-ceos", "strict_config": strict_config},
                    "raw_xml": "<rpc-reply/>",
                }
            elif xpath and "oc-ni:network-instances" in xpath:
                # VRFs - need to return dict with network-instance key
                if "network-instance[name='default']" in xpath or "network-instance" in xpath:
                    return {
                        "resource": {"datastore": datastore, "filter": xpath},
                        "nacm_visibility": "unknown",
                        "value": {
                            "network-instance": [
                                {"name": "default", "config": {"enabled": True, "description": "Default VRF"}},
                            ]
                        },
                        "source_metadata": {"mode": "live-netconf", "host": "arista-ceos", "strict_config": strict_config},
                        "raw_xml": "<rpc-reply/>",
                    }
                # Static routes
                if "static-routes" in xpath:
                    return {
                        "resource": {"datastore": datastore, "filter": xpath},
                        "nacm_visibility": "unknown",
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
                                                        {"config": {"next-hop-address": "10.0.1.254", "outgoing-interface": "Ethernet1"}}
                                                    ]
                                                },
                                            }
                                        ]
                                    },
                                }
                            ]
                        },
                        "source_metadata": {"mode": "live-netconf", "host": "arista-ceos", "strict_config": strict_config},
                        "raw_xml": "<rpc-reply/>",
                    }
                # BGP
                if "protocols/protocol/bgp" in xpath:
                    return {
                        "resource": {"datastore": datastore, "filter": xpath},
                        "nacm_visibility": "unknown",
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
                                                        "config": {"enabled": True, "as": 65001, "router-id": "10.0.1.1"}
                                                    }
                                                },
                                            }
                                        ]
                                    },
                                }
                            ]
                        },
                        "source_metadata": {"mode": "live-netconf", "host": "arista-ceos", "strict_config": strict_config},
                        "raw_xml": "<rpc-reply/>",
                    }
                return {"resource": {"datastore": datastore, "filter": xpath}, "nacm_visibility": "unknown", "value": {}, "source_metadata": {"mode": "live-netconf"}, "raw_xml": "<rpc-reply/>"}
            elif xpath and "oc-lldp:lldp" in xpath:
                return {
                    "resource": {"datastore": datastore, "filter": xpath},
                    "nacm_visibility": "unknown",
                    "value": [],
                    "source_metadata": {"mode": "live-netconf", "host": "arista-ceos", "strict_config": strict_config},
                    "raw_xml": "<rpc-reply/>",
                }
            elif xpath and "oc-sys:system" in xpath:
                return {
                    "resource": {"datastore": datastore, "filter": xpath},
                    "nacm_visibility": "unknown",
                    "value": {"hostname": "arista-spine-01", "version": "4.30.1M", "platform-id": "vEOS"},
                    "source_metadata": {"mode": "live-netconf", "host": "arista-ceos", "strict_config": strict_config},
                    "raw_xml": "<rpc-reply/>",
                }
            return {"resource": {"datastore": datastore, "filter": xpath or "all"}, "nacm_visibility": "unknown", "value": {}, "source_metadata": {"mode": "live-netconf"}, "raw_xml": "<rpc-reply/>"}

        # TNSR handling (original code)
        if xpath is None:
            value = {
                "host-if-config": {
                    "interface": {
                        "name": "eth0",
                        "enabled": "true",
                        "ipv4": {"dhcp-client": {"enabled": "true"}},
                        "ipv6": {"dhcp-client": {"enabled": "true"}},
                    }
                },
                "interfaces-config": {
                    "interface": [
                        {"name": "LAN", "enabled": "true", "ipv4": {"address": {"ip": "10.0.0.1/24"}}},
                        {"name": "WAN", "enabled": "true", "ipv4": {"address": {"ip": "192.0.2.1/31"}}},
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
                                    "neighbors": {"neighbor": {"peer": "192.0.2.2", "peer-group-name": "TRANSIT"}},
                                }
                            }
                        },
                        "prefix-lists": {
                            "list": {
                                "name": "DEFAULT-OUT",
                                "rules": {"rule": {"sequence": "10", "action": "permit", "prefix": "0.0.0.0/0"}},
                            }
                        },
                    }
                },
                "nacm": {
                    "enable-nacm": "true",
                    "read-default": "deny",
                    "write-default": "deny",
                    "exec-default": "deny",
                    "groups": {"group": {"name": "admin", "user-name": ["ansible", "tnsr"]}},
                    "rule-list": {"name": "admin-rules", "group": "admin", "rule": {"name": "permit-all", "action": "permit"}},
                },
                "ssh-server-config": {"host": {"netconf-subsystem": {"enable": "true", "port": "830"}}},
                "logging-config": {"remote-servers": {"remote-server": {"name": "localhost", "address": "127.0.0.1", "port": "10010"}}},
                "prometheus-exporter": {"host-space": {"filters": {"filter": "v2 ^/sys/heartbeat"}}},
                "dataplane-config": {"cpu": {"workers": "6"}, "dpdk": {"dev": [{"name": "WAN"}]}},
                "sysctl-config": {"kernel": {"shmmax": "2147483648"}},
                "system": {"kernel": {"modules": {"vfio": {"noiommu": "true"}}}},
                "bfd-config": {"bfd-table": {"bfd-session": {"name": "transit-bfd", "enable": "true"}}},
                "vpf-config": {
                    "nat-rulesets": {"ruleset": {"name": "WAN-nat", "rules": {"rule": {"sequence": "1000"}}}},
                    "filter-rulesets": {"ruleset": {"name": "WAN-filter", "rules": {"rule": {"sequence": "10"}}}},
                    "options": {"interfaces": {"interface": {"if-name": "WAN", "nat-ruleset": "WAN-nat", "filter-ruleset": "WAN-filter"}}},
                },
            }
        elif xpath == "/interfaces-config/interface[name='LAN']/enabled":
            value = "true"
        elif xpath == "/logging-config":
            value = {"payload": "x" * 16000}
        elif xpath == "/route-config":
            value = {
                "dynamic": {
                    "bgp": {
                        "routers": {
                            "router": {
                                "asn": "65001",
                                "router-id": "10.0.0.1",
                                "neighbors": {"neighbor": {"peer": "192.0.2.2", "peer-group-name": "TRANSIT"}},
                            }
                        }
                    },
                    "prefix-lists": {
                        "list": {
                            "name": "DEFAULT-OUT",
                            "rules": {"rule": {"sequence": "10", "action": "permit", "prefix": "0.0.0.0/0"}},
                        }
                    },
                }
            }
        else:
            value = {"interfaces": {"interface": {"name": "eth0", "enabled": "true"}}}
        return {
            "resource": {"datastore": datastore, "filter": xpath or "all"},
            "nacm_visibility": "unknown",
            "value": value,
            "source_metadata": {
                "mode": "live-netconf",
                "host": "tnsr-lab",
                "strict_config": strict_config,
            },
            "raw_xml": "<rpc-reply/>",
        }


class CapturingLiveClient(DummyLiveClient):
    def __init__(self):
        self.invocations: list[dict[str, Any]] = []

    def datastore_get(self, target, session, *, datastore="running", xpath=None, subtree=None, with_defaults="explicit", strict_config=False):
        del session, subtree, with_defaults
        self.invocations.append(
            {
                "target": target,
                "datastore": datastore,
                "xpath": xpath,
                "strict_config": strict_config,
            }
        )

        if xpath == "/openconfig_interfaces:interfaces/openconfig_interfaces:interface[name='Ethernet1']/enabled":
            value = "true"
        elif xpath is None:
            value = {
                "openconfig_interfaces": {
                    "interfaces": {
                        "interface": {"name": "Ethernet1", "enabled": "true"}
                    }
                }
            }
        else:
            value = {"payload": "x" * 2}

        return {
            "resource": {"datastore": datastore, "filter": xpath or "all"},
            "nacm_visibility": "unknown",
            "value": value,
            "source_metadata": {
                "mode": "live-netconf",
                "host": "arista-ceos",
                "strict_config": strict_config,
            },
            "raw_xml": "<rpc-reply/>",
        }


def _write_live_inventory(tmp_path: Path) -> Path:
    inventory_path = tmp_path / "inventory-live.json"
    payload = {
        "targets": [
            {
                "target_ref": "target://lab/tnsr",
                "name": "tnsr-lab",
                "site": "lab",
                "role": ["edge"],
                "status": "online",
                "safety_state": "ready",
                "transport_mode": "live-ssh",
                "transport": {"protocol": "ssh", "framing": "base:1.0"},
                "host": "tnsr-lab",
                "port": 830,
                "username": "netops",
                "facts": {"vendor": "netgate", "os": "tnsr"},
                "safety_profile": "read-only",
                "last_seen_utc": "2026-03-12T00:00:00Z",
            }
        ]
    }
    inventory_path.write_text(json.dumps(payload), encoding="utf-8")
    return inventory_path


def _write_arista_live_inventory(tmp_path: Path) -> Path:
    inventory_path = tmp_path / "inventory-live-arista.json"
    payload = {
        "targets": [
            {
                "target_ref": "target://lab/arista",
                "name": "arista-ceos",
                "site": "lab",
                "role": ["spine"],
                "status": "online",
                "safety_state": "ready",
                "transport_mode": "live-ssh",
                "transport": {"protocol": "ssh", "framing": "base:1.0"},
                "host": "arista-ceos.example.net",
                "port": 830,
                "username": "admin",
                "facts": {"vendor": "arista", "os": "eos", "platform": "ceos"},
                "namespace_map": {
                    "oc-if": "http://openconfig.net/yang/interfaces",
                    "oc-eth": "http://openconfig.net/yang/interfaces/ethernet",
                    "oc-ip": "http://openconfig.net/yang/interfaces/ip",
                    "oc-vlan": "http://openconfig.net/yang/vlan",
                    "oc-ni": "http://openconfig.net/yang/network-instance",
                    "oc-lldp": "http://openconfig.net/yang/lldp",
                    "oc-sys": "http://openconfig.net/yang/system",
                },
                "safety_profile": "read-only",
                "last_seen_utc": "2026-03-12T00:00:00Z",
            }
        ]
    }
    inventory_path.write_text(json.dumps(payload), encoding="utf-8")
    return inventory_path


def _write_openconfig_live_inventory(tmp_path: Path) -> Path:
    inventory_path = tmp_path / "inventory-live-openconfig.json"
    payload = {
        "targets": [
            {
                "target_ref": "target://lab/arista",
                "name": "arista-ceos",
                "site": "lab",
                "role": ["edge"],
                "status": "online",
                "safety_state": "ready",
                "transport_mode": "live-ssh",
                "transport": {"protocol": "ssh", "framing": "base:1.0"},
                "host": "arista-ceos.example.net",
                "port": 830,
                "username": "admin",
                "facts": {"vendor": "arista", "os": "eos", "platform": "ceos"},
                "namespace_map": {
                    "openconfig_interfaces": "<urn:ietf:params:xml:ns:yang:openconfig-interfaces>",
                    "openconfig_interfaces_ipv4": "<urn:ietf:params:xml:ns:yang:openconfig-if-ip>",
                },
                "safety_profile": "read-only",
                "last_seen_utc": "2026-03-12T00:00:00Z",
            }
        ]
    }
    inventory_path.write_text(json.dumps(payload), encoding="utf-8")
    return inventory_path


def test_read_only_manifest_exposed_and_only_read_only_names():
    runtime = create_server(FIXTURES)
    snapshot = runtime.exposure_snapshot()
    assert set(snapshot.tools) == {
        "inventory.list_targets",
        "netconf.open_session",
        "netconf.discover_capabilities",
        "yang.get_library",
        "netconf.get_monitoring",
        "datastore.get",
        "datastore.get_config",
        "tnsr.get_domain_view",
        "arista.get_domain_view",
        "config.plan_edit",
        "config.validate_plan",
        "config.apply_plan",
        "config.rollback",
    }
    assert set(snapshot.resources) >= {
        "targets://inventory",
        "target://{target_ref}/facts",
        "target://{target_ref}/capabilities",
        "target://{target_ref}/yang-library",
        "target://{target_ref}/datastores/{name}",
        "target://{target_ref}/session-state",
    }
    assert set(snapshot.prompts) >= {
        "discover-device-safely",
        "inspect-operational-state",
        "review-yang-capabilities",
        "netconf-data-fidelity",
    }


def test_discovery_and_filtered_reads():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    list_targets = tool._tools["inventory.list_targets"]({"arguments": {"filter": {"status": "online"}}})
    assert list_targets["status"] == "ok"
    targets = list_targets["data"]["targets"]
    assert any(item["target_ref"] == "target://lab/strict" for item in targets)

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/strict",
            "arguments": {"credential_ref": "cred://vault/lab/strict"},
        }
    )
    assert open_session["status"] == "ok"
    assert "cred://[redacted]" not in str(open_session)

    session_ref = open_session["data"]["session_ref"]
    caps = tool._tools["netconf.discover_capabilities"]({"session_ref": session_ref})
    assert caps["status"] == "ok"
    assert isinstance(caps["data"].get("capability_catalog", []), list)

    lib = tool._tools["yang.get_library"]({"session_ref": session_ref})
    assert lib["status"] == "ok"
    assert lib["data"]["completeness"] == "high"

    monitor = tool._tools["netconf.get_monitoring"]({"session_ref": session_ref, "arguments": {"scope": "all"}})
    assert monitor["status"] == "ok"

    config = tool._tools["datastore.get_config"](
        {
            "session_ref": session_ref,
            "arguments": {"datastore": "running", "xpath": "/interfaces/interface[name='Ethernet1']/mtu"},
        }
    )
    assert config["status"] == "ok"
    assert config["data"]["value"] == 1514

    operational = tool._tools["datastore.get"](
        {
            "session_ref": session_ref,
            "arguments": {"datastore": "operational", "xpath": "/interfaces/interface[name='Ethernet1']/if-speed"},
        }
    )
    assert operational["status"] == "ok"
    assert operational["data"]["value"] == "10G"


def test_arista_fixture_discovery_and_config_read():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    targets = tool._tools["inventory.list_targets"]({"arguments": {"filter": {"status": "online"}}})
    assert any(item["target_ref"] == "target://lab/arista" for item in targets["data"]["targets"])

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/arista",
            "arguments": {"credential_ref": "cred://vault/lab/arista"},
        }
    )
    assert open_session["status"] == "ok"
    assert open_session["data"]["profile"] == "arista-eos-openconfig"

    session_ref = open_session["data"]["session_ref"]
    caps = tool._tools["netconf.discover_capabilities"]({"session_ref": session_ref})
    assert caps["status"] == "ok"
    assert "urn:ietf:params:netconf:capability:candidate:1.0" in caps["data"]["capability_catalog"]

    lib = tool._tools["yang.get_library"]({"session_ref": session_ref})
    assert lib["status"] == "ok"
    assert lib["data"]["provenance"] == "live-netconf"
    assert lib["data"]["completeness"] == "low"

    monitor = tool._tools["netconf.get_monitoring"]({"session_ref": session_ref, "arguments": {"scope": "all"}})
    assert monitor["status"] == "ok"
    assert monitor["data"]["sessions"][0]["session-id"] == "183020499"

    config = tool._tools["datastore.get_config"](
        {
            "session_ref": session_ref,
            "arguments": {"datastore": "running", "xpath": "/interfaces/interface[name='Management1']/description"},
        }
    )
    assert config["status"] == "ok"
    assert config["data"]["value"] == "arista-cEOS-lab"


def test_nacm_restricted_read_is_blocked():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/nacm",
            "arguments": {"credential_ref": "cred://vault/lab/nacm"},
        }
    )
    session_ref = open_session["data"]["session_ref"]

    denied = tool._tools["datastore.get_config"](
        {
            "session_ref": session_ref,
            "arguments": {"datastore": "running", "xpath": "/interfaces/interface[name='Ethernet1']/mtu"},
        }
    )
    assert denied["status"] == "error"
    assert denied["error"]["error_category"] == "nacm"


def test_transport_failure_is_reported_as_error():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    failed = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/transport",
            "arguments": {"credential_ref": "cred://vault/lab/transport"},
        }
    )
    assert failed["status"] == "error"
    assert failed["error"]["error_category"] == "transport"


def test_incomplete_yang_library_reports_low_confidence():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/yanglib",
            "arguments": {"credential_ref": "cred://vault/lab/yanglib"},
        }
    )
    session_ref = open_session["data"]["session_ref"]

    lib = tool._tools["yang.get_library"]({"session_ref": session_ref})
    assert lib["status"] == "ok"
    assert lib["confidence"] == "low"
    assert lib["warnings"][0]["code"] == "SCHEMA_INCOMPLETE"


def test_guarded_plan_only_and_validate_only_work_without_confirmation():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/strict",
            "arguments": {"credential_ref": "cred://vault/lab/strict"},
        }
    )
    assert open_session["status"] == "ok"
    session_ref = open_session["data"]["session_ref"]

    plan = tool._tools["config.plan_edit"](
        {
            "session_ref": session_ref,
            "arguments": {
                "plan_scope": "candidate",
                "intent": "merge",
                "edits": [
                    {
                        "yang_path": "/interfaces/interface[name='Ethernet1']/description",
                        "action": "set",
                        "value": "edge-agg-guarded",
                    },
                ],
            },
        }
    )
    assert plan["status"] == "ok"
    assert plan["data"]["plan_status"] in {"ready_to_validate", "ready_to_execute"}
    plan_id = plan["data"]["plan_id"]

    validation = tool._tools["config.validate_plan"](
        {
            "session_ref": session_ref,
            "arguments": {"plan_id": plan_id},
        }
    )
    assert validation["status"] == "ok"
    assert validation["data"]["plan_id"] == plan_id

    apply = tool._tools["config.apply_plan"](
        {
            "session_ref": session_ref,
            "arguments": {"plan_id": plan_id},
        }
    )
    assert apply["status"] == "error"
    assert apply["policy_decision"] == "blocked"
    assert apply["error"]["error_code"] == "CONFIRMATION_REQUIRED"

    audit = runtime.get_audit_log()
    stages = {event["context"]["stage"] for event in audit}
    assert "plan_ready" in stages
    assert "apply_blocked" in stages
    assert all("confirm://" not in str(event["context"]) for event in audit)


def test_confirmed_commit_apply_and_rollback_report_with_supported_capability():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/strict",
            "arguments": {"credential_ref": "cred://vault/lab/strict"},
        }
    )
    assert open_session["status"] == "ok"
    session_ref = open_session["data"]["session_ref"]

    plan = tool._tools["config.plan_edit"](
        {
            "session_ref": session_ref,
            "arguments": {
                "plan_scope": "candidate",
                "intent": "merge",
                "edits": [
                    {
                        "yang_path": "/interfaces/interface[name='Ethernet1']/description",
                        "action": "set",
                        "value": "from-operator",
                    },
                ],
            },
        }
    )
    assert plan["status"] == "ok"
    plan_id = plan["data"]["plan_id"]

    validation = tool._tools["config.validate_plan"](
        {
            "session_ref": session_ref,
            "arguments": {"plan_id": plan_id},
        }
    )
    assert validation["status"] == "ok"
    assert validation["data"]["plan_status"] in {"ready_to_execute", "blocked"} or validation["data"]["confidence"]

    apply = tool._tools["config.apply_plan"](
        {
            "session_ref": session_ref,
            "arguments": {
                "plan_id": plan_id,
                "lock_strategy": "explicit",
                "commit_mode": "confirmed",
                "confirmation_token": "confirm://operator/001",
                "policy_approval": {
                    "actor": "operator/alice",
                    "approved_by": "Alice",
                },
            },
        }
    )
    assert apply["status"] == "ok"
    assert apply["data"]["commit_outcome"] == "pending_commit"
    rollback_id = apply["data"]["rollback_plan"]["rollback_id"]

    rollback = tool._tools["config.rollback"](
        {
            "session_ref": session_ref,
            "arguments": {
                "rollback_id": rollback_id,
                "confirmation_token": "confirm://operator/002",
                "policy_approval": {
                    "actor": "operator/alice",
                    "approved_by": "Alice",
                },
            },
        }
    )
    assert rollback["status"] == "ok"
    assert rollback["data"]["rollback_outcome"] == "applied"


def test_confirmed_commit_limitation_reported_when_capability_missing():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/yanglib",
            "arguments": {"credential_ref": "cred://vault/lab/yanglib"},
        }
    )
    assert open_session["status"] == "ok"
    session_ref = open_session["data"]["session_ref"]

    plan = tool._tools["config.plan_edit"](
        {
            "session_ref": session_ref,
            "arguments": {
                "plan_scope": "candidate",
                "intent": "merge",
                "edits": [
                    {
                        "yang_path": "/interfaces/interface[name='Ethernet1']/mtu",
                        "action": "set",
                        "value": 1500,
                    },
                ],
            },
        }
    )
    assert plan["status"] == "ok"

    apply = tool._tools["config.apply_plan"](
        {
            "session_ref": session_ref,
            "arguments": {
                "plan_id": plan["data"]["plan_id"],
                "commit_mode": "confirmed",
                "lock_strategy": "explicit",
                "confirmation_token": "confirm://operator/001",
                "policy_approval": {
                    "actor": "operator/alice",
                    "approved_by": "Alice",
                },
            },
        }
    )
    assert apply["status"] == "error"
    assert apply["error"]["error_code"] == "CONFIRMED_COMMIT_UNSUPPORTED"


def test_live_read_only_target_can_be_probed_with_dummy_client(tmp_path: Path):
    inventory_path = _write_live_inventory(tmp_path)
    runtime = create_server(FIXTURES, inventory_path=inventory_path, live_client=DummyLiveClient())
    tool = runtime.get_server()

    targets = tool._tools["inventory.list_targets"]({"arguments": {"filter": {"status": "online"}}})
    assert any(item["target_ref"] == "target://lab/tnsr" for item in targets["data"]["targets"])

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/tnsr",
            "arguments": {"credential_ref": "cred://vault/lab/tnsr"},
        }
    )
    assert open_session["status"] == "ok"
    assert open_session["data"]["mode"] == "live-ssh"
    session_ref = open_session["data"]["session_ref"]

    caps = tool._tools["netconf.discover_capabilities"]({"session_ref": session_ref})
    assert caps["status"] == "ok"
    assert "urn:ietf:params:netconf:capability:with-defaults:1.0" in caps["data"]["capability_catalog"]

    lib = tool._tools["yang.get_library"]({"session_ref": session_ref})
    assert lib["status"] == "ok"
    assert lib["data"]["provenance"] == "live-netconf"

    config = tool._tools["datastore.get_config"](
        {
            "session_ref": session_ref,
            "arguments": {"datastore": "running", "xpath": "/interfaces-config/interface[name='LAN']/enabled"},
        }
    )
    assert config["status"] == "ok"
    assert config["data"]["value"] == "true"

    plan = tool._tools["config.plan_edit"](
        {
            "session_ref": session_ref,
            "arguments": {
                "plan_scope": "candidate",
                "intent": "merge",
                "edits": [{"yang_path": "/interfaces/interface[name='eth0']/enabled", "action": "set", "value": False}],
            },
        }
    )
    assert plan["status"] == "error"
    assert plan["error"]["error_code"] == "LIVE_WRITE_UNSUPPORTED"


def test_datastore_get_config_accepts_xpath_filter_alias_for_live_reads(tmp_path: Path):
    inventory_path = _write_live_inventory(tmp_path)
    runtime = create_server(FIXTURES, inventory_path=inventory_path, live_client=DummyLiveClient())
    tool = runtime.get_server()

    opened = tool._tools["netconf.open_session"]({"target_ref": "target://lab/tnsr"})
    session_ref = opened["data"]["session_ref"]

    config = tool._tools["datastore.get_config"](
        {
            "session_ref": session_ref,
            "arguments": {
                "datastore": "running",
                "xpath_filter": "/interfaces-config/interface[name='LAN']/enabled",
            },
        }
    )

    assert config["status"] == "ok"
    assert config["data"]["resource"]["filter"] == "/interfaces-config/interface[name='LAN']/enabled"
    assert config["data"]["value"] == "true"


def test_datastore_get_config_accepts_prefixed_openconfig_xpath_for_live_reads(tmp_path: Path):
    inventory_path = _write_openconfig_live_inventory(tmp_path)
    live_client = CapturingLiveClient()
    runtime = create_server(FIXTURES, inventory_path=inventory_path, live_client=live_client)
    tool = runtime.get_server()

    opened = tool._tools["netconf.open_session"]({"target_ref": "target://lab/arista"})
    session_ref = opened["data"]["session_ref"]

    config = tool._tools["datastore.get_config"](
        {
            "session_ref": session_ref,
            "arguments": {
                "datastore": "running",
                "xpath": "/openconfig_interfaces:interfaces/openconfig_interfaces:interface[name='Ethernet1']/enabled",
            },
        }
    )

    assert config["status"] == "ok"
    assert config["data"]["value"] == "true"
    assert live_client.invocations
    assert live_client.invocations[0]["xpath"].startswith("/openconfig_interfaces:")
    assert "openconfig_interfaces" in live_client.invocations[0]["target"].get("namespace_map", {})


def test_datastore_get_config_rejects_conflicting_filter_arguments(tmp_path: Path):
    inventory_path = _write_live_inventory(tmp_path)
    runtime = create_server(FIXTURES, inventory_path=inventory_path, live_client=DummyLiveClient())
    tool = runtime.get_server()

    opened = tool._tools["netconf.open_session"]({"target_ref": "target://lab/tnsr"})
    session_ref = opened["data"]["session_ref"]

    config = tool._tools["datastore.get_config"](
        {
            "session_ref": session_ref,
            "arguments": {
                "datastore": "running",
                "xpath": "/interfaces-config/interface[name='LAN']/enabled",
                "xpath_filter": "/different/path",
            },
        }
    )

    assert config["status"] == "error"
    assert config["error"]["error_code"] == "FILTER_CONFLICT"


def test_datastore_get_config_trims_large_live_payloads(tmp_path: Path):
    inventory_path = _write_live_inventory(tmp_path)
    runtime = create_server(FIXTURES, inventory_path=inventory_path, live_client=DummyLiveClient())
    tool = runtime.get_server()

    opened = tool._tools["netconf.open_session"]({"target_ref": "target://lab/tnsr"})
    session_ref = opened["data"]["session_ref"]

    config = tool._tools["datastore.get_config"](
        {
            "session_ref": session_ref,
            "arguments": {
                "datastore": "running",
                "xpath_filter": "/logging-config",
            },
        }
    )

    assert config["status"] == "ok"
    assert config["data"]["source_metadata"]["response_truncated"] is True
    assert "raw_xml" not in config["data"]
    assert config["data"]["response_summary"]["reason"] == "large_datastore_read"


def test_tnsr_config_reads_reject_non_tnsr_vendor_roots(tmp_path: Path):
    inventory_path = _write_live_inventory(tmp_path)
    runtime = create_server(FIXTURES, inventory_path=inventory_path, live_client=DummyLiveClient())
    tool = runtime.get_server()

    opened = tool._tools["netconf.open_session"]({"target_ref": "target://lab/tnsr"})
    session_ref = opened["data"]["session_ref"]

    config = tool._tools["datastore.get_config"](
        {
            "session_ref": session_ref,
            "arguments": {
                "datastore": "running",
                "xpath_filter": "/frr-routing:routing/control-plane-protocols/control-plane-protocol/frr-bgp:bgp/global/afi-safis/afi-safi/filter-config",
            },
        }
    )

    assert config["status"] == "error"
    assert config["error"]["error_code"] == "UNSUPPORTED_VENDOR_PATH"


def test_tnsr_domain_view_returns_compact_prefix_list_view_for_live_session(tmp_path: Path):
    inventory_path = _write_live_inventory(tmp_path)
    runtime = create_server(FIXTURES, inventory_path=inventory_path, live_client=DummyLiveClient())
    tool = runtime.get_server()

    opened = tool._tools["netconf.open_session"]({"target_ref": "target://lab/tnsr"})
    session_ref = opened["data"]["session_ref"]

    view = tool._tools["tnsr.get_domain_view"](
        {
            "session_ref": session_ref,
            "arguments": {
                "domain": "prefix-lists",
            },
        }
    )

    assert view["status"] == "ok"
    assert view["data"]["domain"] == "prefix-lists"
    assert view["data"]["view"]["summary"]["prefix_list_count"] == 1
    assert view["data"]["view"]["prefix_lists"][0]["name"] == "DEFAULT-OUT"


def test_tnsr_domain_view_rejects_non_tnsr_sessions():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    opened = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/strict",
            "arguments": {"credential_ref": "cred://vault/lab/strict"},
        }
    )
    session_ref = opened["data"]["session_ref"]

    view = tool._tools["tnsr.get_domain_view"](
        {
            "session_ref": session_ref,
            "arguments": {"domain": "prefix-lists"},
        }
    )

    assert view["status"] == "error"
    assert view["error"]["error_code"] == "UNSUPPORTED_TARGET"


def test_arista_domain_view_returns_compact_interface_view_for_live_session(tmp_path: Path):
    inventory_path = _write_arista_live_inventory(tmp_path)
    runtime = create_server(FIXTURES, inventory_path=inventory_path, live_client=DummyLiveClient())
    tool = runtime.get_server()

    opened = tool._tools["netconf.open_session"]({"target_ref": "target://lab/arista"})
    session_ref = opened["data"]["session_ref"]

    view = tool._tools["arista.get_domain_view"](
        {
            "session_ref": session_ref,
            "arguments": {
                "domain": "interfaces",
            },
        }
    )

    assert view["status"] == "ok"
    assert view["data"]["domain"] == "interfaces"
    assert view["data"]["view"]["summary"]["interface_count"] == 1
    assert view["data"]["view"]["interfaces"][0]["name"] == "Ethernet1"


def test_arista_domain_view_rejects_non_eos_sessions():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    opened = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/strict",
            "arguments": {"credential_ref": "cred://vault/lab/strict"},
        }
    )
    session_ref = opened["data"]["session_ref"]

    view = tool._tools["arista.get_domain_view"](
        {
            "session_ref": session_ref,
            "arguments": {"domain": "interfaces"},
        }
    )

    assert view["status"] == "error"
    assert view["error"]["error_code"] == "UNSUPPORTED_TARGET"


def test_arista_domain_view_rejects_invalid_domain():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    opened = tool._tools["netconf.open_session"]({"target_ref": "target://lab/arista"})
    session_ref = opened["data"]["session_ref"]

    view = tool._tools["arista.get_domain_view"](
        {
            "session_ref": session_ref,
            "arguments": {"domain": "invalid-domain"},
        }
    )

    assert view["status"] == "error"
    assert view["error"]["error_code"] == "BAD_DOMAIN"
