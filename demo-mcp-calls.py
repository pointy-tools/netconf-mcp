#!/usr/bin/env python3
"""
Demo script showing MCP-style calls to Arista domain views.
Uses fixture data to simulate realistic lab responses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).parent
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from netconf_mcp.vendors.arista import get_domain_view, AristaCollector


class SimulatedMCPClient:
    """Simulates MCP tool calls with realistic lab data"""
    
    def __init__(self):
        # Create collector with fake client that returns realistic lab data
        self.collector = AristaCollector(client=LabDataClient())
    
    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Simulate MCP tool call"""
        if tool_name != "arista.get_domain_view":
            return {"error": f"Unknown tool: {tool_name}"}
        
        target_ref = arguments.get("target_ref", "target://lab/leaf1")
        domain = arguments.get("domain")
        
        if not domain:
            return {"error": "Missing required parameter: domain"}
        
        # Collect snapshot
        target = {
            "target_ref": target_ref,
            "name": target_ref.split("/")[-1],
            "facts": {"vendor": "arista", "os": "eos"},
        }
        
        try:
            snapshot = self.collector.collect_snapshot(target)
            snapshot_dict = snapshot.to_dict()
            
            # Get domain view
            view = get_domain_view(snapshot_dict, domain)
            
            # Return MCP-style response
            return {
                "status": "success",
                "policy_decision": "allowed",
                "data": view
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }


