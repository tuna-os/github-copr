#!/usr/bin/env python3
"""Report Tideforge gate coverage, and refuse to let it get worse.

A recipe declares the targets it wants built. The gate declares the cells it
actually builds. Nothing connected the two, which is how openSUSE ended up
declared by 19 recipes and built by zero cells (#139).

The obvious fix -- assert every declared (recipe, target) pair has a cell --
is not shippable: 34 of 122 pairs are uncovered today, so it would block every
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
import re
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


RECIPE_REFERENCE = re.compile(r"packages/([a-z0-9][a-z0-9+._-]*)/package\.yaml")
RENDER_TARGET = re.compile(r"--target\s+\"?([a-z0-9-]+)\b")


def job_targets(job_text: str, job_name: str, *, arch_gate: bool) -> set[str]:
    """Targets a job names literally, ignoring `${{ matrix.target }}`."""
    targets = set(RENDER_TARGET.findall(job_text))
    if not targets:
        if arch_gate:
            targets = {"arch"}
        elif "opensuse" in job_name:
            targets = {"opensuse-tumbleweed"}
    return targets


def gate_pairs(tree: Tree) -> set[Pair]:
    """(package, target) for every cell the gate actually builds.

    The gate uses three job shapes and every one of them is real coverage:

      * `matrix.include` -- the common case, each cell naming its package and
        usually its target
      * `matrix.package` as a plain list -- rpm-payload, 15 cells
      * no matrix at all -- the dedicated single-package jobs (niri-rpm,
        quickshell-rpm, gtkgreet-rpm, cpptrace-rpm, iio-niri-rpm, dms-stack-rpm)

    An earlier version of this function read only the first shape. It therefore
    reported 20 covered pairs as uncovered, and -- worse -- would not have
    noticed if a dedicated job were deleted, because it never counted that job
    as coverage to begin with. `assert_every_job_understood` below exists so
    that mistake cannot be repeated silently.
    """
    pairs: set[Pair] = set()
    for workflow in GATE_WORKFLOWS:
        text = tree.read(workflow)
        if text is None:
            continue
        data = yaml.safe_load(text) or {}
        arch_gate = "arch" in workflow
        for job_name, job in (data.get("jobs") or {}).items():
            body = yaml.safe_dump(job)
            targets = job_targets(body, job_name, arch_gate=arch_gate)
            matrix = (job.get("strategy") or {}).get("matrix") or {}

            include = matrix.get("include") or []
            if include:
                for cell in include:
                    package = cell.get("package")
                    if not package:
                        continue
                    cell_targets = {cell["target"]} if cell.get("target") else targets
                    pairs.update((package, target) for target in cell_targets)
                continue

            packages = matrix.get("package") or []
            if packages:
                pairs.update(
                    (package, target) for package in packages for target in targets
                )
                continue

            # Matrix-less dedicated job: the packages it builds are the recipes
            # its steps render.
            for package in set(RECIPE_REFERENCE.findall(body)):
                pairs.update((package, target) for target in targets)
    return pairs


def assert_every_job_understood(tree: Tree) -> None:
    """Fail on a gate job this parser derives no coverage from.

    A parser that finds nothing must not read as "there was nothing to find" --
    the same rule lint-generated-rpm.sh applies to an empty rpmlint report. If
    someone adds a fourth job shape, this fails loudly instead of quietly
    undercounting coverage forever.
    """
    unparsed: list[str] = []
    for workflow in GATE_WORKFLOWS:
        text = tree.read(workflow)
        if text is None:
            continue
        data = yaml.safe_load(text) or {}
        arch_gate = "arch" in workflow
        for job_name, job in (data.get("jobs") or {}).items():
            body = yaml.safe_dump(job)
            if not RECIPE_REFERENCE.search(body):
                continue  # builds no package; nothing to account for
            matrix = (job.get("strategy") or {}).get("matrix") or {}
            derived = bool(matrix.get("include") or matrix.get("package")) or bool(
                job_targets(body, job_name, arch_gate=arch_gate)
            )
            if not derived:
                unparsed.append(f"{workflow}:{job_name}")
    if unparsed:
        fail(
            "these gate jobs build packages but this script derives no coverage "
            f"from them: {unparsed}. A job shape the parser does not understand "
            "is counted as zero coverage, which reads identically to a real gap. "
            "Teach gate_pairs() the shape rather than leaving it uncounted."
        )


def uncovered(tree: Tree) -> set[Pair]:
    return declared_pairs(tree) - gate_pairs(tree)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        help="git ref to ratchet against (e.g. origin/main). Omit to report only.",
    )
    args = parser.parse_args()

    assert_every_job_understood(Tree())
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
