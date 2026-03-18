# Arista cEOS-Lab Advanced Topology

This lab provides a multi-node cEOS topology with MLAG, EVPN/VXLAN, ACLs, and routing policies for validating NETCONF data collection across advanced network features.

## Topology Overview

```
                    +----------+
                    |  spine   |
                    |  (eth1)  |
                    +----+-----+
                         | 192.168.0.1/31
                         |
        +----------------+----------------+
        |                                 |
   +----+----+                       +----+----+
   | leaf1  |                       | leaf2  |
   | (eth1) |                       | (eth1) |
   +----+----+                       +----+----+
        | 192.168.0.0/31                  | 192.168.0.2/31
        |                                 |
        +----+                         +----+
        |eth2|                         |eth2|
        +----+                         +----+
        | MLAG Peer-Link               | MLAG Peer-Link
        | (Port-Channel10)             | (Port-Channel10)
        | 192.168.0.4/31               | 192.168.0.5/31
        +----+                         +----+
        |eth3|                         |eth3|
        +----+                         +----+
        | Dual-Attached                | Dual-Attached
        | (Port-Channel20)            | (Port-Channel20)
```

## Node Details

| Node    | Role       | Loopback0   | Management IP   | ASN   |
|---------|------------|-------------|-----------------|-------|
| leaf1   | MLAG Primary / VTEP | 10.0.0.1    | 172.20.20.11    | 65001 |
| leaf2   | MLAG Secondary / VTEP | 10.0.0.2    | 172.20.20.12    | 65001 |
| spine   | EVPN Route Reflector | 10.0.0.3    | 172.20.20.13    | 65001 |

## Feature Coverage

### MLAG Configuration
- **Domain ID**: 10
- **Peer-Link**: Port-Channel10 (VLAN 100)
- **Dual-Attached**: Port-Channel20 carries VLANs 10, 20
- **Priority**: leaf1 = primary, leaf2 = secondary

### EVPN/VXLAN Configuration
- **VTEP Source**: Loopback0
- **L2VNIs**:
  - VLAN 10 (WEB) → VNI 1001
  - VLAN 20 (APP) → VNI 1002
- **L3VNI**: VRF "prod" → VNI 2001
- **EVPN**: iBGP with spine as route-reflector

### ACL Configuration
| ACL Name | Type | Entries | Applied To |
|----------|------|---------|------------|
| ACL-BLOCK-ADMIN | IPv4 Extended | 2 | Ethernet1 (in) on leaf1/leaf2 |
| ACL-ALLOW-WEB | IPv4 Extended | 3 | Vlan10 (in) on leaf1/leaf2 |
| ACL-SPINE-FILTER | IPv4 Extended | 3 | Ethernet1 (in) on spine |

### Routing Policy Configuration
| Prefix-List | Prefix |
|-------------|--------|
| PREFIX-LIST-LOOPBACKS | 10.0.0.0/24 |
| PREFIX-LIST-VXLAN | 172.16.0.0/16 |
| PREFIX-LIST-MGMT | 192.168.0.0/24 |
| PREFIX-LIST-UNDERLAY | 192.168.0.0/24 |

| Route-Map | Applied To |
|-----------|------------|
| RM-IMPORT-LOOPBACKS | BGP neighbor in (leaf1/leaf2) |
| RM-EXPORT-VXLAN | BGP neighbor out (leaf1/leaf2) |
| RM-MLAG-PEER | MLAG peer communication |
| RM-LEAF-IN | Spine BGP neighbor in |
| RM-LEAF-OUT | Spine BGP neighbor out |
| RM-UNDERLAY-IN | Underlay BGP neighbor in |

## Pre-Deployment Requirements

### 1. Load cEOS Image

```bash
docker import cEOS64-lab-4.32.0F.tar.xz ceos:4.32.0F
```

### 2. Verify Image

```bash
docker images | grep ceos
```

## Deployment

### Start the Lab

```bash
cd labs/arista-ceos
sudo containerlab deploy -t containerlab.yml
```

### Verify Node State

```bash
docker ps --filter "name=clab-arista-ceos-lab"
```

### Get Management IPs

```bash
# leaf1
docker inspect -f '{{ range .NetworkSettings.Networks}}{{ .IPAddress }}{{ end }}' clab-arista-ceos-lab-leaf1

# leaf2
docker inspect -f '{{ range .NetworkSettings.Networks}}{{ .IPAddress }}{{ end }}' clab-arista-ceos-lab-leaf2

# spine
docker inspect -f '{{ range .NetworkSettings.Networks}}{{ .IPAddress }}{{ end }}' clab-arista-ceos-lab-spine
```

## Validation Commands

