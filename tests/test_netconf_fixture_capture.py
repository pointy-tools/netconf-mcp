from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import json

from scripts.netconf_fixture_capture import (
    CAPTURE_SCHEMA,
    _collect_capture_payload,
    _config_probes,
    _dedupe,
    _write_capture,
)


class CapturingLiveClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def open_session(
        self,
        target: dict,
        *,
        framing: str = "auto",
        hostkey_policy: str = "strict",
        connect_timeout_ms=None,
    ):
        del target, framing, hostkey_policy, connect_timeout_ms
        return type(
            "LiveSession",
            (),
            {
                "session_id": "901",
                "framing": "base:1.0",
                "server_capabilities": ["urn:ietf:params:netconf:base:1.1"],
                "transport": {"protocol": "ssh", "framing": "base:1.0"},
            },
        )()

    def get_yang_library(self, target, session):
        del target, session
        return {
            "module_set": [{"module": "openconfig-interfaces", "revision": "2021-01-01"}],
            "yang_hashes": {},
            "provenance": "live-netconf",
            "completeness": "high",
            "feature_matrix": {},
            "raw_xml": "<rpc-reply/>",
        }

    def get_monitoring(self, target, session, scope="all"):
        del target, session
        return {
            "scope": scope,
            "sessions": [{"session-id": "901"}],
            "locks": [],
            "datastore_health": {},
            "transport_stats": {},
            "raw_xml": "<rpc-reply/>",
        }

    def datastore_get(
        self,
        target,
        session,
        *,
        datastore: str = "running",
        xpath: str | None = None,
        subtree: dict | None = None,
        with_defaults: str = "explicit",
        strict_config: bool = False,
    ):
        del target, session, subtree, with_defaults, strict_config
        self.calls.append((datastore, xpath))
        if datastore == "running":
            value = f"running:{xpath}"
        else:
            value = f"oper:{xpath}"
        return {
            "resource": {"datastore": datastore, "filter": xpath or "all"},
            "nacm_visibility": "unknown",
            "value": value,
            "source_metadata": {"mode": "live-netconf"},
            "raw_xml": "<rpc-reply/>",
        }


def _write_inventory(tmp_path: Path) -> Path:
    payload = {
        "targets": [
            {
                "target_ref": "target://lab/fixture",
                "name": "fixture-lab",
                "site": "lab",
                "status": "online",
                "safety_state": "ready",
                "transport_mode": "live-ssh",
                "transport": {"protocol": "ssh", "framing": "base:1.0"},
                "host": "fixture.example.net",
                "port": 830,
                "username": "admin",
                "facts": {"vendor": "arista", "os": "eos", "platform": "ceos"},
                "password": "s3cr3t",
                "api_token": "token-please-hide",
                "safety_profile": "read-only",
                "last_seen_utc": "2026-03-12T00:00:00Z",
            }
        ]
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _build_args(inventory: Path, *, output: Path, profile: str = "custom") -> Namespace:
    return Namespace(
        inventory=str(inventory),
        target_ref="target://lab/fixture",
        hostkey_policy="accept-new",
        credential_ref="cred://vault/lab/fixture",
        profile=profile,
        config_xpath=["/interfaces", "/interfaces", "/bgp/state"],
        oper_xpath=["/state/interfaces", "/state/interfaces"],
        fixture_root="tests/fixtures",
        output=str(output),
    )


def test_config_probe_profile_appends_and_dedupes():
    probes = _config_probes(
        "custom",
        ["/interfaces", "/interfaces", "/bgp/state"],
    )
    assert probes == ["/interfaces", "/bgp/state"]


def test_capture_collects_sections_and_deduped_probes(tmp_path: Path):
    inventory_path = _write_inventory(tmp_path)
    output_path = tmp_path / "capture.json"
    live_client = CapturingLiveClient()
    args = _build_args(inventory_path, output=output_path)

    payload = _collect_capture_payload(args, live_client=live_client)

    assert payload["capture_schema"] == CAPTURE_SCHEMA
    assert payload["session"]["mode"] == "live-ssh"
    assert payload["capabilities"]["capability_catalog"] == ["urn:ietf:params:netconf:base:1.1"]
    assert payload["yang_library"]["provenance"] == "live-netconf"
    assert payload["monitoring"]["scope"] == "all"
    assert [entry["xpath"] for entry in payload["reads"]["config"]] == ["/interfaces", "/bgp/state"]
    assert [entry["xpath"] for entry in payload["reads"]["operational"]] == ["/state/interfaces"]
    assert all(call[1] in {"/interfaces", "/bgp/state", "/state/interfaces"} for call in live_client.calls)


def test_capture_write_redacts_sensitive_fields(tmp_path: Path):
    inventory_path = _write_inventory(tmp_path)
    output_path = tmp_path / "capture.json"
    args = _build_args(inventory_path, output=output_path)
    payload = _collect_capture_payload(args, live_client=CapturingLiveClient())

    _write_capture(output_path, payload)
    saved = output_path.read_text(encoding="utf-8")

    assert "s3cr3t" not in saved
    assert "token-please-hide" not in saved
    assert "cred://vault/lab/fixture" not in saved
    emitted = json.loads(saved)
    assert emitted["target"]["password"] == "[redacted]"
    assert emitted["target"]["api_token"] == "[redacted]"
    assert emitted["capture_schema"] == CAPTURE_SCHEMA


def test_dedupe_is_order_preserving():
    assert _dedupe(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]
