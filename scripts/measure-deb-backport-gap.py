#!/usr/bin/env python3
"""Measure what a deb suite needs backported from a newer donor suite.

RFC 011's gap engine covers rpm-md only: measure-target-gap.py is a shim over
measure-hummingbird-gap.py, which parses primary.xml and knows nothing about
APT. This is the deb half, and it answers a different question than the
Hummingbird measurer does.

Hummingbird asks "what does this target fail to PROVIDE at runtime", and
closes over Requires:. A backport asks "what must I REBUILD to move a stack
from one suite to another", and closes over Build-Depends: -- because the
packaging already exists in the donor suite and the work is a rebuild, not an
authoring job.

The restriction that makes the closure finite is the same rule RFC 011 states
for rpm: a build dependency only enters the closure when the DONOR's version
is strictly newer than the TARGET's. Everything the target already satisfies
drops out, so debhelper, gcc and the rest of the toolchain never appear, and
the answer shrinks by itself as the target catches up. Nothing is remembered;
it is recomputed from two live indexes.

Usage:
    scripts/measure-deb-backport-gap.py --manifest manifests/gnome51-deb.yaml
    scripts/measure-deb-backport-gap.py --manifest manifests/gnome51-deb.yaml \
        --target ubuntu --report-json docs/gnome51-deb-gap.json
"""
from __future__ import annotations

import argparse
import collections
import json
import lzma
import pathlib
import sys
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


# --- dpkg version comparison -------------------------------------------------
# Implemented here rather than shelling out: this repo's runners have no
# python-apt, and `dpkg --compare-versions` is not present in every image the
# factory uses. The algorithm is dpkg's, including the rule that '~' sorts
# before everything, end-of-string included, which is the only reason
# 51~beta correctly sorts BELOW 51.

def _order(char: str) -> int:
    if char == "":
        return 0
    if char == "~":
        return -1
    if char.isdigit():
        return 0
    if char.isalpha():
        return ord(char)
    return ord(char) + 256


def _compare_fragment(a: str, b: str) -> int:
    i = j = 0
    while i < len(a) or j < len(b):
        first_diff = 0
        while (i < len(a) and not a[i].isdigit()) or (j < len(b) and not b[j].isdigit()):
            ac = _order(a[i] if i < len(a) else "")
            bc = _order(b[j] if j < len(b) else "")
            if ac != bc:
                return -1 if ac < bc else 1
            i += 1
            j += 1
        while i < len(a) and a[i] == "0":
            i += 1
        while j < len(b) and b[j] == "0":
            j += 1
        while i < len(a) and a[i].isdigit() and j < len(b) and b[j].isdigit():
            if not first_diff:
                first_diff = (a[i] > b[j]) - (a[i] < b[j])
            i += 1
            j += 1
        if i < len(a) and a[i].isdigit():
            return 1
        if j < len(b) and b[j].isdigit():
            return -1
        if first_diff:
            return first_diff
    return 0


def compare_versions(a: str, b: str) -> int:
    """-1, 0 or 1, following dpkg's ordering."""
    def split(v: str) -> tuple[int, str, str]:
        epoch = 0
        if ":" in v:
            head, _, v = v.partition(":")
            epoch = int(head) if head.isdigit() else 0
        upstream, sep, revision = v.rpartition("-")
        if not sep:
            upstream, revision = v, ""
        return epoch, upstream, revision

    ea, ua, ra = split(a)
    eb, ub, rb = split(b)
    if ea != eb:
        return -1 if ea < eb else 1
    result = _compare_fragment(ua, ub)
    if result:
        return result
    return _compare_fragment(ra, rb)


# --- APT index reading -------------------------------------------------------

def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=300) as response:
        return response.read()


