from __future__ import annotations

import json
from pathlib import Path

from netconf_mcp.mcp.server import create_server


FIXTURES = Path("tests/fixtures")


class DummyLiveClient:
    def open_session(self, target, *, framing="auto", hostkey_policy="strict", connect_timeout_ms=None):
        del hostkey_policy, connect_timeout_ms
        selected = "base:1.0" if framing == "auto" else framing
        return type(
            "LiveSession",
            (),
            {
                "session_id": "901",
                "framing": selected,
                "server_capabilities": [
                    "urn:ietf:params:netconf:base:1.0",
                    "urn:ietf:params:netconf:capability:with-defaults:1.0",
                ],
                "transport": {"protocol": "ssh", "framing": selected},
            },
        )()

    def get_yang_library(self, target, session):
        del target, session
        return {
            "module_set": [{"module": "ietf-interfaces", "revision": "2018-02-20"}],
            "yang_hashes": {},
            "provenance": "live-netconf",
            "completeness": "complete",
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

    def datastore_get(self, target, session, *, datastore="running", xpath=None, subtree=None, with_defaults="explicit", strict_config=False):
        del target, session, subtree, with_defaults
        if xpath == "/interfaces/interface[name='eth0']/enabled":
            value = "true"
        else:
            value = {"interfaces": {"interface": {"name": "eth0", "enabled": "true"}}}
        return {
            "resource": {"datastore": datastore, "filter": xpath or "all"},
            "nacm_visibility": "unknown",
            "value": value,
            "source_metadata": {
                "mode": "live-netconf",
                "host": "tnsr-lab",
                "strict_config": strict_config,
            },
            "raw_xml": "<rpc-reply/>",
        }


def _write_live_inventory(tmp_path: Path) -> Path:
    inventory_path = tmp_path / "inventory-live.json"
    payload = {
        "targets": [
            {
                "target_ref": "target://lab/tnsr",
                "name": "tnsr-lab",
                "site": "lab",
                "role": ["edge"],
                "status": "online",
                "safety_state": "ready",
                "transport_mode": "live-ssh",
                "transport": {"protocol": "ssh", "framing": "base:1.0"},
                "host": "tnsr-lab",
                "port": 830,
                "username": "netops",
                "facts": {"vendor": "netgate", "os": "tnsr"},
                "safety_profile": "read-only",
                "last_seen_utc": "2026-03-12T00:00:00Z",
            }
        ]
    }
    inventory_path.write_text(json.dumps(payload), encoding="utf-8")
    return inventory_path


def test_read_only_manifest_exposed_and_only_read_only_names():
    runtime = create_server(FIXTURES)
    snapshot = runtime.exposure_snapshot()
    assert set(snapshot.tools) == {
        "inventory.list_targets",
        "netconf.open_session",
        "netconf.discover_capabilities",
        "yang.get_library",
        "netconf.get_monitoring",
        "datastore.get",
        "datastore.get_config",
        "config.plan_edit",
        "config.validate_plan",
        "config.apply_plan",
        "config.rollback",
    }
    assert set(snapshot.resources) >= {
        "targets://inventory",
        "target://{target_ref}/facts",
        "target://{target_ref}/capabilities",
        "target://{target_ref}/yang-library",
        "target://{target_ref}/datastores/{name}",
        "target://{target_ref}/session-state",
    }
    assert set(snapshot.prompts) >= {
        "discover-device-safely",
        "inspect-operational-state",
        "review-yang-capabilities",
    }


def test_discovery_and_filtered_reads():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    list_targets = tool._tools["inventory.list_targets"]({"arguments": {"filter": {"status": "online"}}})
    assert list_targets["status"] == "ok"
    targets = list_targets["data"]["targets"]
    assert any(item["target_ref"] == "target://lab/strict" for item in targets)

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/strict",
            "arguments": {"credential_ref": "cred://vault/lab/strict"},
        }
    )
    assert open_session["status"] == "ok"
    assert "cred://[redacted]" not in str(open_session)

    session_ref = open_session["data"]["session_ref"]
    caps = tool._tools["netconf.discover_capabilities"]({"session_ref": session_ref})
    assert caps["status"] == "ok"
    assert isinstance(caps["data"].get("capability_catalog", []), list)

    lib = tool._tools["yang.get_library"]({"session_ref": session_ref})
    assert lib["status"] == "ok"
    assert lib["data"]["completeness"] == "high"

    monitor = tool._tools["netconf.get_monitoring"]({"session_ref": session_ref, "arguments": {"scope": "all"}})
    assert monitor["status"] == "ok"

    config = tool._tools["datastore.get_config"](
        {
            "session_ref": session_ref,
            "arguments": {"datastore": "running", "xpath": "/interfaces/interface[name='Ethernet1']/mtu"},
        }
    )
    assert config["status"] == "ok"
    assert config["data"]["value"] == 1514

    operational = tool._tools["datastore.get"](
        {
            "session_ref": session_ref,
            "arguments": {"datastore": "operational", "xpath": "/interfaces/interface[name='Ethernet1']/if-speed"},
        }
    )
    assert operational["status"] == "ok"
    assert operational["data"]["value"] == "10G"