### 1. Verify NETCONF Access

```bash
# leaf1
nc -zv 172.20.20.11 830

# leaf2
nc -zv 172.20.20.12 830

# spine
nc -zv 172.20.20.13 830
```

### 2. Verify MLAG Status (via CLI)

```bash
ssh admin@172.20.20.11 "show mlag"
ssh admin@172.20.20.12 "show mlag"
```

Expected output should show:
- MLAG domain: 10
- State: active
- Peer-link: Po10
- Dual-attached: Po20

### 3. Verify VXLAN Configuration

```bash
ssh admin@172.20.20.11 "show vxlan"
```

Expected output should show:
- Source interface: Loopback0
- UDP port: 4789
- VNI to VLAN mappings

### 4. Verify BGP/EVPN

```bash
ssh admin@172.20.20.11 "show bgp evpn summary"
ssh admin@172.20.20.13 "show bgp evpn summary"
```

Expected output should show:
- BGP state: Established
- EVPN neighbors: 10.0.0.1, 10.0.0.2 (on spine)
- Route-reflector clients: leaf1, leaf2

### 5. Verify ACLs

```bash
ssh admin@172.20.20.11 "show ip access-lists"
```

Expected output should show:
- ACL-BLOCK-ADMIN: 2 entries
- ACL-ALLOW-WEB: 3 entries

### 6. Verify Routing Policy

```bash
ssh admin@172.20.20.11 "show ip prefix-lists"
ssh admin@172.20.20.11 "show route-map"
```

Expected output should show:
- PREFIX-LIST-LOOPBACKS: 1 entry
- PREFIX-LIST-VXLAN: 1 entry
- PREFIX-LIST-MGMT: 1 entry
- Route-maps: RM-IMPORT-LOOPBACKS, RM-EXPORT-VXLAN, RM-MLAG-PEER

## NETCONF Queries

### Query MLAG Configuration

```bash
ssh -p 830 admin@172.20.20.11 -s netconf << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<rpc message-id="1" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <get>
    <filter>
      <network-instances xmlns="http://openconfig.net/yang/network-instance">
        <network-instance>
          <name>default</name>
          <mlag xmlns="http://arista.com/yang/openconfig/mlag">
          </mlag>
        </network-instance>
      </network-instances>
    </filter>
  </get>
</rpc>
EOF
```

### Query VXLAN Configuration

```bash
ssh -p 830 admin@172.20.20.11 -s netconf << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<rpc message-id="2" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <get>
    <filter>
      <vlans xmlns="http://openconfig.net/yang/vlan">
      </vlans>
      <vxlan xmlns="http://arista.com/yang/openconfig/vxlan">
      </vxlan>
    </filter>
  </get>
</rpc>
EOF
```

### Query ACLs

```bash
ssh -p 830 admin@172.20.20.11 -s netconf << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<rpc message-id="3" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <get>
    <filter>
      <acl xmlns="http://openconfig.net/yang/acl">
      </acl>
    </filter>
  </get>
</rpc>
EOF
```

### Query Routing Policy

```bash
ssh -p 830 admin@172.20.20.11 -s netconf << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<rpc message-id="4" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <get>
    <filter>
      <routing-policy xmlns="http://openconfig.net/yang/routing-policy">
      </routing-policy>
    </filter>
  </get>
</rpc>
EOF
```

## Teardown

```bash
cd labs/arista-ceos
sudo containerlab destroy -t containerlab.yml
```

## Troubleshooting

### MLAG Not Coming Up

1. Verify peer-link connectivity:
   ```bash
   ssh admin@172.20.20.11 "show interface Po10"
   ```

2. Check VLAN 100 exists on both nodes:
   ```bash
   ssh admin@172.20.20.11 "show vlan 100"
   ```

### VXLAN Not Working

1. Verify VTEP source:
   ```bash
   ssh admin@172.20.20.11 "show vxlan source-interface"
   ```

2. Check UDP port:
   ```bash
   ssh admin@172.20.20.11 "show vxlan udp-port"
   ```

### BGP Not Establishing

1. Check underlay connectivity:
   ```bash
   ssh admin@172.20.20.11 "ping 192.168.0.1"
   ```

2. Verify BGP neighbors:
   ```bash
   ssh admin@172.20.20.11 "show bgp neighbor"
   ```

## Files

- `containerlab.yml` - Topology definition
- `startup-config-leaf1.cfg` - Leaf1 (MLAG primary) configuration
- `startup-config-leaf2.cfg` - Leaf2 (MLAG secondary) configuration
- `startup-config-spine.cfg` - Spine (EVPN route-reflector) configuration
- `README.md` - This file
