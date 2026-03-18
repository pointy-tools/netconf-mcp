# netconf-mcp

Fixture-first NETCONF MCP server for read-oriented network automation workflows.

## Current scope

This repository currently implements a local Python MCP server with:

- read-only NETCONF discovery flows
- schema-aware planning and guarded write simulation
- structured envelopes, confidence signals, and redaction
- fixture-backed target profiles for happy-path and failure-path testing

The current implementation is designed for safe local development, not direct production device access yet.

## What this is

- an MCP server for structured NETCONF reads
- a safe read/propose workflow for network source-of-truth repos
- a TNSR-first implementation with fixture-backed tests and live read-only validation

## Arista lab path

For live interoperability work, the repository recommends a Linux-hosted `cEOS-lab + containerlab` path as the primary option:

- fast to stand up in CI/local environments
- predictable startup and management-interface behavior
- direct NETCONF access on the standard SSH-managed port `830`

`vEOS-lab` remains a documented fallback when your environment or image access requires it.

## What this is not

- a production-hardened write engine
- a credential-management system
- a complete multi-vendor platform yet

## Supported Vendors

- **TNSR** — Full snapshot, domain views, and proposal generation
- **Arista EOS** — OpenConfig-based snapshot collection and domain views

## Implemented tool surface

Read and discovery:

- `inventory.list_targets`
- `netconf.open_session`
- `netconf.discover_capabilities`
- `yang.get_library`
- `netconf.get_monitoring`
- `datastore.get`
- `datastore.get_config`
- `tnsr.get_domain_view`
- `arista.get_domain_view`

Guarded write workflow:

- `config.plan_edit`
- `config.validate_plan`
- `config.apply_plan`
- `config.rollback`

## Project layout

- `src/netconf_mcp`: package code
- `tests`: integration tests and fixture inventory
- [`docs/architecture.md`](docs/architecture.md): architecture notes
- [`docs/integration-guide.md`](docs/integration-guide.md): quick local flow
- [`docs/safe-operations.md`](docs/safe-operations.md): safety rules
- [`docs/vendors.md`](docs/vendors.md): vendor/interoperability notes

## Quick start

Install dev dependencies:

```bash
python -m pip install -e '.[dev]'
```

Run the test suite:

```bash
python -m pytest -q
```

Run the local server entrypoint:

```bash
python -m netconf_mcp.cli
```

The current CLI uses fixture data under `tests/fixtures`.

For live lab testing, start from the example inventory:

```bash
cp lab-inventory.example.json lab-inventory.json
```

For an Arista-first path, use the Arista example file and the companion lab guide:

```bash
cp lab-inventory.arista.example.json lab-inventory.json
```

Reference [`docs/arista-lab.md`](docs/arista-lab.md) for containerlab startup, image, and verification flow details.

## Status

What is working now:

- fixture-backed NETCONF session and capability discovery
- YANG Library confidence handling
- NACM-restricted read behavior
- transport failure reporting
- guarded write planning, validation, confirmation gating, and rollback simulation
- experimental live read-only TNSR NETCONF probing
- normalized TNSR snapshot generation for code-diff workflows
- TNSR managed-config proposal generation from normalized snapshots
- TNSR routing-policy coverage for prefix-lists and route-maps
- TNSR BFD session coverage in snapshot and proposal outputs
- TNSR NAT and VPF filter-ruleset coverage for source-of-truth proposals
- TNSR-specific MCP domain views for compact policy/config questions
- Arista EOS OpenConfig-based snapshot collection (interfaces, VLANs, VRFs, LAGs, BGP, LLDP, system, routing)
- Arista EOS MCP domain views for compact agent-facing queries

What is still intentionally deferred:

- real-device interoperability validation
- production credential loading and secret-store integration
- notifications and YANG-Push support
- multi-device orchestration
- production hardening for unattended write execution

## Notes

This repository may use ignored local workflow artifacts during development. Public repository content is intended to stay focused on the project itself.

## Data Fidelity

When an agent summarizes structured data returned from NETCONF tools:

- quote returned values verbatim
- avoid paraphrasing, deduplicating, or treating similar-looking entries as equivalent unless the payload proves it
- say explicitly when data is filtered, partial, or truncated
- prefer direct citation of returned fields over narrative interpretation
