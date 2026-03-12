"""CLI entrypoints for the read-only NETCONF MCP server."""

from __future__ import annotations

import os
from pathlib import Path

from netconf_mcp.mcp.server import create_server


def main() -> None:
    fixture_root = Path(os.environ.get("NETCONF_MCP_FIXTURE_ROOT", "tests/fixtures"))
    inventory_path = os.environ.get("NETCONF_MCP_INVENTORY")
    server = create_server(
        fixture_root,
        inventory_path=Path(inventory_path) if inventory_path else None,
    )
    snapshot = server.exposure_snapshot()
    if hasattr(server.get_server(), "run"):
        # Runtime mode for MCP clients
        server.start()
    else:
        print("NETCONF MCP server manifest:")
        print("tools:", snapshot.tools)
        print("resources:", snapshot.resources)
        print("prompts:", snapshot.prompts)


if __name__ == "__main__":
    main()
