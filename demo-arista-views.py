#!/usr/bin/env python3
"""
Demonstration script showing Arista domain views using fixture data.
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


class FakeSession:
    server_capabilities = [
        "urn:ietf:params:netconf:base:1.1",
        "http://openconfig.net/yang/interfaces?module=openconfig-interfaces",
    ]


class DemoClient:
    """Demo client with realistic EOS fixture data"""
    
    def open_session(self, target, *, hostkey_policy="strict", framing="auto", connect_timeout_ms=None):
        return FakeSession()
    
    def get_yang_library(self, target, session):
        return {
            "module_set": [
                {"module": "openconfig-interfaces", "revision": "2024-12-05"},
                {"module": "openconfig-vlan", "revision": "2024-11-10"},
                {"module": "openconfig-network-instance", "revision": "2024-10-15"},
            ],
        }
    
    def datastore_get(self, target, session, *, datastore="running", xpath=None):
        # Interfaces
        if xpath and "oc-if:interfaces" in xpath:
            return {
                "value": [
                    {
                        "name": "Management1",
                        "config": {
                            "enabled": "true",
                            "description": "Management interface",
                            "type": "ethernetCsmacd",
                            "mtu": "1500",
                        },
                        "state": {
                            "admin-status": "UP",
                            "oper-status": "UP",
                        },
                        "subinterfaces": {
                            "subinterface": [
                                {
                                    "index": "0",
                                    "ipv4": {
                                        "addresses": {
                                            "address": [
                                                {
                                                    "ip": "172.20.20.2",
                                                    "config": {"prefix-length": "24"},
                                                }
                                            ]
                                        }
                                    },
                                }
                            ]
                        },
                    },
                    {
                        "name": "Ethernet1",
                        "config": {
                            "enabled": "true",
                            "description": "Uplink to core",
                            "type": "ethernetCsmacd",
                            "mtu": "9000",
                        },
                        "state": {
                            "admin-status": "UP",
                            "oper-status": "UP",
                        },
                        "ethernet": {
                            "config": {"aggregate-id": "Port-Channel1"}
                        },
                    },
                    {
                        "name": "Ethernet2",
                        "config": {
                            "enabled": "true",
                            "description": "Uplink to core",
                            "type": "ethernetCsmacd",
                            "mtu": "9000",
                        },
                        "state": {
                            "admin-status": "UP",
                            "oper-status": "DOWN",
                        },
                        "ethernet": {
                            "config": {"aggregate-id": "Port-Channel1"}
                        },
                    },
                    {
                        "name": "Port-Channel1",
                        "config": {
                            "enabled": "true",
                            "description": "LAG to core switches",
                            "type": "ieee8023adLag",
                            "mtu": "9000",
                        },
                        "state": {
                            "admin-status": "UP",
                            "oper-status": "UP",
                        },
                        "aggregation": {
                            "config": {"lag-type": "LACP"},
                            "state": {"lag-speed": "100000000000"},
                        },
                        "subinterfaces": {
                            "subinterface": [
                                {
                                    "index": "0",
                                    "ipv4": {
                                        "addresses": {
                                            "address": [
                                                {
                                                    "ip": "10.0.1.1",
                                                    "config": {"prefix-length": "24"},
                                                }
                                            ]
                                        }
                                    },
                                }
                            ]
                        },
                    },
                ]
            }
        
        # VLANs
        if xpath and "oc-vlan:vlans" in xpath:
            return {
                "value": {
                    "vlan": [
                        {
                            "vlan-id": "10",
                            "config": {"name": "OFFICE", "status": "ACTIVE"},
                            "members": {
                                "member": [
                                    {"interface": "Ethernet3"},
                                    {"interface": "Ethernet4"},
                                ]
                            },
                        },
                        {
                            "vlan-id": "20",
                            "config": {"name": "SERVERS", "status": "ACTIVE"},
                            "members": {
                                "member": [
                                    {"interface": "Ethernet5"},
                                ]
                            },
                        },
                    ]
                }
            }
        
        # VRFs
        if xpath and "oc-ni:network-instances" in xpath:
            return {
                "value": {
                    "network-instance": [
                        {
                            "name": "default",
                            "config": {"type": "DEFAULT_INSTANCE", "enabled": "true"},
                        },
                        {
                            "name": "MGMT",
                            "config": {"type": "L3VRF", "enabled": "true", "route-distinguisher": "65000:100"},
                            "interfaces": {
                                "interface": [
                                    {"id": "Management1"},
                                ]
                            },
                        },
                    ]
                }
            }
        
        # BGP
        if xpath and "oc-bgp:bgp" in xpath:
            return {
                "value": {
                    "global": {
                        "config": {"as": "65000"},
                        "state": {"router-id": "10.0.1.1"},
                    },
                    "neighbors": {
                        "neighbor": [
                            {
                                "neighbor-address": "10.0.1.2",
                                "config": {"peer-as": "65001", "enabled": "true"},
                                "state": {
                                    "session-state": "ESTABLISHED",
                                    "established-transitions": "5",
                                },
                                "afi-safis": {
                                    "afi-safi": [
                                        {
                                            "afi-safi-name": "IPV4_UNICAST",
                                            "state": {
                                                "prefixes": {"received": "150", "sent": "200"},
                                            },
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                }
            }
        
        # System
        if xpath and "oc-sys:system" in xpath:
            return {
                "value": {
                    "config": {"hostname": "arista-ceos-lab"},
                    "state": {
                        "boot-time": "1710000000",
                        "current-datetime": "2024-03-17T12:00:00Z",
                    },
                }
            }
        
        # LLDP
        if xpath and "oc-lldp:lldp" in xpath:
            return {
                "value": {
                    "interfaces": {
                        "interface": [
                            {
                                "name": "Ethernet1",
                                "neighbors": {
                                    "neighbor": [
                                        {
                                            "id": "00:1c:73:00:00:01",
                                            "state": {
                                                "system-name": "core-switch-1",
                                                "port-id": "Ethernet1/1",
                                                "port-description": "Link to arista-ceos-lab",
                                            },
                                        }
                                    ]
                                },
                            }
                        ]
                    }
                }
            }
        
        # Static routes
        if xpath and "oc-local-routing:static-routes" in xpath:
            return {
                "value": {
                    "static": [
                        {
                            "prefix": "0.0.0.0/0",
                            "next-hops": {
                                "next-hop": [
                                    {
                                        "index": "0",
                                        "config": {"next-hop": "10.0.1.254"},
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        
        return {"value": {}}


def main():
    print("=" * 70)
    print("Arista EOS Domain Views - Demo")
    print("=" * 70)
    print()
    
    # Create collector with demo client
    client = DemoClient()
    collector = AristaCollector(client=client)
    
    # Dummy target
    target = {
        "target_ref": "target://demo/arista",
        "name": "arista-demo",
        "facts": {"vendor": "arista", "os": "eos"},
    }
    
    # Collect snapshot
    print("📸 Collecting snapshot from demo device...")
    snapshot = collector.collect_snapshot(target)
    print(f"✓ Snapshot collected: {len(snapshot.capabilities)} capabilities")
    print()
    
    # Show device summary
    print("🖥️  Device Summary")
    print("-" * 70)
    print(f"  Hostname:     {snapshot.system.hostname or 'N/A'}")
    print(f"  Interfaces:   {len(snapshot.interfaces)}")
    print(f"  LAGs:         {len(snapshot.lags)}")
    print(f"  VLANs:        {len(snapshot.vlans)}")
    print(f"  VRFs:         {len(snapshot.vrfs)}")
    print(f"  BGP ASN:      {snapshot.bgp.asn or 'N/A'}")
    print(f"  Warnings:     {len(snapshot.warnings)}")
    print()
    
    # Convert snapshot to dict for domain views
    snapshot_dict = snapshot.to_dict()
    
    # Domain views
    domains = ["system", "interfaces", "vlans", "vrfs", "lags", "bgp", "lldp", "routing"]
    
    for domain in domains:
        print(f"📊 Domain View: {domain}")
        print("-" * 70)
        try:
            view = get_domain_view(snapshot_dict, domain)
            print(json.dumps(view, indent=2))
        except Exception as e:
            print(f"Error: {e}")
        print()


if __name__ == "__main__":
    main()
