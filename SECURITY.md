# Security Policy

## Scope

`netconf-mcp` is currently intended for safe local development, read-oriented workflows, and guarded simulation. It should not be treated as production-hardened device automation software.

## Reporting

Please report suspected security issues privately to the maintainers before opening a public issue.

When reporting, include:

- affected version or commit
- reproduction steps
- whether the issue affects fixture-only behavior, live read-only behavior, or guarded write simulation
- any relevant logs or redacted payloads

## Current limitations

- Live NETCONF support is primarily read-only.
- Production credential management is not implemented.
- Multi-device orchestration and unattended production write hardening are not complete.
