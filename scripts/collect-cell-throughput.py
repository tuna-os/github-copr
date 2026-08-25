#!/usr/bin/env python3
"""Where a build-chain cell's hours actually go, from its own job log.

Adapted from koji-lag's approach (slopfest/sandogasa, Apache-2.0 OR
MIT): measure the build system from the metadata it already emits,
render small diffable reports, and never guess. The hand-run version of
this analysis exists as docs/hummingbird-throughput.md — five runs
scraped once, which found the chain running at concurrency 1.0 with
--jobs 2. That measurement went stale the day it merged; this tool
makes it repeatable against any cell log.

Per-package durations come from mock's own timers —
`INFO: Done(<srpm>) Config(<cfg>) N minutes M seconds` (and the ERROR:
Exception twin for failures) — NOT from surrounding log timestamps:
build-chain.sh runs workers in background subshells whose whole output
block carries the timestamp of worker exit. Wall clock comes from the
log timestamps of `==> Build chain starting` to `==> ===== Summary`.
Σ mock / wall is the effective concurrency: near 1.0 with --jobs 2 is
the defect the original measurement found.

Usage:
    # download a job log first, e.g. via the Actions API, then:
    scripts/collect-cell-throughput.py hummingbird-x86_64.log
    scripts/collect-cell-throughput.py *.log --json throughput.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import statistics
import sys

_DONE = re.compile(
    r"(?:INFO: Done|ERROR: Exception)\((?P<what>[^)]*)\)"
    r" Config\((?P<config>[^)]*)\)"
    r"(?: (?P<min>\d+) minutes?)? (?P<sec>\d+) seconds?")
_STAMP = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?Z? ")
_WALL_START = "==> Build chain starting"
_WALL_END = "==> ===== Summary"


def _srpm_package(what: str) -> str:
    """/builddir/SRPMS/foo-1.0-1.el10.src.rpm -> foo-1.0-1.el10."""
    stem = what.rsplit("/", 1)[-1]
    return stem.removesuffix(".src.rpm")


def _stamp(line: str) -> datetime.datetime | None:
    match = _STAMP.match(line)
    if not match:
        return None
    return datetime.datetime.fromisoformat(match.group("ts"))


def analyse_log(text: str) -> dict:
    """One log's package timings, failures, and wall clock."""
    packages: dict[str, dict] = {}
    wall_start = wall_end = None
    for line in text.splitlines():
        if _WALL_START in line and wall_start is None:
            wall_start = _stamp(line)
        if _WALL_END in line:
            wall_end = _stamp(line)
        match = _DONE.search(line)
        if not match:
            continue
        seconds = int(match.group("min") or 0) * 60 + int(match.group("sec"))
        packages[_srpm_package(match.group("what"))] = {
            "seconds": seconds,
            "failed": "ERROR: Exception" in line,
        }

    durations = sorted(info["seconds"] for info in packages.values())
    wall = None
    if wall_start and wall_end and wall_end > wall_start:
        wall = int((wall_end - wall_start).total_seconds())
    total = sum(durations)
    report = {
        "packages": packages,
        "package_count": len(packages),
        "failed": sorted(n for n, i in packages.items() if i["failed"]),
        "mock_seconds_total": total,
        "wall_seconds": wall,
        # Σ mock / wall — near 1.0 means the workers are serialized
        # whatever --jobs says (the finding of the original scrape).
        "effective_concurrency": round(total / wall, 2) if wall else None,
    }
    if durations:
        report["distribution"] = {
            "min": durations[0],
            "p10": durations[max(0, len(durations) // 10 - 1)],
            "median": int(statistics.median(durations)),
            "mean": int(statistics.mean(durations)),
            "p90": durations[min(len(durations) - 1,
                                 (len(durations) * 9) // 10)],
            "max": durations[-1],
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="per-package build timings from cell job logs")
    parser.add_argument("logs", nargs="+", type=pathlib.Path)
    parser.add_argument("--json", type=pathlib.Path)
    args = parser.parse_args()

    combined = {}
    for log in args.logs:
        report = analyse_log(log.read_text(errors="replace"))
        combined[log.name] = report
        wall = report["wall_seconds"]
        wall_text = f"{wall / 60:.1f} m" if wall else "n/a"
        concurrency = report["effective_concurrency"] or "n/a"
        print(f"{log.name}: {report['package_count']} package(s), "
              f"Σ mock {report['mock_seconds_total'] / 60:.1f} m, "
              f"wall {wall_text}, concurrency {concurrency}")
        if report["failed"]:
            print(f"  failed: {', '.join(report['failed'])}")
        slowest = sorted(report["packages"].items(),
                         key=lambda kv: -kv[1]["seconds"])[:10]
        for name, info in slowest:
            print(f"  {info['seconds']:>6}s  {name}")

    if args.json:
        args.json.write_text(json.dumps(combined, indent=2, sort_keys=True) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
