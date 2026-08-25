#!/usr/bin/env python3
"""What changed between two buildroots — the koji-diff question, locally.

Compares two buildroot manifests (one NEVRA per line, as written by
scripts/extract-buildroot-manifest.py), or two directories of them
package by package. The output is the answer to "it built last week and
fails today": which packages entered the buildroot, which left, and
which changed version.

Adapted from koji-diff (slopfest/sandogasa, Apache-2.0 OR MIT).

Usage:
    scripts/diff-buildroots.py green.buildroot.txt red.buildroot.txt
    scripts/diff-buildroots.py green-run/buildroots/ red-run/buildroots/

Exit status is 0 whether or not differences exist — this is a
diagnostic lens, not a gate; the diff IS the successful result.
"""
from __future__ import annotations

import argparse
import pathlib
import sys


def parse_nevra(nevra: str) -> tuple[str, str]:
    """NEVRA -> (name, evr.arch). `glibc-2.39-14.el10.x86_64`."""
    stem, _, arch = nevra.rpartition(".")
    parts = stem.rsplit("-", 2)
    if len(parts) < 3:
        return nevra, ""
    name, version, release = parts
    return name, f"{version}-{release}.{arch}"


def read_manifest(path: pathlib.Path) -> dict[str, str]:
    packages = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, evr = parse_nevra(line)
        packages[name] = evr
    return packages


def diff(old: dict[str, str], new: dict[str, str]) -> dict:
    return {
        "added": sorted(set(new) - set(old)),
        "removed": sorted(set(old) - set(new)),
        "changed": sorted(
            name for name in set(old) & set(new) if old[name] != new[name]),
    }


def render(label: str, old: dict, new: dict) -> tuple[int, list[str]]:
    delta = diff(old, new)
    lines = []
    for name in delta["added"]:
        lines.append(f"  + {name}-{new[name]}")
    for name in delta["removed"]:
        lines.append(f"  - {name}-{old[name]}")
    for name in delta["changed"]:
        lines.append(f"  ~ {name}: {old[name]} -> {new[name]}")
    count = sum(len(v) for v in delta.values())
    header = f"{label}: {count} difference(s)" if count else f"{label}: identical"
    return count, [header] + lines


def main() -> int:
    parser = argparse.ArgumentParser(
        description="diff two buildroot manifests or directories of them")
    parser.add_argument("old", type=pathlib.Path)
    parser.add_argument("new", type=pathlib.Path)
    args = parser.parse_args()

    if args.old.is_dir() != args.new.is_dir():
        raise SystemExit("compare a file to a file or a directory to a directory")

    if args.old.is_file():
        _, lines = render("buildroot", read_manifest(args.old),
                          read_manifest(args.new))
        print("\n".join(lines))
        return 0

    old_files = {p.name: p for p in sorted(args.old.glob("*.buildroot.txt"))}
    new_files = {p.name: p for p in sorted(args.new.glob("*.buildroot.txt"))}
    for name in sorted(set(old_files) | set(new_files)):
        if name not in old_files:
            print(f"{name.removesuffix('.buildroot.txt')}: only in {args.new}")
            continue
        if name not in new_files:
            print(f"{name.removesuffix('.buildroot.txt')}: only in {args.old}")
            continue
        count, lines = render(
            name.removesuffix(".buildroot.txt"),
            read_manifest(old_files[name]), read_manifest(new_files[name]))
        if count:
            print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
