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

Beyond name-level satisfiability, two further checks adapted from ebranch
(slopfest/sandogasa, Apache-2.0 OR MIT), each pinned to a failure this
factory has already paid for (#480):

  * version-blocked -- a versioned BuildRequires whose provider exists
    everywhere at a version that satisfies nowhere (gnome-settings-daemon
    needs libnotify >= 0.8.7, the buildroot resolves 0.8.6).
  * runtime-unsatisfied -- a Requires of a binary the build set will
    produce that neither the target nor the build set provides, so the
    clean-install verify must fail (gtkgreet Requires greetd, which was
    in no xfce tier and no enabled repo).

Usage:

    scripts/preflight-buildrequires.py --target <id> [--manifest ORDER.yml]

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
        "gap", HERE / "gap_engine.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_vercmp():
    spec = importlib.util.spec_from_file_location(
        "rpm_vercmp", HERE / "rpm_vercmp.py")
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


def version_blocked(sources, source_versioned, available_evr, vercmp):
    """Versioned BuildRequires no available provider satisfies.

    The name-level check above cannot see the libnotify class (#480):
    gnome-settings-daemon needs `libnotify >= 0.8.7`, every repo in
    sight provides libnotify, and the best of them is 0.8.6 — knowable
    from the indexes, discovered by mock hours into the chain, on both
    arches. This is ebranch's BlockedByBase idea (slopfest/sandogasa):
    a dependency whose provider exists at an unsatisfying version is a
    decision to surface, not a build to attempt.

    `available_evr` maps capability -> set of EVRs it is provided at,
    unioned across everything the buildroot can draw from. A capability
    provided only WITHOUT a version stays out of that map, and out of
    this report — an unjudgeable constraint must not become noise.
    """
    blocked = collections.defaultdict(list)
    for name in sources:
        for dep, op, required in source_versioned.get(name, ()):
            offered = available_evr.get(dep)
            if not offered:
                continue
            if any(vercmp.satisfies(evr, op, required) for evr in offered):
                continue
            best = max(offered, key=lambda evr: _sort_key(vercmp, evr, offered))
            blocked[name].append(f"{dep} {op} {required} (best available {best})")
    return dict(blocked)


def _sort_key(vercmp, evr, offered):
    """Rank an EVR by how many of the offered set it beats or ties."""
    return sum(vercmp.compare_evr(evr, other) >= 0 for other in offered)


def _srpm_name(srpm):
    """python-foo-1.2-3.fc45.src.rpm -> python-foo."""
    if not srpm:
        return None
    stem = srpm[: -len(".src.rpm")] if srpm.endswith(".src.rpm") else srpm
    return stem.rsplit("-", 2)[0]


def runtime_unsatisfied(sources, reference, have, rich_prefix="("):
    """Runtime Requires of the build set's own binaries that nothing supplies.

    The install environment is the target's repositories plus what this
    build order builds — NOT the build reference, which exists only in
    the buildroot. gtkgreet Requires greetd, greetd was in no xfce tier
    and in no enabled repo, and a 53-minute aarch64 build found out at
    clean-install time (#480). The answer was in the indexes: for every
    binary the build set will produce (the reference's binaries whose
    source is in the set), every Requires must resolve against the
    target's capabilities plus the build set's own.

    Adapted from ebranch's check_installability (slopfest/sandogasa),
    which expands its closure until subpackages install; here the build
    orders are curated, so the gap is reported for a human to close.
    """
    packages = reference["packages"]
    provides = reference["provides"]
    wanted = set(sources)
    buildset_bins = {
        bin_name for bin_name, info in packages.items()
        if _srpm_name(info.get("srpm")) in wanted
    }
    available = set(have) | buildset_bins | {
        cap for cap, providers in provides.items() if providers & buildset_bins
    }
    missing = collections.defaultdict(list)
    for bin_name in sorted(buildset_bins):
        for requirement in packages[bin_name].get("requires", ()):
            if requirement is None or requirement.startswith(rich_prefix):
                continue
            if requirement.startswith("rpmlib("):
                continue
            if requirement not in available:
                missing[bin_name].append(requirement)
    return dict(missing)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True,
                        help="factory target id; its gap_measurement contract "
                             "in manifests/package-factory.yaml supplies the "
                             "roots manifest and repository indexes — no "
                             "target is ever assumed")
    parser.add_argument("--manifest", type=pathlib.Path,
                        help="build order to preflight (default: the file "
                             "the target's drift regeneration writes, "
                             "build-order-<target>-desktops.yml)")
    parser.add_argument("--factory", type=pathlib.Path,
                        default=pathlib.Path("manifests/package-factory.yaml"))
    parser.add_argument("--cache", type=pathlib.Path,
                        default=pathlib.Path(".cache/target-gap"))
    parser.add_argument("--arch", default="x86_64")
    args = parser.parse_args()

    gap = load_gap()
    factory = yaml.safe_load(args.factory.read_text())
    measurement = gap.target_measurement(factory, args.target)
    manifest = args.manifest or pathlib.Path(
        f"build-order-{args.target}-desktops.yml")
    baseurl = (measurement["target_index"]
               .replace("$arch", args.arch).replace("$basearch", args.arch))

    target_index = gap.parse_primary(gap.primary_of(baseurl, args.cache)[0])
    reference = gap.parse_primary(gap.primary_of(
        measurement["reference_index"], args.cache)[0])
    source_index = gap.parse_source_primary(
        gap.primary_of(measurement["source_reference_index"], args.cache)[0])
    have = set(target_index["provides"]) | set(target_index["packages"])

    order = yaml.safe_load(manifest.read_text())
    sources = sorted({
        pkg.get("distgit") or pkg["path"].rsplit("/", 1)[-1]
        for tier in order["tiers"] for pkg in tier["packages"]
    })

    blocked = unsatisfiable(sources, source_index, reference["provides"], have,
                            gap.RICH_DEP_PREFIX)

    # Versioned constraints: available = the same buildroot the name-level
    # check assumes (target union reference), judged at EVR level.
    vercmp = load_vercmp()
    source_versioned = gap.parse_source_primary_versioned(
        gap.primary_of(measurement["source_reference_index"], args.cache)[0])
    available_evr = collections.defaultdict(set)
    for index in (target_index, reference):
        for cap, evrs in index.get("provides_evr", {}).items():
            available_evr[cap].update(evrs)
    versioned = version_blocked(sources, source_versioned, available_evr, vercmp)

    # Runtime: the install environment is the target plus the build set,
    # WITHOUT the reference — that is what the clean-install verify sees.
    runtime = runtime_unsatisfied(sources, reference, have, gap.RICH_DEP_PREFIX)

    print(f"source packages in the build order : {len(sources)}")
    print(f"packages that cannot build         : {len(blocked)}")
    print(f"version-blocked packages           : {len(versioned)}")
    print(f"binaries that cannot install       : {len(runtime)}")
    if not blocked and not versioned and not runtime:
        print("\nevery BuildRequires is satisfiable, every version constraint "
              "is met, and every built binary will install")
        return 0

    if blocked:
        blocked_by = collections.Counter(
            cap for caps in blocked.values() for cap in caps)
        print()
        for cap, count in blocked_by.most_common():
            users = sorted(n for n, caps in blocked.items() if cap in caps)
            print(f"  {cap}  blocks {count}: {', '.join(users)}")
    if versioned:
        print("\nversion-blocked (provider exists, version does not satisfy):")
        for name in sorted(versioned):
            for detail in versioned[name]:
                print(f"  {name}  needs {detail}")
    if runtime:
        runtime_by = collections.Counter(
            cap for caps in runtime.values() for cap in caps)
        print("\nruntime Requires nothing in target+build-set provides:")
        for cap, count in runtime_by.most_common():
            users = sorted(n for n, caps in runtime.items() if cap in caps)
            print(f"  {cap}  breaks install of {count}: {', '.join(users)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
