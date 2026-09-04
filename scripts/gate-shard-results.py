#!/usr/bin/env python3
"""Decide whether a package-factory run's shards add up to a passing gate.

Every occupied shard must pass -- with one exception, and the exception is
the whole reason this is a script rather than four lines of bash.

`plan-package-factory.py` gives every full-chain build-chain cell a
CONTINUATION in the next shard: the same cell re-listed as `<id>-c1`, then
`<id>-c2`, carrying `base_id` = the original id. Continuations are planned
statically, before anything builds, and they chain: build-1 needs build-0,
build-2 needs build-1. Two consequences matter here.

  * A continuation resumes its predecessor's partial output by `base_id`, so
    when a shard runs out of chain budget -- or fails partway -- the next
    shard picks the chain up where it stopped.
  * The action key is derived from inputs, which are identical across a
    cell and its continuations. So if the chain ALREADY finished, the
    continuation cache-hits and succeeds without building anything.

Together those mean the LAST continuation of a chain is the authoritative
statement about it: success there is either "I finished the remaining work"
or "there was none left to do". Run 33840428161 is the case that motivated
this (#684): build-0 failed on a transient upstream fetch, build-1 resumed
its partial, built through the failed package and passed validation,
build-2 completed -- and the gate still called the run a failure, because it
read three independent shard results instead of one chain.

What is NOT forgiven, and must not become so (#684 was filed against a gate
whose strictness was deliberate -- see the comment this replaced): a failed
continuation. Nothing runs after it to supersede it, so its failure stands
and the run is red. That is the "chain extension silently died" case: the
day's extra hours lost with no red anywhere.

A shard's result covers every cell in it, and GitHub gives no per-cell
verdict, so forgiveness is conservative: a failed shard is excused only when
EVERY cell in it is superseded by a successful later shard. One
non-continued cell -- a tideforge cell, a canary, a tiers-scoped dispatch,
a >200-cell overflow -- and the shard stays red, because that cell might be
the one that failed and nothing after it speaks for it.
"""

from __future__ import annotations

import argparse
import json
import sys

SHARDS = 3


def chain_key(cell: dict) -> str:
    """The id of the chain a cell belongs to.

    A continuation carries `base_id` = the id of the cell it continues; an
    original carries none. Keying on it puts `foo`, `foo-c1` and `foo-c2` in
    one bucket.
    """
    return str(cell.get("base_id") or cell.get("id") or "")


def cells(matrix: str) -> list[dict]:
    """The `include:` list of a planner matrix, or [] for an empty shard."""
    if not matrix or not matrix.strip():
        return []
    doc = json.loads(matrix)
    return [c for c in doc.get("include") or [] if isinstance(c, dict)]


def evaluate(plan: str, counts: list[int], results: list[str],
             matrices: list[str]) -> tuple[bool, list[str]]:
    """(gate passes, lines to print)."""
    notes: list[str] = []

    if plan != "success":
        return False, [f"plan did not succeed (result: {plan or 'missing'})"]

    per_shard = [cells(m) for m in matrices]
    ok = True

    for index in range(SHARDS):
        if counts[index] <= 0:
            continue
        result = results[index]
        if result == "success":
            continue

        # Which later shards finished cleanly, and what chains do they carry?
        superseded_by: dict[str, int] = {}
        for later in range(index + 1, SHARDS):
            if counts[later] > 0 and results[later] == "success":
                for cell in per_shard[later]:
                    superseded_by.setdefault(chain_key(cell), later)

        shard_cells = per_shard[index]
        orphans = [c for c in shard_cells if chain_key(c) not in superseded_by]

        if shard_cells and not orphans:
            last = max(superseded_by[chain_key(c)] for c in shard_cells)
            notes.append(
                f"shard {index} reported '{result}', but every chain in it "
                f"was carried to a successful continuation (build-{last}); "
                f"the continuation is the authoritative result for a chain, "
                f"so this does not fail the gate"
            )
            continue

        ok = False
        if not shard_cells:
            notes.append(
                f"shard {index} reported '{result}' and the planner recorded "
                f"{counts[index]} cell(s) there, but its matrix is empty or "
                f"unreadable -- treating as a failure rather than guessing"
            )
        else:
            named = ", ".join(sorted({str(c.get("id", "?")) for c in orphans})[:8])
            more = "" if len(orphans) <= 8 else f" (+{len(orphans) - 8} more)"
            notes.append(
                f"shard {index} reported '{result}' and nothing supersedes "
                f"{len(orphans)} of its {len(shard_cells)} cell(s): {named}{more}"
            )

    return ok, notes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--count", default="0", help="total cells planned, for the summary line")
    for index in range(SHARDS):
        ap.add_argument(f"--count-{index}", default="0")
        ap.add_argument(f"--result-{index}", default="")
        ap.add_argument(f"--matrix-{index}", default="")
    args = ap.parse_args(argv)

    def as_int(value: str) -> int:
        try:
            return int(str(value).strip() or 0)
        except ValueError:
            return 0

    counts = [as_int(getattr(args, f"count_{i}")) for i in range(SHARDS)]
    results = [str(getattr(args, f"result_{i}") or "") for i in range(SHARDS)]
    matrices = [str(getattr(args, f"matrix_{i}") or "") for i in range(SHARDS)]

    ok, notes = evaluate(args.plan, counts, results, matrices)
    for note in notes:
        print(("==> " if ok else "ERROR: ") + note)
    print(f"{args.count} package action(s) planned; occupied shards: "
          f"{' '.join(str(c) for c in counts)}; "
          f"results: {' '.join(r or 'none' for r in results)}.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
