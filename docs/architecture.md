# NETCONF MCP v1 Architecture

Read-only discovery-first MCP server based on layered boundaries:

- MCP presentation: tool/resource/prompt handlers
- Safety/policy: all operations marked read-only
- Protocol/transport: simulated NETCONF read flows
- YANG/schema: fixture-based normalized module inventory
- Vendor adapters: capability-based profile branching in fixtures
- Audit/logging: redacted operation ledger

This repository uses only read-only MCP surfaces in v1.
