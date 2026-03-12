"""Redaction helpers for credentials and sensitive strings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

SENSITIVE_KEYS = {
    "credential_ref",
    "credentials",
    "password",
    "private_key",
    "api_token",
    "secret",
    "token",
}


def _redact_scalar(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("cred://"):
        return "cred://[redacted]"
    return value


def redact_mapping(value: Any) -> Any:
    """Deep-copy + redact known secret-bearing strings and fields."""

    if isinstance(value, Mapping):
        out = {}
        for key, nested in value.items():
            redacted_key = key
            if isinstance(key, str):
                lower = key.lower()
                if lower in SENSITIVE_KEYS:
                    out[redacted_key] = "[redacted]"
                    continue
            out[redacted_key] = redact_mapping(nested)
        return out
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_mapping(v) for v in value]

    return _redact_scalar(value)


def load_fixture(path: str | Path) -> dict[str, Any]:
    """Load JSON fixtures with safe fallbacks."""
    import json

    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)
