"""Shared MCP envelopes used by handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Envelope:
    status: str
    policy_decision: str
    tool: str
    operation_id: str
    session_ref: Optional[str]
    data: dict[str, Any] = field(default_factory=dict)
    schema_refs: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    confidence: str = "medium"
    warnings: list[dict[str, Any]] = field(default_factory=list)
    next_safe_action: Optional[str] = None
    error: Optional[dict[str, Any]] = None


READ_ONLY_TOOLSET = [
    "inventory.list_targets",
    "netconf.open_session",
    "netconf.discover_capabilities",
    "yang.get_library",
    "netconf.get_monitoring",
    "datastore.get",
    "datastore.get_config",
]

GUARDED_WRITE_TOOLSET = [
    "config.plan_edit",
    "config.validate_plan",
    "config.apply_plan",
    "config.rollback",
]

READ_ONLY_RESOURCE_URIS = [
    "targets://inventory",
    "target://{target_ref}/facts",
    "target://{target_ref}/capabilities",
    "target://{target_ref}/yang-library",
    "target://{target_ref}/datastores/{name}",
    "target://{target_ref}/session-state",
]

READ_ONLY_PROMPTS = [
    "discover-device-safely",
    "inspect-operational-state",
    "review-yang-capabilities",
    "netconf-data-fidelity",
]
