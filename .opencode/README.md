# Using netconf-mcp with OpenCode

This directory contains OpenCode configuration for the netconf-mcp server.

## Quick Start

1. **Install the MCP server**:
   ```bash
   pip install -e '.[dev]'
   ```

2. **The MCP server is automatically configured** in `.opencode/opencode.json`

3. **Start OpenCode** - the netconf MCP server will be available automatically

## What Tools Are Available?

The netconf-mcp server exposes these tools to OpenCode agents:

### Device Discovery
- `netconf.list_targets` - List available network devices

### Session Management  
- `netconf.open_session` - Open a NETCONF session to a device

### Arista EOS Domains (12 total)
Use `arista.get_domain_view` with these domains:

**Basic:**
- `system` - Device identity, platform, version
- `interfaces` - All interface types
- `vlans` - VLAN configuration
- `vrfs` - VRF instances
- `lags` - Port-channel aggregation
- `bgp` - BGP protocol and neighbors
- `lldp` - Neighbor discovery
- `routing` - Static routes

**Advanced:**
- `routing-policy` - Prefix-lists and route-maps 🆕
- `acls` - IPv4/IPv6 access control lists 🆕
- `mlag` - Multi-chassis LAG 🆕
- `evpn-vxlan` - EVPN/VXLAN overlay 🆕

### TNSR Domains (9 total)
Use `tnsr.get_domain_view` with these domains:

- `bgp`, `prefix-lists`, `route-maps`, `nat`, `dataplane-filters`, `nacm`, `management`, `platform`

## Example Usage

Ask OpenCode:

> "List the available network devices in the lab"

OpenCode will call:
```python
mcp_call("netconf.list_targets")
```

> "Show me the MLAG configuration on leaf1"

OpenCode will:
1. Call `netconf.open_session(target_ref="target://lab/arista-ceos-leaf1")`
2. Call `arista.get_domain_view(session_ref=..., domain="mlag")`

> "Which VNIs are configured on leaf1?"

OpenCode will query the `evpn-vxlan` domain.

> "Are there any orphaned ACLs on leaf1?"

OpenCode will query the `acls` domain and look for ACLs with no interface bindings.

## Lab Topology

The `lab-inventory.arista.json` defines a 3-node Arista lab:

```
   ┌────────────┐
   │   SPINE    │  (BGP Route Reflector)
   └──────┬─────┘
          │
     ┌────┴────┐
     │         │
  ┌──┴───┐  ┌──┴───┐
  │ LEAF1│  │ LEAF2│  (MLAG Pair)
  └──────┘  └──────┘
      ╲       ╱
       ╲     ╱  (MLAG Peer-Link)
```

**Technologies:**
- MLAG for dual-attached hosts
- VXLAN with L2VNI + L3VNI
- EVPN control plane
- Routing policies
- ACLs

## Safety Features

✅ **Read-only operations** - No writes to devices  
✅ **Fixture-backed** - Uses test snapshots, not live devices  
✅ **Guarded proposals** - Config generation without execution  

## Configuration Details

The MCP server is configured in `.opencode/opencode.json`:

```json
{
  "mcpServers": {
    "netconf": {
      "command": "python",
      "args": ["-m", "netconf_mcp.cli", "--inventory", "lab-inventory.arista.json"],
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONPATH": "${workspaceFolder}/src",
        "NETCONF_MCP_FIXTURE_ROOT": "${workspaceFolder}/tests/fixtures"
      }
    }
  }
}
```

### Environment Variables

- `PYTHONPATH` - Points to `src/` for the package
- `NETCONF_MCP_FIXTURE_ROOT` - Points to test fixtures directory

### Inventory Path

The `--inventory lab-inventory.arista.json` argument points to the 3-node lab topology.

## Testing the MCP Server

Run the demo scripts to see what OpenCode agents will see:

```bash
# Show MCP discovery workflow
python3 demo-lab-discovery.py

# Show MCP tool call examples
python3 demo-mcp-calls.py

# See the summary
cat DISCOVERY_DEMO_SUMMARY.md
```

## Troubleshooting

### MCP server won't start

Check that dependencies are installed:
```bash
pip install -e '.[dev]'
```

### "Module not found" errors

Ensure `PYTHONPATH` includes `src/`:
```bash
export PYTHONPATH=/Users/rdw/src/netconf-mcp/src
python -m netconf_mcp.cli --manifest-only
```

### Test the server manually

```bash
python -m netconf_mcp.cli --inventory lab-inventory.arista.json --manifest-only
```

Should print:
```
NETCONF MCP server manifest:
tools: ['netconf.list_targets', 'netconf.open_session', 'arista.get_domain_view', ...]
resources: [...]
prompts: [...]
```

## Learn More

- `README.md` - Main project documentation
- `DEMO-ARISTA.md` - Complete Arista domain examples
- `docs/integration-guide.md` - MCP integration guide
- `docs/arista-lab.md` - Lab topology details
