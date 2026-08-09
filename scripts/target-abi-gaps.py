#!/usr/bin/env python3
"""Which of the target's OWN packages cannot install in the buildroot.

Hummingbird is the highest-priority repository in mock/hummingbird-ci.cfg, so
its packages win the buildroot whenever a name matches.  That is the point --
we must build against the ABI the target actually ships.  It only works while
the target is self-consistent, and it is not:

    package re2-2:20251105-19.hum1.x86_64 from hummingbird requires
      libabsl_hash.so.2601.0.0()(64bit), but none of the providers can be
      installed

Hummingbird's protobuf and re2 were linked against abseil-cpp soname 2601 and
Hummingbird never shipped that abseil.  Rawhide's is 20260526.0, a different
soname.  Those packages are dead on arrival, and so is every buildroot that
pulls one in -- which is what failed libphonenumber in run 31281499563.

Excluding them lets dnf fall back to Rawhide's protobuf/re2, which are
self-consistent.  Excluding a package that cannot install is safe by
construction: no successful resolution could have used it.  The catch is that
the set has to be closed -- dropping protobuf-cpp orphans protobuf-devel,
which requires it by soname -- so this iterates to a fixed point.

    scripts/target-abi-gaps.py --check      # exit 1 if the config is stale
    scripts/target-abi-gaps.py              # print the report
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MOCK_CONFIG = REPO / "mock" / "hummingbird-ci.cfg"


def _load_gap_module():
    spec = importlib.util.spec_from_file_location(
        "measure_hummingbird_gap", REPO / "scripts" / "measure-hummingbird-gap.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def is_soname(capability: str) -> bool:
    """A shared-library dependency, as opposed to a name or a python dist tag.

    Only these cascade.  A missing `python3.14dist(flask)` means an optional
    `+extras` metapackage cannot install, which costs nothing until something
    asks for it; excluding those would hide the gap rather than close it.
    """
    return capability.startswith("lib") and ".so." in capability


def unsatisfiable(target, reference, excluded=frozenset()):
    """Target packages requiring capabilities the buildroot cannot provide."""
    provides: dict[str, set] = collections.defaultdict(set)
    for capability, names in target["provides"].items():
        kept = set(names) - excluded
        if kept:
            provides[capability] |= kept
    for name in target["packages"]:
        if name not in excluded:
            provides[name].add(name)
    have = set(provides) | set(reference["provides"]) | set(reference["packages"])

    broken = {}
    for name, info in target["packages"].items():
        if name in excluded:
            continue
        missing = [
            requirement
            for requirement in info["requires"]
            if not requirement.startswith("(") and requirement not in have
        ]
        if missing:
            broken[name] = missing
    return broken


def exclude_closure(target, reference, limit=16):
    """Smallest exclude set leaving no soname-broken target package behind.

    Iterated rather than computed in one pass because excluding a package can
    break another: protobuf-devel is fine until protobuf-cpp goes, and then it
    is not.  Measured against the indexes of 2026-08-09 this converges in two
    rounds on five packages.
    """
    excluded: set[str] = set()
    for _ in range(limit):
        broken = unsatisfiable(target, reference, excluded)
        fresh = {
            name
            for name, missing in broken.items()
            if any(is_soname(capability) for capability in missing)
        } - excluded
        if not fresh:
            return excluded
        excluded |= fresh
    raise RuntimeError(
        f"exclude set did not converge in {limit} rounds; the target's own "
        "dependency graph is more broken than this tool assumes"
    )


def configured_excludes(text: str) -> set[str]:
    """The excludepkgs the hummingbird repository carries in the mock config."""
    block = re.search(r"\[hummingbird\]\n(.*?)(?=\n\[|\n\"\"\"|\Z)", text, re.S)
    if not block:
        return set()
    found = re.search(r"^excludepkgs=(.*)$", block.group(1), re.M)
    if not found:
        return set()
    return {name.strip() for name in found.group(1).split(",") if name.strip()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero if the mock config is out of date")
    parser.add_argument("--cache", type=Path,
                        default=Path.home() / ".cache" / "tunaos-gap")
    parser.add_argument("--target", default="https://packages.redhat.com/api/"
                        "pulp-content/public-hummingbird/x86_64/")
    parser.add_argument("--reference", default="https://dl.fedoraproject.org/pub/"
                        "fedora/linux/development/rawhide/Everything/x86_64/os/")
    args = parser.parse_args()

    gap = _load_gap_module()
    target = gap.parse_primary(gap.primary_of(args.target, args.cache)[0])
    reference = gap.parse_primary(gap.primary_of(args.reference, args.cache)[0])

    broken = unsatisfiable(target, reference)
    excluded = exclude_closure(target, reference)
    remaining = unsatisfiable(target, reference, excluded)

    print(f"target packages                 {len(target['packages'])}")
    print(f"cannot install as shipped       {len(broken)}")
    print(f"exclude closure                 {','.join(sorted(excluded))}")
    print(f"still broken after the exclude  {len(remaining)}"
          f" (all non-soname: "
          f"{not any(is_soname(c) for m in remaining.values() for c in m)})")

    if args.check:
        configured = configured_excludes(MOCK_CONFIG.read_text())
        if configured != excluded:
            print(
                f"\nmock/hummingbird-ci.cfg excludes {sorted(configured)}\n"
                f"but the measured closure is       {sorted(excluded)}",
                file=sys.stderr,
            )
            return 1
        print("\nmock config matches the measured closure")
    return 0


if __name__ == "__main__":
    sys.exit(main())
