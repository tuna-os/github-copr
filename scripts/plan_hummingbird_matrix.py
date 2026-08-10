#!/usr/bin/env python3
"""Fan `build-hummingbird-desktops.yml` out over desktops.

The workflow used to be a single job with a `desktop:` choice, so the whole
670-package gap was driven one dispatch at a time on one runner.  Measured on
five real runs (see docs/hummingbird-throughput.md) the build step is 95.6%-
97.8% mock time, so a job is busy essentially all of its wall clock -- the
ceiling is how many machines the work is spread over, and there was one.

This emits the matrix that spreads it.  The desktop names come out of the gap
report (`docs/hummingbird-desktop-gap.json` `.desktops`), which is the same
source `scripts/select-desktop-tiers.py` resolves a desktop against inside
each job, so the fan-out and the per-job tier selection cannot disagree about
which desktops exist.  Tier names are no longer a source of desktops: #303
retiered the manifest into one topological order over every desktop at once
(`layer-NN`), so a tier belongs to whichever desktops need its packages, not
to one named desktop.

Selection rules, matching what the workflow's own `Select tiers` step then
does inside each job:

  explicit `tiers:`   one job.  The tier list is absolute -- it names the
                      tiers to build, across whatever desktops need them --
                      so splitting it per desktop would change which tiers
                      run, not just where.
  `desktop: all`      one job per desktop, in gap-report order.
  `desktop: <name>`   one job.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def desktops_in(report: dict) -> list[str]:
    """Desktop names in gap-report order.

    Reading them out of the measured report rather than hard-coding them keeps
    this honest when the gap is re-measured: a sixth desktop in the report fans
    out to a sixth job with no workflow edit.
    """
    return list(report["desktops"])


def plan(report: dict, desktop: str, tiers: str) -> list[str]:
    known = desktops_in(report)
    if tiers.strip():
        return [desktop]
    if desktop == "all":
        return known
    if desktop not in known:
        raise SystemExit(
            f"no such desktop={desktop!r}; the gap report has {known}"
        )
    return [desktop]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gap-report", required=True, type=Path)
    parser.add_argument("--desktop", required=True)
    parser.add_argument("--tiers", default="")
    args = parser.parse_args(argv)

    report = json.loads(args.gap_report.read_text())
    print("desktops=" + json.dumps(plan(report, args.desktop, args.tiers)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
