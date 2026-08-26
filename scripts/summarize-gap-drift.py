#!/usr/bin/env python3
"""Describe what a regenerated build order changed, without lying about it.

The drift job opens a PR whose body is the only thing most readers will judge
it by, so the body has to distinguish the three things that can happen to a
package:

  dropped  the target now ships it, so we stop building it
  added    the target stopped shipping it, or the closure grew
  MOVED    same package, different spec directory -- a version-track change

The old summary compared FULL PATHS, so a move could never cancel: `gdm`
appeared as a drop of `src/gnome-51/gdm` and an add of `src/gnome-50/gdm`,
under the headings "the target now ships these" and "the target stopped
shipping". Both false, and the pair reads as routine upstream churn.

Measured on tuna-os/tunaos-packages#542 (2026-08-26): that PR moved all 19
GNOME packages from src/gnome-51 to src/gnome-50 -- a desktop-wide downgrade
of gdm, gnome-shell, mutter, gtk4 and the rest -- and described it as the
target having adopted them. The target ships none of them; that is the whole
premise of the gap measurement.

A move is the one category worth reading closely, so it is reported first and
shows both paths.
"""
from __future__ import annotations

import argparse
import re
import sys

PATH = re.compile(r"^([-+])\s*-?\s*path:\s*(src/\S+)")


def parse(diff: str) -> tuple[set[str], set[str]]:
    """The src/ paths a unified diff removes and adds."""
    removed: set[str] = set()
    added: set[str] = set()
    for line in diff.splitlines():
        match = PATH.match(line)
        if not match:
            continue
        (removed if match.group(1) == "-" else added).add(match.group(2))
    return removed, added


def classify(removed: set[str], added: set[str]):
    """Split into moves (same basename, different directory), drops and adds."""
    def by_name(paths):
        out: dict[str, set[str]] = {}
        for path in paths:
            out.setdefault(path.rsplit("/", 1)[1], set()).add(path)
        return out

    gone, came = by_name(removed), by_name(added)
    # A name on both sides whose paths are IDENTICAL did not move: the line
    # was rewritten in place (a reordering, or a `bootstrap:` flag changing
    # next to it), so -U0 shows it as both a removal and an addition.
    # Reporting that as a move puts `lame: src/hummingbird/lame ->
    # src/hummingbird/lame` in the list and teaches readers to skim it.
    moved = sorted(
        (name, sorted(gone[name] - came[name]), sorted(came[name] - gone[name]))
        for name in gone.keys() & came.keys()
        if gone[name] != came[name]
    )
    dropped = sorted(p for n in gone.keys() - came.keys() for p in gone[n])
    plus = sorted(p for n in came.keys() - gone.keys() for p in came[n])
    return moved, dropped, plus


def render(target: str, moved, dropped, added) -> str:
    out = [
        f"Automated re-measurement: {target}'s live target index",
        "published a new revision, so the build order was regenerated",
        "against it.",
        "",
    ]
    if moved:
        out += [
            f"**{len(moved)} package(s) MOVED to a different spec directory.**",
            "This is not the target adopting or dropping anything — it is a",
            "change of which tree we build them from, usually a version track.",
            "Read these before merging:",
            "",
            "```",
        ]
        out += [f"{name}: {', '.join(old)} -> {', '.join(new)}"
                for name, old, new in moved]
        out += ["```", ""]
    if dropped:
        out += ["Dropped from the build set (the target now ships these):",
                "```"] + dropped + ["```", ""]
    if added:
        out += ["Added to the build set (the target stopped shipping, "
                "or new closure members):", "```"] + added + ["```", ""]
    if not (moved or dropped or added):
        out.append("No package set changes — only measurement provenance moved.")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    args = ap.parse_args()
    removed, added = parse(sys.stdin.read())
    sys.stdout.write(render(args.target, *classify(removed, added)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
