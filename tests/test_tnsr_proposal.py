from __future__ import annotations

import json
from pathlib import Path

from netconf_mcp.proposals.tnsr import (
    build_managed_tnsr_config_from_payload,
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
            "neighbors": [
                {"peer": "192.0.2.2", "enabled": True, "bfd": True, "peer_group": "TRANSIT", "remote_asn": "64512", "description": None, "update_source": None, "ebgp_multihop_max_hops": 4}
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
        "raw_sections": {"config_root_keys": ["interfaces-config"]},
    }


def test_build_managed_tnsr_config_from_payload_normalizes_and_sorts():
    managed = build_managed_tnsr_config_from_payload(_sample_snapshot_payload())

    assert managed["schema_version"] == "tnsr-managed-config-v1"
    assert managed["device"]["name"] == "tnsr-lab"
    assert [item["name"] for item in managed["config"]["interfaces"]] == ["LAN", "WAN", "eth0"]
    assert managed["config"]["routing"]["static_routes"][0]["destination_prefix"] == "0.0.0.0/0"
    assert managed["config"]["bgp"]["neighbors"][0]["peer"] == "192.0.2.2"
    assert managed["config"]["bgp"]["ebgp_requires_policy"] is True
    assert managed["config"]["bgp"]["neighbors"][0]["bfd"] is True
    assert managed["config"]["routing_policy"]["prefix_lists"][0]["name"] == "DEFAULT-OUT"
    assert managed["config"]["routing_policy"]["route_maps"][0]["name"] == "TRANSIT-OUT"
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
                    "routing": {"static_routes": []},
                    "bgp": {"asn": None, "router_id": None, "neighbors": [], "network_announcements": []},
                    "routing_policy": {"prefix_lists": [], "route_maps": []},
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
