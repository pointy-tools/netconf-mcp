# Integration Guide (Fixture-first)

- Start server: `python -m netconf_mcp.cli`
- Session tool flow:
  1. `inventory.list_targets`
  2. `netconf.open_session`
  3. `netconf.discover_capabilities`
  4. `yang.get_library`
  5. `datastore.get` / `datastore.get_config`

All inputs are fixture-driven under `tests/fixtures`.
