#!/usr/bin/env python3
"""Decide whether a convergence loop dispatches another wave, stops, or asks.

## The loop this closes

A build-chain wave does not finish a desktop. It builds what fits in its
runners and its clock, publishes what it built, and leaves a residue. Closing
a target has therefore always meant a human watching: dispatch, wait hours,
read the served count, decide, dispatch again. The 2026-08-28 GNOME 51 night
was four waves driven that way, and three of the four decisions were
mechanical -- "the index moved, the gap is still open, go again".

The fourth was not, and that is the whole design constraint: a loop that
cannot tell "still working" from "stuck" is a loop that burns runners on a
wall forever. So this decides from ONE measurement -- how many of the build
order's packages the published index now serves -- against the same
measurement from the previous wave:

    remaining == 0                  -> done
    remaining <  previous           -> continue: the wave made progress
    remaining >= previous           -> blocked: two waves, no movement
    wave      >= max_waves          -> budget: stop and report

`blocked` is not a failure. It is the loop reaching the edge of what
rebuilding can fix and handing the residue to whoever (or whatever) writes
packaging fixes -- with scripts/classify-chain-failures.py's blocker list as
the handoff. See docs/rfc/rfc012-request-driven-convergence.md.

## Why the served index and not the wave's own result

A wave reports success per shard, and a shard is green when its packages
built -- which says nothing about whether they reached users. The published
index is the only thing that answers "is this actually served", it is what
the next wave's `--served-nvrs` skip reads, and it is what an image
installing the desktop resolves against. Measuring anything else would let
the loop declare victory over packages nobody can install; #519 is what that
looks like when it goes wrong in the other direction.

Nothing here is inferred from a name or a run conclusion. Every number comes
out of a live index, and --report-json records which revision it came from.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "factory_status", ROOT / "scripts" / "factory-status.py"
)
_status = importlib.util.module_from_spec(_spec)


def _load_status():
    """Import factory-status lazily: it installs a urllib opener at import."""
    if not getattr(_status, "index_names", None):
        _spec.loader.exec_module(_status)
    return _status


DONE = "done"
CONTINUE = "continue"
BLOCKED = "blocked"
BUDGET = "budget"


def wanted_names(build_order: pathlib.Path) -> list[str]:
    """Every source package a build order declares, in tier order.

    A tier entry is either a `path:` into the source tree, a `copr_name:`, or
    a bare `name:` for a dist-git import. The NAME is the last path segment
    in every case, because that is what the index answers for -- the tree
    layout is ours and the index does not know it.
    """
    manifest = yaml.safe_load(build_order.read_text(encoding="utf-8"))
    names: list[str] = []
    for tier in manifest.get("tiers") or []:
        for package in tier.get("packages") or []:
            if isinstance(package, str):
                names.append(package.rsplit("/", 1)[-1])
                continue
            name = (
                package.get("name")
                or package.get("path", "").rsplit("/", 1)[-1]
                or package.get("copr_name", "")
            )
            if name:
                names.append(name)
    return list(dict.fromkeys(names))


def measure(build_order: pathlib.Path, index_urls: list[str],
            cache: pathlib.Path) -> dict:
    status = _load_status()
    wanted = wanted_names(build_order)
    served: set[str] = set()
    provenance = []
    unreachable = []
    for url in index_urls:
        try:
            names, where = status.index_names(url, cache)
        except Exception as error:  # noqa: BLE001 -- reported, never swallowed
            # An index that cannot be read is NAMED, not dropped. Dropping it
            # would understate `served`, which reads as "more work remains" --
            # the loop would keep dispatching waves that rebuild packages the
            # repo already carries.
            unreachable.append({"url": url, "error": str(error)})
            continue
        served |= names
        provenance.append(where)
    remaining = [name for name in wanted if name not in served]
    return {
        "wanted": len(wanted),
        "served": len(wanted) - len(remaining),
        "remaining": remaining,
        "index_provenance": provenance,
        "unreachable_indexes": unreachable,
    }


def decide(remaining: int, previous: int | None, wave: int,
           max_waves: int) -> tuple[str, str]:
    if remaining == 0:
        return DONE, "every package in the build order is served"
    if wave >= max_waves:
        return BUDGET, (
            f"wave {wave} of {max_waves}: {remaining} package(s) still "
            "unserved, and the wave budget is spent"
        )
    if previous is None:
        return CONTINUE, f"first wave: {remaining} package(s) to build"
    if remaining < previous:
        return CONTINUE, (
            f"the last wave served {previous - remaining} more package(s); "
            f"{remaining} to go"
        )
    return BLOCKED, (
        f"{remaining} package(s) unserved and the count did not fall "
        f"(was {previous}). Rebuilding cannot fix this; the residue needs a "
        "packaging change."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build-order", type=pathlib.Path, required=True)
    parser.add_argument(
        "--served-index", action="append", default=[],
        help="Published index URL; repeat for each arch and each prefix.",
    )
    parser.add_argument(
        "--previous-remaining", type=int, default=None,
        help="The remaining count the previous wave reported. Omit on the "
             "first wave.",
    )
    parser.add_argument("--wave", type=int, default=1)
    parser.add_argument("--max-waves", type=int, default=8)
    parser.add_argument("--cache", type=pathlib.Path,
                        default=pathlib.Path(".cache/converge"))
    parser.add_argument("--report-json", type=pathlib.Path)
    parser.add_argument(
        "--github-output", type=pathlib.Path,
        default=pathlib.Path(os.environ["GITHUB_OUTPUT"])
        if os.environ.get("GITHUB_OUTPUT") else None,
    )
    args = parser.parse_args(argv)

    if not args.served_index:
        raise SystemExit(
            "--served-index is required: convergence is measured against the "
            "published index, never against a wave's own result"
        )

    measurement = measure(args.build_order, args.served_index, args.cache)
    remaining = len(measurement["remaining"])
    verdict, why = decide(
        remaining, args.previous_remaining, args.wave, args.max_waves
    )
    if measurement["unreachable_indexes"] and verdict == DONE:
        # "Done" from an index we could not read is the one verdict that must
        # never be reached on partial evidence: it ends the loop.
        verdict, why = BLOCKED, (
            "an index could not be read, so `done` cannot be trusted: "
            + ", ".join(u["url"] for u in measurement["unreachable_indexes"])
        )

    report = {
        "wave": args.wave,
        "max_waves": args.max_waves,
        "verdict": verdict,
        "why": why,
        "previous_remaining": args.previous_remaining,
        **measurement,
    }
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, indent=2) + "\n")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"verdict={verdict}\n")
            handle.write(f"remaining={remaining}\n")
            handle.write(f"served={measurement['served']}\n")
            handle.write(f"wanted={measurement['wanted']}\n")
            handle.write(f"next_wave={args.wave + 1}\n")
            handle.write(f"why={why}\n")
    print(
        f"wave {args.wave}/{args.max_waves}: "
        f"{measurement['served']}/{measurement['wanted']} served -> "
        f"{verdict.upper()} ({why})",
        file=sys.stderr,
    )
    if measurement["remaining"]:
        print(
            "remaining: " + ", ".join(measurement["remaining"][:40])
            + (" …" if remaining > 40 else ""),
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
