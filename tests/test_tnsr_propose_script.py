from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def test_tnsr_propose_split_layout_writes_domain_files(tmp_path: Path):
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        """{
  "snapshot_type": "tnsr-normalized-config-v1",
  "collected_at_utc": "2026-03-12T12:00:00+00:00",
  "target_ref": "target://lab/tnsr",
  "device": {"name": "tnsr-lab", "vendor": "netgate", "os": "tnsr", "host": "tnsr.example.net", "site": "lab", "role": ["edge"]},
  "capabilities": ["urn:ietf:params:netconf:base:1.1"],
  "module_inventory": [{"module": "netgate-bgp", "revision": "2025-10-02"}],
  "interfaces": [{"name": "LAN", "kind": "dataplane", "enabled": true, "description": null, "ipv4_addresses": ["10.0.0.1/24"]}],
  "static_routes": [{"table": "default", "destination_prefix": "0.0.0.0/0", "next_hop": "192.0.2.1", "interface": "WAN"}],
  "bgp": {"asn": "65001", "router_id": "10.0.0.1", "vrf_id": "default", "ipv4_unicast_enabled": false, "ebgp_requires_policy": true, "log_neighbor_changes": true, "network_import_check": true, "keepalive_seconds": 3, "hold_time_seconds": 9, "neighbors": [], "network_announcements": []},
  "prefix_lists": [],
  "route_maps": [],
  "bfd_sessions": [],
  "nat_rulesets": [{"name": "WAN-nat", "description": "NAT for WAN", "rules": []}],
  "acl_rulesets": [{"name": "LAN-filter", "description": "Filter rules for LAN", "rules": []}],
  "interface_policy_bindings": [{"interface": "WAN", "nat_ruleset": "WAN-nat", "filter_ruleset": "WAN-filter"}],
  "raw_sections": {}
}""",
        encoding="utf-8",
    )

    proposal_path = tmp_path / "proposal.md"
    managed_root = tmp_path / "managed" / "tnsr-lab"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/tnsr_propose.py",
            "--snapshot",
            str(snapshot_path),
            "--layout",
            "split",
            "--managed-file",
            str(managed_root),
            "--proposal-file",
            str(proposal_path),
        ],
        cwd="/Users/rdw/src/netconf-mcp",
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Proposal index:" in result.stdout
    assert proposal_path.exists()
    proposal_text = proposal_path.read_text(encoding="utf-8")
    assert "Action: `create`" in proposal_text
    assert str(managed_root / "routing" / "bgp.json") in proposal_text
    assert str(managed_root / "security" / "nat-rulesets.json") in proposal_text
    assert str(managed_root / "observed-state.json") not in proposal_text
