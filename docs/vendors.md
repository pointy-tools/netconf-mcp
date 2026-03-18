# Vendor Profiles

V1 uses simulator profiles and fixtures. Profiles can emulate RFC deviations in a safe way:

- strict-rfc6241
- nacm-restricted
- yanglib-incomplete
- transport-fail
- arista-eos-openconfig

## Arista EOS

### Overview

Arista EOS is supported through OpenConfig YANG models. The implementation uses namespace-prefixed XPath queries to access OpenConfig data paths.

### Model Support

Arista EOS uses OpenConfig models with the following namespace prefixes:

| Prefix | Namespace |
|--------|-----------|
| `oc-if` | `http://openconfig.net/yang/interfaces` |
| `oc-eth` | `http://openconfig.net/yang/interfaces/ethernet` |
| `oc-ip` | `http://openconfig.net/yang/interfaces/ip` |
| `oc-lacp` | `http://openconfig.net/yang/lacp` |
| `oc-vlan` | `http://openconfig.net/yang/vlan` |
| `oc-ni` | `http://openconfig.net/yang/network-instance` |
| `oc-lldp` | `http://openconfig.net/yang/lldp` |
| `oc-sys` | `http://openconfig.net/yang/system` |
| `oc-bgp` | `http://openconfig.net/yang/bgp` |
| `oc-rpol` | `http://openconfig.net/yang/routing-policy` |
| `oc-local-routing` | `http://openconfig.net/yang/local-routing` |
| `oc-aaa` | `http://openconfig.net/yang/aaa` |

### Supported Domains

The following domain views are available via `arista.get_domain_view`:

| Domain | Description | Data Source |
|--------|-------------|-------------|
| `interfaces` | Interface config and IP addresses | OpenConfig |
| `vlans` | VLAN configuration | OpenConfig |
| `vrfs` | VRF/network instance config | OpenConfig |
| `lags` | LACP LAG interfaces | OpenConfig |
| `bgp` | BGP global config (ASN, router-id) | OpenConfig |
| `lldp` | LLDP neighbor discovery | OpenConfig |
| `system` | System hostname and version | OpenConfig |
| `routing` | Static routes | OpenConfig |
| `routing-policy` | Route maps and prefix lists | OpenConfig |
| `acls` | Access control lists (IPv4/IPv6) | OpenConfig |
| `mlag` | Multi-chassis LAG configuration | Arista-proprietary |
| `evpn-vxlan` | EVPN/VXLAN overlay configuration | Arista-proprietary |

**Note**: MLAG and EVPN/VXLAN domains use Arista-proprietary data sources (not OpenConfig) and require EOS-specific YANG models.

### Snapshot Collection

Collect a normalized snapshot:

```bash
python scripts/arista_snapshot.py \
  --inventory lab-inventory.json \
  --target-ref target://lab/arista \
  --hostkey-policy accept-new \
  --output arista-snapshot.json
```

### MCP Tool Usage

After opening a session, use the domain tool:

```
Tool: arista.get_domain_view
Arguments: {
  "session_ref": "session-001",
  "domain": "interfaces"
}
```

### Fixture Notes

- `target://lab/arista` uses `arista-eos-openconfig` profile data sourced from a sanitized live capture.
- Capture metadata indicates EOS `4.35.2F` on `ceos` (`/tests/fixtures/profiles/arista-eos-openconfig.json`), with partial YANG library metadata (`completeness: low`).
- Monitor/session values in the fixture are curated and synthetic reads are intentionally minimal:
  - `/interfaces/interface[name='Management1']/description`
  - `/system/hostname`

### Limitations

- Domain view tool requires a live session (not fixture-backed)
- BGP neighbor details not yet extracted (only global config)
- OpenConfig model coverage depends on YANG library advertised by the device

### Inventory Configuration

Arista targets require a `namespace_map` in the inventory for OpenConfig XPath queries:

```json
{
  "target_ref": "target://lab/arista",
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
  }
}
```

## TNSR

See [`docs/integration-guide.md`](integration-guide.md) for complete TNSR documentation including snapshot collection, domain views, and proposal generation workflows.