class LabDataClient:
    """Fake client returning realistic 3-node MLAG/EVPN lab data"""
    
    def __init__(self):
        self.session_data = {
            "server_capabilities": [
                "urn:ietf:params:netconf:base:1.1",
                "http://openconfig.net/yang/interfaces?module=openconfig-interfaces",
                "http://openconfig.net/yang/routing-policy?module=openconfig-routing-policy",
                "http://openconfig.net/yang/acl?module=openconfig-acl",
                "http://openconfig.net/yang/evpn?module=openconfig-evpn",
            ]
        }
    
    def open_session(self, target, *, hostkey_policy="strict", framing="auto", connect_timeout_ms=None):
        return self.session_data
    
    def get_yang_library(self, target, session):
        return {
            "module_set": [
                {"module": "openconfig-interfaces", "revision": "2024-12-05"},
                {"module": "openconfig-routing-policy", "revision": "2024-11-10"},
                {"module": "openconfig-acl", "revision": "2024-10-15"},
            ],
        }
    
    def datastore_get(self, target, session, *, datastore="running", xpath=None):
        # Prefix-sets
        if xpath and "oc-def-sets:prefix-sets" in xpath:
            return {
                "value": {
                    "prefix-set": [
                        {
                            "name": "PL-LOOPBACKS",
                            "config": {"name": "PL-LOOPBACKS"},
                            "prefixes": {
                                "prefix": [
                                    {
                                        "ip-prefix": "10.0.0.0/24",
                                        "masklength-range": "24..32",
                                        "config": {"ip-prefix": "10.0.0.0/24", "masklength-range": "24..32"}
                                    }
                                ]
                            }
                        },
                        {
                            "name": "PL-CONNECTED",
                            "config": {"name": "PL-CONNECTED"},
                            "prefixes": {
                                "prefix": [
                                    {
                                        "ip-prefix": "172.16.0.0/16",
                                        "masklength-range": "16..32",
                                        "config": {"ip-prefix": "172.16.0.0/16", "masklength-range": "16..32"}
                                    }
                                ]
                            }
                        },
                        {
                            "name": "PL-DEFAULT",
                            "config": {"name": "PL-DEFAULT"},
                            "prefixes": {
                                "prefix": [
                                    {
                                        "ip-prefix": "0.0.0.0/0",
                                        "masklength-range": "exact",
                                        "config": {"ip-prefix": "0.0.0.0/0", "masklength-range": "exact"}
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        
        # Routing policies
        if xpath and "oc-rpol:policy-definitions" in xpath:
            return {
                "value": {
                    "policy-definition": [
                        {
                            "name": "RM-BGP-OUT",
                            "config": {"name": "RM-BGP-OUT"},
                            "statements": {
                                "statement": [
                                    {
                                        "name": "10",
                                        "config": {"name": "10"},
                                        "conditions": {
                                            "match-prefix-set": {
                                                "config": {"prefix-set": "PL-LOOPBACKS"}
                                            }
                                        },
                                        "actions": {
                                            "config": {"policy-result": "ACCEPT_ROUTE"},
                                            "bgp-actions": {
                                                "set-community": {
                                                    "config": {"method": "INLINE"},
                                                    "inline": {
                                                        "communities": [{"community": "65001:100"}]
                                                    }
                                                }
                                            }
                                        }
                                    },
                                    {
                                        "name": "20",
                                        "config": {"name": "20"},
                                        "conditions": {
                                            "match-prefix-set": {
                                                "config": {"prefix-set": "PL-CONNECTED"}
                                            }
                                        },
                                        "actions": {
                                            "config": {"policy-result": "ACCEPT_ROUTE"}
                                        }
                                    }
                                ]
                            }
                        },
                        {
                            "name": "RM-EVPN-IMPORT",
                            "config": {"name": "RM-EVPN-IMPORT"},
                            "statements": {
                                "statement": [
                                    {
                                        "name": "10",
                                        "config": {"name": "10"},
                                        "actions": {
                                            "config": {"policy-result": "ACCEPT_ROUTE"}
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        
        # ACL sets
        if xpath and "oc-acl:acl-sets" in xpath:
            return {
                "value": {
                    "acl-set": [
                        {
                            "name": "ACL-BLOCK-ADMIN",
                            "type": "ACL_IPV4",
                            "config": {"name": "ACL-BLOCK-ADMIN", "type": "ACL_IPV4"},
                            "acl-entries": {
                                "acl-entry": [
                                    {
                                        "sequence-id": "10",
                                        "config": {"sequence-id": "10"},
                                        "ipv4": {
                                            "config": {"source-address": "192.168.1.0/24"}
                                        },
                                        "actions": {
                                            "config": {"forwarding-action": "DROP"}
                                        }
                                    },
                                    {
                                        "sequence-id": "20",
                                        "config": {"sequence-id": "20"},
                                        "ipv4": {
                                            "config": {"source-address": "0.0.0.0/0"}
                                        },
                                        "actions": {
                                            "config": {"forwarding-action": "ACCEPT"}
                                        }
                                    }
                                ]
                            }
                        },
                        {
                            "name": "ACL-ALLOW-WEB",
                            "type": "ACL_IPV4",
                            "config": {"name": "ACL-ALLOW-WEB", "type": "ACL_IPV4"},
                            "acl-entries": {
                                "acl-entry": [
                                    {
                                        "sequence-id": "10",
                                        "config": {"sequence-id": "10", "description": "Allow HTTP"},
                                        "ipv4": {
                                            "config": {"protocol": "6"}
                                        },
                                        "transport": {
                                            "config": {"destination-port": "80"}
                                        },
                                        "actions": {
                                            "config": {"forwarding-action": "ACCEPT"}
                                        }
                                    },
                                    {
                                        "sequence-id": "20",
                                        "config": {"sequence-id": "20", "description": "Allow HTTPS"},
                                        "ipv4": {
                                            "config": {"protocol": "6"}
                                        },
                                        "transport": {
                                            "config": {"destination-port": "443"}
                                        },
                                        "actions": {
                                            "config": {"forwarding-action": "ACCEPT"}
                                        }
                                    },
                                    {
                                        "sequence-id": "30",
                                        "config": {"sequence-id": "30"},
                                        "actions": {
                                            "config": {"forwarding-action": "DROP"}
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        
        # ACL interface bindings
        if xpath and "oc-acl:interfaces" in xpath:
            return {
                "value": {
                    "interface": [
                        {
                            "id": "Ethernet1",
                            "ingress-acl-sets": {
                                "ingress-acl-set": [
                                    {
                                        "set-name": "ACL-ALLOW-WEB",
                                        "type": "ACL_IPV4",
                                        "config": {"set-name": "ACL-ALLOW-WEB", "type": "ACL_IPV4"}
                                    }
                                ]
                            }
                        },
                        {
                            "id": "Management1",
                            "ingress-acl-sets": {
                                "ingress-acl-set": [
                                    {
                                        "set-name": "ACL-BLOCK-ADMIN",
                                        "type": "ACL_IPV4",
                                        "config": {"set-name": "ACL-BLOCK-ADMIN", "type": "ACL_IPV4"}
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        
        # MLAG global config
        if xpath and "oc-mlag:mlag" in xpath:
            return {
                "value": {
                    "config": {
                        "domain-id": "MLAG-DOMAIN",
                        "local-interface": "Vlan100",
                        "peer-address": "192.168.100.2",
                        "peer-link": "Port-Channel10"
                    },
                    "state": {
                        "domain-id": "MLAG-DOMAIN",
                        "status": "active",
                        "peer-link-status": "up"
                    }
                }
            }
        
        # MLAG interfaces
        if xpath and "mlag-id" in xpath:
            return {
                "value": [
                    {
                        "name": "Port-Channel20",
                        "mlag": {
                            "config": {"mlag-id": "20"},
                            "state": {"mlag-id": "20", "status": "active"}
                        }
                    },
                    {
                        "name": "Port-Channel30",
                        "mlag": {
                            "config": {"mlag-id": "30"},
                            "state": {"mlag-id": "30", "status": "active"}
                        }
                    }
                ]
            }
        
        # EVPN instances
        if xpath and "oc-evpn:evpn" in xpath:
            return {
                "value": [
                    {
                        "name": "VLAN10",
                        "config": {"name": "VLAN10", "type": "L2VSI"},
                        "evpn": {
                            "config": {
                                "route-distinguisher": "65001:1001"
                            },
                            "route-targets": {
                                "route-target": [
                                    {
                                        "type": "IMPORT",
                                        "config": {"route-target": "65001:1001"}
                                    },
                                    {
                                        "type": "EXPORT",
                                        "config": {"route-target": "65001:1001"}
                                    }
                                ]
                            }
                        },
                        "vlans": {
                            "vlan": [
                                {"vlan-id": "10", "config": {"vni": "1001"}}
                            ]
                        }
                    },
                    {
                        "name": "VLAN20",
                        "config": {"name": "VLAN20", "type": "L2VSI"},
                        "evpn": {
                            "config": {
                                "route-distinguisher": "65001:1002"
                            },
                            "route-targets": {
                                "route-target": [
                                    {
                                        "type": "IMPORT",
                                        "config": {"route-target": "65001:1002"}
                                    },
                                    {
                                        "type": "EXPORT",
                                        "config": {"route-target": "65001:1002"}
                                    }
                                ]
                            }
                        },
                        "vlans": {
                            "vlan": [
                                {"vlan-id": "20", "config": {"vni": "1002"}}
                            ]
                        }
                    },
                    {
                        "name": "prod",
                        "config": {"name": "prod", "type": "L3VRF"},
                        "evpn": {
                            "config": {
                                "route-distinguisher": "65001:2001"
                            },
                            "route-targets": {
                                "route-target": [
                                    {
                                        "type": "IMPORT",
                                        "config": {"route-target": "65001:2001"}
                                    },
                                    {
                                        "type": "EXPORT",
                                        "config": {"route-target": "65001:2001"}
                                    }
                                ]
                            }
                        },
                        "config": {"vni": "2001"}
                    }
                ]
            }
        
        # VXLAN mappings
        if xpath and "Vxlan1" in xpath:
            return {
                "value": {
                    "config": {
                        "source-interface": "Loopback0",
                        "udp-port": "4789"
                    },
                    "vlan-vni-mappings": {
                        "vlan-vni-mapping": [
                            {"vlan-id": "10", "vni": "1001"},
                            {"vlan-id": "20", "vni": "1002"}
                        ]
                    },
                    "vrf-vni-mappings": {
                        "vrf-vni-mapping": [
                            {"vrf-name": "prod", "vni": "2001"}
                        ]
                    }
                }
            }
        
        return {"value": {}}


def print_mcp_call(tool_name: str, arguments: dict, response: dict):
    """Pretty print an MCP call and response"""
    print("\n" + "=" * 80)
    print(f"MCP Tool Call: {tool_name}")
    print("=" * 80)
    print("\n📤 Request:")
    print(json.dumps({"tool": tool_name, "arguments": arguments}, indent=2))
    print("\n📥 Response:")
    print(json.dumps(response, indent=2))
    print("\n" + "=" * 80)


def main():
    """Run demo of MCP calls"""
    print("\n🚀 Arista EOS MCP Domain View Demo")
    print("=" * 80)
    print("Simulating MCP tool calls against 3-node MLAG/EVPN lab")
    print("Target: leaf1 (MLAG primary with EVPN/VXLAN overlay)")
    
    client = SimulatedMCPClient()
    
    # Demo calls for each new domain
    demos = [
        {
            "name": "Routing Policy",
            "domain": "routing-policy",
            "description": "Prefix-lists and route-maps for BGP policy"
        },
        {
            "name": "ACLs",
            "domain": "acls",
            "description": "Access control lists with interface bindings"
        },
        {
            "name": "MLAG",
            "domain": "mlag",
            "description": "Multi-chassis LAG configuration and state"
        },
        {
            "name": "EVPN/VXLAN",
            "domain": "evpn-vxlan",
            "description": "Overlay networking with L2/L3 VNIs"
        }
    ]
    
    for demo in demos:
        print(f"\n\n{'=' * 80}")
        print(f"🔍 Demo: {demo['name']}")
        print(f"📝 {demo['description']}")
        
        arguments = {
            "target_ref": "target://lab/leaf1",
            "domain": demo["domain"]
        }
        
        response = client.call_tool("arista.get_domain_view", arguments)
        print_mcp_call("arista.get_domain_view", arguments, response)
        
        # Show summary stats
        if response.get("status") == "success":
            data = response.get("data", {})
            summary = data.get("summary", {})
            print(f"\n📊 Summary:")
            for key, value in summary.items():
                print(f"  • {key}: {value}")


if __name__ == "__main__":
    main()
