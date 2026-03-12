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

The smoke runner always executes:

1. `inventory.list_targets`
2. `netconf.open_session`
3. `netconf.discover_capabilities`
4. `yang.get_library`
5. `netconf.get_monitoring`
6. profile-selected `datastore.get_config` probes
7. optional `datastore.get`

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
- static routes
- BGP global config and neighbors
- BGP timers and policy-requirement flags
- prefix-lists when the live subtree is exposed cleanly
- route-maps when the live subtree is exposed cleanly
- BFD sessions
- NAT rulesets from `vpf-config`
- VPF filter-rulesets and interface policy bindings

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

This is the intended near-term loop for TNSR:

1. collect a read-only snapshot from the live device
2. generate a proposed repo-side config update
3. review the proposal and decide how your source-of-truth should change
4. let your deployment workflow handle device changes later
