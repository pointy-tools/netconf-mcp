from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def test_tnsr_show_uses_snapshot_and_prints_prefix_list_summary(tmp_path: Path):
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(
        """{
  "prefix_lists": [
    {"name": "AWS-PUBLIC-ANNOUNCE", "rules": [{"sequence": "1", "action": "permit", "prefix": "16.15.176.0/20"}]},
    {"name": "DEFAULT-OUT", "rules": [{"sequence": "10", "action": "permit", "prefix": "0.0.0.0/0"}]}
  ],
  "nacm": {"enabled": true, "groups": [], "rule_lists": []},
  "interfaces": [],
  "host_interfaces": [],
  "static_routes": [],
  "bgp": {"neighbors": []},
  "route_maps": [],
  "bfd_sessions": [],
  "nat_rulesets": [],
  "acl_rulesets": [],
  "interface_policy_bindings": [],
  "ssh_server": {},
  "logging": {"remote_servers": []},
  "prometheus_exporter": {},
  "dataplane": {"dpdk_devices": []},
  "sysctl": [],
  "system": {"kernel_modules": []}
}""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/tnsr_show.py",
            "--snapshot",
            str(snapshot_path),
            "--domain",
            "prefix-lists",
        ],
        cwd="/Users/rdw/src/netconf-mcp",
        check=True,
        capture_output=True,
        text=True,
    )

    assert "\"prefix_list_count\": 2" in result.stdout
    assert "\"AWS-PUBLIC-ANNOUNCE\"" in result.stdout
