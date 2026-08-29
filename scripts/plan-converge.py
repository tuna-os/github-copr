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

    open stage closed, all of them  -> packages-ready
    the open stage advanced         -> continue: the wave moved the stack
    the open stage did not move     -> blocked: two waves, no movement
    wave >= max_waves               -> budget: stop and report

## Why a stage and not a count

Measured 2026-08-28 against the live hummingbird index, the same repo on the
same day reads 580/673 over the build order and 3/10 over the packages a GNOME
session actually requires. A loop optimising the first number spends waves on
vdirsyncer and hplip while gdm and gnome-shell are absent -- every one of them
moves 580/673 upward and moves the stack not at all.

So the objective is scripts/stack_readiness.py's ordered stages, and only the
FIRST OPEN one decides anything. See docs/rfc/rfc012-request-driven-convergence.md.

## Why the terminal verdict is `packages-ready` and not `done`

Nothing here proves a desktop boots. tunaOS's `.github/green-criteria.yml`
defines that -- the image builds, ships the declared desktop, and boots under
QEMU with TUNAOS_DESKTOP_CONTRACT_OK on the serial console -- and only its gate
can assert it. What this side can assert is the negative that was costing whole
runs: while the contract stage is open, the image CANNOT boot into a session,
and building one to find out is fifteen minutes spent learning something
already known (tunaOS run 32813037866: 410 packages, no gnome-shell, no gdm,
the desktop check waived it, the gate failed a quarter of an hour later on a
marker that could never fire).

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
sys.path.insert(0, str(ROOT / "scripts"))
import stack_readiness  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "factory_status", ROOT / "scripts" / "factory-status.py"
)
_status = importlib.util.module_from_spec(_spec)


def _load_status():
    """Import factory-status lazily: it installs a urllib opener at import."""
    if not getattr(_status, "index_names", None):
        _spec.loader.exec_module(_status)
    return _status


# The terminal verdict is deliberately NOT called `done`: this side can prove
# every needed package is served, never that a desktop comes up. `done` belongs
# to tunaOS's gate.
PACKAGES_READY = "packages-ready"
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
            cache: pathlib.Path, *, roots_manifest: str = "",
            desktop: str = "") -> dict:
    """Served-vs-wanted, partitioned into stack_readiness's ordered stages.

    Without a roots manifest there is no desktop contract to stage by, so the
    whole build order becomes one `order` stage. That is a real case (a target
    with no gap_measurement) and it degrades to the flat count rather than
    inventing a contract.
    """
    status = _load_status()
    order_names = wanted_names(build_order)
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

    required: list[str] = []
    installed: list[str] = []
    if roots_manifest and desktop:
        required, installed = stack_readiness.desktop_sets(
            roots_manifest, desktop
        )
    staged = stack_readiness.stages(order_names, required, installed, served)
    open_stage = stack_readiness.first_open(staged)
    remaining = [name for name in order_names if name not in served]
    # Names the desktop needs that the build order does not carry still count:
    # a contract package nothing plans to build is the most important kind of
    # missing, and scoring only the order's own names would hide it.
    for stage in staged:
        for name in stage.remaining:
            if name not in remaining:
                remaining.append(name)
    return {
        "wanted": len(order_names),
        "served": len(order_names) - len([
            n for n in order_names if n not in served
        ]),
        "remaining": remaining,
        "stages": [
            {"name": s.name, "wanted": len(s.wanted), "served": s.served,
             "remaining": list(s.remaining)}
            for s in staged
        ],
        "open_stage": open_stage.name if open_stage else "",
        "open_remaining": len(open_stage.remaining) if open_stage else 0,
        "index_provenance": provenance,
        "unreachable_indexes": unreachable,
    }


