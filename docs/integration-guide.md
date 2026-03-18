# Integration Guide (Fixture-first)

- Start server: `python -m netconf_mcp.cli`
- Session tool flow:
  1. `inventory.list_targets`
  2. `netconf.open_session`
  3. `netconf.discover_capabilities`
  4. `yang.get_library`
  5. `datastore.get` / `datastore.get_config`

All inputs are fixture-driven under `tests/fixtures`.

## Experimental live read-only mode

You can point the server at a separate inventory file for lab-device testing:

Start by copying the example inventory and filling in your own lab details:

```bash
cp lab-inventory.example.json lab-inventory.json
```

```bash
NETCONF_MCP_INVENTORY=lab-inventory.json python -m netconf_mcp.cli
```

Example live target entry:

```json
{
  "target_ref": "target://lab/tnsr",
  "name": "tnsr-lab",
  "status": "online",
  "transport_mode": "live-ssh",
  "transport": {"protocol": "ssh", "framing": "base:1.0"},
  "host": "tnsr-lab.example.net",
  "port": 830,
  "username": "netops",
  "facts": {"vendor": "netgate", "os": "tnsr"},
  "safety_profile": "read-only"
}
```

Notes:

- The live path uses the local `ssh` client and NETCONF subsystem.
- Current live mode is read-only only; write operations are blocked.
- Using `ssh_config_host` instead of `host` is supported when local SSH config manages host aliases and keys.

## Recommended Arista lab startup path

The repository recommends `cEOS-lab + containerlab` on Linux first for Arista discovery:

- it is reproducible with `docker`/`containerlab`
- startup is fast for fixture-first experiments
- standard NETCONF endpoint remains on SSH port `830`

Reference setup and verification details in [`docs/arista-lab.md`](docs/arista-lab.md).

Quick-start Arista example:

```bash
cp lab-inventory.arista.example.json lab-inventory.json
cd labs/arista-ceos
containerlab deploy -t containerlab.yml
cd -
```

Verify NETCONF reachability:

```bash
cd labs/arista-ceos
docker inspect -f '{{ range .NetworkSettings.Networks}}{{ .IPAddress }}{{ end }}' clab-arista-ceos-lab-ceos1
nc -zv <mgmt-ip> 830
ssh -p 830 root@<mgmt-ip> -s netconf
```

Run the live capture flow against the new Arista target:

```bash
cd <repo-root>
python scripts/netconf_fixture_capture.py \
  --inventory lab-inventory.json \
  --target-ref target://lab/arista \
  --hostkey-policy accept-new \
  --profile custom \
  --output arista-live-capture.json \
  --config-xpath '/oc-if:interfaces' \
  --oper-xpath '/oc-if:interfaces-state'
```

Hardware validation against physical Arista gear is intentionally a **later phase** after
virtual-lab fixture capture and plan review.

## Arista EOS Integration

This section covers the Arista EOS-specific integration patterns using OpenConfig YANG models.

### Inventory Configuration

Arista EOS targets require a `namespace_map` for OpenConfig XPath queries:

```json
{
  "target_ref": "target://lab/arista",
  "name": "arista-ceos-lab",
  "status": "online",
  "transport_mode": "live-ssh",
  "transport": {"protocol": "ssh", "framing": "base:1.0"},
  "host": "arista-ceos.example.net",
  "port": 830,
  "username": "admin",
  "facts": {
    "vendor": "arista",
    "os": "eos",
    "platform": "ceos"
  },
  "namespace_map": {
    "oc-if": "http://openconfig.net/yang/interfaces",
    "oc-eth": "http://openconfig.net/yang/interfaces/ethernet",
    "oc-ip": "http://openconfig.net/yang/interfaces/ip",
    "oc-vlan": "http://openconfig.net/yang/vlan",
    "oc-ni": "http://openconfig.net/yang/network-instance",
    "oc-lldp": "http://openconfig.net/yang/lldp",
    "oc-sys": "http://openconfig.net/yang/system",
    "oc-bgp": "http://openconfig.net/yang/bgp"
  },
  "safety_profile": "read-only"
}
```

### Snapshot Collection

Collect a normalized Arista EOS snapshot:

```bash
python scripts/arista_snapshot.py \
  --inventory lab-inventory.json \
  --target-ref target://lab/arista \
  --hostkey-policy accept-new \
  --output arista-snapshot.json
```

The snapshot normalizes:

- device identity and facts
- NETCONF capabilities
- module inventory (YANG library)
- interfaces with IP addresses
- LAG/LACP interfaces
- VLANs
- VRFs/network instances
- static routes
- BGP global configuration
- LLDP neighbors
- system information (hostname, version, platform)

