"""The gate reads chains, not three independent shard results (#684).

`plan-package-factory.py` gives every full-chain build-chain cell a
continuation in each later shard -- `<id>-c1`, `<id>-c2`, both carrying
`base_id` = the original id -- and the shards are chained, so a continuation
resumes its predecessor's partial by `base_id`. Because the action key is
derived from inputs that do not change between a cell and its continuations,
a continuation of an ALREADY-FINISHED chain cache-hits and succeeds without
building. So a successful last continuation means the chain is complete
either way.

Run 33840428161 is what this is for: build-0 failed on a transient upstream
fetch, build-1 resumed the partial, built through the failed package and
passed validation, build-2 completed -- and the gate reported failure, because
it required all three shards to be green independently.

The strictness it replaced was deliberate, and the half that must survive is
that a FAILED CONTINUATION still fails: nothing runs after it, so nothing
speaks for it, and forgiving it would turn "the chain extension died and we
lost the day's remaining hours" into a green run.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "gate-shard-results.py"
WORKFLOW = ROOT / ".github" / "workflows" / "package-factory.yml"

spec = importlib.util.spec_from_file_location("gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def matrix(*cells: dict) -> str:
    return json.dumps({"include": list(cells)})


def cell(cid: str, base: str | None = None, **extra) -> dict:
    out = {"id": cid, "engine": "build-chain", **extra}
    if base:
        out["base_id"] = base
    return out


CHAIN_0 = matrix(cell("gnome50-el10-x86_64"))
CHAIN_1 = matrix(cell("gnome50-el10-x86_64-c1", base="gnome50-el10-x86_64"))
CHAIN_2 = matrix(cell("gnome50-el10-x86_64-c2", base="gnome50-el10-x86_64"))


# ── the case that motivated it ───────────────────────────────────────────────


def test_run_33840428161_would_now_pass():
    """build-0 failure, both continuations green."""
    ok, notes = gate.evaluate(
        "success", [1, 1, 1],
        ["failure", "success", "success"],
        [CHAIN_0, CHAIN_1, CHAIN_2],
    )
    assert ok, notes
    assert any("authoritative" in n for n in notes)


def test_a_chain_that_only_needed_one_continuation_passes():
    ok, _ = gate.evaluate(
        "success", [1, 1, 0], ["failure", "success", ""], [CHAIN_0, CHAIN_1, ""],
    )
    assert ok


# ── the strictness that must survive ─────────────────────────────────────────


def test_a_failed_last_continuation_still_fails():
    """Nothing runs after it, so nothing supersedes it. This is the
    'chain extension silently died' case the old gate existed to catch."""
    ok, notes = gate.evaluate(
        "success", [1, 1, 1],
        ["success", "success", "failure"],
        [CHAIN_0, CHAIN_1, CHAIN_2],
    )
    assert not ok
    assert any("gnome50-el10-x86_64-c2" in n for n in notes)


def test_a_failed_middle_continuation_fails_when_the_last_also_fails():
    ok, _ = gate.evaluate(
        "success", [1, 1, 1],
        ["success", "failure", "failure"],
        [CHAIN_0, CHAIN_1, CHAIN_2],
    )
    assert not ok


def test_every_shard_green_passes():
    ok, notes = gate.evaluate(
        "success", [1, 1, 1], ["success"] * 3, [CHAIN_0, CHAIN_1, CHAIN_2],
    )
    assert ok and not notes


def test_a_failed_plan_fails_whatever_the_shards_say():
    ok, _ = gate.evaluate(
        "failure", [1, 1, 1], ["success"] * 3, [CHAIN_0, CHAIN_1, CHAIN_2],
    )
    assert not ok


# ── forgiveness is per chain, and conservative ───────────────────────────────


def test_an_uncontinued_cell_in_a_failed_shard_keeps_it_red():
    """A shard result covers every cell in it and GitHub gives no per-cell
    verdict. A tideforge/canary/tiers cell has no continuation, so it might
    be the one that failed and nothing speaks for it."""
    shard0 = matrix(
        cell("gnome50-el10-x86_64"),
        cell("some-tideforge-cell", engine="tideforge"),
    )
    ok, notes = gate.evaluate(
        "success", [2, 1, 1],
        ["failure", "success", "success"],
        [shard0, CHAIN_1, CHAIN_2],
    )
    assert not ok
    assert any("some-tideforge-cell" in n for n in notes)


def test_overflow_in_a_later_shard_is_not_a_continuation():
    """>200-cell overflow lands in build-1 with no base_id and nothing after
    it. Its failure must stand."""
    overflow = matrix(cell("cell-201"), cell("cell-202"))
    ok, notes = gate.evaluate(
        "success", [200, 2, 0],
        ["success", "failure", ""],
        [matrix(cell("cell-1")), overflow, ""],
    )
    assert not ok
    assert any("cell-201" in n or "cell-202" in n for n in notes)


def test_one_chain_carried_does_not_excuse_another_that_was_not():
    a0, b0 = cell("family-a"), cell("family-b")
    ok, notes = gate.evaluate(
        "success", [2, 1, 0],
        ["failure", "success", ""],
        [matrix(a0, b0), matrix(cell("family-a-c1", base="family-a")), ""],
    )
    assert not ok
    assert any("family-b" in n for n in notes)


def test_a_skipped_shard_with_planned_cells_is_not_forgiven_by_itself():
    ok, _ = gate.evaluate(
        "success", [1, 0, 0], ["skipped", "", ""], [CHAIN_0, "", ""],
    )
    assert not ok


def test_an_empty_shard_is_not_checked():
    ok, notes = gate.evaluate(
        "success", [1, 0, 0], ["success", "skipped", "skipped"], [CHAIN_0, "", ""],
    )
    assert ok and not notes


def test_an_unreadable_matrix_fails_rather_than_guesses():
    ok, notes = gate.evaluate(
        "success", [1, 1, 0], ["failure", "success", ""], ["", CHAIN_1, ""],
    )
    assert not ok
    assert any("empty or unreadable" in n for n in notes)


# ── the wiring ───────────────────────────────────────────────────────────────


def test_the_gate_runs_this_script_and_feeds_it_the_matrices():
    body = WORKFLOW.read_text()
    assert "scripts/gate-shard-results.py" in body
    for index in range(3):
        assert f"needs.plan.outputs.matrix_{index}" in body, (
            "the gate cannot reconcile chains without the planner's matrices"
        )


def test_the_script_exits_nonzero_on_a_real_failure():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--plan", "success", "--count", "1",
         "--count-0", "1", "--result-0", "failure", "--matrix-0", CHAIN_0],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1
    assert "ERROR:" in proc.stdout


def test_the_script_exits_zero_when_a_continuation_carried_the_chain():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--plan", "success", "--count", "1",
         "--count-0", "1", "--result-0", "failure", "--matrix-0", CHAIN_0,
         "--count-1", "1", "--result-1", "success", "--matrix-1", CHAIN_1],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "authoritative" in proc.stdout
