# netconf-mcp

Fixture-first NETCONF MCP server for local agent workflows.

## Current scope

This repository currently implements a local Python MCP server with:

- read-only NETCONF discovery flows
- schema-aware planning and guarded write simulation
- structured envelopes, confidence signals, and redaction
- fixture-backed target profiles for happy-path and failure-path testing

The current implementation is designed for safe local development, not direct production device access yet.

## Implemented tool surface

Read and discovery:

- `inventory.list_targets`
- `netconf.open_session`
- `netconf.discover_capabilities`
- `yang.get_library`
- `netconf.get_monitoring`
- `datastore.get`
- `datastore.get_config`

Guarded write workflow:

- `config.plan_edit`
- `config.validate_plan`
- `config.apply_plan`
- `config.rollback`

## Project layout

- [`src/netconf_mcp`](/Users/rdw/src/netconf-mcp/src/netconf_mcp): package code
- [`tests`](/Users/rdw/src/netconf-mcp/tests): integration tests and fixture inventory
- [`docs/architecture.md`](/Users/rdw/src/netconf-mcp/docs/architecture.md): architecture notes
- [`docs/integration-guide.md`](/Users/rdw/src/netconf-mcp/docs/integration-guide.md): quick local flow
- [`docs/safe-operations.md`](/Users/rdw/src/netconf-mcp/docs/safe-operations.md): safety rules
- [`docs/vendors.md`](/Users/rdw/src/netconf-mcp/docs/vendors.md): vendor/interoperability notes

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

The current CLI uses fixture data under [`tests/fixtures`](/Users/rdw/src/netconf-mcp/tests/fixtures).

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

What is still intentionally deferred:

- real-device interoperability validation
- production credential loading and secret-store integration
- notifications and YANG-Push support
- multi-device orchestration
- production hardening for unattended write execution

## Notes

This repository also contains workflow-generated planning artifacts under ignored local workflow paths. The repo root README is intentionally focused on the implemented project rather than the internal planning prompt that produced it.
