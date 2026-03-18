# Arista cEOS-Lab Guide

This repository recommends `cEOS-lab + containerlab` on a Linux host as the first Arista validation path.

## Baseline release guidance

- Current baseline target: **EOS 4.x (containerlab docs example: `ceos:4.32.0F`)**.
- This line is used as an initial lab baseline because it is explicitly documented for containerlab workflows and supports modern NETCONF access on port `830`.
- Exact minimum patch level is often constrained by your Arista account entitlement; confirm the exact tag available to your account before importing.

## Why cEOS-lab first

- single host, containerized lab with repeatable startup
- direct alignment with this project's read-only MCP probe flow
- small resource profile for developer laptops compared with full hardware
- easy teardown/reset when the fixture-first workflow needs fresh reads

## Files to use

- topology: `labs/arista-ceos/containerlab.yml`
- startup config: `labs/arista-ceos/startup-config.cfg`
- inventory example: `lab-inventory.arista.example.json`

## Image and licensing notes

`arista_ceos` nodes require an Arista image tarball.

1. Register/login at the Arista software download portal.
2. Download a cEOS lab tarball from your licensed line.
3. Import locally:

```bash
docker import cEOS64-lab-4.32.0F.tar.xz ceos:4.32.0F
```

If your entitlement only offers a different patch tag, update both import command and `containerlab.yml` image tag together.

## Resource guidance (baseline)

- CPU: 2-4 vCPUs
- RAM: 6-8 GiB minimum
- Disk: 25-40 GiB free
- Linux host: x86_64 with Docker and containerlab installed

Set `systemd.unified_cgroup_hierarchy=0` for older cEOS variants only if you hit cgroup boot issues.
From `cEOS 4.32.0F` onward, containerlab handles cgroup v1/v2 selection automatically.

## Start the lab

```bash
cd labs/arista-ceos
containerlab deploy -t containerlab.yml
```

Verify node state and discover management IP:

```bash
docker ps --filter "name=clab-arista-ceos-lab"
docker inspect -f '{{ range .NetworkSettings.Networks}}{{ .IPAddress }}{{ end }}' clab-arista-ceos-lab-ceos1
```

## Management and NETCONF verification (port 830)

1. Confirm SSH/NETCONF port availability:

```bash
nc -zv <mgmt-ip> 830
```

2. Confirm NETCONF can start a transport session:

```bash
ssh -p 830 root@<mgmt-ip> -s netconf
```

3. Confirm a NETCONF datastore-read path is reachable via the MCP smoke runner:

```bash
cd <repo-root>
cp lab-inventory.arista.example.json lab-inventory.json
NETCONF_MCP_INVENTORY=lab-inventory.json python -m netconf_mcp.cli
```

For lightweight live verification against the sample target:

```bash
python scripts/netconf_fixture_capture.py \
  --inventory lab-inventory.json \
  --target-ref target://lab/arista \
  --hostkey-policy accept-new \
  --profile custom \
  --output arista-live-capture.json \
  --config-xpath '/interfaces' \
  --oper-xpath '/interfaces-state/interface'
```

The smoke runner is generic and safe for read-only probes; only add vendor-specific xpaths that you can tolerate in read mode.

## End-to-End Workflow

This section documents the complete Arista EOS workflow from lab setup to MCP tool usage.

### Step 1: Set up the inventory

Copy the example inventory and update with your lab details:

```bash
cp lab-inventory.arista.example.json lab-inventory.json
# Edit lab-inventory.json with your cEOS management IP
```

Example inventory entry:

```json
{
  "target_ref": "target://lab/arista",
  "name": "arista-ceos-lab",
  "status": "online",
  "transport_mode": "live-ssh",
  "transport": {"protocol": "ssh", "framing": "base:1.0"},
  "host": "10.0.0.100",
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
    "oc-bgp": "http://openconfig.net/yang/bgp"
  },
  "safety_profile": "read-only"
}
```

### Step 2: Capture fixture data

Use the fixture capture script to collect live data for fixture development:

```bash
python scripts/netconf_fixture_capture.py \
  --inventory lab-inventory.json \
  --target-ref target://lab/arista \
  --hostkey-policy accept-new \
  --profile custom \
  --output arista-live-capture.json \
  --config-xpath '/oc-if:interfaces' \
  --oper-xpath '/oc-if:interfaces-state'
```

### Step 3: Collect a normalized snapshot

Collect a normalized snapshot for source-of-truth workflows:

```bash
python scripts/arista_snapshot.py \
  --inventory lab-inventory.json \
  --target-ref target://lab/arista \
  --hostkey-policy accept-new \
  --output arista-snapshot.json
```

Example output:

```
Wrote normalized snapshot to arista-snapshot.json
Interfaces: 8
LAGs: 2
VLANs: 5
VRFs: 1
Static routes: 3
Warnings: 0
```

### Step 4: Query domain views

Use domain views for compact, agent-friendly queries:

