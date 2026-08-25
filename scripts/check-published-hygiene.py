#!/usr/bin/env python3
"""Hygiene checks over the SERVED package indexes, per target and arch.

Adapted from hs-relmon's `dupe-subpkgs` and `file-conflicts`
(slopfest/sandogasa, Apache-2.0 OR MIT), pointed at this factory's own
published prefixes. Each check corresponds to a defect class this
repository has already shipped and then fixed reactively:

  * duplicate NEVRA within one prefix -- the createrepo_c --update class
    (#358): a stale index entry survives next to the fresh one.
  * one binary name from two SOURCE packages within one prefix -- the
    hs-relmon dupe-subpkgs class: two sources fight over a name and dnf
    picks by version, not by intent.
  * one binary name served from two PREFIXES of the same target -- the
    "one NEVRA served twice" class (#471): every buildroot that enables
    the target's published_index list sees both, and which wins depends
    on repo priority, which #453/#455 showed is not a defence.
  * one FILE owned by differently-named packages across the enabled
    prefixes -- the sharpest conflict: dnf resolves both packages happily
    and rpm fails the transaction at install time.

The checks read the same `published_index` contract every buildroot
reads, so a clean report means the *combination* a buildroot actually
sees is clean -- not merely each prefix in isolation.

Every format the factory contract declares is covered, through the
format-neutral index layer (scripts/repo_index.py): rpm-md primary.xml,
flat-APT Packages, and pacman .db. Scope, recorded deliberately:
primary.xml lists only "primary" files (binaries and /etc), so the rpm
file-conflict check covers the class that breaks installs first, not
every shared path; flat APT repos and pacman .db files carry NO file
lists at all, so on those formats the file-conflict check has nothing
to read and reports nothing -- absence of findings there is absence of
data, not cleanliness. The other three checks run on every format.

Usage:
    scripts/check-published-hygiene.py                # every served target
    scripts/check-published-hygiene.py --target el10 --arch x86_64
    scripts/check-published-hygiene.py --target ubuntu --json report.json

Exits non-zero when any finding exists, so a publisher can gate on it.
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


_MODULES: dict[str, object] = {}


def load(name: str, filename: str):
    if name not in _MODULES:
        spec = importlib.util.spec_from_file_location(name, HERE / filename)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULES[name] = module
    return _MODULES[name]


def iter_packages(blob: bytes):
    """Every package row of a primary.xml, duplicates included.

    parse_primary keys by name and therefore cannot see the very thing
    the duplicate checks exist for. The implementation lives in the
    format-neutral layer (scripts/repo_index.py) alongside the deb and
    pacman row readers; this alias keeps the rpm spelling.
    """
    yield from load("repo_index", "repo_index.py").iter_rpm_rows(blob)


def analyse(prefixes: dict[str, list[dict]], fmt: str = "rpm") -> dict:
    """All four checks over {prefix url: [package rows]}, any format."""
    findings = {
        "duplicate_nevra_in_prefix": [],
        "duplicate_name_two_sources_in_prefix": [],
        "name_served_by_multiple_prefixes": [],
        "file_conflicts": [],
    }

    for prefix, rows in prefixes.items():
        seen_nevra = collections.Counter(
            (row["name"], row["evr"], row["arch"]) for row in rows)
        for (name, evr, arch), count in sorted(seen_nevra.items()):
            if count > 1:
                findings["duplicate_nevra_in_prefix"].append({
                    "prefix": prefix, "name": name, "evr": evr,
                    "arch": arch, "count": count,
                })
        ri = load("repo_index", "repo_index.py")
        by_name = collections.defaultdict(set)
        for row in rows:
            if row["srpm"]:
                by_name[row["name"]].add(ri.source_name(fmt, row["srpm"]))
        for name, srcs in sorted(by_name.items()):
            if len(srcs) > 1:
                findings["duplicate_name_two_sources_in_prefix"].append({
                    "prefix": prefix, "name": name, "sources": sorted(srcs),
                })

    name_by_prefix = collections.defaultdict(dict)
    for prefix, rows in prefixes.items():
        for row in rows:
            if row["arch"] == "src":
                continue
            name_by_prefix[row["name"]][prefix] = row["evr"]
    for name, where in sorted(name_by_prefix.items()):
        if len(where) > 1:
            evrs = set(where.values())
            findings["name_served_by_multiple_prefixes"].append({
                "name": name, "prefixes": dict(sorted(where.items())),
                # Same EVR everywhere is redundancy; different EVRs mean
                # repo priority silently decides what installs.
                "severity": "redundant" if len(evrs) == 1 else "shadowing",
            })

    ri = load("repo_index", "repo_index.py")
    owners = collections.defaultdict(set)
    for prefix, rows in prefixes.items():
        for row in rows:
            if row["arch"] == "src":
                continue
            for path in row["files"]:
                owners[path].add((row["name"],
                                  ri.source_name(fmt, row["srpm"]) or ""))
    for path, who in sorted(owners.items()):
        # Distinct SOURCES, as hs-relmon keys it: subpackages of one
        # source sharing an identical file is a packaging choice rpm
        # permits; the same path from two unrelated sources is the
        # transaction-time failure this check exists for.
        sources = {src for _, src in who}
        if len(sources) > 1:
            findings["file_conflicts"].append({
                "file": path,
                "owners": sorted(f"{name} (from {src})" for name, src in who),
            })
    return findings


def total(findings: dict) -> int:
    return sum(len(rows) for rows in findings.values())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="hygiene checks over the served package indexes")
    parser.add_argument("--target", action="append",
                        help="target id from package-factory.yaml "
                             "(default: every target with a served index)")
    parser.add_argument("--arch", action="append",
                        help="architecture (default: every declared one)")
    parser.add_argument("--cache", type=pathlib.Path,
                        default=pathlib.Path(".cache/published-hygiene"))
    parser.add_argument("--json", type=pathlib.Path,
                        help="also write the full findings as JSON")
    args = parser.parse_args()

    ri = load("repo_index", "repo_index.py")
    published = load("published_index", "published_index.py")
    contract = published.load()

    report = {}
    dirty = 0
    for target_id, target in sorted(contract["targets"].items()):
        if args.target and target_id not in args.target:
            continue
        fmt = target.get("format")
        index = target.get("published_index")
        if not index:
            continue
        for arch in target.get("architectures") or []:
            if args.arch and arch not in args.arch:
                continue
            urls = published.urls_for(target, arch)
            if not urls:
                continue
            prefixes = {}
            for url in urls:
                rows = list(ri.iter_rows(url, fmt, args.cache))
                if fmt == "deb":
                    # A flat apt repo serves every architecture from one
                    # Packages; apt selects on the Architecture field, so
                    # the per-arch view filters the same way.
                    rows = [r for r in rows if r["arch"] in (arch, "all")]
                prefixes[url] = rows
            findings = analyse(prefixes, fmt)
            report[f"{target_id}/{arch}"] = findings
            count = total(findings)
            dirty += count
            print(f"{target_id}/{arch}: {sum(len(r) for r in prefixes.values())}"
                  f" package entries over {len(urls)} prefix(es), "
                  f"{count} finding(s)")
            for check, rows in findings.items():
                for row in rows:
                    print(f"  [{check}] {json.dumps(row, sort_keys=True)}")

    if args.json:
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"wrote {args.json}")
    if dirty:
        print(f"\n{dirty} finding(s) -- the served combination is not clean")
        return 1
    print("\nthe served indexes are clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
