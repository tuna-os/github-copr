#!/usr/bin/env python3
"""Resolve a desktop name to the tiers that actually build it.

`build-order-hummingbird-desktops.yml` groups packages into tiers named after
the desktop that *introduced* them, not after every desktop that needs them.
A package shared by GNOME and XFCE lands in a `gnome-*` tier and appears
nowhere else, because the manifest deduplicates across desktops.

So selecting tiers by name prefix builds a small fraction of a desktop and
reports success.  Measured against the 78-tier manifest:

    desktop   tiers named <desktop>-*   tiers actually needed
    xfce                            9                     28
    cosmic                          9                     21
    kde                            19                     31
    niri                           14                     42

XFCE needs 248 source packages; nine of them are in `xfce-*` tiers.  A run of
`desktop: xfce` builds those nine and the other 239 are silently skipped --
which is not a build failure, it is a build that never attempts the work.

This resolves the other direction: take the desktop's `source_packages_to_build`
from the gap report and select every tier holding at least one of them.  If any
needed package lives in no tier at all, that is an error rather than a shorter
list, because a short list is indistinguishable from a correct one at the point
where it matters.
"""

import argparse
import json
import sys

import yaml

BOOTSTRAP_PREFIX = "bootstrap-"


def tier_packages(tier):
    """Source-package names in a tier.

    `distgit:` names the Fedora package to import; entries with a reviewed
    spec directory in this repository carry no `distgit:` and are named by
    the last component of their path.
    """
    names = set()
    for pkg in tier["packages"]:
        names.add(pkg.get("distgit") or pkg["path"].rsplit("/", 1)[-1])
    return names


def select(manifest, report, desktop, requested=None, exclude=()):
    tiers = manifest["tiers"]
    names = [t["name"] for t in tiers]
    contents = {t["name"]: tier_packages(t) for t in tiers}
    bootstrap = [n for n in names if n.startswith(BOOTSTRAP_PREFIX)]

    if requested:
        missing = [t for t in requested if t not in names]
        if missing:
            raise SystemExit(f"no such tier(s): {missing}")
        # An explicit list is taken verbatim: it is how a single tier gets
        # re-run on its own, including a bootstrap tier.
        selected = list(requested)
    elif desktop == "all":
        selected = list(names)
    else:
        if desktop not in report["desktops"]:
            raise SystemExit(
                f"desktop {desktop!r} not in gap report; have: "
                + ", ".join(sorted(report["desktops"]))
            )
        need = set(report["desktops"][desktop]["source_packages_to_build"])
        selected = bootstrap + [
            n for n in names
            if not n.startswith(BOOTSTRAP_PREFIX) and (contents[n] & need)
        ]
        covered = set().union(*(contents[n] for n in selected)) if selected else set()
        unplaced = need - covered
        if unplaced:
            raise SystemExit(
                f"{len(unplaced)} package(s) {desktop} needs are in no tier of "
                f"the manifest: {', '.join(sorted(unplaced)[:20])}"
                + (" ..." if len(unplaced) > 20 else "")
            )

    if exclude:
        selected = [n for n in selected if n not in set(exclude)]
    if not selected:
        raise SystemExit(f"no tiers selected for desktop={desktop}")
    # Order follows the manifest, which is the build order. Selecting a subset
    # must not reorder it.
    return selected


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--gap-report", required=True)
    ap.add_argument("--desktop", default="gnome")
    ap.add_argument(
        "--tiers", default="",
        help="comma-separated tier names; overrides --desktop when non-empty",
    )
    ap.add_argument(
        "--exclude-tiers", default="",
        help="comma-separated tiers to drop from the result, for splitting a "
             "shared trunk out of a per-desktop run",
    )
    args = ap.parse_args(argv)

    manifest = yaml.safe_load(open(args.manifest))
    report = json.load(open(args.gap_report))
    requested = [t.strip() for t in args.tiers.split(",") if t.strip()]
    exclude = [t.strip() for t in args.exclude_tiers.split(",") if t.strip()]
    print(",".join(select(manifest, report, args.desktop, requested, exclude)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
