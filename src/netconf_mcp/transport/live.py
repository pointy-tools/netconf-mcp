"""Experimental live NETCONF transport using the local ssh client."""

from __future__ import annotations

from dataclasses import dataclass
from subprocess import CompletedProcess, run
from typing import Any
import re
from xml.etree import ElementTree as etree


NETCONF_EOM = "]]>]]>"
NETCONF_BASE_10 = "urn:ietf:params:netconf:base:1.0"


@dataclass
class LiveNetconfSession:
    target_ref: str
    session_id: str
    framing: str
    server_capabilities: list[str]
    transport: dict[str, Any]


class LiveNetconfError(RuntimeError):
    def __init__(self, payload: dict[str, Any]):
        super().__init__(payload.get("error_message", "NETCONF transport error"))
        self.payload = payload


class LiveNetconfSSHClient:
    """Minimal NETCONF-over-SSH client for read-only lab probing."""

    def __init__(self, runner=None):
        self.runner = runner or run

    def open_session(
        self,
        target: dict[str, Any],
        *,
        framing: str = "auto",
        hostkey_policy: str = "strict",
        connect_timeout_ms: int | None = None,
    ) -> LiveNetconfSession:
        hello = self._exchange(target, rpc_xml=None, hostkey_policy=hostkey_policy, connect_timeout_ms=connect_timeout_ms)
        capabilities = self._parse_capabilities(hello)
        selected_framing = framing if framing != "auto" else self._detect_framing(capabilities)
        return LiveNetconfSession(
            target_ref=target["target_ref"],
            session_id=self._parse_session_id(hello),
            framing=selected_framing,
            server_capabilities=capabilities,
            transport={"protocol": "ssh", "framing": selected_framing},
        )

    def get_yang_library(self, target: dict[str, Any], session: LiveNetconfSession) -> dict[str, Any]:
        del session
        primary = self._exchange(
            target,
            rpc_xml=(
                "<rpc message-id='101' xmlns='urn:ietf:params:xml:ns:netconf:base:1.0'>"
                "<get><filter type='subtree'>"
                "<yang-library xmlns='urn:ietf:params:xml:ns:yang:ietf-yang-library'/>"
                "</filter></get></rpc>"
            ),
        )
        modules = self._extract_modules(primary)
        completeness = "complete" if modules else "partial"
        if not modules:
            fallback = self._exchange(
                target,
                rpc_xml=(
                    "<rpc message-id='102' xmlns='urn:ietf:params:xml:ns:netconf:base:1.0'>"
                    "<get><filter type='subtree'>"
                    "<netconf-state xmlns='urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring'>"
                    "<schemas/></netconf-state>"
                    "</filter></get></rpc>"
                ),
            )
            modules = self._extract_legacy_schemas(fallback)
            completeness = "partial" if modules else "low"

        return {
            "module_set": modules,
            "yang_hashes": {},
            "provenance": "live-netconf",
            "completeness": completeness,
            "feature_matrix": {},
            "raw_xml": etree.tostring(primary, encoding="unicode"),
        }

    def get_monitoring(self, target: dict[str, Any], session: LiveNetconfSession, scope: str = "all") -> dict[str, Any]:
        del session
        reply = self._exchange(
            target,
            rpc_xml=(
                "<rpc message-id='201' xmlns='urn:ietf:params:xml:ns:netconf:base:1.0'>"
                "<get><filter type='subtree'>"
                "<netconf-state xmlns='urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring'/>"
                "</filter></get></rpc>"
            ),
        )
        sessions = [{"session-id": value} for value in self._find_text(reply, "session-id")]
        locks = []
        for lock in self._find_elements(reply, "global-lock"):
            holders = self._find_text(lock, "locked-by-session")
            locks.append({"datastore": "global", "held_by": holders[0] if holders else "unknown"})

        return {
            "scope": scope,
            "sessions": sessions,
            "locks": locks,
            "datastore_health": {},
            "transport_stats": {},
            "raw_xml": etree.tostring(reply, encoding="unicode"),
        }

    def datastore_get(
        self,
        target: dict[str, Any],
        session: LiveNetconfSession,
        *,
        datastore: str = "running",
        xpath: str | None = None,
        subtree: dict[str, Any] | None = None,
        with_defaults: str = "explicit",
        strict_config: bool = False,
    ) -> dict[str, Any]:
        del session, subtree, with_defaults
        if strict_config:
            rpc_xml = (
                "<rpc message-id='301' xmlns='urn:ietf:params:xml:ns:netconf:base:1.0'>"
                f"<get-config><source><{datastore}/></source></get-config></rpc>"
            )
        else:
            rpc_xml = (
                "<rpc message-id='302' xmlns='urn:ietf:params:xml:ns:netconf:base:1.0'>"
                "<get/></rpc>"
            )

        reply = self._exchange(target, rpc_xml=rpc_xml)
        data_nodes = self._find_elements(reply, "data")
        data_node = data_nodes[0] if data_nodes else reply

        if xpath:
            matches = self._select_simple_path(data_node, xpath)
            if not matches:
                raise LiveNetconfError(
                    {
                        "status": "error",
                        "error_category": "protocol",
                        "error_code": "NOT_FOUND",
                        "error_type": "NOT_FOUND",
                        "error_tag": "invalid-value",
                        "error_message": "Requested path not found in live response",
                    }
                )
            selected: Any = [self._node_to_value(match) for match in matches]
            if len(selected) == 1:
                selected = selected[0]
        else:
            selected = self._node_to_value(data_node)

        return {
            "resource": {"datastore": datastore, "filter": xpath or "all"},
            "nacm_visibility": "unknown",
            "value": selected,
            "source_metadata": {
                "mode": "live-netconf",
                "host": target.get("host") or target.get("ssh_config_host"),
            },
            "raw_xml": etree.tostring(reply, encoding="unicode"),
        }

    def _exchange(
        self,
        target: dict[str, Any],
        *,
        rpc_xml: str | None,
        hostkey_policy: str = "strict",
        connect_timeout_ms: int | None = None,
    ) -> etree.Element:
        payload = self._build_client_hello()
        if rpc_xml:
            payload += rpc_xml + NETCONF_EOM

        result = self._run_ssh(
            target,
            payload,
            hostkey_policy=hostkey_policy,
            connect_timeout_ms=connect_timeout_ms,
        )
        if result.returncode != 0:
            raise LiveNetconfError(
                {
                    "status": "error",
                    "error_category": "transport",
                    "error_code": "SSH_CONNECT_FAILED",
                    "error_type": "SSH_CONNECT_FAILED",
                    "error_tag": "transport",
                    "error_message": (result.stderr or "ssh command failed").strip(),
                }
            )

        frames = [chunk.strip() for chunk in result.stdout.split(NETCONF_EOM) if chunk.strip()]
        if not frames:
            raise LiveNetconfError(
                {
                    "status": "error",
                    "error_category": "protocol",
                    "error_code": "EMPTY_REPLY",
                    "error_type": "EMPTY_REPLY",
                    "error_tag": "operation-failed",
                    "error_message": "NETCONF server returned no frames",
                }
            )

        if rpc_xml and len(frames) > 1:
            return self._parse_xml(frames[-1])
        return self._parse_xml(frames[0])

    def _run_ssh(
        self,
        target: dict[str, Any],
        payload: str,
        *,
        hostkey_policy: str,
        connect_timeout_ms: int | None,
    ) -> CompletedProcess[str]:
        command = ["ssh", "-o", "BatchMode=yes"]
        if hostkey_policy != "strict":
            command += ["-o", "StrictHostKeyChecking=no"]
        timeout_s = max(int((connect_timeout_ms or 5000) / 1000), 1)
        command += ["-o", f"ConnectTimeout={timeout_s}"]

        if target.get("identity_file"):
            command += ["-i", str(target["identity_file"])]

        if target.get("ssh_config_host"):
            destination = str(target["ssh_config_host"])
        else:
            host = target.get("host")
            if not host:
                raise LiveNetconfError(
                    {
                        "status": "error",
                        "error_category": "transport",
                        "error_code": "MISSING_HOST",
                        "error_type": "MISSING_HOST",
                        "error_tag": "transport",
                        "error_message": "Live target requires host or ssh_config_host",
                    }
                )
            user = target.get("username")
            destination = f"{user}@{host}" if user else str(host)
            if target.get("port"):
                command += ["-p", str(target["port"])]

        command += [destination, "-s", "netconf"]
        return self.runner(
            command,
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout_s + 2,
            check=False,
        )

    @staticmethod
    def _build_client_hello() -> str:
        return (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<hello xmlns='urn:ietf:params:xml:ns:netconf:base:1.0'>"
            "<capabilities>"
            f"<capability>{NETCONF_BASE_10}</capability>"
            "</capabilities>"
            "</hello>"
            f"{NETCONF_EOM}"
        )

    @staticmethod
    def _parse_xml(payload: str) -> etree.Element:
        try:
            return etree.fromstring(payload.encode("utf-8"))
        except etree.ParseError as exc:
            raise LiveNetconfError(
                {
                    "status": "error",
                    "error_category": "protocol",
                    "error_code": "BAD_XML",
                    "error_type": "BAD_XML",
                    "error_tag": "malformed-message",
                    "error_message": str(exc),
                }
            ) from exc

    @staticmethod
    def _parse_capabilities(hello: etree.Element) -> list[str]:
        return [cap.strip() for cap in LiveNetconfSSHClient._find_text(hello, "capability")]

    @staticmethod
    def _parse_session_id(hello: etree.Element) -> str:
        values = LiveNetconfSSHClient._find_text(hello, "session-id")
        return values[0] if values else "live-session"

    @staticmethod
    def _detect_framing(capabilities: list[str]) -> str:
        if any("base:1.1" in cap for cap in capabilities):
            return "base:1.1"
        return "base:1.0"

    @staticmethod
    def _extract_modules(root: etree.Element) -> list[dict[str, Any]]:
        modules = []
        for module in LiveNetconfSSHClient._find_elements(root, "module"):
            names = LiveNetconfSSHClient._children_text(module, "name")
            if not names:
                continue
            revisions = LiveNetconfSSHClient._children_text(module, "revision")
            namespaces = LiveNetconfSSHClient._children_text(module, "namespace")
            modules.append(
                {
                    "module": names[0],
                    "revision": revisions[0] if revisions else None,
                    "namespace": namespaces[0] if namespaces else None,
                }
            )
        return modules

    @staticmethod
    def _extract_legacy_schemas(root: etree.Element) -> list[dict[str, Any]]:
        modules = []
        for schema in LiveNetconfSSHClient._find_elements(root, "schema"):
            identifiers = LiveNetconfSSHClient._children_text(schema, "identifier")
            if not identifiers:
                continue
            versions = LiveNetconfSSHClient._children_text(schema, "version")
            namespaces = LiveNetconfSSHClient._children_text(schema, "namespace")
            modules.append(
                {
                    "module": identifiers[0],
                    "revision": versions[0] if versions else None,
                    "namespace": namespaces[0] if namespaces else None,
                }
            )
        return modules

    @classmethod
    def _node_to_value(cls, node: Any) -> Any:
        if not isinstance(node, etree.Element):
            return str(node)

        children = [child for child in list(node) if isinstance(child.tag, str)]
        if not children:
            text = (node.text or "").strip()
            return text if text else etree.tostring(node, encoding="unicode")

        out: dict[str, Any] = {}
        for child in children:
            key = cls._local_name(child.tag)
            value = cls._node_to_value(child)
            if key in out:
                if not isinstance(out[key], list):
                    out[key] = [out[key]]
                out[key].append(value)
            else:
                out[key] = value
        return out

    @staticmethod
    def _select_simple_path(root: etree.Element, xpath: str) -> list[etree.Element]:
        if not xpath.startswith("/"):
            raise LiveNetconfError(
                {
                    "status": "error",
                    "error_category": "schema",
                    "error_code": "UNSUPPORTED_XPATH",
                    "error_type": "UNSUPPORTED_XPATH",
                    "error_tag": "invalid-value",
                    "error_message": "Only absolute NETCONF/YANG paths are supported",
                }
            )

        current = [root]
        for raw_segment in [segment for segment in xpath.split("/") if segment]:
            match = re.fullmatch(r"(?P<name>[A-Za-z0-9:_-]+)(\[(?P<key>[A-Za-z0-9:_-]+)='(?P<value>[^']+)'\])?", raw_segment)
            if not match:
                raise LiveNetconfError(
                    {
                        "status": "error",
                        "error_category": "schema",
                        "error_code": "UNSUPPORTED_XPATH",
                        "error_type": "UNSUPPORTED_XPATH",
                        "error_tag": "invalid-value",
                        "error_message": f"Unsupported xpath segment: {raw_segment}",
                    }
                )
            name = match.group("name").split(":")[-1]
            next_nodes: list[etree.Element] = []
            for node in current:
                for child in list(node):
                    if LiveNetconfSSHClient._local_name(child.tag) != name:
                        continue
                    if match.group("key"):
                        key_name = match.group("key").split(":")[-1]
                        key_value = match.group("value")
                        if key_value not in LiveNetconfSSHClient._children_text(child, key_name):
                            continue
                    next_nodes.append(child)
            current = next_nodes
        return current

    @staticmethod
    def _children_text(node: etree.Element, child_name: str) -> list[str]:
        values = []
        for child in list(node):
            if LiveNetconfSSHClient._local_name(child.tag) != child_name:
                continue
            text = (child.text or "").strip()
            if text:
                values.append(text)
        return values

    @staticmethod
    def _find_elements(node: etree.Element, local_name: str) -> list[etree.Element]:
        return [
            child
            for child in node.iter()
            if isinstance(child.tag, str) and LiveNetconfSSHClient._local_name(child.tag) == local_name
        ]

    @staticmethod
    def _find_text(node: etree.Element, local_name: str) -> list[str]:
        values = []
        for child in LiveNetconfSSHClient._find_elements(node, local_name):
            text = (child.text or "").strip()
            if text:
                values.append(text)
        return values

    @staticmethod
    def _local_name(tag: str) -> str:
        if "}" in tag:
            return tag.rsplit("}", 1)[-1]
        return tag
