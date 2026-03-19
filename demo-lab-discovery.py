#!/usr/bin/env python3
"""
MCP Discovery Demo - Shows what agents learn about Arista EOS devices.

Demonstrates the 12 domains exposed by the 'arista.get_domain_view' MCP tool,
with focus on the 4 NEW advanced domains we just added.
"""

from __future__ import annotations

import json


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def show_mcp_call(tool: str, args: dict | None = None) -> None:
    """Show an MCP tool invocation."""
    print(f"🔧 MCP Tool Call:")
    if args:
        args_json = json.dumps(args, indent=2)
        print(f"   {tool}({args_json})")
    else:
        print(f"   {tool}()")
    print()


def main() -> None:
    print_section("MCP ARISTA EOS DISCOVERY - 3-Node Lab")
    
    print("""
This demonstrates what an AI agent can discover about an Arista EOS network
through the netconf-mcp server's 'arista.get_domain_view' tool.

Lab Topology:
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
    """)
    
    # Step 1: List targets
    print_section("STEP 1: Discover Available Devices")
    show_mcp_call("netconf.list_targets")
    
    print("📊 MCP Response:")
    response = {
        "targets": [
            {
                "target_ref": "target://lab/arista-ceos-leaf1",
                "name": "arista-ceos-lab-leaf1",
                "site": "home-lab",
                "role": ["leaf", "mlag-primary", "vtep"],
                "safety_state": "ready"
            },
            {
                "target_ref": "target://lab/arista-ceos-leaf2",
                "name": "arista-ceos-lab-leaf2",
                "site": "home-lab",
                "role": ["leaf", "mlag-secondary", "vtep"],
                "safety_state": "ready"
            },
            {
                "target_ref": "target://lab/arista-ceos-spine",
                "name": "arista-ceos-lab-spine",
                "site": "home-lab",
                "role": ["spine", "route-reflector"],
                "safety_state": "ready"
            }
        ]
    }
    print(json.dumps(response, indent=2))
    
    # Step 2: Open session
    print_section("STEP 2: Open Session to LEAF1")
    show_mcp_call("netconf.open_session", {
        "target_ref": "target://lab/arista-ceos-leaf1",
        "hostkey_policy": "accept-new"
    })
    
    print("📊 MCP Response:")
    response = {
        "status": "success",
        "session_ref": "session://arista-ceos-lab-leaf1/a1b2c3d4",
        "capabilities": [
            "urn:ietf:params:netconf:base:1.0",
            "urn:ietf:params:netconf:capability:writable-running:1.0",
            "http://openconfig.net/yang/interfaces?module=openconfig-interfaces",
            "http://openconfig.net/yang/bgp?module=openconfig-bgp",
            # ... more capabilities
        ],
        "transport": "ssh",
        "mode": "fixture"
    }
    print(json.dumps(response, indent=2))
    
    session_ref = "session://arista-ceos-lab-leaf1/a1b2c3d4"
    
    # Now demonstrate the 4 NEW advanced domains
    
    # Domain 1: MLAG
    print_section("NEW DOMAIN 1: MLAG (Multi-Chassis Link Aggregation)")
    show_mcp_call("arista.get_domain_view", {
        "session_ref": session_ref,
        "domain": "mlag"
    })
    
    print("📊 MCP Response:")
    response = {
        "status": "success",
        "data": {
            "domain": "mlag",
            "data_source": "arista-proprietary (no OpenConfig equivalent for MLAG peer semantics)",
            "summary": {
                "configured": True,
                "domain_id": "MLAG_DOMAIN",
                "local_ip": "10.255.255.1",
                "peer_address": "10.255.255.2",
                "peer_link": "Port-Channel10",
                "state": "active",
                "total_mlag_interfaces": 2
            },
            "global_config": {
                "domain_id": "MLAG_DOMAIN",
                "local_interface_ip": "10.255.255.1/30",
                "peer_address": "10.255.255.2",
                "peer_link": "Port-Channel10",
                "dual_primary_detection_delay": 300,
                "reload_delay_non_mlag": 330,
                "reload_delay_mlag": 300
            },
            "mlag_interfaces": [
                {
                    "name": "Port-Channel1",
                    "mlag_id": "1",
                    "state": "active-full"
                },
                {
                    "name": "Port-Channel2",
                    "mlag_id": "2",
                    "state": "active-full"
                }
            ],
            "warnings": []
        }
    }
    print(json.dumps(response, indent=2))
    
    print("\n💡 Agent Insights:")
    print("   • LEAF1 is the MLAG primary (local IP .1, peer IP .2)")
    print("   • MLAG domain active with 2 dual-attached port-channels")
    print("   • Peer-link uses Port-Channel10 with /30 addressing")
    print("   • Split-brain protection: 300s dual-primary detection delay")
    
    # Domain 2: EVPN/VXLAN
    print_section("NEW DOMAIN 2: EVPN/VXLAN (Overlay Networking)")
    show_mcp_call("arista.get_domain_view", {
        "session_ref": session_ref,
        "domain": "evpn-vxlan"
    })
    
    print("📊 MCP Response:")
    response = {
        "status": "success",
        "data": {
            "domain": "evpn-vxlan",
            "data_source": "mixed (OpenConfig control-plane + Arista-proprietary VNI mappings)",
            "summary": {
                "total_evpn_instances": 3,
                "total_vxlan_mappings": 3,
                "l2_vni_count": 2,
                "l3_vni_count": 1,
                "vxlan_source_interface": "Loopback1"
            },
            "evpn_instances": [
                {
                    "name": "VLAN_1001",
                    "type": "L2VSI",
                    "evpn_enabled": True,
                    "evi": 1001,
                    "route_distinguisher": "10.0.0.1:1001",
                    "import_route_targets": ["65001:1001"],
                    "export_route_targets": ["65001:1001"]
                },
                {
                    "name": "VLAN_1002",
                    "type": "L2VSI",
                    "evpn_enabled": True,
                    "evi": 1002,
                    "route_distinguisher": "10.0.0.1:1002",
                    "import_route_targets": ["65001:1002"],
                    "export_route_targets": ["65001:1002"]
                },
                {
                    "name": "TENANT_A",
                    "type": "L3VRF",
                    "evpn_enabled": True,
                    "evi": 2001,
                    "route_distinguisher": "10.0.0.1:2001",
                    "import_route_targets": ["65001:2001"],
                    "export_route_targets": ["65001:2001"]
                }
            ],
            "vxlan_mappings": [
                {"vni": 1001, "vlan_id": "1001", "vni_type": "l2vni"},
                {"vni": 1002, "vlan_id": "1002", "vni_type": "l2vni"},
                {"vni": 2001, "vrf_name": "TENANT_A", "vni_type": "l3vni"}
            ],
            "warnings": []
        }
    }
    print(json.dumps(response, indent=2))
    
    print("\n💡 Agent Insights:")
    print("   • 2 L2 VNIs (1001, 1002) for VLAN extension across MLAG pair")
    print("   • 1 L3 VNI (2001) for inter-subnet routing in VRF TENANT_A")
    print("   • VTEP source: Loopback1 (unique per leaf)")
    print("   • Route-targets enable selective route import/export")
    
    # Domain 3: Routing Policy
    print_section("NEW DOMAIN 3: Routing Policy (Prefix-Lists & Route-Maps)")
    show_mcp_call("arista.get_domain_view", {
        "session_ref": session_ref,
        "domain": "routing-policy"
    })
    
    print("📊 MCP Response:")
    response = {
        "status": "success",
        "data": {
            "domain": "routing-policy",
            "data_source": "openconfig (openconfig-routing-policy, openconfig-defined-sets)",
            "summary": {
                "total_prefix_sets": 3,
                "total_routing_policies": 3,
                "total_policy_statements": 8
            },
            "prefix_sets": [
                {
                    "name": "ALLOWED_PREFIXES",
                    "mode": "IPV4",
                    "prefix_count": 3,
                    "prefixes": [
                        {"prefix": "10.0.0.0/8", "masklength_range": "exact"},
                        {"prefix": "172.16.0.0/12", "masklength_range": "exact"},
                        {"prefix": "192.168.0.0/16", "masklength_range": "exact"}
                    ]
                },
                {
                    "name": "DENIED_PREFIXES",
                    "mode": "IPV4",
                    "prefix_count": 2,
                    "prefixes": [
                        {"prefix": "0.0.0.0/0", "masklength_range": "exact"},
                        {"prefix": "169.254.0.0/16", "masklength_range": "exact"}
                    ]
                },
                {
                    "name": "INTERNAL_NETWORKS",
                    "mode": "IPV4",
                    "prefix_count": 1,
                    "prefixes": [
                        {"prefix": "10.0.0.0/8", "masklength_range": "16..24"}
                    ]
                }
            ],
            "routing_policies": [
                {
                    "name": "BGP_EXPORT_POLICY",
                    "total_statements": 3,
                    "references_prefix_sets": ["ALLOWED_PREFIXES", "DENIED_PREFIXES"],
                    "statements": [
                        {
                            "name": "10",
                            "match_prefix_sets": ["DENIED_PREFIXES"],
                            "action": "REJECT_ROUTE"
                        },
                        {
                            "name": "20",
                            "match_prefix_sets": ["ALLOWED_PREFIXES"],
                            "action": "ACCEPT_ROUTE"
                        },
                        {
                            "name": "30",
                            "match_prefix_sets": [],
                            "action": "REJECT_ROUTE"
                        }
                    ]
                },
                {
                    "name": "BGP_IMPORT_POLICY",
                    "total_statements": 2,
                    "references_prefix_sets": ["INTERNAL_NETWORKS"],
                    "statements": [
                        {
                            "name": "10",
                            "match_prefix_sets": ["INTERNAL_NETWORKS"],
                            "action": "ACCEPT_ROUTE"
                        },
                        {
                            "name": "20",
                            "match_prefix_sets": [],
                            "action": "REJECT_ROUTE"
                        }
                    ]
                },
                {
                    "name": "EVPN_FILTER",
                    "total_statements": 1,
                    "references_prefix_sets": [],
                    "statements": [
                        {
                            "name": "10",
                            "match_prefix_sets": [],
                            "action": "ACCEPT_ROUTE"
                        }
                    ]
                }
            ],
            "warnings": []
        }
    }
    print(json.dumps(response, indent=2))
    
    print("\n💡 Agent Insights:")
    print("   • 3 prefix-sets define allowed/denied/internal networks")
    print("   • 3 route-maps control BGP export/import and EVPN filtering")
    print("   • BGP_EXPORT_POLICY references 2 prefix-sets (cross-reference tracked)")
    print("   • Default-deny strategy: explicit prefix-set matches required")
    
    # Domain 4: ACLs
    print_section("NEW DOMAIN 4: Access Control Lists")
    show_mcp_call("arista.get_domain_view", {
        "session_ref": session_ref,
        "domain": "acls"
    })
    
    print("📊 MCP Response:")
    response = {
        "status": "success",
        "data": {
            "domain": "acls",
            "data_source": "openconfig (openconfig-acl)",
            "summary": {
                "total_acl_sets": 4,
                "ipv4_acl_count": 3,
                "ipv6_acl_count": 1,
                "total_acl_entries": 15,
                "total_acl_bindings": 3
            },
            "acl_sets": [
                {
                    "name": "MANAGEMENT_ACCESS",
                    "type": "ACL_IPV4",
                    "description": "Restrict management plane access",
                    "entry_count": 5,
                    "bound_to_interfaces": ["Management1"],
                    "entries": [
                        {
                            "sequence_id": 10,
                            "action": "ACCEPT",
                            "source_address": "10.0.0.0/8",
                            "protocol": "IP_TCP",
                            "destination_port": "22"
                        },
                        {
                            "sequence_id": 20,
                            "action": "ACCEPT",
                            "source_address": "10.0.0.0/8",
                            "protocol": "IP_TCP",
                            "destination_port": "443"
                        },
                        {
                            "sequence_id": 30,
                            "action": "ACCEPT",
                            "source_address": "10.0.0.0/8",
                            "protocol": "IP_TCP",
                            "destination_port": "830"
                        },
                        {
                            "sequence_id": 40,
                            "action": "DROP",
                            "source_address": "0.0.0.0/0"
                        }
                    ]
                },
                {
                    "name": "COPP_SYSTEM",
                    "type": "ACL_IPV4",
                    "description": "Control plane protection",
                    "entry_count": 6,
                    "bound_to_interfaces": [],
                    "entries": []
                },
                {
                    "name": "EDGE_INGRESS",
                    "type": "ACL_IPV4",
                    "description": "Edge interface ingress filtering",
                    "entry_count": 3,
                    "bound_to_interfaces": ["Ethernet1", "Ethernet2"],
                    "entries": []
                },
                {
                    "name": "MGMT_IPV6",
                    "type": "ACL_IPV6",
                    "description": "IPv6 management access",
                    "entry_count": 1,
                    "bound_to_interfaces": ["Management1"],
                    "entries": []
                }
            ],
            "interface_bindings": [
                {
                    "interface_name": "Management1",
                    "ingress_acl": "MANAGEMENT_ACCESS",
                    "egress_acl": None
                },
                {
                    "interface_name": "Ethernet1",
                    "ingress_acl": "EDGE_INGRESS",
                    "egress_acl": None
                },
                {
                    "interface_name": "Ethernet2",
                    "ingress_acl": "EDGE_INGRESS",
                    "egress_acl": None
                }
            ],
            "warnings": ["ACL 'COPP_SYSTEM' is not bound to any interfaces (orphaned)"]
        }
    }
    print(json.dumps(response, indent=2))
    
    print("\n💡 Agent Insights:")
    print("   • 4 ACLs: 3 IPv4, 1 IPv6")
    print("   • MANAGEMENT_ACCESS protects SSH/HTTPS/NETCONF on Management1")
    print("   • EDGE_INGRESS filters traffic on Ethernet1/2")
    print("   • COPP_SYSTEM is orphaned (not bound to any interface)")
    print("   • MCP tracks interface bindings for impact analysis")
    
    # Routing Policy Example
    print_section("NEW DOMAIN 3: Routing Policy Details")
    
    print("💡 Cross-Reference Tracking:")
    print("""
The routing-policy domain tracks which route-maps reference which prefix-sets:

Route-Map: BGP_EXPORT_POLICY
  └─ Statement 10: DENY if prefix matches 'DENIED_PREFIXES'
       └─ DENIED_PREFIXES contains:
            • 0.0.0.0/0 (default route)
            • 169.254.0.0/16 (link-local)
  
  └─ Statement 20: ACCEPT if prefix matches 'ALLOWED_PREFIXES'
       └─ ALLOWED_PREFIXES contains:
            • 10.0.0.0/8
            • 172.16.0.0/12
            • 192.168.0.0/16
  
  └─ Statement 30: DENY all other prefixes (default-deny)

This allows agents to:
  • Understand which prefixes are affected by policy changes
  • Detect orphaned prefix-sets (defined but never referenced)
  • Validate policy logic (deny before accept, catch-all statements)
    """)
    
    # EVPN/VXLAN Details
    print_section("NEW DOMAIN 2: EVPN/VXLAN Architecture")
    
    print("💡 VNI Classification and Overlay Design:")
    print("""
L2 VNIs (Layer-2 VXLAN Network Identifiers):
  • VNI 1001 → VLAN 1001 (stretched across MLAG pair)
  • VNI 1002 → VLAN 1002 (stretched across MLAG pair)
  
  Purpose: Extend VLANs across the fabric (L2 adjacency)
  EVPN Route Type: Type-2 (MAC/IP Advertisement)

L3 VNI (Layer-3 VXLAN Network Identifier):
  • VNI 2001 → VRF TENANT_A (symmetric IRB routing)
  
  Purpose: Inter-subnet routing within the tenant VRF
  EVPN Route Type: Type-5 (IP Prefix Route)

Network Instance Hierarchy:
  TENANT_A (VRF)
    ├─ VLAN_1001 (L2VSI, subnet 10.1.1.0/24)
    ├─ VLAN_1002 (L2VSI, subnet 10.1.2.0/24)
    └─ L3VNI 2001 (symmetric routing between subnets)

This allows agents to:
  • Distinguish L2 extension from L3 routing VNIs
  • Map VLANs to VNIs to VRFs to understand the forwarding plane
  • Validate route-target consistency across MLAG peers
    """)
    
    print_section("ALL 12 AVAILABLE DOMAINS")
    
    domains = [
        ("BASIC", [
            ("system", "Device identity, platform, software version"),
            ("interfaces", "Physical, Port-Channel, Loopback, VXLAN interfaces"),
            ("vlans", "VLAN configuration and state"),
            ("vrfs", "VRF instances and route-distinguishers"),
            ("lags", "Link aggregation groups"),
            ("bgp", "BGP protocol, neighbors, address-families"),
            ("lldp", "Neighbor discovery topology"),
            ("routing", "Static routes and default routes"),
        ]),
        ("ADVANCED 🆕", [
            ("routing-policy", "Prefix-lists and route-maps with cross-references"),
            ("acls", "IPv4/IPv6 ACLs with interface bindings"),
            ("mlag", "Multi-chassis LAG with peer state"),
            ("evpn-vxlan", "EVPN instances and VXLAN VNI mappings"),
        ])
    ]
    
    for category, domain_list in domains:
        print(f"\n{category}:")
        for domain, description in domain_list:
            print(f"   • {domain:20s} - {description}")
    
    print_section("WHAT MAKES THESE DOMAINS USEFUL FOR AGENTS?")
    
    print("""
🎯 Compact, Agent-Friendly Views:
   • Summary section: Quick stats for decision-making
   • Details section: Complete data for deep analysis
   • Warnings section: Anomalies, orphaned resources, conflicts
   • Cross-references: Track relationships between resources

🔒 Safety Features:
   • Read-only operations (no accidental changes)
   • Fixture-backed testing (isolated from production)
   • Guarded write proposals (planning, not execution)
   • Data source transparency (OpenConfig vs vendor-specific)

📊 Use Cases:
   • Network discovery: "What VLANs are configured on leaf1?"
   • Topology mapping: "Show me the MLAG peer relationship"
   • Overlay validation: "Which VNIs map to which VLANs?"
   • Policy analysis: "Which route-maps reference ALLOWED_PREFIXES?"
   • Security audit: "Which ACLs are not bound to any interface?"
   • Change impact: "If I modify this prefix-set, which route-maps are affected?"

🚀 Agent Workflow:
   1. List targets → discover devices and roles
   2. Open session → establish NETCONF connection
   3. Query domains → get structured, normalized views
   4. Analyze data → understand network state and relationships
   5. Generate proposals → create safe, validated config changes (future work)
    """)
    
    print_section("TRY IT YOURSELF")
    
    print("""
# Using the MCP CLI (after installation):
python -m netconf_mcp.cli --inventory lab-inventory.arista.json

# Then in your MCP client:
mcp_call("netconf.list_targets")
mcp_call("netconf.open_session", {"target_ref": "target://lab/arista-ceos-leaf1"})
mcp_call("arista.get_domain_view", {"session_ref": "<session-ref>", "domain": "mlag"})
mcp_call("arista.get_domain_view", {"session_ref": "<session-ref>", "domain": "evpn-vxlan"})
mcp_call("arista.get_domain_view", {"session_ref": "<session-ref>", "domain": "routing-policy"})
mcp_call("arista.get_domain_view", {"session_ref": "<session-ref>", "domain": "acls"})

# Or use the test suite to see all domains in action:
python -m pytest -q tests/test_arista_views.py -k "mlag or evpn or routing_policy or acl"
    """)


if __name__ == "__main__":
    main()
