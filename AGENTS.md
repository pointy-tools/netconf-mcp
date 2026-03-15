# AGENTS.md

Guidance for coding agents working in `netconf-mcp`.

## Mission
This repository builds a fixture-first NETCONF MCP server for agent workflows.
The current focus is safe read-oriented discovery, guarded proposal generation, and TNSR-specific workflows.
Treat the repo as safety-sensitive network automation code, even when tests are fixture-backed.

## Current State
- Main language: Python with `setuptools` `src/` packaging.
- Repo metadata requires Python `>=3.12`; CI runs on `3.12` and `3.13`.
- Tests use `pytest` with optional dev deps `pytest` and `pytest-asyncio`.
- No repo-local Ruff, Black, isort, mypy, pyright, or flake8 config was found.
- No repo-local Cursor rules were found in `.cursor/rules/` or `.cursorrules`.
- No Copilot instructions were found in `.github/copilot-instructions.md`.

## High-Level Architecture
- `src/netconf_mcp/cli.py`: CLI entrypoint and startup/debug behavior.
- `src/netconf_mcp/mcp/server.py`: MCP tool/resource/prompt registration and response envelopes.
- `src/netconf_mcp/protocol/engine.py`: read engine, session tracking, and guarded workflow logic.
- `src/netconf_mcp/transport/fixtures.py`: fixture-backed transport/repository logic.
- `src/netconf_mcp/transport/live.py`: experimental live NETCONF-over-SSH reads.
- `src/netconf_mcp/vendors/tnsr.py`: TNSR snapshot collection and normalization.
- `src/netconf_mcp/vendors/tnsr_views.py`: compact agent-facing TNSR domain views.
- `src/netconf_mcp/proposals/tnsr.py`: snapshot-to-source-of-truth proposal generation.
- `src/netconf_mcp/utils/`: redaction and filtering helpers.
- `tests/` and `tests/fixtures/`: unit, integration, inventory, and profile coverage.
- `docs/` and `scripts/`: design notes plus live-helper workflows.

## Safety And Domain Rules
- Preserve the repository's read-first posture.
- Do not add production write behavior without explicit safety controls and review hooks.
- Keep inline credentials and secrets out of outputs, fixtures, docs, and logs.
- Use redaction helpers for secret-bearing structures.
- Treat NETCONF-returned values as authoritative and quote them verbatim when summarizing.
- Do not collapse, normalize, deduplicate, or infer equivalence between similar-looking values unless the payload proves it.
- Prefer vendor-aware domain views over broad datastore reads for agent-facing TNSR workflows.

Say explicitly when data is partial, filtered, truncated, or low-confidence.

## Environment Setup
Preferred setup, matching README and CI:

```bash
python -m pip install -e '.[dev]'
```
- This repo uses a `src/` layout, so direct `python -m netconf_mcp.cli` only works after installation or with `PYTHONPATH=src`.
- In this workspace, `python` is `3.14`, and editable install failed because setuptools rejected the legacy `License :: OSI Approved :: MIT License` classifier during build metadata evaluation.
- For reliable local work, prefer Python `3.12` or `3.13` to match CI.
- If you cannot install the package, use `PYTHONPATH=src` for ad hoc local execution.

## Build, Lint, And Test Commands
There is no dedicated lint command configured in the repo.
There is no dedicated typecheck command configured in the repo.
There is no documented packaging build command in the repo's normal workflow.
The concrete, repo-backed commands are below.

### Core Commands
- Install dev dependencies: `python -m pip install -e '.[dev]'`
- Run all tests: `python -m pytest -q`
- Run one test file: `python -m pytest -q tests/test_cli.py`
- Run one test function: `python -m pytest -q tests/test_cli.py::test_manifest_only_prints_manifest`
- Run tests by keyword: `python -m pytest -q -k manifest`
- Run integration test file: `python -m pytest -q tests/integration/test_mcp_flow.py`
- Run CLI after install: `python -m netconf_mcp.cli`
- Run CLI without install: `PYTHONPATH=src python -m netconf_mcp.cli`
- Print MCP manifest only: `PYTHONPATH=src python -m netconf_mcp.cli --manifest-only`

### Useful Script Commands
- Live TNSR smoke flow: `python scripts/tnsr_read_only_smoke.py --inventory lab-inventory.json --target-ref target://lab/tnsr --hostkey-policy accept-new --summary-only`
- One extra config probe: `python scripts/tnsr_read_only_smoke.py --inventory lab-inventory.json --target-ref target://lab/tnsr --hostkey-policy accept-new --config-xpath "/interfaces-config/interface[name='LAN']/ipv4/address/ip"`
- Snapshot collection: `python scripts/tnsr_snapshot.py --inventory lab-inventory.json --target-ref target://lab/tnsr --hostkey-policy accept-new --output tnsr-snapshot.json`
- Domain view from live inventory: `python scripts/tnsr_show.py --inventory lab-inventory.json --target-ref target://lab/tnsr --hostkey-policy accept-new --domain prefix-lists`
- Domain view from snapshot: `python scripts/tnsr_show.py --snapshot tnsr-snapshot.json --domain bgp`
- Proposal generation: `python scripts/tnsr_propose.py --snapshot tnsr-snapshot.json`
- Split-layout proposal generation: `python scripts/tnsr_propose.py --snapshot tnsr-snapshot.json --layout split`

