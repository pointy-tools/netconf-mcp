# Safe Operations

## Core rules

1. No inline credentials in tool outputs.
2. Read-only by default for all exposed tools.
3. NACM-limited reads return structured error responses.
4. Incomplete schema discovery reports low confidence and carries warnings.
5. Secrets are redacted from structured logs.