### MCP Arista Domain Tool

For agent workflows, use the dedicated Arista MCP domain tool:

```
Tool: arista.get_domain_view
Arguments: {
  "session_ref": "session-001",
  "domain": "interfaces"
}
```

Supported domains:

- `interfaces` — Interface config, descriptions, IP addresses
- `vlans` — VLAN IDs and names
- `vrfs` — VRF/network instances
- `lags` — LACP LAG interfaces and members
- `bgp` — BGP global config (ASN, router-id)
- `lldp` — LLDP neighbor discovery
- `system` — Hostname, version, platform
- `routing` — Static routes by VRF
- `routing-policy` — Route maps and prefix lists
- `acls` — Access control lists (IPv4/IPv6)
- `mlag` — Multi-chassis LAG configuration (arista-proprietary)
- `evpn-vxlan` — EVPN/VXLAN overlay configuration

Example response for `interfaces` domain:

```json
{
  "status": "ok",
  "vendor": "arista",
  "payload": {
    "domain": "interfaces",
    "summary": {
      "interface_count": 8,
      "enabled_count": 8,
      "with_ipv4": 5,
      "with_ipv6": 1,
      "interface_names": ["Ethernet1", "Ethernet2", "Management1", "Loopback0", "Port-Channel1", "Port-Channel2", "Vlan100", "Vlan200"]
    },
    "interfaces": [
      {"name": "Management1", "enabled": true, "description": "Management", "ipv4_addresses": ["10.0.0.100/24"]},
      {"name": "Ethernet1", "enabled": true, "description": "Uplink to Core"},
      {"name": "Ethernet2", "enabled": true, "description": "Downlink to Access"},
      {"name": "Loopback0", "enabled": true, "ipv4_addresses": ["192.168.0.1/32"]},
      {"name": "Port-Channel1", "enabled": true, "lag_type": "LACP", "members": ["Ethernet1"]},
      {"name": "Port-Channel2", "enabled": true, "lag_type": "LACP", "members": ["Ethernet2"]},
      {"name": "Vlan100", "enabled": true, "ipv4_addresses": ["10.100.0.1/24"]},
      {"name": "Vlan200", "enabled": true, "ipv4_addresses": ["10.200.0.1/24"]}
    ],
    "analysis_warnings": []
  }
}
```

Example response for `bgp` domain:

```json
{
  "status": "ok",
  "vendor": "arista",
  "payload": {
    "domain": "bgp",
    "summary": {
      "enabled": true,
      "asn": "65001",
      "router_id": "192.168.0.1"
    },
    "bgp": {
      "enabled": true,
      "asn": "65001",
      "router_id": "192.168.0.1"
    },
    "analysis_warnings": []
  }
}
```

Example response for `routing` domain:

```json
{
  "status": "ok",
  "vendor": "arista",
  "payload": {
    "domain": "routing",
    "summary": {
      "static_route_count": 3,
      "vrfs_with_routes": ["default", "MGMT"],
      "default_routes": ["0.0.0.0/0"]
    },
    "static_routes": [
      {"vrf": "default", "destination_prefix": "0.0.0.0/0", "next_hop": "10.0.0.1", "interface": "Management1"},
      {"vrf": "default", "destination_prefix": "10.50.0.0/16", "next_hop": "10.0.0.2", "interface": "Ethernet1"},
      {"vrf": "MGMT", "destination_prefix": "192.168.100.0/24", "next_hop": "172.16.0.1", "interface": "Management1"}
    ]
  }
}
```

Example response for `routing-policy` domain:

```json
{
  "status": "ok",
  "vendor": "arista",
  "payload": {
    "domain": "routing-policy",
    "summary": {
      "prefix_list_count": 2,
      "route_map_count": 2,
      "prefix_list_names": ["PL-DEFAULT-ROUTES", "PL-NETWORKS"],
      "route_map_names": ["RM-BGP-IN", "RM-BGP-OUT"]
    },
    "prefix_lists": [
      {
        "name": "PL-DEFAULT-ROUTES",
        "entries": [
          {"sequence": 10, "action": "permit", "prefix": "0.0.0.0/0", "mask_length_range": "0..32"},
          {"sequence": 20, "action": "permit", "prefix": "10.0.0.0/8", "mask_length_range": "8..32"}
        ]
      }
    ],
    "route_maps": [
      {
        "name": "RM-BGP-IN",
        "entries": [
          {"sequence": 10, "action": "permit", "match": {"prefix_list": "PL-NETWORKS"}, "set": {"local_preference": 200}}
        ]
      }
    ],
    "analysis_warnings": []
  }
}
```

Example response for `acls` domain:

