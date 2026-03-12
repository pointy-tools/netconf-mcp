from __future__ import annotations

import json
from pathlib import Path

from netconf_mcp.proposals.tnsr import (
    build_managed_tnsr_config_from_payload,
    build_split_managed_tnsr_files,
    build_split_tnsr_proposal_index,
    build_tnsr_proposal_artifacts,
)


def _sample_snapshot_payload() -> dict:
    return {
        "snapshot_type": "tnsr-normalized-config-v1",
        "collected_at_utc": "2026-03-12T12:00:00+00:00",
        "target_ref": "target://lab/tnsr",
        "device": {
            "name": "tnsr-lab",
            "vendor": "netgate",
            "os": "tnsr",
            "host": "tnsr.example.net",
            "site": "lab",
            "role": ["edge"],
        },
        "capabilities": [
            "urn:ietf:params:netconf:capability:candidate:1.0",
            "urn:ietf:params:netconf:base:1.1",
        ],
        "module_inventory": [
            {"module": "netgate-interface", "revision": "2025-10-02"},
            {"module": "netgate-bgp", "revision": "2025-10-02"},
        ],
        "interfaces": [
            {"name": "WAN", "kind": "dataplane", "enabled": False, "description": None, "ipv4_addresses": ["192.0.2.1/31"]},
            {"name": "LAN", "kind": "dataplane", "enabled": True, "description": "lan-uplink", "ipv4_addresses": ["10.0.0.1/24"]},
            {"name": "eth0", "kind": "host", "enabled": True, "description": None, "ipv4_addresses": []},
        ],
        "host_interfaces": [
            {
                "name": "eth0",
                "enabled": True,
                "ipv4_addresses": [],
                "ipv4_dhcp_client_enabled": True,
                "ipv6_dhcp_client_enabled": True,
            }
        ],
        "static_routes": [
            {"table": "default", "destination_prefix": "0.0.0.0/0", "next_hop": "192.0.2.0", "interface": "WAN"}
        ],
        "bgp": {
            "asn": "65001",
            "router_id": "10.0.0.1",
            "vrf_id": "default",
            "ipv4_unicast_enabled": False,
            "ebgp_requires_policy": True,
            "log_neighbor_changes": True,
            "network_import_check": True,
            "keepalive_seconds": 3,
            "hold_time_seconds": 9,
            "ipv4_unicast_multipath": 8,
            "neighbors": [
                {
                    "peer": "192.0.2.2",
                    "enabled": True,
                    "bfd": True,
                    "peer_group": "TRANSIT",
                    "remote_asn": "64512",
                    "description": None,
                    "update_source": None,
                    "ebgp_multihop_max_hops": 4,
                    "activate": True,
                    "route_map_in": "TRANSIT-IN",
                    "route_map_out": "TRANSIT-OUT",
                    "default_originate_route_map": "DEFAULT-OUT",
                    "send_community_standard": True
                }
            ],
            "network_announcements": ["10.0.0.0/24"],
        },
        "prefix_lists": [
            {"name": "DEFAULT-OUT", "rules": [{"sequence": "10", "action": "permit", "prefix": "0.0.0.0/0"}]}
        ],
        "route_maps": [
            {
                "name": "TRANSIT-OUT",
                "rules": [
                    {"sequence": "10", "policy": "permit", "match_ip_prefix_list": "DEFAULT-OUT", "set_as_path_prepend": "65001"}
                ],
            }
        ],
        "bfd_sessions": [
            {
                "name": "transit-bfd",
                "enabled": True,
                "interface": "LAN",
                "local_ip_address": "10.0.0.1",
                "peer_ip_address": "192.0.2.2",
                "desired_min_tx": 500000,
                "required_min_rx": 500000,
                "detect_multiplier": 3,
            }
        ],
        "nat_rulesets": [
            {
                "name": "WAN-nat",
                "description": "NAT for WAN",
                "rules": [
                    {
                        "sequence": "1000",
                        "description": "Dynamic NAT from RFC1918",
                        "direction": "out",
                        "dynamic": True,
                        "algorithm": "ip-hash",
                        "match_from_prefix": "10.0.0.0/8",
                        "translation_interface": "WAN",
                    }
                ],
            }
        ],
        "acl_rulesets": [
            {
                "name": "LAN-filter",
                "description": "Filter rules for LAN",
                "rules": [
                    {
                        "sequence": "10",
                        "description": "Permit RFC1918 egress",
                        "direction": "out",
                        "ip_version": "ipv4",
                        "pass_action": True,
                        "stateful": True,
                        "protocol_set": None,
                        "from_prefix": None,
                        "to_prefix": "10.0.0.0/8",
                    }
                ],
            }
        ],
        "interface_policy_bindings": [
            {"interface": "LAN", "nat_ruleset": None, "filter_ruleset": "LAN-filter"},
            {"interface": "WAN", "nat_ruleset": "WAN-nat", "filter_ruleset": "WAN-filter"},
        ],
        "nacm": {
            "enabled": True,
            "read_default": "deny",
            "write_default": "deny",
            "exec_default": "deny",
            "groups": [
                {"name": "admin", "user_names": ["ansible", "root", "tnsr"]}
            ],
            "rule_lists": [
                {
                    "name": "admin-rules",
                    "group": "admin",
                    "rules": [
                        {
                            "name": "permit-all",
                            "module_name": "*",
                            "access_operations": "*",
                            "action": "permit",
                        }
                    ],
                }
            ],
        },
        "ssh_server": {
            "netconf_enabled": True,
            "netconf_port": 830,
        },
        "logging": {
            "remote_servers": [
                {
                    "name": "localhost",
                    "address": "127.0.0.1",
                    "port": 10010,
                    "transport_protocol": "udp",
                    "facility": "all",
                    "priority": "warning",
                }
            ]
        },
        "prometheus_exporter": {
            "host_space_filter": "v2 ^/sys/heartbeat ^/interfaces/",
        },
        "dataplane": {
            "buffers_per_numa": 131070,
            "cpu_main_core": 1,
            "cpu_skip_cores": 1,
            "cpu_workers": 6,
            "dpdk_uio_driver": "vfio-pci",
            "dpdk_devices": [
                {"name": "WAN", "pci_id": "0000:28:00.0", "num_rx_queues": 6, "devargs": "llq_policy=1"},
                {"name": "LAN", "pci_id": "0000:29:00.0", "num_rx_queues": 6, "devargs": "llq_policy=1"},
            ],
            "main_heap_size": "8g",
            "statseg_heap_size": "2g",
        },
        "sysctl": [
            {"name": "kernel.shmmax", "value": "2147483648"},
            {"name": "vm.max_map_count", "value": "65530"},
        ],
        "system": {
            "kernel_modules": [
                {"module": "vfio", "attributes": {"noiommu": "true"}}
            ]
        },
        "raw_sections": {"config_root_keys": ["interfaces-config"]},
    }


