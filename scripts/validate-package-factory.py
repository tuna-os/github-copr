#!/usr/bin/env python3
"""Validate the cross-distro package-factory target contract."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    data = yaml.safe_load(args.manifest.read_text())
    if data.get("schema") != 1:
        fail("schema must be 1")

    seen_upstreams: set[str] = set()
    for upstream in data.get("upstreams", []):
        upstream_id = upstream.get("id", "")
        if not upstream_id or upstream_id in seen_upstreams:
            fail(f"invalid or duplicate upstream id: {upstream_id!r}")
        if not upstream.get("url", "").startswith("https://"):
            fail(f"{upstream_id}: URL must use HTTPS")
        if upstream.get("license_review") != "required":
            fail(f"{upstream_id}: license_review must be required")
        seen_upstreams.add(upstream_id)

    targets = data.get("targets", {})
    required = {"el10", "ubuntu", "debian", "opensuse-tumbleweed", "arch"}
    if set(targets) != required:
        fail(f"targets must be exactly {sorted(required)}")
    for target_id, target in targets.items():
        if target.get("status") not in {"supported", "scaffold"}:
            fail(f"{target_id}: status must be supported or scaffold")
        for field in ("format", "architectures", "r2_path", "repository", "probe_image"):
            if not target.get(field):
                fail(f"{target_id}: {field} is required")
        if "/" not in target["probe_image"]:
            fail(f"{target_id}: probe_image must be a fully-qualified container image")
        if not target["r2_path"].startswith(("rpm/", "apt/", "pacman/")):
            fail(f"{target_id}: r2_path has an unsupported namespace")
        if not all(arch in {"x86_64", "aarch64", "amd64", "arm64"} for arch in target["architectures"]):
            fail(f"{target_id}: unsupported architecture")
    print("Package factory manifest: valid")


if __name__ == "__main__":
    main()