def decide(open_stage: str, open_remaining: int,
           previous_stage: str | None, previous_remaining: int | None,
           wave: int, max_waves: int) -> tuple[str, str]:
    """The verdict, from the FIRST OPEN stage only.

    A later stage moving while the open one stands still is not progress
    toward a stack -- it is a wave spent on the tail. Judging on the open
    stage is what makes "580/673 and climbing" stop reading as success while
    gdm is absent.
    """
    if not open_stage:
        return PACKAGES_READY, (
            "every package the stack needs is served; whether it BOOTS is "
            "the gate's question"
        )
    where = f"`{open_stage}` stage: {open_remaining} package(s) to go"
    if wave >= max_waves:
        return BUDGET, f"wave {wave} of {max_waves}: {where}, budget spent"
    if previous_stage is None or previous_remaining is None:
        return CONTINUE, f"first wave: {where}"
    if previous_stage != open_stage:
        # The open stage moved on. Stages are ordered, so that is progress by
        # construction -- and it is the only progress signal that means the
        # stack got closer rather than merely the repo.
        return CONTINUE, (
            f"the last wave closed `{previous_stage}`; now {where}"
        )
    if open_remaining < previous_remaining:
        return CONTINUE, (
            f"the last wave served {previous_remaining - open_remaining} "
            f"more of `{open_stage}`; {open_remaining} to go"
        )
    return BLOCKED, (
        f"{where}, and the count did not fall (was {previous_remaining}). "
        "Rebuilding cannot fix this; the residue needs a packaging change."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--request",
        help='e.g. "gnome 51 on hummingbird". Supplies the build order, the '
             "served indexes and the desktop whose contract stages the "
             "objective -- all from the target contract, so a target is a "
             "contract block rather than a flag list.",
    )
    parser.add_argument("--build-order", type=pathlib.Path)
    parser.add_argument(
        "--served-index", action="append", default=[],
        help="Published index URL; repeat for each arch and each prefix.",
    )
    parser.add_argument("--roots-manifest", default="")
    parser.add_argument("--desktop", default="")
    parser.add_argument(
        "--previous-stage", default=None,
        help="The open stage the previous wave reported. Omit on wave 1.",
    )
    parser.add_argument(
        "--previous-remaining", type=int, default=None,
        help="That stage's remaining count. Omit on wave 1.",
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

    build_order = args.build_order
    indexes = list(args.served_index)
    roots_manifest = args.roots_manifest
    desktop = args.desktop
    if args.request:
        # A plain import, not importlib: build_request defines dataclasses,
        # and a module executed without being registered in sys.modules makes
        # @dataclass fail resolving its own annotations. scripts/ is already
        # on sys.path above.
        import build_request

        plan = build_request.resolve(args.request)
        if plan.unmeasurable:
            raise SystemExit(plan.unmeasurable)
        build_order = build_order or ROOT / plan.build_order
        roots_manifest = roots_manifest or plan.roots_manifest
        desktop = desktop or plan.desktop
        indexes = indexes or [
            url for arch in plan.architectures
            for url in plan.served_index.get(arch, [])
        ]

    if not build_order:
        raise SystemExit("--build-order or --request is required")
    if not indexes:
        raise SystemExit(
            "--served-index is required: convergence is measured against the "
            "published index, never against a wave's own result"
        )

    measurement = measure(
        build_order, indexes, args.cache,
        roots_manifest=roots_manifest, desktop=desktop,
    )
    verdict, why = decide(
        measurement["open_stage"], measurement["open_remaining"],
        args.previous_stage or None, args.previous_remaining,
        args.wave, args.max_waves,
    )
    if measurement["unreachable_indexes"] and verdict == PACKAGES_READY:
        # `packages-ready` ends the loop and green-lights an image build, so
        # it is the one verdict that must never be reached from an index we
        # could not read: an unreadable index understates `served`, and this
        # is the direction where that flips from cautious to catastrophic.
        verdict, why = BLOCKED, (
            "an index could not be read, so `packages-ready` cannot be "
            "trusted: "
            + ", ".join(u["url"] for u in measurement["unreachable_indexes"])
        )

    report = {
        "request": args.request or "",
        "wave": args.wave,
        "max_waves": args.max_waves,
        "verdict": verdict,
        "why": why,
        "previous_stage": args.previous_stage,
        "previous_remaining": args.previous_remaining,
        **measurement,
    }
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, indent=2) + "\n")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"verdict={verdict}\n")
            handle.write(f"open_stage={measurement['open_stage']}\n")
            handle.write(f"open_remaining={measurement['open_remaining']}\n")
            handle.write(f"remaining={len(measurement['remaining'])}\n")
            handle.write(f"served={measurement['served']}\n")
            handle.write(f"wanted={measurement['wanted']}\n")
            handle.write(f"next_wave={args.wave + 1}\n")
            handle.write(f"why={why}\n")

    print(f"wave {args.wave}/{args.max_waves}: {verdict.upper()} — {why}",
          file=sys.stderr)
    for stage in measurement["stages"]:
        print(f"  {stage['name']:9} {stage['served']:4}/{stage['wanted']:<4}"
              f" remaining {len(stage['remaining'])}", file=sys.stderr)
    if measurement["open_stage"]:
        stage = next(s for s in measurement["stages"]
                     if s["name"] == measurement["open_stage"])
        print("  open: " + ", ".join(stage["remaining"][:20])
              + (" …" if len(stage["remaining"]) > 20 else ""),
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