def test_build_managed_tnsr_config_from_payload_normalizes_and_sorts():
    managed = build_managed_tnsr_config_from_payload(_sample_snapshot_payload())

    assert managed["schema_version"] == "tnsr-managed-config-v1"
    assert managed["device"]["name"] == "tnsr-lab"
    assert [item["name"] for item in managed["config"]["interfaces"]] == ["LAN", "WAN", "eth0"]
    assert managed["config"]["management"]["ssh_server"]["netconf_enabled"] is True
    assert managed["config"]["management"]["host_interfaces"][0]["name"] == "eth0"
    assert managed["config"]["management"]["logging"]["remote_servers"][0]["name"] == "localhost"
    assert managed["config"]["management"]["prometheus_exporter"]["host_space_filter"] == "v2 ^/sys/heartbeat ^/interfaces/"
    assert managed["config"]["platform"]["dataplane"]["cpu_workers"] == 6
    assert managed["config"]["platform"]["dataplane"]["dpdk_devices"][0]["name"] == "LAN"
    assert managed["config"]["platform"]["sysctl"][0]["name"] == "kernel.shmmax"
    assert managed["config"]["platform"]["system"]["kernel_modules"][0]["module"] == "vfio"
    assert managed["config"]["routing"]["static_routes"][0]["destination_prefix"] == "0.0.0.0/0"
    assert managed["config"]["bgp"]["neighbors"][0]["peer"] == "192.0.2.2"
    assert managed["config"]["bgp"]["ebgp_requires_policy"] is True
    assert managed["config"]["bgp"]["ipv4_unicast_multipath"] == 8
    assert managed["config"]["bgp"]["neighbors"][0]["bfd"] is True
    assert managed["config"]["bgp"]["neighbors"][0]["route_map_in"] == "TRANSIT-IN"
    assert managed["config"]["bgp"]["neighbors"][0]["route_map_out"] == "TRANSIT-OUT"
    assert managed["config"]["bgp"]["neighbors"][0]["default_originate_route_map"] == "DEFAULT-OUT"
    assert managed["config"]["bgp"]["neighbors"][0]["send_community_standard"] is True
    assert managed["config"]["routing_policy"]["prefix_lists"][0]["name"] == "DEFAULT-OUT"
    assert managed["config"]["routing_policy"]["route_maps"][0]["name"] == "TRANSIT-OUT"
    assert managed["config"]["bfd"]["sessions"][0]["name"] == "transit-bfd"
    assert managed["config"]["nat"]["rulesets"][0]["name"] == "WAN-nat"
    assert managed["config"]["acl"]["rulesets"][0]["name"] == "LAN-filter"
    assert managed["config"]["acl"]["interface_bindings"][0]["interface"] == "LAN"
    assert managed["config"]["nacm"]["groups"][0]["name"] == "admin"
    assert managed["config"]["nacm"]["rule_lists"][0]["rules"][0]["action"] == "permit"
    assert managed["observed_state"]["netconf_capabilities"] == [
        "urn:ietf:params:netconf:base:1.1",
        "urn:ietf:params:netconf:capability:candidate:1.0",
    ]


