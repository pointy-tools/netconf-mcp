from __future__ import annotations

from pathlib import Path

from netconf_mcp.mcp.server import create_server


FIXTURES = Path("tests/fixtures")


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
