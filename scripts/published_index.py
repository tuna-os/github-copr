#!/usr/bin/env python3
"""Resolve a target/arch's published index URL(s) from the factory contract.

`published_index` in manifests/package-factory.yaml is the SERVED read URL of
what a target has published — distinct from `r2_path`, which is the bucket
WRITE path. Three consumers read it, and until now each carried its own
four-line YAML snippet to do so: scripts/factory-status.py (measurement),
scripts/run-package-factory-cell.sh (cross-cell BuildRequires) and
scripts/verify-package-factory-cell.sh (cross-cell runtime deps).

## Why a list, not a string (#467)

One target can have more than one produced index, because two publishers
write to two disjoint prefixes:

    publish-tideforge-rpms.yml   -> repo/10-x86_64   (served /repo/10/x86_64/)
    publish-build-chain-rpms.yml -> xfce/10-stream-x86_64

Only the first was declared, so every build-chain product was invisible to
every buildroot. `tideforge-xfwl4-el10` was not blocked on libxfce4ui-devel
being unbuilt — it has been built and served since before the issue was
filed. It was blocked on being served where nothing looked.

A bare string is still accepted and means a one-element list: most targets
genuinely have one index, and rewriting them into single-item lists would be
noise that hides the two that do not.

## What is deliberately NOT in el10's list

The other build-chain families publish to their own prefixes too
(gnome49/10-stream-x86_64, gnome51/10-stream-x86_64). They are NOT declared,
and that is a decision, not an omission: those prefixes carry GNOME 50/51
bootstrap builds of glib2 whose `Obsoletes: glib2 < 2.87.3` REPLACES the
AppStream package in any transaction regardless of repo priority — publish
run 32405815822 failed on exactly that with the priority fix fully in
effect. Adding an index is additive to a buildroot's package universe, so
only indexes whose contents are safe to see belong here. Adding one is a
measured change; adding all of them is a repo-poisoning hazard.

Usage:
    published_index.py TARGET ARCH        # one URL per line, none if absent
    published_index.py TARGET ARCH --join # space-separated on one line
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifests" / "package-factory.yaml"


def normalise(value) -> list[str]:
    """A published_index entry as a list of URLs.

    Accepts a bare string (the common one-index case) or a list. Blank
    entries are dropped so a commented-out URL cannot become an empty
    baseurl that dnf reads as the current directory.
    """
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise TypeError(f"published_index entry must be a string or list, got {value!r}")
    return [str(url).strip() for url in value if str(url).strip()]


def urls_for(target: dict, arch: str) -> list[str]:
    """Published index URLs for one target contract and architecture."""
    return normalise((target.get("published_index") or {}).get(arch))


def load(manifest: pathlib.Path = MANIFEST) -> dict:
    return yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve published index URLs")
    parser.add_argument("target")
    parser.add_argument("arch", nargs="?", default="")
    parser.add_argument("--manifest", type=pathlib.Path, default=MANIFEST)
    parser.add_argument("--join", action="store_true",
                        help="print space-separated on one line")
    args = parser.parse_args(argv)

    factory = load(args.manifest)
    target = (factory.get("targets") or {}).get(args.target) or {}
    resolved = urls_for(target, args.arch)
    if args.join:
        print(" ".join(resolved))
    else:
        for url in resolved:
            print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