## Test Strategy For Agents
- Always run the smallest relevant pytest command first, then the broader suite you affected.
- Prefer single-test invocations while iterating.
- Finish with `python -m pytest -q` when changes touch shared behavior.
- Tests are plain pytest functions; no custom markers or marker-based workflows are configured.
- Integration coverage lives in `tests/integration/`.
- Tests commonly use `monkeypatch`, `capsys`, `tmp_path`, fake classes, and inline fixture payloads.
- `tests/conftest.py` appends `src/` to `sys.path`; scripts do something similar themselves.

## Code Style
### Imports
- Keep `from __future__ import annotations` at the top of Python modules; it is used almost everywhere.
- Follow standard import grouping: stdlib first, then absolute imports from `netconf_mcp`.
- Prefer absolute package imports like `from netconf_mcp.transport.live import LiveNetconfSSHClient`.
- Avoid introducing relative imports unless the file already uses them.
- In scripts, keep the existing `PROJECT_ROOT` / `SRC_ROOT` bootstrap pattern if the script is intended to run without install.

### Formatting
- Use 4-space indentation.
- Use double quotes consistently.
- Keep module docstrings concise and descriptive.
- Keep functions small when possible, but match surrounding file style before refactoring.
- Use trailing commas in multiline literals and call sites where the file already does so.

### Types And Data Modeling
- Use modern built-in generics: `list[str]`, `dict[str, Any]`, `tuple[...]`.
- Use `| None` unions instead of `Optional[...]` in new code unless matching an older local pattern.
- Prefer dataclasses for structured snapshot and contract records.
- Keep payload shapes explicit and stable; many tests assert exact key names.
- Avoid introducing untyped ad hoc structures when there is an existing dataclass or envelope shape to extend.

### Naming
- Functions, methods, variables, and test names use `snake_case`.
- Classes and dataclasses use `PascalCase`.
- Constants use `UPPER_CASE`.
- Internal helpers often use a leading underscore.
- Keep NETCONF/MCP tool names and schema-derived field names exactly as defined by the protocol or payload.

### Error Handling
- Prefer structured domain errors over generic exceptions in core logic.
- `transport/live.py` raises `LiveNetconfError` with structured payloads; follow that pattern for transport-layer failures.
- `mcp/server.py` wraps outcomes into stable `status` / `policy_decision` / `data` / `error` envelopes.
- Catch broad exceptions only at clear boundaries, such as CLI startup or compatibility fallbacks.
- When returning error payloads, preserve keys like `error_category`, `error_code`, `error_type`, and `error_tag`.
- Keep retry guidance and safety implications explicit.

### JSON, Output, And Determinism
- Preserve returned device values verbatim.
- Keep proposal and script JSON deterministic; existing code uses `indent=2` and often `sort_keys=True`.
- Favor stable ordering when generating managed config artifacts or summaries.
- Be careful with truncation logic and confidence/warning fields; agents rely on them.

### Logging And Secrets
- There is little or no standard `logging` module usage in current code; do not add logging noise casually.
- CLI/debug output currently uses `print(..., file=sys.stderr)`.
- Redact secret-bearing mappings with `redact_mapping()`.
- Never expose raw credential refs or secret values in audit or tool payloads.

## Repo-Specific Implementation Preferences
- Prefer editing existing modules over adding new top-level abstractions.
- Reuse MCP envelope and audit patterns from `src/netconf_mcp/mcp/server.py`.
- Reuse normalization helpers and snapshot dataclasses from `src/netconf_mcp/vendors/tnsr.py`.
- Prefer TNSR domain views for agent-facing questions about BGP, prefix-lists, route-maps, NAT, filters, NACM, management, or platform settings.
- For new CLI or script behavior, mirror the existing argparse style and user-facing phrasing.
- For fixture-backed behavior, update or add tests rather than relying on manual reasoning.

## Practical Workflow For Future Sessions
- Read `README.md`, `docs/integration-guide.md`, and `docs/safe-operations.md` before changing behavior that affects tool semantics.
- Check `pyproject.toml` and `.github/workflows/tests.yml` before assuming new tooling exists.
- If changing protocol or MCP payload shapes, update tests first or alongside the change.
- If changing a script, also inspect the matching `tests/test_*script.py` coverage.
- If installation fails in a non-CI interpreter, fall back to `PYTHONPATH=src` for local read/test/debug loops and note the interpreter mismatch.
