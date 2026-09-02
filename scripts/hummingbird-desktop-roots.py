#!/usr/bin/env python3
"""Print the roots a Hummingbird desktop needs a consumer image to resolve.

One line per package: required_packages first, then install_packages, in
catalog order and deduplicated -- the same list scripts/gap_engine.py and
scripts/check-hummingbird-installability.py walk, so the container gate
(scripts/check-hummingbird-installability-container.sh) asks dnf about
exactly the roots the static walk asks the index about.

Usage:
    scripts/hummingbird-desktop-roots.py gnome            # roots, one per line
    scripts/hummingbird-desktop-roots.py --list           # desktop ids
    scripts/hummingbird-desktop-roots.py --consumed-for gnome
        # ids of consumed_indexes the desktop's consumed_from names (0 or 1)
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def roots_of(definition: dict) -> list[str]:
    return list(dict.fromkeys(
        (definition.get("required_packages") or []) + (definition.get("install_packages") or [])
    ))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("desktop", nargs="?")
    ap.add_argument("--catalog", type=pathlib.Path, default=ROOT / "manifests" / "hummingbird-desktops.yaml")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--consumed-for", metavar="DESKTOP")
    args = ap.parse_args(argv)
    catalog = yaml.safe_load(args.catalog.read_text(encoding="utf-8"))
    desktops = catalog["desktops"]
    if args.list:
        print("\n".join(d for d in desktops if d != "bluefin"))
        return 0
    if args.consumed_for:
        consumed = desktops[args.consumed_for].get("consumed_from")
        if consumed:
            print(consumed)
        return 0
    if not args.desktop:
        ap.error("a desktop, --list or --consumed-for is required")
    if args.desktop not in desktops:
        print(f"unknown desktop {args.desktop!r}; have {sorted(desktops)}", file=sys.stderr)
        return 2
    print("\n".join(roots_of(desktops[args.desktop])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
