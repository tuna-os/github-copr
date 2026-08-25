#!/usr/bin/env python3
"""What was actually in the buildroot when this package built.

Adapted from koji-diff's buildroot comparison (slopfest/sandogasa,
Apache-2.0 OR MIT), which answers "what changed between the build that
worked and the build that did not" from build-system metadata instead of
archaeology. This factory's version of that archaeology is on record:
the libnotify diagnosis in #480 took a chain of issue comments to
establish what the buildroot had actually resolved, when the answer was
sitting in mock's own logs the whole time.

Reads a mock result directory (or a root.log directly) and emits one
sorted NEVRA per line — a manifest small enough to keep next to the
built RPMs, and diffable with scripts/diff-buildroots.py.

Sources, in order of fidelity:
  * installed_pkgs.log — mock's own `rpm -qa` of the finished buildroot,
    already one NEVRA per line.
  * root.log — the dnf transaction tables (`Installing:` /
    `Installing dependencies:` / …), reassembled into NEVRAs. Used when
    installed_pkgs.log is absent.

Usage:
    scripts/extract-buildroot-manifest.py RESULTDIR --output pkg.buildroot.txt
    scripts/extract-buildroot-manifest.py results/root.log
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

# `DEBUG util.py:446:  payload` — mock prefixes every relayed dnf line.
_MOCK_PREFIX = re.compile(r"^(?:DEBUG|INFO|WARNING)\s+\S+:\d+:\s?(.*)$")

_SECTION_STARTS = (
    "Installing:",
    "Installing dependencies:",
    "Installing weak dependencies:",
    "Upgrading:",
    "Reinstalling:",
)
_SECTION_ENDS = ("Transaction Summary", "Installing Environment Groups:")


def payload(line: str) -> str:
    match = _MOCK_PREFIX.match(line)
    return match.group(1) if match else line


def from_root_log(text: str) -> set[str]:
    """NEVRAs named by the dnf transaction tables in a root.log."""
    packages: set[str] = set()
    in_section = False
    for raw in text.splitlines():
        line = payload(raw).rstrip()
        stripped = line.strip()
        if stripped in _SECTION_STARTS:
            in_section = True
            continue
        if any(stripped.startswith(end) for end in _SECTION_ENDS):
            in_section = False
            continue
        if not in_section:
            continue
        if not stripped or stripped.startswith(("Package ", "----")):
            continue
        # ` name  arch  evr  repo  size unit` — a table row is indented
        # and columnar; a non-row (blank, next header) ends nothing by
        # itself because dnf separates sections explicitly.
        columns = stripped.split()
        if len(columns) < 4:
            in_section = False
            continue
        name, arch, evr = columns[0], columns[1], columns[2]
        packages.add(f"{name}-{evr}.{arch}")
    return packages


def extract(path: pathlib.Path) -> list[str]:
    if path.is_dir():
        installed = path / "installed_pkgs.log"
        if installed.is_file():
            return sorted({line.strip() for line in
                           installed.read_text().splitlines() if line.strip()})
        path = path / "root.log"
    if not path.is_file():
        raise SystemExit(f"{path}: no installed_pkgs.log or root.log to read")
    return sorted(from_root_log(path.read_text(errors="replace")))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="one sorted NEVRA per line from a mock result")
    parser.add_argument("result", type=pathlib.Path,
                        help="mock result directory, or a root.log")
    parser.add_argument("--output", type=pathlib.Path,
                        help="write here instead of stdout")
    args = parser.parse_args()

    manifest = extract(args.result)
    if not manifest:
        # An empty manifest would diff as "everything changed" against a
        # real one; absence is more honest than an empty file.
        print(f"{args.result}: no buildroot packages found", file=sys.stderr)
        return 1
    body = "\n".join(manifest) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body)
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
