#!/usr/bin/env python3
"""Ask the factory for a desktop on a target, in words.

    scripts/request.py "gnome 51 on hummingbird"
    scripts/request.py "gnome 51 on hummingbird" --measure
    scripts/request.py "gnome 52 on hummingbird" --adopt
    scripts/request.py "gnome 51 on hummingbird" --json plan.json

This is the front door to the loop RFC 012 describes. It answers, in this
order:

  1. Does the contract know this ask?  (target, desktop, release, arches,
     cells, build order, served indexes -- all from files, no network.)
  2. Is the ask a MOVE?  A release the roots manifest does not declare is a
     rename across six declarations, and missing one is silent: an un-listed
     source path does not re-key its cell, so the action cache serves output
     built from the old spec. `--adopt` moves them together or fails.
  3. How far is it from done?  `--measure` reads the live published index and
     reports served-vs-wanted over the generated build order -- the same
     number the convergence loop stops on.

What it deliberately does NOT do is generate the build order itself. That is
scripts/measure-target-gap.py, driven by the same contract, and running it
here would put a second caller in front of the one engine RFC 011 exists to
keep single. This prints the command.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_request  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _converge():
    spec = importlib.util.spec_from_file_location(
        "plan_converge", ROOT / "scripts" / "plan-converge.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render(plan: build_request.Plan, measurement: dict | None) -> str:
    lines = [
        f"# {plan.desktop} {plan.release} on {plan.target}",
        "",
        f"- target contract : manifests/package-factory.yaml -> {plan.target}",
        f"- roots manifest  : {plan.roots_manifest or '(none)'}",
        f"- build order     : {plan.build_order or '(none — curated by hand)'}",
        f"- architectures   : {', '.join(plan.architectures) or '(none)'}",
        f"- cells           : {', '.join(plan.cells) or '(none)'}",
        f"- desktop roots   : {len(plan.roots)}",
        f"- source paths    : {', '.join(plan.source_paths) or '(none)'}",
        "",
    ]
    if plan.unmeasurable:
        lines += [
            "## This target cannot answer a request yet",
            "",
            plan.unmeasurable,
            "",
        ]
    if plan.is_move:
        lines += [
            f"## This is a move: {plan.declared_track_dir} -> {plan.track_dir}",
            "",
            "Declarations that name the track and must move together:",
            "",
        ]
        lines += [
            f"  - {d.path.relative_to(ROOT)} ({d.occurrences})"
            for d in plan.declarations
        ]
        lines += ["", "Run again with `--adopt` to move them.", ""]
        if plan.decisions:
            lines += [
                "Declarations a move touches that `--adopt` will NOT rewrite "
                "— they model more than one track at once, so the shift is "
                "yours to make:",
                "",
            ]
            lines += [
                f"  - {d.path.relative_to(ROOT)} ({d.occurrences})"
                for d in plan.decisions
            ]
            lines += [""]
    for note in plan.notes:
        lines += [f"> {note}", ""]

    if plan.build_order and not plan.unmeasurable:
        lines += [
            "## Regenerate the build order from the live indexes",
            "",
            "```",
            f"scripts/measure-target-gap.py --target {plan.target} \\",
            f"  --report-json {plan.report_json} \\",
            f"  --build-order {plan.build_order}",
            "```",
            "",
        ]

    if measurement:
        remaining = len(measurement["remaining"])
        lines += [
            "## Distance to done, measured against the published index",
            "",
            f"- served  : {measurement['served']}/{measurement['wanted']}",
            f"- remaining: {remaining}",
            "",
        ]
        if measurement["unreachable_indexes"]:
            lines += [
                "Indexes that could not be read (so `served` is a floor, "
                "not the answer):",
                "",
            ]
            lines += [
                f"  - {u['url']}: {u['error']}"
                for u in measurement["unreachable_indexes"]
            ]
            lines += [""]
        if remaining:
            shown = measurement["remaining"][:40]
            lines += [
                "Still to build"
                + (f" (first 40 of {remaining})" if remaining > 40 else "")
                + ":",
                "",
                "  " + ", ".join(shown),
                "",
            ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("request", help='e.g. "gnome 51 on hummingbird"')
    parser.add_argument(
        "--adopt", action="store_true",
        help="Move every declaration onto the requested release track.",
    )
    parser.add_argument(
        "--measure", action="store_true",
        help="Read the live published index and report served vs wanted.",
    )
    parser.add_argument("--json", type=pathlib.Path)
    args = parser.parse_args(argv)

    try:
        plan = build_request.resolve(args.request)
    except build_request.RequestError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.adopt:
        if not plan.is_move:
            print(
                f"nothing to adopt: {plan.roots_manifest} already declares "
                f"{plan.desktop} {plan.release}",
                file=sys.stderr,
            )
        else:
            changed = build_request.adopt(plan, apply=True)
            for path, count in sorted(changed.items()):
                print(f"moved {count} reference(s) in {path}", file=sys.stderr)
            for decision in plan.decisions:
                print(
                    f"NOT rewritten: {decision.path.relative_to(ROOT)} — it "
                    "models more than one release track and the shift is a "
                    "decision, not a rename",
                    file=sys.stderr,
                )
            print(
                "\nRe-measure before dispatching: the build order still "
                f"describes {plan.declared_release}.",
                file=sys.stderr,
            )

    measurement = None
    if args.measure:
        if not plan.build_order:
            print(
                "error: --measure needs a generated build order, and "
                f"{plan.target} declares none",
                file=sys.stderr,
            )
            return 2
        order = ROOT / plan.build_order
        if not order.exists():
            print(f"error: {plan.build_order} is not in the tree",
                  file=sys.stderr)
            return 2
        urls = [u for arch in plan.architectures
                for u in plan.served_index.get(arch, [])]
        measurement = _converge().measure(
            order, urls, pathlib.Path(".cache/converge")
        )

    text = render(plan, measurement)
    if args.json:
        payload = plan.as_dict()
        if measurement:
            payload["measurement"] = {
                k: v for k, v in measurement.items() if k != "remaining"
            }
            payload["measurement"]["remaining"] = measurement["remaining"]
        args.json.write_text(json.dumps(payload, indent=2) + "\n")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