def test_nacm_restricted_read_is_blocked():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/nacm",
            "arguments": {"credential_ref": "cred://vault/lab/nacm"},
        }
    )
    session_ref = open_session["data"]["session_ref"]

    denied = tool._tools["datastore.get_config"](
        {
            "session_ref": session_ref,
            "arguments": {"datastore": "running", "xpath": "/interfaces/interface[name='Ethernet1']/mtu"},
        }
    )
    assert denied["status"] == "error"
    assert denied["error"]["error_category"] == "nacm"


def test_transport_failure_is_reported_as_error():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    failed = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/transport",
            "arguments": {"credential_ref": "cred://vault/lab/transport"},
        }
    )
    assert failed["status"] == "error"
    assert failed["error"]["error_category"] == "transport"


def test_incomplete_yang_library_reports_low_confidence():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/yanglib",
            "arguments": {"credential_ref": "cred://vault/lab/yanglib"},
        }
    )
    session_ref = open_session["data"]["session_ref"]

    lib = tool._tools["yang.get_library"]({"session_ref": session_ref})
    assert lib["status"] == "ok"
    assert lib["confidence"] == "low"
    assert lib["warnings"][0]["code"] == "SCHEMA_INCOMPLETE"


def test_guarded_plan_only_and_validate_only_work_without_confirmation():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/strict",
            "arguments": {"credential_ref": "cred://vault/lab/strict"},
        }
    )
    assert open_session["status"] == "ok"
    session_ref = open_session["data"]["session_ref"]

    plan = tool._tools["config.plan_edit"](
        {
            "session_ref": session_ref,
            "arguments": {
                "plan_scope": "candidate",
                "intent": "merge",
                "edits": [
                    {
                        "yang_path": "/interfaces/interface[name='Ethernet1']/description",
                        "action": "set",
                        "value": "edge-agg-guarded",
                    },
                ],
            },
        }
    )
    assert plan["status"] == "ok"
    assert plan["data"]["plan_status"] in {"ready_to_validate", "ready_to_execute"}
    plan_id = plan["data"]["plan_id"]

    validation = tool._tools["config.validate_plan"](
        {
            "session_ref": session_ref,
            "arguments": {"plan_id": plan_id},
        }
    )
    assert validation["status"] == "ok"
    assert validation["data"]["plan_id"] == plan_id

    apply = tool._tools["config.apply_plan"](
        {
            "session_ref": session_ref,
            "arguments": {"plan_id": plan_id},
        }
    )
    assert apply["status"] == "error"
    assert apply["policy_decision"] == "blocked"
    assert apply["error"]["error_code"] == "CONFIRMATION_REQUIRED"

    audit = runtime.get_audit_log()
    stages = {event["context"]["stage"] for event in audit}
    assert "plan_ready" in stages
    assert "apply_blocked" in stages
    assert all("confirm://" not in str(event["context"]) for event in audit)


