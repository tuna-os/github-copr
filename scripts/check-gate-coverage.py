#!/usr/bin/env python3
"""Report Tideforge gate coverage, and refuse to let it get worse.

A recipe declares the targets it wants built. The gate declares the cells it
actually builds. Nothing connected the two, which is how openSUSE ended up
declared by 19 recipes and built by zero cells (#139).

The obvious fix -- assert every declared (recipe, target) pair has a cell --
is not shippable: 77 of 122 pairs are uncovered today, so it would block every
PR from the moment it landed. The obvious workaround, an allowlist of accepted
gaps, is how a curated list stops being curated; `lint-generated-rpm.sh` says
the same thing about its own fatal-checks list, and it is right.

So: ratchet. Count the gap and print it, and fail only when a change *adds* an
uncovered pair. Existing gaps stay visible as a number that has to go down;
new ones cannot be introduced silently. There is no allowlist to launder a gap
through, and no checked-in snapshot to rot -- the baseline is recomputed from
the git ref on every run.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

GATE_WORKFLOWS = (
    ".github/workflows/build-tideforge-supported.yml",
    ".github/workflows/build-tideforge-arch.yml",
)
MANIFEST = "manifests/package-factory.yaml"

Pair = tuple[str, str]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


class Tree:
    """Repository contents, either on disk or at a git ref."""

    def __init__(self, ref: str | None = None) -> None:
        self.ref = ref

    def read(self, path: str) -> str | None:
        if self.ref is None:
            file = Path(path)
            return file.read_text() if file.exists() else None
        result = subprocess.run(
            ["git", "show", f"{self.ref}:{path}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout if result.returncode == 0 else None

    def recipes(self) -> list[str]:
        if self.ref is None:
            return sorted(str(p) for p in Path("packages").glob("*/package.yaml"))
        result = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", self.ref, "packages/"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            fail(f"cannot read packages/ at ref {self.ref!r} -- is it fetched?")
        return sorted(p for p in result.stdout.splitlines() if p.endswith("/package.yaml"))


def declared_pairs(tree: Tree) -> set[Pair]:
    """(package, target) for every target a recipe asks to be built for."""
    pairs: set[Pair] = set()
    for path in tree.recipes():
        if "_template" in path:
            continue
        text = tree.read(path)
        if text is None:
            continue
        recipe = yaml.safe_load(text) or {}
        package = Path(path).parent.name
        for target in recipe.get("targets", []):
            pairs.add((package, target))
    return pairs


def gate_pairs(tree: Tree) -> set[Pair]:
    """(package, target) for every cell the gate actually builds."""
    pairs: set[Pair] = set()
    for workflow in GATE_WORKFLOWS:
        text = tree.read(workflow)
        if text is None:
            continue
        data = yaml.safe_load(text) or {}
        arch_gate = "arch" in workflow
        for job_name, job in (data.get("jobs") or {}).items():
            include = (job.get("strategy") or {}).get("matrix", {}).get("include", [])
            for cell in include:
                package = cell.get("package")
                if not package:
                    continue
                # Most cells name their target. The openSUSE job pins its target
                # in the step body, and the Arch gate builds exactly one target
                # by construction, so infer those from where the cell lives.
                target = cell.get("target")
                if target is None:
                    if "opensuse" in job_name:
                        target = "opensuse-tumbleweed"
                    elif arch_gate:
                        target = "arch"
                if target:
                    pairs.add((package, target))
    return pairs


def uncovered(tree: Tree) -> set[Pair]:
    return declared_pairs(tree) - gate_pairs(tree)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        help="git ref to ratchet against (e.g. origin/main). Omit to report only.",
    )
    args = parser.parse_args()

    current = uncovered(Tree())
    declared = declared_pairs(Tree())
    print(
        f"Gate coverage: {len(declared) - len(current)}/{len(declared)} "
        f"declared (recipe, target) pairs have a cell -- {len(current)} uncovered"
    )

    if not args.baseline:
        return

    previous = uncovered(Tree(args.baseline))
    added = sorted(current - previous)
    if added:
        listing = "\n".join(f"    {package} ({target})" for package, target in added)
        fail(
            "these (recipe, target) pairs are declared but have no cell in the "
            f"Tideforge gate, and did not exist at {args.baseline}:\n{listing}\n"
            "  A recipe that declares a target nothing builds is untested while "
            "looking supported -- the defect #139 was about. Add a matrix cell "
            "for each, or drop the target from the recipe.\n"
            "  Pre-existing gaps are not blocked here; only new ones. There is "
            "deliberately no allowlist."
        )

    removed = len(previous) - len(current)
    if removed > 0:
        print(f"Gate coverage improved: {removed} fewer uncovered pair(s) than {args.baseline}")
    else:
        print(f"Gate coverage held: no new uncovered pairs against {args.baseline}")


if __name__ == "__main__":
    main()
