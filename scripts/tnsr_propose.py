#!/usr/bin/env python3
"""Generate repo-managed config proposals from a normalized TNSR snapshot."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from netconf_mcp.proposals.tnsr import (  # noqa: E402
    build_managed_tnsr_config_from_payload,
    build_tnsr_proposal_artifacts,
)
from netconf_mcp.utils.redact import load_fixture  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a repo-managed TNSR config proposal from a normalized snapshot."
    )
    parser.add_argument(
        "--snapshot",
        required=True,
        help="Path to a normalized TNSR snapshot JSON.",
    )
    parser.add_argument(
        "--managed-file",
        default=None,
        help="Canonical repo-managed config path. Defaults to managed-configs/tnsr/<device>.json.",
    )
    parser.add_argument(
        "--proposal-file",
        default=None,
        help="Proposal markdown path. Defaults to proposals/tnsr/<device>.md.",
    )
    parser.add_argument(
        "--candidate-file",
        default=None,
        help="Candidate config JSON path. Defaults to proposals/tnsr/<device>.candidate.json.",
    )
    return parser.parse_args()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "tnsr-target"


def _default_paths(snapshot: dict, managed_file: str | None, proposal_file: str | None, candidate_file: str | None) -> tuple[Path, Path, Path]:
    device_name = snapshot.get("device", {}).get("name") or snapshot.get("target_ref", "tnsr-target")
    slug = _slugify(str(device_name))
    managed_path = Path(managed_file) if managed_file else Path("managed-configs") / "tnsr" / f"{slug}.json"
    proposal_path = Path(proposal_file) if proposal_file else Path("proposals") / "tnsr" / f"{slug}.md"
    candidate_path = (
        Path(candidate_file)
        if candidate_file
        else Path("proposals") / "tnsr" / f"{slug}.candidate.json"
    )
    return managed_path, proposal_path, candidate_path


def main() -> None:
    args = _parse_args()
    snapshot_payload = load_fixture(Path(args.snapshot))
    candidate_config = build_managed_tnsr_config_from_payload(snapshot_payload)
    managed_path, proposal_path, candidate_path = _default_paths(
        snapshot_payload,
        args.managed_file,
        args.proposal_file,
        args.candidate_file,
    )

    proposal_text, candidate_text = build_tnsr_proposal_artifacts(
        managed_path=managed_path,
        candidate_config=candidate_config,
    )

    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_path.write_text(proposal_text + "\n", encoding="utf-8")
    candidate_path.write_text(candidate_text, encoding="utf-8")

    print(f"Proposal: {proposal_path}")
    print(f"Candidate config: {candidate_path}")
    print(f"Canonical managed file: {managed_path}")


if __name__ == "__main__":
    main()