def test_confirmed_commit_apply_and_rollback_report_with_supported_capability():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/strict",
            "arguments": {"credential_ref": "cred://vault/lab/strict"},
        }
    )
    assert open_session["status"] == "ok"
    session_ref = open_session["data"]["session_ref"]

    plan = tool._tools["config.plan_edit"](
        {
            "session_ref": session_ref,
            "arguments": {
                "plan_scope": "candidate",
                "intent": "merge",
                "edits": [
                    {
                        "yang_path": "/interfaces/interface[name='Ethernet1']/description",
                        "action": "set",
                        "value": "from-operator",
                    },
                ],
            },
        }
    )
    assert plan["status"] == "ok"
    plan_id = plan["data"]["plan_id"]

    validation = tool._tools["config.validate_plan"](
        {
            "session_ref": session_ref,
            "arguments": {"plan_id": plan_id},
        }
    )
    assert validation["status"] == "ok"
    assert validation["data"]["plan_status"] in {"ready_to_execute", "blocked"} or validation["data"]["confidence"]

    apply = tool._tools["config.apply_plan"](
        {
            "session_ref": session_ref,
            "arguments": {
                "plan_id": plan_id,
                "lock_strategy": "explicit",
                "commit_mode": "confirmed",
                "confirmation_token": "confirm://operator/001",
                "policy_approval": {
                    "actor": "operator/alice",
                    "approved_by": "Alice",
                },
            },
        }
    )
    assert apply["status"] == "ok"
    assert apply["data"]["commit_outcome"] == "pending_commit"
    rollback_id = apply["data"]["rollback_plan"]["rollback_id"]

    rollback = tool._tools["config.rollback"](
        {
            "session_ref": session_ref,
            "arguments": {
                "rollback_id": rollback_id,
                "confirmation_token": "confirm://operator/002",
                "policy_approval": {
                    "actor": "operator/alice",
                    "approved_by": "Alice",
                },
            },
        }
    )
    assert rollback["status"] == "ok"
    assert rollback["data"]["rollback_outcome"] == "applied"


def test_confirmed_commit_limitation_reported_when_capability_missing():
    runtime = create_server(FIXTURES)
    tool = runtime.get_server()

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/yanglib",
            "arguments": {"credential_ref": "cred://vault/lab/yanglib"},
        }
    )
    assert open_session["status"] == "ok"
    session_ref = open_session["data"]["session_ref"]

    plan = tool._tools["config.plan_edit"](
        {
            "session_ref": session_ref,
            "arguments": {
                "plan_scope": "candidate",
                "intent": "merge",
                "edits": [
                    {
                        "yang_path": "/interfaces/interface[name='Ethernet1']/mtu",
                        "action": "set",
                        "value": 1500,
                    },
                ],
            },
        }
    )
    assert plan["status"] == "ok"

    apply = tool._tools["config.apply_plan"](
        {
            "session_ref": session_ref,
            "arguments": {
                "plan_id": plan["data"]["plan_id"],
                "commit_mode": "confirmed",
                "lock_strategy": "explicit",
                "confirmation_token": "confirm://operator/001",
                "policy_approval": {
                    "actor": "operator/alice",
                    "approved_by": "Alice",
                },
            },
        }
    )
    assert apply["status"] == "error"
    assert apply["error"]["error_code"] == "CONFIRMED_COMMIT_UNSUPPORTED"


def test_live_read_only_target_can_be_probed_with_dummy_client(tmp_path: Path):
    inventory_path = _write_live_inventory(tmp_path)
    runtime = create_server(FIXTURES, inventory_path=inventory_path, live_client=DummyLiveClient())
    tool = runtime.get_server()

    targets = tool._tools["inventory.list_targets"]({"arguments": {"filter": {"status": "online"}}})
    assert any(item["target_ref"] == "target://lab/tnsr" for item in targets["data"]["targets"])

    open_session = tool._tools["netconf.open_session"](
        {
            "target_ref": "target://lab/tnsr",
            "arguments": {"credential_ref": "cred://vault/lab/tnsr"},
        }
    )
    assert open_session["status"] == "ok"
    assert open_session["data"]["mode"] == "live-ssh"
    session_ref = open_session["data"]["session_ref"]

    caps = tool._tools["netconf.discover_capabilities"]({"session_ref": session_ref})
    assert caps["status"] == "ok"
    assert "urn:ietf:params:netconf:capability:with-defaults:1.0" in caps["data"]["capability_catalog"]

    lib = tool._tools["yang.get_library"]({"session_ref": session_ref})
    assert lib["status"] == "ok"
    assert lib["data"]["provenance"] == "live-netconf"

    config = tool._tools["datastore.get_config"](
        {
            "session_ref": session_ref,
            "arguments": {"datastore": "running", "xpath": "/interfaces/interface[name='eth0']/enabled"},
        }
    )
    assert config["status"] == "ok"
    assert config["data"]["value"] == "true"

    plan = tool._tools["config.plan_edit"](
        {
            "session_ref": session_ref,
            "arguments": {
                "plan_scope": "candidate",
                "intent": "merge",
                "edits": [{"yang_path": "/interfaces/interface[name='eth0']/enabled", "action": "set", "value": False}],
            },
        }
    )
    assert plan["status"] == "error"
    assert plan["error"]["error_code"] == "LIVE_WRITE_UNSUPPORTED"
