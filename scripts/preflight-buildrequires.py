#!/usr/bin/env python3
"""Find the packages that cannot build before spending four hours proving it.

A tier's job only discovers an unsatisfiable BuildRequires when it gets there.
On the 40-layer order that can be hours in, and the answer was knowable before
the run started: for every source package in the build order, is every one of
its BuildRequires provided by something -- the target, the reference, or another
package in the build set?

Run against the current manifest this reports one package out of 1245:

    SwayNotificationCenter  needs pkgconfig(granite-7)

Rawhide carries exactly one granite source package and it provides
pkgconfig(granite) and libgranite.so.6. Three Rawhide packages BuildRequire
granite-7 -- SwayNotificationCenter, minder, warble -- so this is a Fedora-wide
FTBFS rather than anything specific to Hummingbird, and SwayNotificationCenter
is a declared niri root.

Usage:

    scripts/preflight-buildrequires.py --manifest build-order-hummingbird-desktops.yml

Exits non-zero when anything is unsatisfiable, so it can gate a dispatch.
"""

import argparse
import collections
import importlib.util
import pathlib
import sys

import yaml

HERE = pathlib.Path(__file__).resolve().parent


def load_gap():
    spec = importlib.util.spec_from_file_location(
        "gap", HERE / "measure-hummingbird-gap.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unsatisfiable(sources, source_index, provides, have, rich_prefix="("):
    """Which BuildRequires of these sources nothing can supply.

    A requirement is fine if the target already ships it, if rpm resolves it at
    install time (a rich dependency), or if anything in the reference provides
    it -- the reference is the buildroot, and the build set is a subset of it,
    so "not in the reference" means not available from any source at all.
    """
    blocked = collections.defaultdict(list)
    for name in sources:
        for requirement in source_index.get(name, ()):
            if requirement in have or requirement.startswith(rich_prefix):
                continue
            if requirement not in provides:
                blocked[name].append(requirement)
    return dict(blocked)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=pathlib.Path,
                        default=pathlib.Path("build-order-hummingbird-desktops.yml"))
    parser.add_argument("--catalog", type=pathlib.Path,
                        default=pathlib.Path("manifests/hummingbird-desktops.yaml"))
    parser.add_argument("--cache", type=pathlib.Path,
                        default=pathlib.Path(".cache/hummingbird-gap"))
    parser.add_argument("--arch", default="x86_64")
    args = parser.parse_args()

    gap = load_gap()
    catalog = yaml.safe_load(args.catalog.read_text())
    target = catalog["target"]
    baseurl = target["baseurl"].replace("$arch", args.arch).replace("$basearch", args.arch)

    target_index = gap.parse_primary(gap.primary_of(baseurl, args.cache)[0])
    reference = gap.parse_primary(gap.primary_of(gap.DEFAULT_REFERENCE, args.cache)[0])
    source_index = gap.parse_source_primary(
        gap.primary_of(gap.DEFAULT_SOURCE_REFERENCE, args.cache)[0])
    have = set(target_index["provides"]) | set(target_index["packages"])

    order = yaml.safe_load(args.manifest.read_text())
    sources = sorted({
        pkg.get("distgit") or pkg["path"].rsplit("/", 1)[-1]
        for tier in order["tiers"] for pkg in tier["packages"]
    })

    blocked = unsatisfiable(sources, source_index, reference["provides"], have,
                            gap.RICH_DEP_PREFIX)

    print(f"source packages in the build order : {len(sources)}")
    print(f"packages that cannot build         : {len(blocked)}")
    if not blocked:
        print("\nevery BuildRequires in the build order is satisfiable")
        return 0

    blocked_by = collections.Counter(
        cap for caps in blocked.values() for cap in caps)
    print()
    for cap, count in blocked_by.most_common():
        users = sorted(n for n, caps in blocked.items() if cap in caps)
        print(f"  {cap}  blocks {count}: {', '.join(users)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
