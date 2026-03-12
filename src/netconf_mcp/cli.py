"""CLI entrypoints for the read-only NETCONF MCP server."""

from __future__ import annotations

from pathlib import Path

from netconf_mcp.mcp.server import create_server


def main() -> None:
    server = create_server(Path("tests/fixtures"))
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
