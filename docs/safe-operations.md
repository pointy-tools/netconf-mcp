# Safe Operations

## Core rules

1. No inline credentials in tool outputs.
2. Read-only by default for all exposed tools.
3. NACM-limited reads return structured error responses.
4. Incomplete schema discovery reports low confidence and carries warnings.
5. Secrets are redacted from structured logs.

## Arista EOS Safety Notes

- All Arista workflows use the `safety_profile: read-only` setting in inventory.
- OpenConfig XPath queries require proper namespace configuration; malformed queries return errors, not partial data.
- Domain view tool requires a live session; fixture-backed snapshots cannot be queried through the MCP tool.
- Snapshot collection performs read-only NETCONF operations only; no configuration changes are made.
- LLDP neighbor data is collected from the operational datastore and reflects current discovery state.

## TNSR Safety Notes

See [`docs/integration-guide.md`](integration-guide.md) for TNSR-specific safety guidance.
