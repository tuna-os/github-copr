#!/usr/bin/env python3
"""Validate Hummingbird's project-owned desktop RPM source catalog."""
from __future__ import annotations
import argparse
import pathlib
import sys
import yaml

def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=pathlib.Path)
    args = parser.parse_args()
    root = args.catalog.resolve().parents[1]
    data = yaml.safe_load(args.catalog.read_text())
    if data.get("schema") != 1:
        fail("schema must be 1")
    for field in ("id", "baseurl", "r2_path", "dist"):
        if not data.get("target", {}).get(field):
            fail(f"target.{field} is required")
    for desktop, definition in data.get("desktops", {}).items():
        if not definition.get("required_packages") or not definition.get("sources"):
            fail(f"{desktop} needs packages and sources")
        # install_packages is what tunaOS actually installs; required_packages
        # is only the contract surface its desktop gate checks. The gap
        # measurement resolves both, and a required package missing from the
        # install list is a package nothing would install — the exact shape of
        # the GNOME failure in LUKS run 31100096864.
        install = definition.get("install_packages")
        if install is not None:
            orphans = sorted(set(definition["required_packages"]) - set(install))
            if orphans:
                fail(f"{desktop}: required but never installed: {orphans}")
        for source in definition["sources"]:
            if len(source) != 1:
                fail(f"{desktop}: source has multiple kinds")
            if "local" in source and not (root / source["local"]).is_dir():
                fail(f"{desktop}: missing local source {source['local']}")
            if "fedora_distgit" in source and not source["fedora_distgit"].replace("-", "").isalnum():
                fail(f"{desktop}: invalid Fedora dist-git name")
            if "upstream_rpm" in source and not source["upstream_rpm"].startswith("https://"):
                fail(f"{desktop}: upstream source must use HTTPS")
    print("Hummingbird desktop catalog: valid")

if __name__ == "__main__":
    main()
