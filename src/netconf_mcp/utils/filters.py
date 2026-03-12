"""Small helpers for deterministic fixture-aware path filtering."""

from __future__ import annotations

import re


def _parse_xpath_segment(segment: str):
    m = re.match(r"(?P<key>[a-zA-Z0-9_-]+)\[(?P<cond_name>[a-zA-Z0-9_-]+)=\'(?P<cond_val>[^']+)\'\]$", segment)
    if m:
        return m.group("key"), m.group("cond_name"), m.group("cond_val")
    return segment, None, None


def xpath_filter(document: dict, xpath: str):
    """Extract a deterministic fixture node from a simple NETCONF-like payload."""

    if not xpath:
        return document

    current = document
    for segment in [seg for seg in xpath.strip("/").split("/") if seg]:
        key, cond_name, cond_val = _parse_xpath_segment(segment)

        if not isinstance(current, dict):
            return None

        if cond_name is None:
            current = current.get(key)
            continue

        collection = current.get(key)
        if not isinstance(collection, dict):
            return None

        # Fixture convention: keyed by identifier under keyed collections
        if cond_name == "name" and cond_val in collection:
            current = collection.get(cond_val)
        else:
            return None

    return current


def with_module_filter(payload: dict, modules: list[str] | None):
    if not modules:
        return payload
    filtered = {}
    for module in modules:
        if module in payload:
            filtered[module] = payload[module]
    return filtered
