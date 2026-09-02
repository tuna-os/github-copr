#!/usr/bin/env python3
"""Split a build order into tier-bands and per-band shards for fan-out.

The invariant this rides: a build order's tiers are dependency layers, so
packages WITHIN one tier never depend on each other. Disjoint subsets of a
band's packages can therefore build on separate runners against the same
inputs (the served index plus every earlier band's collected output), and a
single collector merges the results between bands. Nothing here changes what
gets built -- only where.

Output (JSON on stdout):

    {
      "bands": [
        {"index": 0,
         "tiers": "bootstrap-00,bootstrap-01",
         "shards": [["src/a", "src/b"], ["src/c"]]},
        ...
      ]
    }

Band boundaries respect tier order: a band is a contiguous run of tiers, cut
so package counts stay roughly even. Shards are dealt round-robin in tier
order, which keeps each shard's work spread across the band's tiers rather
than concentrating one slow tier in one shard.

Shard lists are consumed by `build-chain.sh --packages-file`; the tiers
string by `--tiers`. Empty shards are dropped so the workflow matrix never
schedules a runner with nothing to do.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def read_tiers(order: str) -> list[tuple[str, list[str]]]:
    """[(tier_name, [pkg_path, ...]), ...] in build order."""
    parse = SCRIPT_DIR / "parse-build-order.py"
    names = subprocess.run(
        [sys.executable, str(parse), order, "--tiers"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    tiers = []
    for name in names:
        out = subprocess.run(
            [sys.executable, str(parse), order, "--tier", name],
            capture_output=True, text=True, check=True,
        ).stdout
        pkgs = [line.split("\t")[0] for line in out.splitlines() if line.strip()]
        tiers.append((name, pkgs))
    return tiers


def cut_bands(tiers: list[tuple[str, list[str]]], band_count: int) -> list[list[tuple[str, list[str]]]]:
    """Contiguous tier runs with roughly even package counts.

    Greedy: close the current band once it holds its fair share of the
    REMAINING packages over the REMAINING bands, but never leave more bands
    than tiers left to fill them.
    """
    total = sum(len(p) for _, p in tiers)
    bands: list[list[tuple[str, list[str]]]] = []
    current: list[tuple[str, list[str]]] = []
    placed = 0
    current_count = 0
    for i, (name, pkgs) in enumerate(tiers):
        current.append((name, pkgs))
        current_count += len(pkgs)
        placed += len(pkgs)
        bands_left = band_count - len(bands)
        tiers_left = len(tiers) - i - 1
        fair = (total - placed + current_count) / max(bands_left, 1)
        if bands_left > 1 and current_count >= fair and tiers_left >= bands_left - 1:
            bands.append(current)
            current = []
            current_count = 0
    if current:
        bands.append(current)
    return bands


def deal_shards(pkgs: list[str], shard_count: int) -> list[list[str]]:
    shards: list[list[str]] = [[] for _ in range(shard_count)]
    for i, p in enumerate(pkgs):
        shards[i % shard_count].append(p)
    return [s for s in shards if s]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--order", required=True)
    ap.add_argument("--bands", type=int, default=5)
    ap.add_argument("--shards", type=int, default=8)
    args = ap.parse_args()
    if args.bands < 1 or args.shards < 1:
        raise SystemExit("--bands and --shards must be >= 1")

    tiers = read_tiers(args.order)
    if not tiers:
        raise SystemExit(f"{args.order}: no tiers")

    bands = []
    for idx, band in enumerate(cut_bands(tiers, args.bands)):
        pkgs = [p for _, tier_pkgs in band for p in tier_pkgs]
        bands.append({
            "index": idx,
            "tiers": ",".join(name for name, _ in band),
            "shards": deal_shards(pkgs, args.shards),
        })
    json.dump({"bands": bands}, sys.stdout)
    print()


if __name__ == "__main__":
    main()