```bash
# Get interfaces summary
python -c "
import json
from pathlib import Path
from netconf_mcp.vendors.arista import get_domain_view

snapshot = json.loads(Path('arista-snapshot.json').read_text())
view = get_domain_view(snapshot, 'interfaces')
print(json.dumps(view, indent=2))
"
```

Example `interfaces` domain view output:

```json
{
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
```

### Step 5: Use MCP tools

Start the MCP server with live inventory:

```bash
NETCONF_MCP_INVENTORY=lab-inventory.json python -m netconf_mcp.cli
```

Available Arista MCP tools:

| Tool | Description |
|------|-------------|
| `arista.get_domain_view` | Query compact domain views (interfaces, vlans, vrfs, lags, bgp, lldp, system, routing, routing-policy, acls, mlag, evpn-vxlan) |

Example MCP tool call:

```
Tool: arista.get_domain_view
Arguments: {
  "session_ref": "session-001",
  "domain": "bgp"
}
```

Example response:

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

## Supported Domains

| Domain | Description | Example Query |
|--------|-------------|---------------|
| `interfaces` | Interface config, descriptions, IP addresses | `get_domain_view(snapshot, "interfaces")` |
| `vlans` | VLAN IDs and names | `get_domain_view(snapshot, "vlans")` |
| `vrfs` | VRF/network instances | `get_domain_view(snapshot, "vrfs")` |
| `lags` | LACP LAG interfaces and members | `get_domain_view(snapshot, "lags")` |
| `bgp` | BGP global config (ASN, router-id) | `get_domain_view(snapshot, "bgp")` |
| `lldp` | LLDP neighbor discovery | `get_domain_view(snapshot, "lldp")` |
| `system` | Hostname, version, platform | `get_domain_view(snapshot, "system")` |
| `routing` | Static routes by VRF | `get_domain_view(snapshot, "routing")` |
| `routing-policy` | Route maps and prefix lists | `get_domain_view(snapshot, "routing-policy")` |
| `acls` | Access control lists (IPv4/IPv6) | `get_domain_view(snapshot, "acls")` |
| `mlag` | Multi-chassis LAG config (arista-proprietary) | `get_domain_view(snapshot, "mlag")` |
| `evpn-vxlan` | EVPN/VXLAN overlay configuration | `get_domain_view(snapshot, "evpn-vxlan")` |

## Validation Commands for New Domains

Test the newly implemented domains with these commands:

```bash
# Collect a snapshot first
python scripts/arista_snapshot.py \
  --inventory lab-inventory.json \
  --target-ref target://lab/arista \
  --hostkey-policy accept-new \
  --output arista-snapshot.json

# Query routing policy domain
python -c "
import json
from pathlib import Path
from netconf_mcp.vendors.arista import get_domain_view
snapshot = json.loads(Path('arista-snapshot.json').read_text())
view = get_domain_view(snapshot, 'routing-policy')
print(json.dumps(view, indent=2))
"

# Query ACLs domain
python -c "
import json
from pathlib import Path
from netconf_mcp.vendors.arista import get_domain_view
snapshot = json.loads(Path('arista-snapshot.json').read_text())
view = get_domain_view(snapshot, 'acls')
print(json.dumps(view, indent=2))
"

# Query MLAG domain
python -c "
import json
from pathlib import Path
from netconf_mcp.vendors.arista import get_domain_view
snapshot = json.loads(Path('arista-snapshot.json').read_text())
view = get_domain_view(snapshot, 'mlag')
print(json.dumps(view, indent=2))
"

# Query EVPN/VXLAN domain
python -c "
import json
from pathlib import Path
from netconf_mcp.vendors.arista import get_domain_view
snapshot = json.loads(Path('arista-snapshot.json').read_text())
view = get_domain_view(snapshot, 'evpn-vxlan')
print(json.dumps(view, indent=2))
"
```

## Troubleshooting

### Namespace configuration missing

If you see XPath errors, ensure the inventory target includes the `namespace_map`:

```
Error: namespace not found for prefix 'oc-if'
```

Fix: Add the required OpenConfig namespace prefixes to your inventory entry.

### NETCONF port not reachable

Verify the cEOS container is running and NETCONF is enabled:

```bash
nc -zv <mgmt-ip> 830
ssh -p 830 admin@<mgmt-ip> -s netconf
```

### Host key verification failed

Use `--hostkey-policy accept-new` for first-time connections:

```bash
python scripts/arista_snapshot.py \
  --inventory lab-inventory.json \
  --hostkey-policy accept-new
```

## Planned next phase

After initial fixture capture and proposal generation, move to hardware validation as a later phase.
The docs intentionally keep hardware validation separate because physical lab access is not yet assumed available.

## Future Work

Hardware validation phase (planned):

- Physical Arista switch testing
- Validation against multiple EOS versions
- Hardware-specific features (transceivers, optics, etc.)