```json
{
  "status": "ok",
  "vendor": "arista",
  "payload": {
    "domain": "acls",
    "summary": {
      "acl_count": 2,
      "ipv4_acl_count": 2,
      "ipv6_acl_count": 0,
      "acl_names": ["ACL-EDGE-IN", "ACL-EDGE-OUT"]
    },
    "acls": [
      {
        "name": "ACL-EDGE-IN",
        "type": "ACL_IPV4",
        "sequence_entries": [
          {"sequence": 10, "action": "permit", "protocol": "tcp", "source_prefix": "10.0.0.0/8", "destination_prefix": "any", "destination_port": "443"},
          {"sequence": 20, "action": "deny", "protocol": "ip", "source_prefix": "any", "destination_prefix": "any"}
        ]
      }
    ],
    "analysis_warnings": []
  }
}
```

Example response for `mlag` domain:

```json
{
  "status": "ok",
  "vendor": "arista",
  "payload": {
    "domain": "mlag",
    "summary": {
      "mlag_count": 1,
      "domain_id": "MLAG-DOMAIN-1",
      "peer_link": "Port-Channel100",
      "member_interfaces": ["Ethernet49", "Ethernet50"]
    },
    "mlag_config": {
      "domain_id": "MLAG-DOMAIN-1",
      "peer_address": "10.255.255.1",
      "peer_link": "Port-Channel100",
      "source_address": "10.255.255.2",
      "peer_link_member_interfaces": ["Ethernet49", "Ethernet50"],
      "mlag_interfaces": [
        {"interface": "Port-Channel10", "description": "MLAG-to-Access-1"}
      ],
      "data_source": "arista-proprietary"
    },
    "analysis_warnings": []
  }
}
```

Example response for `evpn-vxlan` domain:

```json
{
  "status": "ok",
  "vendor": "arista",
  "payload": {
    "domain": "evpn-vxlan",
    "summary": {
      "vlan_count": 2,
      "l2vni_count": 2,
      "l3vni_count": 1,
      "evpn_instance_count": 1
    },
    "vxlan_config": {
      "source_interface": "Loopback1",
      "udp_port": 4789,
      "vlans": [
        {"vlan_id": 10, "vlan_name": "DATA", "vni": 10010, "gateway_interface": "Vlan10"},
        {"vlan_id": 20, "vlan_name": "VOICE", "vni": 10020, "gateway_interface": "Vlan20"}
      ],
      "l3_vni": {"vrf": "TENANT-A", "vni": 50001, "gateway_interface": "Vlan5001"},
      "data_source": "arista-proprietary"
    },
    "evpn_instances": [
      {
        "name": "EVPN-TENANTS",
        "rd": "10.0.1.1:100",
        "import_rt": ["65000:100"],
        "export_rt": ["65000:100"]
      }
    ],
    "analysis_warnings": []
  }
}
```

### Direct Python Usage

Use the domain view functions directly in Python scripts:

```python
import json
from pathlib import Path
from netconf_mcp.vendors.arista import get_domain_view

# Load snapshot
snapshot = json.loads(Path("arista-snapshot.json").read_text())

# Query domain
view = get_domain_view(snapshot, "interfaces")
print(json.dumps(view, indent=2))
```

### OpenConfig XPath Examples

When using `datastore.get_config` with Arista, use namespace-prefixed paths:

```bash
# Get all interfaces
--config-xpath '/oc-if:interfaces/interface'

# Get specific interface
--config-xpath "/oc-if:interfaces/interface[name='Ethernet1']/config"

# Get VLANs
--config-xpath '/oc-vlan:vlans/vlan'

# Get network instances (VRFs)
--config-xpath '/oc-ni:network-instances/network-instance'

# Get BGP config
--config-xpath '/oc-ni:network-instances/network-instance/protocols/protocol/bgp'
```

Note: The `namespace_map` in the inventory must include the prefixes used in your XPath queries.

## TNSR smoke run

TNSR is the primary live target profile right now. The helper script defaults to `--profile tnsr` and runs a canned safe probe set that checks:

- session open
- capability discovery
- YANG library
- monitoring
- interface names
- LAN/WAN enabled state
- LAN/WAN configured IPv4 addresses
- host interface `eth0` enabled state
- NETCONF subsystem enabled/port state
- static route table names
- static route destination prefixes
- BGP ASN and router ID
- BGP neighbor peers

Run the default TNSR profile:

```bash
python scripts/tnsr_read_only_smoke.py \
  --inventory lab-inventory.json \
  --target-ref target://lab/tnsr \
  --hostkey-policy accept-new \
  --summary-only
```

Run one additional custom config read on top of the built-in TNSR probes:

