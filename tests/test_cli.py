from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from netconf_mcp import cli


@dataclass
class _Snapshot:
    tools: list[str]
    resources: list[str]
    prompts: list[str]


class _Server:
    def __init__(self):
        self.started = False

    def run(self):
        self.started = True


class _Runtime:
    def __init__(self):
        self.server = _Server()

    def exposure_snapshot(self):
        return _Snapshot(
            tools=["inventory.list_targets"],
            resources=["resource://inventory"],
            prompts=["review-yang-capabilities"],
        )

    def get_server(self):
        return self.server

    def start(self):
        self.server.run()


def test_manifest_only_prints_manifest(monkeypatch, capsys):
    monkeypatch.setattr(cli, "create_server", lambda fixture_root, inventory_path=None: _Runtime())

    exit_code = cli.main(["--manifest-only"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "NETCONF MCP server manifest:" in captured.out
    assert "inventory.list_targets" in captured.out


def test_debug_failure_prints_traceback(monkeypatch, capsys):
    def _raise(_fixture_root: Path, inventory_path=None):
        del inventory_path
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "create_server", _raise)

    exit_code = cli.main(["--debug"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Traceback" in captured.err
    assert "RuntimeError: boom" in captured.err
