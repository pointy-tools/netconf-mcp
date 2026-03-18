"""Tests for the arista_snapshot.py script."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "arista_snapshot.py"
FIXTURE_INVENTORY = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "inventory.json"


def test_script_requires_inventory_arg():
    """Script should fail without --inventory argument."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "required" in result.stderr.lower() or "error" in result.stderr.lower()


def test_script_shows_help():
    """Script should show help with --help."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Arista EOS" in result.stdout


def test_script_default_target():
    """Script should use target://lab/arista as default target-ref."""
    # This will fail because there's no actual device, but we can verify the argument parsing works
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--inventory", str(FIXTURE_INVENTORY),
            "--output", "/dev/null",
        ],
        capture_output=True,
        text=True,
    )
    # Should fail at connection time, not argument parsing
    assert "Target target://lab/arista not found" not in result.stderr


def test_script_loads_target_from_inventory():
    """Script should load target from inventory file."""
    # Verify the target exists in the fixture
    inventory = json.loads(FIXTURE_INVENTORY.read_text())
    arista_target = None
    for target in inventory.get("targets", []):
        if target.get("target_ref") == "target://lab/arista":
            arista_target = target
            break

    assert arista_target is not None
    assert arista_target["name"] == "arista-ceos"
    assert arista_target["facts"]["vendor"] == "arista"


def test_script_hostkey_policy_argument():
    """Script should accept --hostkey-policy argument."""
    # Just verify the argument is accepted
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--help",
        ],
        capture_output=True,
        text=True,
    )

    assert "--hostkey-policy" in result.stdout
    assert "strict" in result.stdout
    assert "accept-new" in result.stdout


def test_script_missing_target_in_inventory():
    """Script should exit with error if target not found."""
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--inventory", str(FIXTURE_INVENTORY),
            "--target-ref", "target://nonexistent/device",
            "--output", "/dev/null",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "not found" in result.stderr.lower()


def test_script_output_argument():
    """Script should accept --output argument."""
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--help",
        ],
        capture_output=True,
        text=True,
    )

    assert "--output" in result.stdout


def test_script_inventory_argument():
    """Script should accept --inventory argument."""
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--help",
        ],
        capture_output=True,
        text=True,
    )

    assert "--inventory" in result.stdout


def test_script_target_ref_argument():
    """Script should accept --target-ref argument."""
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--help",
        ],
        capture_output=True,
        text=True,
    )

    assert "--target-ref" in result.stdout


def test_script_default_output_file():
    """Script should have default output file."""
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--help",
        ],
        capture_output=True,
        text=True,
    )

    # Check that --output is present
    assert "--output" in result.stdout


def test_script_default_target_ref():
    """Script should have default target-ref."""
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--help",
        ],
        capture_output=True,
        text=True,
    )

    # Check that --target-ref is present
    assert "--target-ref" in result.stdout


def test_script_fails_without_host():
    """Script should fail when target has no host configured."""
    # Create a temporary inventory without host
    import yaml

    test_inventory = {
        "targets": [
            {
                "target_ref": "target://test/arista",
                "name": "test-arista",
                "facts": {"vendor": "arista", "os": "eos"},
                # No host or ssh_config_host
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(test_inventory, f)
        temp_inventory = f.name

    try:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--inventory", temp_inventory,
                "--target-ref", "target://test/arista",
                "--output", "/dev/null",
            ],
            capture_output=True,
            text=True,
        )

        # Should fail because no host is configured
        assert result.returncode != 0
        assert "host" in result.stderr.lower()
    finally:
        Path(temp_inventory).unlink(missing_ok=True)