def test_build_tnsr_proposal_artifacts_reports_create_when_managed_file_missing(tmp_path: Path):
    managed_path = tmp_path / "managed-configs" / "tnsr" / "tnsr-lab.json"
    proposal_text, candidate_text = build_tnsr_proposal_artifacts(
        managed_path=managed_path,
        candidate_config=build_managed_tnsr_config_from_payload(_sample_snapshot_payload()),
    )

    assert "Managed file: create" in proposal_text
    assert f"Target file: `{managed_path}`" in proposal_text
    assert f"+++ {managed_path} (proposed)" in proposal_text
    assert "Prefix lists: 0 -> 1" in proposal_text
    assert "Route maps: 0 -> 1" in proposal_text
    assert "BFD sessions: 0 -> 1" in proposal_text
    assert "NAT rulesets: 0 -> 1" in proposal_text
    assert "ACL rulesets: 0 -> 1" in proposal_text
    assert "NACM rule lists: 0 -> 1" in proposal_text
    assert "Host interfaces: 0 -> 1" in proposal_text
    assert "Sysctl settings: 0 -> 2" in proposal_text
    assert "Kernel modules: 0 -> 1" in proposal_text
    assert "Logging servers: 0 -> 1" in proposal_text
    candidate = json.loads(candidate_text)
    assert candidate["config"]["bgp"]["asn"] == "65001"


