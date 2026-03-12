"""CLI entrypoints for the read-only NETCONF MCP server."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import traceback

from netconf_mcp.mcp.server import create_server


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the NETCONF MCP server.")
    parser.add_argument(
        "--fixture-root",
        default=os.environ.get("NETCONF_MCP_FIXTURE_ROOT", "tests/fixtures"),
        help="Fixture root for local profiles. Defaults to NETCONF_MCP_FIXTURE_ROOT or tests/fixtures.",
    )
    parser.add_argument(
        "--inventory",
        default=os.environ.get("NETCONF_MCP_INVENTORY"),
        help="Optional inventory JSON for live targets. Defaults to NETCONF_MCP_INVENTORY.",
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Print the manifest and exit instead of starting stdio mode.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=_env_flag("NETCONF_MCP_DEBUG"),
        help="Print startup context and full tracebacks on failure.",
    )
    return parser.parse_args(argv)


def _print_debug_context(*, fixture_root: Path, inventory_path: Path | None) -> None:
    print("NETCONF MCP debug startup", file=sys.stderr)
    print(f"fixture_root={fixture_root}", file=sys.stderr)
    print(f"inventory_path={inventory_path}", file=sys.stderr)
    print(f"cwd={Path.cwd()}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    fixture_root = Path(args.fixture_root)
    inventory_path = Path(args.inventory) if args.inventory else None

    try:
        if args.debug:
            _print_debug_context(fixture_root=fixture_root, inventory_path=inventory_path)

        server = create_server(
            fixture_root,
            inventory_path=inventory_path,
        )
        snapshot = server.exposure_snapshot()

        if args.debug:
            print(f"tools={snapshot.tools}", file=sys.stderr)
            print(f"resources={snapshot.resources}", file=sys.stderr)
            print(f"prompts={snapshot.prompts}", file=sys.stderr)

        if args.manifest_only or not hasattr(server.get_server(), "run"):
            print("NETCONF MCP server manifest:")
            print("tools:", snapshot.tools)
            print("resources:", snapshot.resources)
            print("prompts:", snapshot.prompts)
            return 0

        server.start()
        return 0
    except Exception as exc:
        if args.debug:
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"NETCONF MCP startup failed: {exc}", file=sys.stderr)
            print("Retry with --debug for a full traceback.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