```bash
python scripts/tnsr_read_only_smoke.py \
  --inventory lab-inventory.json \
  --target-ref target://lab/tnsr \
  --hostkey-policy accept-new \
  --config-xpath "/interfaces-config/interface[name='LAN']/ipv4/address/ip"
```

Optional operational read:

```bash
python scripts/tnsr_read_only_smoke.py \
  --inventory lab-inventory.json \
  --target-ref target://lab/tnsr \
  --hostkey-policy accept-new \
  --oper-xpath "/interfaces-state/interface[name='eth0']/oper-status"
```

## Live capture artifact helper

Use this helper for deterministic JSON artifacts before building fixture profiles:

```bash
python scripts/netconf_fixture_capture.py \
  --inventory lab-inventory.json \
  --target-ref target://lab/tnsr \
  --hostkey-policy accept-new \
  --output tnsr-live-capture.json
```

The resulting JSON includes:

- `capture_schema`
- `target_ref`
- `target` (credential fields redacted)
- `session`
- `capabilities`
- `yang_library`
- `monitoring`
- `reads.config[]`
- `reads.operational[]`

The smoke runner always executes:

1. `inventory.list_targets`
2. `netconf.open_session`
3. `netconf.discover_capabilities`
4. `yang.get_library`
5. `netconf.get_monitoring`
6. profile-selected `datastore.get_config` probes
7. optional `datastore.get`

## MCP TNSR domain tool

For agent workflows, prefer the dedicated TNSR MCP domain tool over large raw datastore reads when the question is about a known TNSR config domain.

Current domain choices:

- `interfaces`
- `routing`
- `bgp`
- `prefix-lists`
- `route-maps`
- `bfd`
- `nat`
- `filters`
- `nacm`
- `management`
- `platform`

The MCP tool name is:

- `tnsr.get_domain_view`

Use it after `netconf.open_session`, passing the existing `session_ref` plus a `domain`.

## Normalized TNSR snapshot

Use the snapshot collector when you want a stable JSON artifact to diff against code-managed configuration:

```bash
python scripts/tnsr_snapshot.py \
  --inventory lab-inventory.json \
  --target-ref target://lab/tnsr \
  --hostkey-policy accept-new \
  --output tnsr-snapshot.json
```

The snapshot currently normalizes:

- device identity
- NETCONF capabilities
- module inventory
- interfaces
- host interface DHCP/client state
- NETCONF subsystem management config
- logging remote-server config
- Prometheus exporter host-space filter config
- dataplane tuning and DPDK device assignments
- sysctl settings
- system kernel-module settings
- static routes
- BGP global config and neighbors
- BGP timers and policy-requirement flags
- prefix-lists when the live subtree is exposed cleanly
- route-maps when the live subtree is exposed cleanly
- BFD sessions
- NAT rulesets from `vpf-config`
- VPF filter-rulesets and interface policy bindings

## TNSR domain views

Use the domain-view helper when you want a smaller, agent-friendly summary instead of a full normalized snapshot:

```bash
python scripts/tnsr_show.py \
  --inventory lab-inventory.json \
  --target-ref target://lab/tnsr \
  --hostkey-policy accept-new \
  --domain prefix-lists
```

Supported domains currently include:

- `interfaces`
- `routing`
- `bgp`
- `prefix-lists`
- `route-maps`
- `bfd`
- `nat`
- `filters`
- `nacm`
- `management`
- `platform`

## Snapshot-to-code proposal flow

Use the proposal generator when you want a safe repo-facing candidate change instead of touching the device:

```bash
python scripts/tnsr_propose.py \
  --snapshot tnsr-snapshot.json
```

By default this writes:

- `managed-configs/tnsr/<device>.json`: canonical file path the repo can manage over time
- `proposals/tnsr/<device>.candidate.json`: candidate config rendered from the latest snapshot
- `proposals/tnsr/<device>.md`: markdown summary plus unified diff against the canonical managed file

For repo review workflows, split mode is often easier to consume:

```bash
python scripts/tnsr_propose.py \
  --snapshot tnsr-snapshot.json \
  --layout split
```

That layout breaks TNSR config into domain files such as:

- `management/ssh-server.json`
- `management/host-interfaces.json`
- `management/logging.json`
- `management/prometheus-exporter.json`
- `platform/dataplane.json`
- `platform/sysctl.json`
- `platform/system.json`
- `routing/bgp.json`
- `security/nat-rulesets.json`

This is the intended near-term loop for TNSR:

1. collect a read-only snapshot from the live device
2. generate a proposed repo-side config update
3. review the proposal and decide how your source-of-truth should change
4. let your deployment workflow handle device changes later
