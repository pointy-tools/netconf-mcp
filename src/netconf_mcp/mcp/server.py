"""Read-only MCP server implementation for fixture-backed NETCONF discovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from netconf_mcp.core.contracts import (
    Envelope,
    READ_ONLY_PROMPTS,
    READ_ONLY_RESOURCE_URIS,
    READ_ONLY_TOOLSET,
    GUARDED_WRITE_TOOLSET,
)
from netconf_mcp.protocol.engine import NetconfReadEngine
from netconf_mcp.utils.redact import redact_mapping

try:
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover - fallback for environments without MCP SDK
    class FastMCP:
        def __init__(self, name: str):
            self.name = name
            self._tools: dict[str, Any] = {}
            self._resources: dict[str, Any] = {}
            self._prompts: dict[str, Any] = {}

        def tool(self, name: str):
            def decorator(fn):
                self._tools[name] = fn
                return fn

            return decorator

        def resource(self, uri: str):
            def decorator(fn):
                self._resources[uri] = fn
                return fn

            return decorator

        def prompt(self, name: str):
            def decorator(fn):
                self._prompts[name] = fn
                return fn

            return decorator

        def run(self, *args, **kwargs):
            return None


@dataclass
class MCPManifest:
    tools: list[str]
    resources: list[str]
    prompts: list[str]


class NetconfMCPServer:
    def __init__(self, fixture_root: Path, *, inventory_path: Path | None = None, live_client: Any | None = None):
        self.fixture_root = Path(fixture_root)
        self.engine = NetconfReadEngine(self.fixture_root, inventory_path=inventory_path, live_client=live_client)
        self.server = FastMCP("netconf-mcp")
        self.manifest = MCPManifest(
            tools=list(READ_ONLY_TOOLSET) + list(GUARDED_WRITE_TOOLSET),
            resources=list(READ_ONLY_RESOURCE_URIS),
            prompts=list(READ_ONLY_PROMPTS),
        )
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.server.tool("inventory.list_targets")
        def _inventory_list_targets(arguments: dict[str, Any] | None = None):
            """List available targets and basic facts without inferring anything beyond returned fields."""
            arguments = arguments or {}
            request = self._envelope_request("inventory.list_targets", arguments)
            payload = self.engine.list_targets(
                filter=request["arguments"].get("filter"),
                include=request["arguments"].get("include"),
            )
            return self._ok(
                request["operation_id"],
                "inventory.list_targets",
                request["target_ref"],
                payload,
            )

        @self.server.tool("netconf.open_session")
        def _open_session(arguments: dict[str, Any] | None = None):
            """Open a NETCONF session for a target before issuing reads or guarded workflow operations."""
            arguments = arguments or {}
            request = self._envelope_request("netconf.open_session", arguments)
            args = request["arguments"]
            status, payload = self.engine.open_session(
                target_ref=request["target_ref"],
                credential_ref=args.get("credential_ref"),
                framing=args.get("framing", "auto"),
                hostkey_policy=args.get("hostkey_policy", "strict"),
                connect_timeout_ms=args.get("connect_timeout_ms"),
            )
            if status == "error":
                return self._error(
                    request["operation_id"],
                    "netconf.open_session",
                    request["target_ref"],
                    payload,
                )
            return self._ok(
                request["operation_id"],
                "netconf.open_session",
                request["target_ref"],
                payload,
            )

        @self.server.tool("netconf.discover_capabilities")
        def _discover_capabilities(arguments: dict[str, Any] | None = None):
            """Return advertised NETCONF capabilities; callers should quote capability strings verbatim."""
            arguments = arguments or {}
            request = self._envelope_request("netconf.discover_capabilities", arguments)
            status, payload = self.engine.discover_capabilities(request["session_ref"])
            if status == "error":
                return self._error(
                    request["operation_id"],
                    "netconf.discover_capabilities",
                    request["target_ref"],
                    payload,
                    session_ref=request["session_ref"],
                )
            return self._ok(
                request["operation_id"],
                "netconf.discover_capabilities",
                request["target_ref"],
                payload,
                session_ref=request["session_ref"],
            )

        @self.server.tool("yang.get_library")
        def _get_library(arguments: dict[str, Any] | None = None):
            """Return YANG library/module inventory; callers should report module names and revisions exactly as returned."""
            arguments = arguments or {}
            request = self._envelope_request("yang.get_library", arguments)
            status, payload = self.engine.get_library(request["session_ref"])
            if status == "error":
                return self._error(
                    request["operation_id"],
                    "yang.get_library",
                    request["target_ref"],
                    payload,
                    session_ref=request["session_ref"],
                )
            envelope = self._ok(
                request["operation_id"],
                "yang.get_library",
                request["target_ref"],
                payload,
                session_ref=request["session_ref"],
            )
            if payload.get("completeness") == "low":
                envelope["confidence"] = "low"
                envelope["warnings"].append(
                    {
                        "code": "SCHEMA_INCOMPLETE",
                        "message": "YANG library payload is partial",
                    }
                )
            return envelope

        @self.server.tool("netconf.get_monitoring")
        def _monitoring(arguments: dict[str, Any] | None = None):
            """Return NETCONF monitoring data; summarize conservatively and preserve returned identifiers verbatim."""
            arguments = arguments or {}
            request = self._envelope_request("netconf.get_monitoring", arguments)
            args = request["arguments"]
            status, payload = self.engine.get_monitoring(
                request["session_ref"],
                scope=args.get("scope", "all"),
            )
            if status == "error":
                return self._error(
                    request["operation_id"],
                    "netconf.get_monitoring",
                    request["target_ref"],
                    payload,
                    session_ref=request["session_ref"],
                )
            return self._ok(
                request["operation_id"],
                "netconf.get_monitoring",
                request["target_ref"],
                payload,
                session_ref=request["session_ref"],
            )

        @self.server.tool("datastore.get")
        def _get_datastore(arguments: dict[str, Any] | None = None):
            """Read structured operational or mixed datastore data.

            Treat returned values as authoritative structured output. Quote values verbatim when summarizing.
            Do not collapse, deduplicate, normalize, or infer equivalence between similar-looking entries unless
            the raw payload explicitly proves it.
            """
            return self._datastore_read("datastore.get", arguments, strict_config=False)

        @self.server.tool("datastore.get_config")
        def _get_config(arguments: dict[str, Any] | None = None):
            """Read structured configuration data from a datastore.

            Treat returned values as authoritative structured output. Quote values verbatim when summarizing.
            Do not collapse, deduplicate, normalize, or infer equivalence between similar-looking entries unless
            the raw payload explicitly proves it. If the response is large or truncated, say so before drawing conclusions.
            """
            return self._datastore_read("datastore.get_config", arguments, strict_config=True)

        @self.server.tool("config.plan_edit")
        def _plan_edit(arguments: dict[str, Any] | None = None):
            arguments = arguments or {}
            request = self._envelope_request("config.plan_edit", arguments)
            args = request["arguments"]
            self._audit_event(
                request["operation_id"],
                "config.plan_edit",
                request["target_ref"],
                {
                    "stage": "plan_attempt",
                    "session_ref": request["session_ref"],
                    "plan_scope": args.get("plan_scope", "running"),
                    "intent": args.get("intent", "merge"),
                    "edit_count": len(args.get("edits") or []),
                },
            )

            status, payload = self.engine.plan_edit(
                request["session_ref"],
                edits=args.get("edits"),
                plan_scope=args.get("plan_scope", "running"),
                intent=args.get("intent", "merge"),
                safety_profile_ref=args.get("safety_profile_ref"),
            )
            if status == "error":
                self._audit_event(
                    request["operation_id"],
                    "config.plan_edit",
                    request["target_ref"],
                    {
                        "stage": "plan_blocked",
                        "error_code": payload.get("error_code"),
                    },
                )
                return self._error(
                    request["operation_id"],
                    "config.plan_edit",
                    request["target_ref"],
                    payload,
                    session_ref=request["session_ref"],
                )

            self._audit_event(
                request["operation_id"],
                "config.plan_edit",
                request["target_ref"],
                {
                    "stage": "plan_ready",
                    "plan_id": payload.get("plan_id"),
                },
            )
            return self._ok(
                request["operation_id"],
                "config.plan_edit",
                request["target_ref"],
                payload,
                session_ref=request["session_ref"],
                confidence=payload.get("confidence", "medium"),
            )

        @self.server.tool("config.validate_plan")
        def _validate_plan(arguments: dict[str, Any] | None = None):
            arguments = arguments or {}
            request = self._envelope_request("config.validate_plan", arguments)
            args = request["arguments"]
            self._audit_event(
                request["operation_id"],
                "config.validate_plan",
                request["target_ref"],
                {
                    "stage": "validate_attempt",
                    "session_ref": request["session_ref"],
                    "plan_id": args.get("plan_id"),
                },
            )

            status, payload = self.engine.validate_plan(
                request["session_ref"],
                plan_id=args.get("plan_id"),
            )
            if status == "error":
                self._audit_event(
                    request["operation_id"],
                    "config.validate_plan",
                    request["target_ref"],
                    {
                        "stage": "validate_blocked",
                        "error_code": payload.get("error_code"),
                    },
                )
                return self._error(
                    request["operation_id"],
                    "config.validate_plan",
                    request["target_ref"],
                    payload,
                    session_ref=request["session_ref"],
                )

            self._audit_event(
                request["operation_id"],
                "config.validate_plan",
                request["target_ref"],
                {
                    "stage": "validate_complete",
                    "plan_id": args.get("plan_id"),
                    "plan_status": payload.get("plan_status"),
                },
            )
            return self._ok(
                request["operation_id"],
                "config.validate_plan",
                request["target_ref"],
                payload,
                session_ref=request["session_ref"],
                confidence=payload.get("confidence", "medium"),
            )

        @self.server.tool("config.apply_plan")
        def _apply_plan(arguments: dict[str, Any] | None = None):
            arguments = arguments or {}
            request = self._envelope_request("config.apply_plan", arguments)
            args = request["arguments"]
            confirmation_token = args.get("confirmation_token")
            policy_approval = args.get("policy_approval")
            self._audit_event(
                request["operation_id"],
                "config.apply_plan",
                request["target_ref"],
                {
                    "stage": "apply_attempt",
                    "session_ref": request["session_ref"],
                    "plan_id": args.get("plan_id"),
                    "has_confirmation_token": bool(confirmation_token),
                    "has_policy_approval": bool(policy_approval),
                    "commit_mode": args.get("commit_mode", "normal"),
                },
            )

            status, payload = self.engine.apply_plan(
                request["session_ref"],
                plan_id=args.get("plan_id"),
                confirmation_token=confirmation_token,
                policy_approval=policy_approval,
                lock_strategy=args.get("lock_strategy", "explicit"),
                commit_mode=args.get("commit_mode", "normal"),
                confirmed_timeout_s=args.get("confirmed_timeout_s"),
            )
            if status == "error":
                self._audit_event(
                    request["operation_id"],
                    "config.apply_plan",
                    request["target_ref"],
                    {
                        "stage": "apply_blocked",
                        "error_code": payload.get("error_code"),
                        "has_confirmation_token": bool(confirmation_token),
                        "has_policy_approval": bool(policy_approval),
                    },
                )
                return self._error(
                    request["operation_id"],
                    "config.apply_plan",
                    request["target_ref"],
                    payload,
                    session_ref=request["session_ref"],
                )

            self._audit_event(
                request["operation_id"],
                "config.apply_plan",
                request["target_ref"],
                {
                    "stage": "apply_executed",
                    "plan_id": args.get("plan_id"),
                    "commit_outcome": payload.get("commit_outcome"),
                    "has_confirmation_token": True,
                    "has_policy_approval": True,
                },
            )
            return self._ok(
                request["operation_id"],
                "config.apply_plan",
                request["target_ref"],
                payload,
                session_ref=request["session_ref"],
            )

        @self.server.tool("config.rollback")
        def _rollback(arguments: dict[str, Any] | None = None):
            arguments = arguments or {}
            request = self._envelope_request("config.rollback", arguments)
            args = request["arguments"]
            confirmation_token = args.get("confirmation_token")
            policy_approval = args.get("policy_approval")
            self._audit_event(
                request["operation_id"],
                "config.rollback",
                request["target_ref"],
                {
                    "stage": "rollback_attempt",
                    "session_ref": request["session_ref"],
                    "rollback_id": args.get("rollback_id"),
                    "has_confirmation_token": bool(confirmation_token),
                    "has_policy_approval": bool(policy_approval),
                },
            )

            status, payload = self.engine.rollback(
                request["session_ref"],
                rollback_id=args.get("rollback_id"),
                confirmation_token=confirmation_token,
                policy_approval=policy_approval,
            )
            if status == "error":
                self._audit_event(
                    request["operation_id"],
                    "config.rollback",
                    request["target_ref"],
                    {
                        "stage": "rollback_blocked",
                        "error_code": payload.get("error_code"),
                        "has_confirmation_token": bool(confirmation_token),
                        "has_policy_approval": bool(policy_approval),
                    },
                )
                return self._error(
                    request["operation_id"],
                    "config.rollback",
                    request["target_ref"],
                    payload,
                    session_ref=request["session_ref"],
                )

            self._audit_event(
                request["operation_id"],
                "config.rollback",
                request["target_ref"],
                {
                    "stage": "rollback_executed",
                    "rollback_id": args.get("rollback_id"),
                    "rollback_outcome": payload.get("rollback_outcome"),
                },
            )
            return self._ok(
                request["operation_id"],
                "config.rollback",
                request["target_ref"],
                payload,
                session_ref=request["session_ref"],
            )

        @self.server.resource("targets://inventory")
        def _resource_inventory() -> dict:
            return self._ok("resource://inventory", "target://inventory", "resource", self.engine.list_targets())["data"]

        @self.server.resource("target://{target_ref}/facts")
        def _resource_facts(target_ref: str) -> dict[str, Any]:
            return {
                "resource_id": f"target://{target_ref}/facts",
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                "evidence_refs": [f"facts://{target_ref}"],
                "confidence": "high",
                "schema_refs": [],
                "data": {
                    "target_ref": target_ref,
                },
            }

        @self.server.resource("target://{target_ref}/capabilities")
        def _resource_capabilities(target_ref: str) -> dict[str, Any]:
            # convenience for read-only resource tests; returns an empty shell when no session exists
            return {
                "resource_id": f"target://{target_ref}/capabilities",
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                "evidence_refs": [f"capability-cache://{target_ref}"],
                "confidence": "medium",
                "schema_refs": [],
                "data": {
                    "target_ref": target_ref,
                    "capabilities": [],
                },
            }

        @self.server.resource("target://{target_ref}/yang-library")
        def _resource_yang_library(target_ref: str) -> dict[str, Any]:
            return {
                "resource_id": f"target://{target_ref}/yang-library",
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                "evidence_refs": [f"yanglib://{target_ref}"],
                "confidence": "low",
                "schema_refs": [],
                "data": {
                    "target_ref": target_ref,
                    "module_set": [],
                },
            }

        @self.server.resource("target://{target_ref}/datastores/{name}")
        def _resource_datastore(target_ref: str, name: str) -> dict[str, Any]:
            return {
                "resource_id": f"target://{target_ref}/datastores/{name}",
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                "evidence_refs": [f"datastore-cache://{target_ref}/{name}"],
                "confidence": "medium",
                "schema_refs": [],
                "data": {
                    "target_ref": target_ref,
                    "datastore": name,
                },
            }

        @self.server.resource("target://{target_ref}/session-state")
        def _resource_session_state(target_ref: str) -> dict[str, Any]:
            return {
                "resource_id": f"target://{target_ref}/session-state",
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                "evidence_refs": [f"session-state://{target_ref}"],
                "confidence": "medium",
                "schema_refs": [],
                "data": {
                    "target_ref": target_ref,
                    "active": False,
                },
            }

        @self.server.prompt("discover-device-safely")
        def _prompt_discover(target_ref: str, session_ref: str, include_yang_library: bool = True) -> str:
            return (
                "Use approved read-only flows only. Target=" + target_ref
                + f", include_yang_library={include_yang_library}"
            )

        @self.server.prompt("inspect-operational-state")
        def _prompt_operational(target_ref: str, session_ref: str, object_path: str) -> str:
            return (
                f"Inspect operational read for {target_ref} object={object_path}.\n"
                "Use datastore.get with requested_mode read and a precise xpath filter."
            )

        @self.server.prompt("review-yang-capabilities")
        def _prompt_review(target_ref: str, session_ref: str, gap_tolerance: str = "low") -> str:
            return (
                f"Review yang capabilities for {target_ref}. gap_tolerance={gap_tolerance}. "
                "Prefer evidence-backed interpretation only."
            )

        @self.server.prompt("netconf-data-fidelity")
        def _prompt_data_fidelity(target_ref: str, session_ref: str, scope: str = "structured-data") -> str:
            return (
                f"Review returned NETCONF data for {target_ref}. scope={scope}. "
                "Treat the payload as authoritative structured output. Quote values verbatim, avoid paraphrasing or "
                "deduplicating similar-looking entries, and explicitly mention if data is partial, truncated, or "
                "based on a narrowed filter."
            )

    def _datastore_read(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
        *,
        strict_config: bool,
    ):
        arguments = arguments or {}
        request = self._envelope_request(tool_name, arguments)
        args = request["arguments"]
        validation_error = self._validate_datastore_arguments(args)
        if validation_error:
            return self._error(
                request["operation_id"],
                tool_name,
                request["target_ref"],
                validation_error,
                session_ref=request["session_ref"],
            )

        xpath = args.get("xpath") or args.get("xpath_filter")
        try:
            status, payload = self.engine.datastore_get(
                request["session_ref"],
                datastore=args.get("datastore", "running"),
                xpath=xpath,
                subtree=args.get("subtree"),
                with_defaults=args.get("with_defaults", "explicit"),
                module_filter=args.get("module_filter"),
                strict_config=strict_config,
            )
        except KeyError:
            return self._error(
                request["operation_id"],
                tool_name,
                request["target_ref"],
                {
                    "status": "error",
                    "error_category": "transport",
                    "error_code": "SESSION_UNKNOWN",
                    "error_type": "SESSION_UNKNOWN",
                    "error_message": "Unknown session reference",
                },
            )

        if status == "error":
            return self._error(
                request["operation_id"],
                tool_name,
                request["target_ref"],
                payload,
                session_ref=request["session_ref"],
            )
        payload = self._guard_datastore_payload(payload)

        if args.get("filter"):
            self._audit_event(request["operation_id"], request["tool"], request["target_ref"], {
                "filter": args.get("filter"),
            })
        return self._ok(
            request["operation_id"],
            tool_name,
            request["target_ref"],
            payload,
            session_ref=request["session_ref"],
        )

    def _envelope_request(self, tool: str, payload: dict[str, Any]) -> dict[str, Any]:
        arguments = payload.get("arguments", payload)
        target_ref = payload.get("target_ref")
        if target_ref is None:
            target_ref = arguments.get("target_ref")
        session_ref = payload.get("session_ref")
        if session_ref is None:
            session_ref = arguments.get("session_ref")

        return {
            "operation_id": payload.get("operation_id") or str(uuid4()),
            "tool": tool,
            "target_ref": target_ref,
            "session_ref": session_ref,
            "requested_mode": payload.get("requested_mode", "read"),
            "arguments": arguments,
        }

    def _ok(self, operation_id: str, tool: str, target_ref: str | None, data: dict[str, Any], *, session_ref: str | None = None, confidence: str = "high"):
        return {
            "status": "ok",
            "policy_decision": "allowed",
            "tool": tool,
            "operation_id": operation_id,
            "session_ref": session_ref,
            "data": redact_mapping(data),
            "schema_refs": data.get("schema_refs", []),
            "evidence_refs": [
                f"session://{target_ref or 'unknown'}",
                f"tool://{tool}",
            ],
            "confidence": confidence,
            "warnings": [],
            "next_safe_action": None,
            "error": None,
        }

    def _error(self, operation_id: str, tool: str, target_ref: str | None, error: dict[str, Any], *, session_ref: str | None = None):
        status = error.get("status", "error")
        policy_decision = "blocked" if error.get("error_category") in {"nacm", "policy"} else "needs_confirmation"
        if error.get("error_category") == "transport":
            policy_decision = "blocked"
        return {
            "status": status,
            "policy_decision": policy_decision,
            "tool": tool,
            "operation_id": operation_id,
            "session_ref": session_ref,
            "data": {},
            "schema_refs": [],
            "evidence_refs": [f"error://{tool}"],
            "confidence": "low",
            "warnings": [],
            "next_safe_action": "Retry with valid session and available fixture profile",
            "error": {
                "error_category": error.get("error_category", "protocol"),
                "error_type": error.get("error_type", "UNSPECIFIED"),
                "error_code": error.get("error_code", "UNSPECIFIED"),
                "error_tag": error.get("error_tag"),
                "error_app_tag": error.get("error_app_tag"),
                "error_path": error.get("error_path"),
                "retryable": error.get("error_category") in {"transport", "protocol"},
                "retry_backoff_ms": 0,
                "suggested_next_steps": error.get("suggested_next_steps", ["check fixture profile"]),
            },
        }

    def _audit_event(self, operation_id: str, tool: str, target_ref: str | None, context: dict[str, Any]) -> None:
        # placeholder for audit stream: keep redacted payload only
        self._audit_log = getattr(self, "_audit_log", [])
        self._audit_log.append(
            {
                "operation_id": operation_id,
                "tool": tool,
                "target_ref": target_ref,
                "context": redact_mapping(context),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
        )

    def get_audit_log(self):
        return list(getattr(self, "_audit_log", []))

    @staticmethod
    def _validate_datastore_arguments(args: dict[str, Any]) -> dict[str, Any] | None:
        xpath = args.get("xpath")
        xpath_filter = args.get("xpath_filter")
        subtree = args.get("subtree")
        provided = [
            name
            for name, value in (
                ("xpath", xpath),
                ("xpath_filter", xpath_filter),
                ("subtree", subtree),
            )
            if value not in (None, "")
        ]
        if xpath and xpath_filter and xpath != xpath_filter:
            return {
                "status": "error",
                "error_category": "protocol",
                "error_type": "BAD_INPUT",
                "error_code": "FILTER_CONFLICT",
                "error_tag": "invalid-value",
                "error_message": "Provide only one filter path, not both xpath and xpath_filter with different values",
                "suggested_next_steps": ["Use xpath or xpath_filter with the same value", "Remove the conflicting filter argument"],
            }
        if len(provided) > 1 and not (len(provided) == 2 and set(provided) == {"xpath", "xpath_filter"} and xpath == xpath_filter):
            return {
                "status": "error",
                "error_category": "protocol",
                "error_type": "BAD_INPUT",
                "error_code": "FILTER_CONFLICT",
                "error_tag": "invalid-value",
                "error_message": "Provide only one filter type per datastore read",
                "suggested_next_steps": ["Choose either xpath/xpath_filter or subtree", "Retry with a single filter argument"],
            }
        return None

    @staticmethod
    def _guard_datastore_payload(payload: dict[str, Any]) -> dict[str, Any]:
        raw_xml = payload.get("raw_xml")
        value = payload.get("value")
        approx_size = 0
        if raw_xml:
            approx_size += len(raw_xml)
        try:
            approx_size += len(json.dumps(value, sort_keys=True))
        except Exception:
            pass

        if approx_size < 12000:
            return dict(payload)

        source_metadata = dict(payload.get("source_metadata") or {})
        source_metadata["response_truncated"] = True
        guarded = dict(payload)
        guarded["source_metadata"] = source_metadata
        guarded["response_summary"] = {
            "approx_chars": approx_size,
            "reason": "large_datastore_read",
            "hint": "Retry with a more precise xpath filter or a vendor-specific read flow",
        }
        guarded.pop("raw_xml", None)
        return guarded

    def get_server(self):
        return self.server

    def start(self, transport: str = "stdio") -> None:
        return self.server.run()

    def exposure_snapshot(self):
        if hasattr(self.server, "_tools"):
            tools = sorted(self.server._tools)
            resources = sorted(self.server._resources)
            prompts = sorted(self.server._prompts)
        else:
            tools = list(READ_ONLY_TOOLSET)
            resources = list(READ_ONLY_RESOURCE_URIS)
            prompts = list(READ_ONLY_PROMPTS)
        return MCPManifest(tools=tools, resources=resources, prompts=prompts)


def create_server(
    fixture_root: Path | str | None = None,
    *,
    inventory_path: Path | str | None = None,
    live_client: Any | None = None,
) -> NetconfMCPServer:
    root = Path(fixture_root or Path("tests/fixtures"))
    resolved_inventory = Path(inventory_path) if inventory_path else None
    return NetconfMCPServer(root, inventory_path=resolved_inventory, live_client=live_client)
