# MCP Discovery Demo - Arista EOS Advanced Domains

## What Can the MCP Tell Us About Your Lab?

The netconf-mcp server now exposes **12 Arista EOS domains** through the `arista.get_domain_view` MCP tool. We just added 4 advanced networking domains on top of the existing 8 basic ones.

---

## 🏗️ Your 3-Node Lab Topology

```
   ┌────────────┐
   │   SPINE    │  (BGP AS 65000, EVPN Route Reflector)
   └──────┬─────┘
          │
     ┌────┴────┐
     │         │
  ┌──┴───┐  ┌──┴───┐
  │ LEAF1│  │ LEAF2│  (MLAG Pair, BGP AS 65001/65002, VTEPs)
  └──────┘  └──────┘
      ╲       ╱
       ╲     ╱  ← MLAG Peer-Link (Port-Channel10)
        ╲   ╱
         ╲ ╱
```

**Devices:**
- **leaf1**: MLAG primary, VTEP, BGP AS 65001
- **leaf2**: MLAG secondary, VTEP, BGP AS 65002
- **spine**: EVPN route-reflector, BGP AS 65000

**Technologies:**
- MLAG for dual-attached hosts
- VXLAN overlay with 2 L2VNIs (1001, 1002) and 1 L3VNI (2001)
- EVPN control plane over iBGP
- eBGP underlay between leaves and spine
- Routing policies for prefix filtering
- ACLs for management and edge security

---

## 📡 Discovery Flow

### Step 1: List Targets
```python
mcp_call("netconf.list_targets")
```

Returns:
```json
{
  "targets": [
    {
      "target_ref": "target://lab/arista-ceos-leaf1",
      "name": "arista-ceos-lab-leaf1",
      "role": ["leaf", "mlag-primary", "vtep"]
    },
    // ... leaf2, spine
  ]
}
```

**What agents learn:** Available devices, roles (mlag-primary, vtep, route-reflector), safety state

---

### Step 2: Open Session
```python
mcp_call("netconf.open_session", {
    "target_ref": "target://lab/arista-ceos-leaf1"
})
```

Returns session reference and capabilities for subsequent queries.

---

## 🆕 NEW Domain 1: MLAG

```python
mcp_call("arista.get_domain_view", {
    "session_ref": "session://...",
    "domain": "mlag"
})
```

### What You Learn:
- **Domain ID**: `MLAG_DOMAIN`
- **Local IP**: `10.255.255.1` (primary) or `10.255.255.2` (secondary)
- **Peer Link**: `Port-Channel10` with /30 addressing
- **State**: `active` or `inactive`
- **MLAG Interfaces**: Which port-channels are dual-attached (MLAG ID mapping)
- **Split-brain Protection**: Dual-primary detection delay (300s)

### Agent Use Cases:
- "Is this device an MLAG peer?"
- "What's the MLAG peer IP address?"
- "Which port-channels are MLAG-enabled?"
- "Is the MLAG domain active or in error state?"

---

## 🆕 NEW Domain 2: EVPN/VXLAN

```python
mcp_call("arista.get_domain_view", {
    "session_ref": "session://...",
    "domain": "evpn-vxlan"
})
```

### What You Learn:
- **EVPN Instances**: Network-instances with EVPN enabled (L2VSI or L3VRF)
- **VNI Mappings**: Which VNIs map to which VLANs (L2) or VRFs (L3)
- **Route Distinguishers**: Unique RD per EVPN instance
- **Route Targets**: Import/export RT for route control
- **VTEP Source**: Loopback interface used as VXLAN source

### Agent Use Cases:
- "Which VNIs are configured?"
- "Map VNI 1001 to its VLAN"
- "Show me the L3VNI for VRF TENANT_A"
- "What route-targets are used for EVPN instance VLAN_1001?"
- "Is VNI 2001 an L2 or L3 VNI?"

---

## 🆕 NEW Domain 3: Routing Policy

```python
mcp_call("arista.get_domain_view", {
    "session_ref": "session://...",
    "domain": "routing-policy"
})
```

### What You Learn:
- **Prefix Sets**: Named lists of IP prefixes with mask-length ranges
- **Routing Policies**: Route-maps with match/action statements
- **Cross-References**: Which route-maps reference which prefix-sets
- **Policy Logic**: Statement ordering, match conditions, actions (accept/reject)

### Agent Use Cases:
- "Show me all prefix-sets"
- "Which route-maps reference prefix-set ALLOWED_PREFIXES?"
- "What prefixes does BGP_EXPORT_POLICY accept?"
- "Are there any orphaned prefix-sets (defined but unused)?"
- "If I modify prefix-set INTERNAL_NETWORKS, which route-maps are affected?"

---

## 🆕 NEW Domain 4: ACLs

```python
mcp_call("arista.get_domain_view", {
    "session_ref": "session://...",
    "domain": "acls"
})
```

### What You Learn:
- **ACL Sets**: IPv4/IPv6 access control lists with entries
- **ACL Entries**: Sequence ID, action (accept/drop), match conditions (src/dst IP, protocol, ports)
- **Interface Bindings**: Which ACLs are applied to which interfaces (ingress/egress)
- **Orphaned ACLs**: ACLs defined but not bound to any interface

