"""Simulation-first NETCONF read-only engine with optional live read-only probing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from netconf_mcp.core.contracts import READ_ONLY_TOOLSET
from netconf_mcp.utils import filters
from netconf_mcp.utils.filters import xpath_filter
from netconf_mcp.transport.fixtures import FixtureRepository
from netconf_mcp.transport.live import LiveNetconfError, LiveNetconfSSHClient


@dataclass
class Session:
    session_ref: str
    target_ref: str
    target_name: str
    profile: str
    backend: str
    framing: str
    capabilities: list[str]
    opened_at: str


class NetconfReadEngine:
    """A strict read-only, fixture-backed protocol simulator."""

    def __init__(self, fixture_root: Path, *, inventory_path: Path | None = None, live_client: LiveNetconfSSHClient | None = None):
        self.fixture_root = Path(fixture_root)
        self.repository = FixtureRepository(self.fixture_root, inventory_path=inventory_path)
        self.live_client = live_client or LiveNetconfSSHClient()
        self.sessions: dict[str, Session] = {}
        self.plans: dict[str, dict[str, Any]] = {}
        self.pending_rollbacks: dict[str, dict[str, Any]] = {}

    def list_targets(
        self,
        *,
        filter: dict[str, Any] | None = None,
        include: list[str] | None = None,
    ) -> dict[str, Any]:
        targets = self.repository.inventory()
        include = set(include or [])
        filtered = []

        for item in targets:
            include_target = True
            if filter:
                if "status" in filter and filter["status"] == "online":
                    include_target = item.get("status") == "online"
                for key in ("site", "role"):
                    if key in filter and filter[key] and item.get(key) != filter[key]:
                        include_target = False
            if not include_target:
                continue
            projected = {
                "target_ref": item["target_ref"],
                "name": item.get("name"),
                "site": item.get("site"),
                "role": item.get("role"),
                "transport": item.get("transport"),
            }
            if "facts" in include:
                projected["facts"] = item.get("facts", {})
            if "capability_profile" in include:
                projected["capability_profile"] = item.get("capability_profile")
            if "safety_profile" in include:
                projected["safety_profile"] = item.get("safety_profile")
            projected["last_seen_utc"] = item.get("last_seen_utc")
            projected["safety_state"] = item.get("safety_state", "unknown")
            filtered.append(projected)

        return {
            "targets": filtered,
        }

    def open_session(
        self,
        *,
        target_ref: str,
        credential_ref: str | None = None,
        framing: str = "auto",
        hostkey_policy: str = "strict",
        connect_timeout_ms: int | None = None,
        operation_id: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        del credential_ref  # no in-band secret usage
        target = self._target_by_ref(target_ref)
        if target.get("transport_mode") == "live-ssh":
            try:
                live_session = self.live_client.open_session(
                    target,
                    framing=framing,
                    hostkey_policy=hostkey_policy,
                    connect_timeout_ms=connect_timeout_ms,
                )
            except LiveNetconfError as exc:
                return "error", exc.payload

            session_ref = f"session://{target['name']}/{uuid.uuid4().hex[:8]}"
            session = Session(
                session_ref=session_ref,
                target_ref=target_ref,
                target_name=target["name"],
                profile=target_ref,
                backend="live-ssh",
                framing=live_session.framing,
                capabilities=live_session.server_capabilities,
                opened_at=datetime.now(timezone.utc).isoformat(),
            )
            self.sessions[session_ref] = session
            return "ok", {
                "session_ref": session_ref,
                "transport": live_session.transport,
                "server_capabilities": live_session.server_capabilities,
                "client_capabilities": ["urn:ietf:params:netconf:base:1.0"],
                "capability_gaps": [],
                "hello_latency_ms": None,
                "session_id": live_session.session_id,
                "framed_version": live_session.framing,
                "profile": "live-netconf",
                "mode": "live-ssh",
            }

        del hostkey_policy, connect_timeout_ms
        try:
            profile = self.repository.profile(target["profile"])
        except FileNotFoundError as exc:
            return "error", {
                "status": "error",
                "error_category": "transport",
                "error_code": "PROFILE_MISSING",
                "error_tag": "transport",
                "message": "Simulator profile missing",
            } | {},

        if profile.data.get("transport_failure"):
            return "error", {
                "status": "error",
                "error_category": "transport",
                "error_code": "CONNECT_FAILED",
                "error_tag": "transport",
                "message": "Unable to connect to simulator profile",
            }

        selected_framing = profile.data.get("hello", {}).get("framing", "base:1.1")
        if framing != "auto" and framing != selected_framing:
            selected_framing = framing

        session_ref = f"session://{target['name']}/{uuid.uuid4().hex[:8]}"
        session = Session(
            session_ref=session_ref,
            target_ref=target_ref,
            target_name=target["name"],
            profile=target["profile"],
            backend="fixture",
            framing=selected_framing,
            capabilities=profile.data.get("hello", {}).get("capabilities", []),
            opened_at=datetime.now(timezone.utc).isoformat(),
        )
        self.sessions[session_ref] = session

        return "ok", {
            "session_ref": session_ref,
            "transport": {
                "protocol": "ssh",
                "framing": selected_framing,
            },
            "server_capabilities": session.capabilities,
            "client_capabilities": [
                "urn:ietf:params:netconf:base:1.1",
                "urn:ietf:params:netconf:capability:writable-running:1.0",
            ],
            "capability_gaps": profile.data.get("capability_gaps", []),
            "hello_latency_ms": 12,
            "session_id": profile.data.get("hello", {}).get("session_id", 0),
            "framed_version": selected_framing,
            "profile": target["profile"],
        }

    def discover_capabilities(self, session_ref: str) -> tuple[str, dict[str, Any]]:
        session = self._require_session(session_ref)
        if session.backend == "live-ssh":
            return "ok", {
                "capability_catalog": session.capabilities,
                "version_profile": {
                    "netconf-base": "1.1" if any("base:1.1" in cap for cap in session.capabilities) else "1.0",
                },
                "required_missing": [
                    required
                    for required in (
                        "urn:ietf:params:netconf:capability:candidate:1.0",
                        "urn:ietf:params:netconf:capability:with-defaults:1.0",
                    )
                    if required not in session.capabilities
                ],
                "feature_flags": [],
                "nacm_hints": {},
                "session_ref": session_ref,
                "source_metadata": {"mode": "live-netconf"},
            }
        profile = self._load_profile(session.profile)

        if not profile:
            return "error", self._protocol_error("PROFILE_EXPIRED", "Profile no longer available")

        caps = profile.data.get("hello", {}).get("capabilities", [])
        feature_flags = profile.data.get("feature_flags", [])
        required_missing = []
        for required in ("urn:ietf:params:netconf:capability:candidate:1.0", "urn:ietf:params:netconf:capability:with-defaults:1.0"):
            if required not in caps:
                required_missing.append(required)

        return "ok", {
            "capability_catalog": caps,
            "version_profile": {
                "netconf-base": "1.1" if "base:1.1" in caps else "1.0",
            },
            "required_missing": required_missing,
            "feature_flags": feature_flags,
            "nacm_hints": profile.data.get("nacm", {}),
            "session_ref": session_ref,
        }

    def get_library(self, session_ref: str) -> tuple[str, dict[str, Any]]:
        session = self._require_session(session_ref)
        if session.backend == "live-ssh":
            target = self._target_by_ref(session.target_ref)
            try:
                payload = self.live_client.get_yang_library(target, session)
            except LiveNetconfError as exc:
                return "error", exc.payload
            confidence = "high" if payload.get("completeness") == "complete" else "low"
            payload["completeness"] = confidence
            return "ok", payload

        profile = self._load_profile(session.profile)
        if not profile:
            return "error", self._protocol_error("PROFILE_EXPIRED", "Profile no longer available")

        modules = profile.data.get("yang_library", {}).get("module_set", [])
        completeness = profile.data.get("yang_library", {}).get("completeness", "low")
        confidence = "high" if completeness == "complete" else "low"

        return "ok", {
            "module_set": modules,
            "yang_hashes": profile.data.get("yang_library", {}).get("yang_hashes", {}),
            "provenance": profile.data.get("yang_library", {}).get("provenance", "fixture"),
            "completeness": confidence,
            "feature_matrix": profile.data.get("yang_library", {}).get("feature_matrix", {}),
        }

    def plan_edit(
        self,
        session_ref: str,
        *,
        edits: list[dict[str, Any]] | None = None,
        plan_scope: str = "running",
        intent: str = "merge",
        safety_profile_ref: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        del safety_profile_ref
        session = self._require_session(session_ref)
        if session.backend != "fixture":
            return "error", {
                "status": "error",
                "error_category": "policy",
                "error_code": "LIVE_WRITE_UNSUPPORTED",
                "error_type": "LIVE_WRITE_UNSUPPORTED",
                "error_tag": "operation-not-supported",
                "error_message": "Live NETCONF targets are read-only in the current implementation",
            }
        profile = self._load_profile(session.profile)
        if not profile:
            return "error", self._protocol_error("PROFILE_EXPIRED", "Profile no longer available")

        if not isinstance(edits, list) or not edits:
            return "error", {
                "status": "error",
                "error_category": "schema",
                "error_code": "PLAN_MISSING_EDITS",
                "error_type": "PLAN_MISSING_EDITS",
                "error_tag": "invalid-value",
                "error_message": "No editable operations were supplied",
            }

        candidate = self._has_capability(profile, "urn:ietf:params:netconf:capability:candidate:1.0")
        writable_running = self._has_capability(profile, "urn:ietf:params:netconf:capability:writable-running:1.0")
        schema_confidence = "high"
        plan_scope = plan_scope or "running"
        profile_modules = {
            item.get("module")
            for item in profile.data.get("yang_library", {}).get("module_set", [])
            if isinstance(item, dict) and "module" in item
        }
        schema_checks = []
        warnings = []

        for index, edit in enumerate(edits):
            if not isinstance(edit, dict) or "yang_path" not in edit:
                return "error", {
                    "status": "error",
                    "error_category": "schema",
                    "error_code": "PLAN_BAD_EDIT",
                    "error_type": "PLAN_BAD_EDIT",
                    "error_tag": "invalid-value",
                    "error_message": f"Edit #{index} is missing yang_path",
                }

            yang_path = str(edit.get("yang_path")).strip()
            module_name = yang_path.lstrip("/").split("/")[0]
            if not yang_path.startswith("/"):
                return "error", {
                    "status": "error",
                    "error_category": "schema",
                    "error_code": "PLAN_BAD_EDIT_PATH",
                    "error_type": "PLAN_BAD_EDIT_PATH",
                    "error_tag": "invalid-value",
                    "error_message": f"Invalid yang_path: {yang_path}",
                }
            if module_name and module_name not in profile_modules:
                schema_confidence = "low"
                warnings.append(
                    {
                        "code": "SCHEMA_UNKNOWN_MODULE",
                        "message": f"Module '{module_name}' missing from cached YANG modules",
                        "path": yang_path,
                    }
                )
            schema_checks.append(
                {
                    "code": "PATH_PARSE",
                    "result": "pass",
                    "path": yang_path,
                }
            )

        if plan_scope not in {"candidate", "running", "startup"}:
            return "error", {
                "status": "error",
                "error_category": "schema",
                "error_code": "PLAN_BAD_SCOPE",
                "error_type": "PLAN_BAD_SCOPE",
                "error_tag": "invalid-value",
                "error_message": "Unsupported datastore scope",
            }

        if plan_scope == "candidate" and not candidate:
            warnings.append(
                {
                    "code": "CAPABILITY_MISMATCH",
                    "message": "Candidate datastore not advertised",
                    "path": plan_scope,
                }
            )
        if plan_scope == "running" and not writable_running:
            warnings.append(
                {
                    "code": "CAPABILITY_MISMATCH",
                    "message": "Writable-running not advertised",
                    "path": plan_scope,
                }
            )

        if warnings:
            schema_confidence = "low"

        plan_id = f"plan://{session.target_ref}/{uuid.uuid4().hex[:8]}"
        self.plans[plan_id] = {
            "plan_id": plan_id,
            "session_ref": session_ref,
            "target_ref": session.target_ref,
            "plan_scope": plan_scope,
            "intent": intent,
            "edits": edits,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "confidence": schema_confidence,
            "schema_checks": schema_checks,
            "plan_status": "ready_to_validate",
            "validation": {"checked": False},
            "warnings": warnings,
        }

        return "ok", {
            "plan_id": plan_id,
            "plan_status": "ready_to_validate",
            "created_utc": self.plans[plan_id]["created_utc"],
            "schema_checks": schema_checks,
            "validation_warnings": warnings,
            "confidence": schema_confidence,
        }

    def validate_plan(self, session_ref: str, plan_id: str) -> tuple[str, dict[str, Any]]:
        plan = self.plans.get(plan_id)
        if not plan or plan.get("session_ref") != session_ref:
            return "error", {
                "status": "error",
                "error_category": "policy",
                "error_code": "PLAN_NOT_FOUND",
                "error_type": "PLAN_NOT_FOUND",
                "error_tag": "unknown-element",
                "error_message": "Plan not found for this session",
            }

        session = self._require_session(session_ref)
        if session.backend != "fixture":
            return "error", {
                "status": "error",
                "error_category": "policy",
                "error_code": "LIVE_WRITE_UNSUPPORTED",
                "error_type": "LIVE_WRITE_UNSUPPORTED",
                "error_tag": "operation-not-supported",
                "error_message": "Live NETCONF targets are read-only in the current implementation",
            }
        profile = self._load_profile(session.profile)
        if not profile:
            return "error", self._protocol_error("PROFILE_EXPIRED", "Profile no longer available")

        candidate = self._has_capability(profile, "urn:ietf:params:netconf:capability:candidate:1.0")
        writable_running = self._has_capability(profile, "urn:ietf:params:netconf:capability:writable-running:1.0")
        denied_paths = set(profile.data.get("nacm", {}).get("denied_paths", []))

        capability_checks = []
        validation_warnings = []
        plan_scope = plan.get("plan_scope", "running")
        blocked = False

        if plan_scope == "candidate" and candidate:
            capability_checks.append({"code": "CANDIDATE_OK", "result": "pass"})
        elif plan_scope == "candidate" and not candidate:
            capability_checks.append({"code": "CANDIDATE_MISSING", "result": "fail"})
            blocked = True
        elif plan_scope == "running" and writable_running:
            capability_checks.append({"code": "WRITABLE_RUNNING_OK", "result": "pass"})
        elif plan_scope == "running" and not writable_running:
            capability_checks.append({"code": "WRITABLE_RUNNING_MISSING", "result": "fail"})
            blocked = True
        else:
            capability_checks.append({"code": "RUNNING_UNKNOWN", "result": "warn"})

        for edit in plan.get("edits", []):
            yang_path = edit.get("yang_path")
            if yang_path in denied_paths:
                blocked = True
                validation_warnings.append(
                    {
                        "code": "NACM_ACCESS_DENIED",
                        "message": "Edit path is denied by NACM",
                        "path": yang_path,
                    }
                )

        plan_status = "blocked" if blocked else "ready_to_execute"
        plan["validation"] = {
            "checked": True,
            "capability_checks": capability_checks,
            "schema_checks": plan.get("schema_checks", []),
            "validation_warnings": validation_warnings,
            "capability_gates": candidate,
            "nacm_mode": profile.data.get("nacm", {}).get("mode", "unknown"),
        }
        plan["plan_status"] = plan_status
        plan["warnings"] = validation_warnings

        return "ok", {
            "plan_id": plan_id,
            "plan_status": plan_status,
            "schema_checks": plan.get("schema_checks", []),
            "capability_checks": capability_checks,
            "validation_warnings": validation_warnings,
            "confidence": "high" if not validation_warnings and plan.get("confidence") == "high" else "low",
        }

    def apply_plan(
        self,
        session_ref: str,
        *,
        plan_id: str,
        confirmation_token: str | None = None,
        policy_approval: dict[str, Any] | None = None,
        lock_strategy: str = "explicit",
        commit_mode: str = "normal",
        confirmed_timeout_s: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        del confirmed_timeout_s
        if not confirmation_token or not policy_approval:
            return "error", {
                "status": "error",
                "error_category": "policy",
                "error_code": "CONFIRMATION_REQUIRED",
                "error_type": "CONFIRMATION_REQUIRED",
                "error_tag": "access-denied",
                "error_message": "confirmation_token and policy_approval are required for write execution",
            }

        session = self._require_session(session_ref)
        if session.backend != "fixture":
            return "error", {
                "status": "error",
                "error_category": "policy",
                "error_code": "LIVE_WRITE_UNSUPPORTED",
                "error_type": "LIVE_WRITE_UNSUPPORTED",
                "error_tag": "operation-not-supported",
                "error_message": "Live NETCONF targets are read-only in the current implementation",
            }
        profile = self._load_profile(session.profile)
        if not profile:
            return "error", self._protocol_error("PROFILE_EXPIRED", "Profile no longer available")

        plan = self.plans.get(plan_id)
        if not plan or plan.get("session_ref") != session_ref:
            return "error", {
                "status": "error",
                "error_category": "policy",
                "error_code": "PLAN_NOT_FOUND",
                "error_type": "PLAN_NOT_FOUND",
                "error_message": "Plan not found for this session",
            }

        if plan.get("plan_status") != "ready_to_execute":
            validate_status, validation = self.validate_plan(session_ref, plan_id)
            if validate_status == "error":
                return validate_status, validation
            if validation.get("plan_status") != "ready_to_execute":
                return "error", {
                    "status": "error",
                    "error_category": "policy",
                    "error_code": "PLAN_NOT_APPROVED",
                    "error_type": "PLAN_NOT_APPROVED",
                    "error_message": "Plan must validate successfully before execution",
                }

        candidate = self._has_capability(profile, "urn:ietf:params:netconf:capability:candidate:1.0")
        writable_running = self._has_capability(profile, "urn:ietf:params:netconf:capability:writable-running:1.0")
        confirmed_capability = self._has_capability(profile, "urn:ietf:params:netconf:capability:confirmed-commit:1.0")

        plan_scope = plan["plan_scope"]
        if plan_scope == "running" and not writable_running and not candidate:
            return "error", {
                "status": "error",
                "error_category": "policy",
                "error_code": "DATASTORE_NOT_WRITABLE",
                "error_type": "DATASTORE_NOT_WRITABLE",
                "error_message": "Selected datastore is not writable on this device",
            }

        if lock_strategy == "explicit":
            conflict = self._active_lock_conflict(profile, plan_scope, session_ref)
            if conflict:
                return "error", {
                    "status": "error",
                    "error_category": "concurrency",
                    "error_code": "LOCK_HELD",
                    "error_type": "LOCK_HELD",
                    "error_message": f"Datastore {plan_scope} already held by {conflict}",
                }

        if commit_mode == "confirmed" and not confirmed_capability:
            return "error", {
                "status": "error",
                "error_category": "policy",
                "error_code": "CONFIRMED_COMMIT_UNSUPPORTED",
                "error_type": "CONFIRMED_COMMIT_UNSUPPORTED",
                "error_message": "Device does not advertise confirmed-commit capability",
                "limitations": [
                    "confirmed-commit requested but unsupported",
                    "rollback is not safe on this target",
                ],
            }

        transaction_id = f"tx://{session.target_ref}/{uuid.uuid4().hex[:8]}"
        post_verify_ref = f"verify://{session.target_ref}/{uuid.uuid4().hex[:8]}"
        lock_state = {
            "datastore": plan_scope,
            "held_by": session_ref if lock_strategy == "explicit" else None,
            "lock_strategy": lock_strategy,
        }

        if commit_mode == "confirmed":
            rollback_id = f"rollback://{session.target_ref}/{uuid.uuid4().hex[:8]}"
            self.pending_rollbacks[rollback_id] = {
                "session_ref": session_ref,
                "target_ref": session.target_ref,
                "plan_id": plan_id,
                "plan_scope": plan_scope,
                "issued_at": datetime.now(timezone.utc).isoformat(),
            }
            plan["applied"] = True
            return "ok", {
                "plan_id": plan_id,
                "transaction_id": transaction_id,
                "commit_outcome": "pending_commit",
                "lock_state": lock_state,
                "rollback_plan": {
                    "rollback_id": rollback_id,
                    "strategy": "confirmed-revert",
                    "revert_to": f"state://pre-commit/{session.target_ref}",
                },
                "post_commit_checks": {
                    "required": [edit.get("yang_path") for edit in plan.get("edits", [])],
                    "evidence_ref": post_verify_ref,
                },
                "verified_with": ["capability-check", "plan-validation", "confirmed-commit"],
            }

        plan["applied"] = True
        return "ok", {
            "plan_id": plan_id,
            "transaction_id": transaction_id,
            "commit_outcome": "committed",
            "lock_state": lock_state,
            "post_commit_checks": {
                "required": [edit.get("yang_path") for edit in plan.get("edits", [])],
                "evidence_ref": post_verify_ref,
            },
            "verified_with": ["capability-check", "plan-validation", "direct-write"],
        }

    def rollback(self, session_ref: str, *, rollback_id: str, confirmation_token: str | None = None, policy_approval: dict[str, Any] | None = None):
        if not confirmation_token or not policy_approval:
            return "error", {
                "status": "error",
                "error_category": "policy",
                "error_code": "CONFIRMATION_REQUIRED",
                "error_type": "CONFIRMATION_REQUIRED",
                "error_message": "confirmation_token and policy_approval are required for rollback",
            }

        pending = self.pending_rollbacks.get(rollback_id)
        if not pending or pending.get("session_ref") != session_ref:
            return "error", {
                "status": "error",
                "error_category": "policy",
                "error_code": "ROLLBACK_NOT_FOUND",
                "error_type": "ROLLBACK_NOT_FOUND",
                "error_message": "No matching rollback action was found",
            }

        session = self._require_session(session_ref)
        if session.backend != "fixture":
            return "error", {
                "status": "error",
                "error_category": "policy",
                "error_code": "LIVE_WRITE_UNSUPPORTED",
                "error_type": "LIVE_WRITE_UNSUPPORTED",
                "error_tag": "operation-not-supported",
                "error_message": "Live NETCONF targets are read-only in the current implementation",
            }
        profile = self._load_profile(session.profile)
        if not profile:
            return "error", self._protocol_error("PROFILE_EXPIRED", "Profile no longer available")

        confirmed_capability = self._has_capability(profile, "urn:ietf:params:netconf:capability:confirmed-commit:1.0")
        if not confirmed_capability:
            return "error", {
                "status": "error",
                "error_category": "policy",
                "error_code": "ROLLBACK_UNSUPPORTED",
                "error_type": "ROLLBACK_UNSUPPORTED",
                "error_message": "Rollback path requires confirmed-commit capability",
                "limitations": ["rollback unavailable on this target"],
            }

        del self.pending_rollbacks[rollback_id]
        return "ok", {
            "rollback_id": rollback_id,
            "plan_id": pending["plan_id"],
            "rollback_outcome": "applied",
            "evidence_ref": f"verify://rollback/{session.target_ref}/{uuid.uuid4().hex[:8]}",
        }

    def get_monitoring(self, session_ref: str, scope: str = "all") -> tuple[str, dict[str, Any]]:
        session = self._require_session(session_ref)
        if session.backend == "live-ssh":
            target = self._target_by_ref(session.target_ref)
            try:
                return "ok", self.live_client.get_monitoring(target, session, scope=scope)
            except LiveNetconfError as exc:
                return "error", exc.payload
        profile = self._load_profile(session.profile)
        if not profile:
            return "error", self._protocol_error("PROFILE_EXPIRED", "Profile no longer available")

        monitoring = profile.data.get("monitoring", {})
        return "ok", {
            "scope": scope,
            "sessions": monitoring.get("sessions", []),
            "locks": monitoring.get("locks", []),
            "datastore_health": monitoring.get("datastore_health", {}),
            "transport_stats": monitoring.get("transport_stats", {}),
        }

    def datastore_get(
        self,
        session_ref: str,
        datastore: str = "running",
        *,
        xpath: str | None = None,
        subtree: dict[str, Any] | None = None,
        with_defaults: str = "explicit",
        module_filter: list[str] | None = None,
        strict_config: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        session = self._require_session(session_ref)
        if session.backend == "live-ssh":
            target = self._target_by_ref(session.target_ref)
            try:
                payload = self.live_client.datastore_get(
                    target,
                    session,
                    datastore=datastore,
                    xpath=xpath,
                    subtree=subtree,
                    with_defaults=with_defaults,
                    strict_config=strict_config,
                )
            except LiveNetconfError as exc:
                return "error", exc.payload
            return "ok", payload

        del with_defaults, strict_config
        profile = self._load_profile(session.profile)
        if not profile:
            return "error", self._protocol_error("PROFILE_EXPIRED", "Profile no longer available")

        nacm = profile.data.get("nacm", {})
        denials = nacm.get("denied_paths", [])
        data = profile.data.get("datastores", {}).get(datastore, {})

        if not data:
            return "error", self._protocol_error("BAD_DATASTORE", "Datastore unavailable in fixture")

        if xpath and xpath in denials:
            return "error", {
                "status": "error",
                "error_category": "nacm",
                "error_type": "ACCESS_DENIED",
                "error_code": "NACM_ACCESS_DENIED",
                "error_tag": "access-denied",
                "error_message": "Path visibility is restricted by NACM",
            },

        selected = data
        if xpath:
            selected = xpath_filter(data, xpath)
        elif subtree:
            selected = subtree

        if xpath and selected is None:
            return "error", self._protocol_error("NOT_FOUND", "Requested path not found")

        selected = filters.with_module_filter(selected, module_filter)

        return "ok", {
            "resource": {
                "datastore": datastore,
                "filter": xpath or subtree or "all",
            },
            "nacm_visibility": "full" if nacm.get("mode") == "open" else "partial",
            "value": selected,
            "source_metadata": {
                "profile": session.profile,
            },
        }

    def _require_session(self, session_ref: str) -> Session:
        if session_ref not in self.sessions:
            raise KeyError("Session not found")
        return self.sessions[session_ref]

    def _load_profile(self, profile_key: str):
        try:
            return self.repository.profile(profile_key)
        except FileNotFoundError:
            return None

    @staticmethod
    def _has_capability(profile: SimulatedProfile, capability_uri: str) -> bool:
        return capability_uri in profile.data.get("hello", {}).get("capabilities", [])

    @staticmethod
    def _active_lock_conflict(profile: SimulatedProfile, datastore: str, session_ref: str) -> str | None:
        locks = profile.data.get("monitoring", {}).get("locks", [])
        for lock in locks:
            if not isinstance(lock, dict):
                continue
            if lock.get("datastore") != datastore:
                continue
            holder = lock.get("held_by", "")
            if not holder:
                continue
            holder_lc = str(holder)
            if holder_lc == session_ref or holder_lc.endswith("/none"):
                continue
            return holder_lc
        return None

    def _target_by_ref(self, target_ref: str) -> dict[str, Any]:
        for item in self.repository.inventory():
            if item["target_ref"] == target_ref:
                return item
        raise KeyError(f"target not found: {target_ref}")

    def _protocol_error(self, code: str, message: str):
        return {
            "status": "error",
            "error_category": "protocol",
            "error_code": code,
            "error_type": code,
            "error_tag": "operation-failed",
            "error_message": message,
        }
