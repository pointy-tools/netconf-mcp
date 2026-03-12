from __future__ import annotations

from subprocess import CompletedProcess

from netconf_mcp.transport.live import LiveNetconfSSHClient, LiveNetconfSession


HELLO = (
    "<?xml version='1.0' encoding='UTF-8'?>"
    "<hello xmlns='urn:ietf:params:xml:ns:netconf:base:1.0'>"
    "<capabilities><capability>urn:ietf:params:netconf:base:1.1</capability></capabilities>"
    "<session-id>1</session-id>"
    "</hello>]]>]]>"
)


def test_build_subtree_filter_for_keyed_xpath():
    xml = LiveNetconfSSHClient._build_subtree_filter("/interfaces-config/interface[name='LAN']/enabled")
    assert xml == (
        "<filter type='subtree'>"
        "<interfaces-config><interface><name>LAN</name><enabled></enabled></interface></interfaces-config>"
        "</filter>"
    )


def test_datastore_get_uses_subtree_filter_for_strict_xpath_reads():
    captured: list[str] = []

    def runner(command, input=None, capture_output=None, text=None, timeout=None, check=None):
        del command, capture_output, text, timeout, check
        captured.append(input)
        if "<get-config>" in input:
            return CompletedProcess(
                args=[],
                returncode=0,
                stdout=(
                    HELLO
                    + "<rpc-reply xmlns='urn:ietf:params:xml:ns:netconf:base:1.0'>"
                    "<data><route-config><prefix-lists><list><name>DEFAULT-OUT</name></list></prefix-lists></route-config></data>"
                    "</rpc-reply>]]>]]>"
                ),
                stderr="",
            )
        return CompletedProcess(args=[], returncode=0, stdout=HELLO, stderr="")

    client = LiveNetconfSSHClient(runner=runner)
    session = LiveNetconfSession(
        target_ref="target://lab/tnsr",
        session_id="1",
        framing="base:1.1",
        server_capabilities=["urn:ietf:params:netconf:base:1.1"],
        transport={"protocol": "ssh", "framing": "base:1.1"},
    )
    payload = client.datastore_get(
        {"target_ref": "target://lab/tnsr", "host": "tnsr.example.net", "username": "tnsr"},
        session,
        datastore="running",
        xpath="/route-config/prefix-lists",
        strict_config=True,
    )

    assert "<filter type='subtree'><route-config><prefix-lists></prefix-lists></route-config></filter>" in captured[0]
    assert payload["value"]["list"]["name"] == "DEFAULT-OUT"