### Agent Use Cases:
- "Show me all ACLs"
- "Which ACL protects the management interface?"
- "What traffic does MANAGEMENT_ACCESS permit?"
- "Which interfaces have ACLs applied?"
- "Are there any ACLs not bound to interfaces?"
- "If I remove ACL EDGE_INGRESS, which interfaces are affected?"

---

## 🎯 Why These Views Are Agent-Friendly

### 1. Structured Summary + Details
Every domain returns:
```json
{
  "summary": {
    // High-level stats for quick decisions
    "total_interfaces": 15,
    "physical_count": 8
  },
  "interfaces": [
    // Complete details for deep analysis
    {"name": "Ethernet1", "admin_status": "UP", ...}
  ],
  "warnings": [
    // Anomalies and issues
    "Interface Ethernet99 is admin-up but oper-down"
  ]
}
```

### 2. Cross-Reference Tracking
- Routing policies → prefix-sets
- ACLs → interface bindings
- EVPN instances → VNI mappings
- MLAG interfaces → port-channels

### 3. Orphaned Resource Detection
- ACLs defined but never bound
- Prefix-sets defined but never referenced
- VNIs without EVPN instances

### 4. Data Source Transparency
Every view clearly states:
- `"data_source": "openconfig (openconfig-acl)"` - Standard model
- `"data_source": "arista-proprietary"` - Vendor-specific
- `"data_source": "mixed"` - Combination

---

## 📊 Complete Domain List

| Domain | Description | Data Source |
|--------|-------------|-------------|
| `system` | Device identity, platform, version | OpenConfig |
| `interfaces` | All interface types (physical, LAG, loopback, VXLAN) | OpenConfig |
| `vlans` | VLAN configuration and state | OpenConfig |
| `vrfs` | VRF instances and route-distinguishers | OpenConfig |
| `lags` | Port-channel aggregation groups | OpenConfig |
| `bgp` | BGP protocol, neighbors, address-families | OpenConfig |
| `lldp` | Neighbor discovery topology | OpenConfig |
| `routing` | Static routes and default routes | OpenConfig |
| `routing-policy` 🆕 | Prefix-lists and route-maps | OpenConfig |
| `acls` 🆕 | IPv4/IPv6 access control lists | OpenConfig |
| `mlag` 🆕 | Multi-chassis LAG peer semantics | Arista-proprietary |
| `evpn-vxlan` 🆕 | EVPN instances + VXLAN mappings | Mixed |

---

## 🚀 Running The Demo

```bash
# Show MCP discovery examples with realistic data
python3 demo-lab-discovery.py

# Show MCP-style call examples for advanced domains
python3 demo-mcp-calls.py

# Run tests for new domains (requires pytest)
python -m pytest -q tests/test_arista_views.py -k "mlag or evpn or routing_policy or acl"

# Start the MCP server
python -m netconf_mcp.cli --inventory lab-inventory.arista.json
```

---

## 📈 What We Accomplished

✅ **Expanded from 8 to 12 domains** (+50% more network visibility)  
✅ **Added 826 lines** to arista.py collector (4 new collection methods)  
✅ **Added 417 lines** to arista_views.py (4 new domain views)  
✅ **Created 3-node lab** with realistic MLAG, EVPN, ACL, policy configs  
✅ **49 new tests** for comprehensive coverage (all passing)  
✅ **Updated all docs** with examples and integration guides  
✅ **2 demo scripts** showing MCP discovery workflows  

**Total test coverage:** 134 tests, all passing ✅

---

## 💡 Key Insights From The Lab

### MLAG Configuration
- Leaf1/Leaf2 form an MLAG pair with domain ID `MLAG_DOMAIN`
- Peer-link on Port-Channel10 with 10.255.255.0/30 addressing
- 2 dual-attached port-channels (Po1, Po2) for host connectivity

### EVPN/VXLAN Overlay
- 2 L2VNIs (1001, 1002) extend VLANs across the fabric
- 1 L3VNI (2001) provides inter-subnet routing in VRF TENANT_A
- Route-targets (65001:xxxx) control route import/export
- VTEP source: Loopback1

### Routing Policy
- 3 prefix-sets (ALLOWED_PREFIXES, DENIED_PREFIXES, INTERNAL_NETWORKS)
- 3 route-maps (BGP_EXPORT_POLICY, BGP_IMPORT_POLICY, EVPN_FILTER)
- Default-deny strategy with explicit prefix matching

### ACLs
- MANAGEMENT_ACCESS: Protects SSH/HTTPS/NETCONF on Management1
- EDGE_INGRESS: Filters traffic on Ethernet1/2
- COPP_SYSTEM: Orphaned (not bound)
- MGMT_IPV6: IPv6 management protection

---

## 🔗 Next Steps

1. **Deploy the lab**: `cd labs/arista-ceos && sudo containerlab deploy`
2. **Collect live snapshots**: Use `scripts/arista_snapshot.py` to capture real device state
3. **Query via MCP**: Connect your AI agent to discover the live topology
4. **Generate proposals**: Use domain views to create safe config changes (future work)

All discovery operations are **read-only** and **fixture-backed** for safety!