def test_build_tnsr_proposal_artifacts_shows_update_diff(tmp_path: Path):
    managed_path = tmp_path / "managed-configs" / "tnsr" / "tnsr-lab.json"
    managed_path.parent.mkdir(parents=True, exist_ok=True)
    managed_path.write_text(
        json.dumps(
            {
                "schema_version": "tnsr-managed-config-v1",
                "device": {"name": "tnsr-lab"},
                "config": {
                    "interfaces": [],
                    "management": {
                        "ssh_server": {"netconf_enabled": None, "netconf_port": None},
                        "host_interfaces": [],
                        "logging": {"remote_servers": []},
                        "prometheus_exporter": {"host_space_filter": None},
                    },
                    "platform": {"dataplane": {"dpdk_devices": []}, "sysctl": [], "system": {"kernel_modules": []}},
                    "routing": {"static_routes": []},
                    "bgp": {"asn": None, "router_id": None, "neighbors": [], "network_announcements": []},
                    "routing_policy": {"prefix_lists": [], "route_maps": []},
                    "bfd": {"sessions": []},
                    "nat": {"rulesets": []},
                    "acl": {"rulesets": [], "interface_bindings": []},
                    "nacm": {"groups": [], "rule_lists": []},
                },
                "observed_state": {"netconf_capabilities": [], "yang_modules": []},
                "metadata": {"generated_from_snapshot_type": "tnsr-normalized-config-v1", "collected_at_utc": "2026-03-12T00:00:00+00:00"},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    proposal_text, _candidate_text = build_tnsr_proposal_artifacts(
        managed_path=managed_path,
        candidate_config=build_managed_tnsr_config_from_payload(_sample_snapshot_payload()),
    )

    assert "Managed file: update" in proposal_text
    assert "-    \"interfaces\": []" in proposal_text
    assert "+    \"interfaces\": [" in proposal_text
    assert "+      \"prefix_lists\": [" in proposal_text
    assert "+      \"sessions\": [" in proposal_text
    assert "+      \"rulesets\": [" in proposal_text


def test_build_split_managed_tnsr_files_groups_by_domain():
    candidate = build_managed_tnsr_config_from_payload(_sample_snapshot_payload())

    files = build_split_managed_tnsr_files(candidate)

    assert "device.json" in files
    assert "interfaces.json" in files
    assert "management/ssh-server.json" in files
    assert "management/host-interfaces.json" in files
    assert "management/logging.json" in files
    assert "management/prometheus-exporter.json" in files
    assert "platform/dataplane.json" in files
    assert "platform/sysctl.json" in files
    assert "platform/system.json" in files
    assert "routing/bgp.json" in files
    assert "routing/prefix-lists.json" in files
    assert "services/bfd.json" in files
    assert "security/nat-rulesets.json" in files
    assert "security/acl-rulesets.json" in files
    assert "security/interface-policy-bindings.json" in files
    assert "security/nacm.json" in files
    assert "observed-state.json" not in files
    assert "\"name\": \"WAN-nat\"" in files["security/nat-rulesets.json"]
    assert "\"name\": \"LAN-filter\"" in files["security/acl-rulesets.json"]
    assert "\"admin-rules\"" in files["security/nacm.json"]
    assert "\"netconf_port\": 830" in files["management/ssh-server.json"]
    assert "\"localhost\"" in files["management/logging.json"]
    assert "\"cpu_workers\": 6" in files["platform/dataplane.json"]
    assert "\"vfio\"" in files["platform/system.json"]


def test_build_split_managed_tnsr_files_can_include_observed_state():
    candidate = build_managed_tnsr_config_from_payload(_sample_snapshot_payload())

    files = build_split_managed_tnsr_files(candidate, include_observed_state=True)

    assert "observed-state.json" in files
    assert "\"observed_state\"" in files["observed-state.json"]


def test_build_split_tnsr_proposal_index_reports_per_file_create(tmp_path: Path):
    candidate = build_managed_tnsr_config_from_payload(_sample_snapshot_payload())
    files = build_split_managed_tnsr_files(candidate)
    managed_root = tmp_path / "managed-configs" / "tnsr" / "tnsr-lab"

    proposal_text = build_split_tnsr_proposal_index(
        managed_root=managed_root,
        file_map=files,
    )

    assert "### `" in proposal_text
    assert "Action: `create`" in proposal_text
    assert "security/nat-rulesets.json" in proposal_text
    assert "services/bfd.json" in proposal_text
    assert "security/nacm.json" in proposal_text
    assert "management/ssh-server.json" in proposal_text
    assert "management/logging.json" in proposal_text
    assert "platform/dataplane.json" in proposal_text
    assert "platform/system.json" in proposal_text