def parse_sources(text: str) -> dict[str, dict[str, str]]:
    """deb822 Sources index -> {source name: stanza}.

    Only the fields this measurement uses are kept, and a later stanza for the
    same source wins only if its version is higher -- a suite can legitimately
    carry two versions of a source (e.g. -updates merged into a single view).
    """
    wanted = {"Package", "Version", "Binary", "Build-Depends", "Build-Depends-Arch"}
    sources: dict[str, dict[str, str]] = {}
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        stanza: dict[str, str] = {}
        key = None
        for line in block.splitlines():
            if line.startswith((" ", "\t")):
                if key in wanted:
                    stanza[key] = stanza.get(key, "") + " " + line.strip()
                continue
            key, _, value = line.partition(":")
            if key in wanted:
                stanza[key] = value.strip()
        name = stanza.get("Package")
        if not name or "Version" not in stanza:
            continue
        existing = sources.get(name)
        if existing is None or compare_versions(stanza["Version"], existing["Version"]) > 0:
            sources[name] = stanza
    return sources


def binary_to_source(sources: dict[str, dict[str, str]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name, stanza in sources.items():
        for binary in stanza.get("Binary", "").split(","):
            binary = binary.strip()
            if binary:
                mapping[binary] = name
    return mapping


def build_dep_clauses(stanza: dict[str, str]) -> list[list[tuple[str, str, str]]]:
    """Build-Depends as clauses of alternatives: [(name, op, version), ...].

    The constraint is kept, not discarded. Dropping it was the first version of
    this measurement and it was wrong: against a devel suite nearly every
    source is newer than an LTS's, so "donor is newer" closed over the whole
    archive and reported 1263 packages for Ubuntu, sweeping in swig, gettext,
    node-mocha and the Go and Ruby toolchains. What actually forces a rebuild
    is the target failing a DECLARED constraint, and most build-deps carry
    none at all.
    """
    clauses: list[list[tuple[str, str, str]]] = []
    raw = " ".join(
        stanza.get(field, "") for field in ("Build-Depends", "Build-Depends-Arch")
    )
    for clause in raw.split(","):
        alternatives: list[tuple[str, str, str]] = []
        for alternative in clause.split("|"):
            token = alternative.strip()
            if not token:
                continue
            name, op, version = token, "", ""
            if "(" in token:
                name, _, rest = token.partition("(")
                constraint = rest.split(")")[0].strip()
                for candidate in (">=", "<=", ">>", "<<", "="):
                    if constraint.startswith(candidate):
                        op = candidate
                        version = constraint[len(candidate):].strip()
                        break
            name = name.split("[")[0].split("<")[0].strip().split(":")[0].strip()
            if name:
                alternatives.append((name, op, version))
        if alternatives:
            clauses.append(alternatives)
    return clauses


def satisfies(have: str | None, op: str, want: str) -> bool:
    """Does `have` meet the constraint? Absent never satisfies."""
    if have is None:
        return False
    if not op:
        return True  # present at any version is enough
    result = compare_versions(have, want)
    return {
        ">=": result >= 0,
        ">>": result > 0,
        "<=": result <= 0,
        "<<": result < 0,
        "=": result == 0,
    }[op]


# --- the measurement ---------------------------------------------------------

def merge_indexes(urls) -> dict[str, dict[str, str]]:
    """One suite view from one or more component indexes, highest version wins."""
    if isinstance(urls, str):
        urls = [urls]
    merged: dict[str, dict[str, str]] = {}
    for url in urls:
        text = lzma.decompress(fetch(url)).decode("utf8", "replace")
        for name, stanza in parse_sources(text).items():
            existing = merged.get(name)
            if existing is None or compare_versions(stanza["Version"], existing["Version"]) > 0:
                merged[name] = stanza
    return merged



def measure(roots, donor, target, bin2src, target_binary) -> dict:
    """Close over Build-Depends, keeping only what the target cannot satisfy."""
    needed: dict[str, dict] = {}
    missing_roots: list[str] = []
    queue = collections.deque()

    for root in roots:
        if root not in donor:
            missing_roots.append(root)
            continue
        queue.append((root, 0))

    while queue:
        name, depth = queue.popleft()
        donor_stanza = donor.get(name)
        if donor_stanza is None:
            continue
        donor_version = donor_stanza["Version"]
        target_version = target.get(name, {}).get("Version")
        # The rule that bounds the closure: already satisfied means not our job.
        if target_version is not None and compare_versions(donor_version, target_version) <= 0:
            continue
        record = needed.get(name)
        if record is not None:
            record["depth"] = max(record["depth"], depth)
            continue
        needed[name] = {
            "source": name,
            "donor_version": donor_version,
            "target_version": target_version,
            "reason": "absent from target" if target_version is None else "target is older",
            "depth": depth,
        }
        for alternatives in build_dep_clauses(donor_stanza):
            # An alternative group is satisfied if ANY of its members is, so a
            # rebuild is only forced when every alternative fails.
            if any(
                satisfies(target_binary.get(binary), op, version)
                for binary, op, version in alternatives
            ):
                continue
            binary, _, _ = alternatives[0]
            source = bin2src.get(binary)
            if source and source != name:
                queue.append((source, depth + 1))

    return {"needed": needed, "missing_roots": missing_roots}


def donor_cannot_build(needed, donor, donor_binary) -> dict[str, list[str]]:
    """Packages the DONOR itself cannot satisfy the build dependencies of.

    A donor suite is not a static thing: it is mid-transition much of the
    time, and a source package in it may have been built against a version
    that has since moved on -- or has not yet migrated out of -proposed.

    Measured, not hypothetical. wayland-protocols 1.49-1 in Ubuntu stonking
    build-depends on libwayland-dev (>= 1.25.0), and `wayland` is 1.24.0-2 in
    BOTH stonking and resolute; 1.26.0-1 sits in stonking-proposed and has not
    migrated. So that package cannot be rebuilt from stonking at all, by us or
    by anyone, and the closure was right to leave `wayland` out -- the donor
    has nothing newer to offer.

    Without this check the order looks fine and the chain discovers it two
    minutes in, per package, after paying for a container and a buildroot
    (run 32643256826). Checking against the donor's own versions up front
    turns that into one line of the report.
    """
    blocked: dict[str, list[str]] = {}
    for name in needed:
        stanza = donor.get(name)
        if stanza is None:
            continue
        unmet = []
        for alternatives in build_dep_clauses(stanza):
            if any(
                satisfies(donor_binary.get(binary), op, version)
                for binary, op, version in alternatives
            ):
                continue
            # Only report what this view can actually decide. A Sources index
            # lists a source's REAL binaries; it says nothing about Provides,
            # so every virtual package looks absent. Reporting those made the
            # first version of this check flag 16 of 16 packages on
            # debhelper-compat, dh-sequence-gir, dh-sequence-gnome and the
            # gir1.2-*-dev virtuals -- all of them satisfied in reality, and
            # noise that would bury the one true finding.
            #
            # "Present but too old" is decidable. "Not in the map" is not, so
            # it stays silent.
            if not any(binary in donor_binary for binary, _, _ in alternatives):
                continue
            unmet.append(
                " | ".join(
                    f"{binary} ({op} {version})" if op else binary
                    for binary, op, version in alternatives
                )
            )
        if unmet:
            blocked[name] = unmet
    return blocked


def tiers(needed: dict[str, dict]) -> list[list[str]]:
    by_depth: dict[int, list[str]] = collections.defaultdict(list)
    for name, record in needed.items():
        by_depth[record["depth"]].append(name)
    # Deepest build-dependency first: a tier must build before what needs it.
    return [sorted(by_depth[d]) for d in sorted(by_depth, reverse=True)]


def render_build_order(target: str, entry: dict, roots: list[str]) -> str:
    """A tiered order the deb chain builder consumes.

    Deliberately NOT the same shape as build-order*.yml: those name a `path`
    to a spec directory in this repository, and a backport has no such path --
    the packaging comes from the donor suite. The unit here is a source
    package name and the exact donor version to fetch, so that a rebuild is
    reproducible against a moving archive.

    Generated, never hand-edited: re-running the measurement is the way to
    update it, and the header says so because a curated copy would rot the
    moment either suite moves.
    """
    versions = {p["source"]: p["donor_version"] for p in entry["packages"]}
    lines = [
        "# GENERATED by scripts/measure-deb-backport-gap.py -- do not hand-edit.",
        "# Re-run the measurement to update; a hand-edited copy rots as soon as",
        "# either suite moves, which is the failure this file exists to avoid.",
        f"target: {target}",
        f"target_suite: {entry['target_suite']}",
        f"donor_suite: {entry['donor_suite']}",
        "roots:",
    ]
    lines += [f"  - {root}" for root in roots]
    lines.append("tiers:")
    for index, tier in enumerate(entry["tiers"]):
        lines.append(f"  - name: tier-{index}")
        lines.append("    packages:")
        for source in tier:
            lines.append(f"      - source: {source}")
            lines.append(f"        version: \"{versions[source]}\"")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--target", help="Only measure this target from the manifest")
    parser.add_argument("--report-json")
    parser.add_argument(
        "--build-order",
        help="Write a tiered build order for --target here (requires --target)",
    )
    args = parser.parse_args()
    if args.build_order and not args.target:
        raise SystemExit("--build-order needs --target: an order is per-target")

    manifest = yaml.safe_load(pathlib.Path(args.manifest).read_text(encoding="utf-8"))
    roots = manifest["roots"]
    report = {"stack": manifest.get("stack"), "roots": roots, "targets": {}}

    for name, spec in manifest["targets"].items():
        if args.target and name != args.target:
            continue
        # A suite's sources are split across components (Ubuntu keeps some of
        # GNOME in universe), so each side is a LIST of indexes merged into one
        # view. Merging by highest version is what parse_sources already does
        # within an index; do the same across them.
        donor = merge_indexes(spec["donor_index"])
        target = merge_indexes(spec["target_index"])
        # Build-Depends name BINARY packages; the target's source version is
        # the honest proxy available from a Sources index, and binary and
        # source versions agree except where a source renames its binaries.
        target_binary = {
            binary: stanza["Version"]
            for stanza in target.values()
            for binary in (b.strip() for b in stanza.get("Binary", "").split(","))
            if binary
        }
        result = measure(roots, donor, target, binary_to_source(donor), target_binary)
        donor_binary = {
            binary: stanza["Version"]
            for stanza in donor.values()
            for binary in (b.strip() for b in stanza.get("Binary", "").split(","))
            if binary
        }
        blocked = donor_cannot_build(result["needed"], donor, donor_binary)
        order = tiers(result["needed"])
        report["targets"][name] = {
            "donor_suite": spec["donor_suite"],
            "target_suite": spec["target_suite"],
            "donor_sources": len(donor),
            "target_sources": len(target),
            "needed_count": len(result["needed"]),
            "missing_roots": result["missing_roots"],
            "donor_cannot_build": blocked,
            "tiers": order,
            "packages": sorted(result["needed"].values(), key=lambda r: (-r["depth"], r["source"])),
        }
        print(f"{name}: {spec['target_suite']} <- {spec['donor_suite']}: "
              f"{len(result['needed'])} source packages need rebuilding, "
              f"{len(order)} tiers", file=sys.stderr)
        if result["missing_roots"]:
            print(f"  roots absent from donor: {result['missing_roots']}", file=sys.stderr)
        if blocked:
            print(f"  NOT BUILDABLE FROM {spec['donor_suite']} ({len(blocked)}):", file=sys.stderr)
            for source, unmet in sorted(blocked.items()):
                print(f"    {source}: {'; '.join(unmet)}", file=sys.stderr)

    if args.build_order:
        entry = report["targets"][args.target]
        pathlib.Path(args.build_order).write_text(
            render_build_order(args.target, entry, report["roots"]), encoding="utf-8"
        )

    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report_json:
        pathlib.Path(args.report_json).write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
