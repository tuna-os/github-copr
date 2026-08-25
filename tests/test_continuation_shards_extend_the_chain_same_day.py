"""One nightly must bank more than one budget of chain, without new machinery.

A full desktop family (1,248 packages for hummingbird) is ~44h of mock time.
The soft deadline ends a cell cleanly at ~4.5h; before this, the next attempt
was tomorrow's schedule — ~5.5h of chain per DAY. The build-1/build-2 shards
existed only as >200-cell overflow and had never once run.

Chaining them and seeding CONTINUATION copies of each full-chain cell triples
the chain hours per run, built entirely from mechanisms that already exist
and are already tested: the continuation's partial artifact is NAMED by
base_id so the resume step restores the previous shard's upload, and the
input-derived action key means a shard that FINISHES the chain makes every
later continuation cache-hit and skip.

The failure modes pinned here are the quiet ones:
  * shards running in parallel again (a continuation racing its predecessor
    for the same partial),
  * the gate passing while an occupied continuation shard failed (a green
    run whose extra hours silently died),
  * continuations leaking onto bounded cells (canary, TIERS-scoped,
    tideforge), which have no partial progress to resume.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLANNER = ROOT / "scripts" / "plan-package-factory.py"
FACTORY = ROOT / ".github" / "workflows" / "package-factory.yml"
CELL = ROOT / ".github" / "workflows" / "package-factory-cell.yml"


def plan(selector: str) -> list[list[dict]]:
    proc = subprocess.run(
        [sys.executable, str(PLANNER), "--selector", selector],
        capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr[-1500:]
    payload = json.loads(proc.stdout)
    return [json.loads(m)["include"] for m in payload["matrices"]]


def test_full_chain_cells_continue_into_chained_shards():
    shards = plan("family=hummingbird-desktops")
    base_ids = {c["id"] for c in shards[0]}
    assert base_ids, "planner selected nothing — the fixture family moved"
    for index, suffix in ((1, "-c1"), (2, "-c2")):
        got = {c["id"]: c.get("base_id") for c in shards[index]}
        for base in base_ids:
            assert f"{base}{suffix}" in got, (
                f"shard {index} lacks a continuation for {base}"
            )
            assert got[f"{base}{suffix}"] == base, (
                "continuation does not carry base_id — the resume step will "
                "look for a partial artifact that nothing uploads"
            )


def plan_args(*args: str) -> list[list[dict]]:
    proc = subprocess.run(
        [sys.executable, str(PLANNER), *args],
        capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr[-1500:]
    payload = json.loads(proc.stdout)
    return [json.loads(m)["include"] for m in payload["matrices"]]


def test_bounded_cells_do_not_continue():
    """A tideforge cell builds one package; nothing to resume.

    Selected via --cell rather than engine=tideforge: the engine selector
    matches ~289 cells, so shards 1-2 legitimately hold OVERFLOW there —
    which the first version of this test misread as leaked continuations.
    """
    shards = plan_args("--cell", "tideforge-libunwind-devel-el10-x86_64")
    assert shards[0], "the fixture cell id no longer exists — pick another"
    assert not shards[1] and not shards[2], (
        "a single-package cell grew continuations"
    )


def test_canary_cells_do_not_continue():
    """Canaries are bounded by construction: canary_cells() rewrites the id
    to -canary and sets tiers=canary_tiers, and a cell with TIERS set asked
    for a bounded slice — nothing to continue."""
    changed = ROOT / ".factory-test-changed"  # a path affecting no single format
    changed.write_text(".github/workflows/package-factory-cell.yml\n")
    try:
        shards = plan_args("--canary-common", "--changed-files", str(changed))
    finally:
        changed.unlink()
    canaries = [c for c in shards[0] if c["id"].endswith("-canary")]
    assert canaries, "canary-common selected no canaries — fixture moved"
    # Full-chain cells in the same plan MAY continue (a continuation of a
    # completed cell cache-hits its action key and skips in seconds, so it is
    # a cheap no-op). The property that matters is narrower: a TIERS-bounded
    # canary must never be extended past the slice it asked for.
    canary_ids = {c["id"] for c in canaries}
    leaked = [c for shard in shards[1:] for c in shard
              if c.get("base_id") in canary_ids]
    assert not leaked, f"bounded canaries grew continuations: {[c['id'] for c in leaked]}"


def _jobs() -> dict:
    return yaml.safe_load(FACTORY.read_text())["jobs"]


def test_the_shards_are_chained_not_parallel():
    jobs = _jobs()
    assert "build-0" in jobs["build-1"]["needs"], (
        "build-1 no longer waits for build-0 — a continuation racing its "
        "predecessor for the same partial artifact"
    )
    assert "build-1" in jobs["build-2"]["needs"]


def test_the_shard_conditions_read_occupancy_not_overflow_count():
    jobs = _jobs()
    for name, key in (("build-1", "count_1"), ("build-2", "count_2")):
        cond = jobs[name].get("if", "")
        assert key in cond, (
            f"{name} is still gated on the >200 overflow count; continuation "
            "cells would put work there that the condition never runs"
        )
        assert "!cancelled()" in cond, (
            f"{name} skips when any build-0 cell fails — one unrelated red "
            "cell throwing away the day's remaining chain hours"
        )


def test_the_partial_is_named_by_base_id_and_overwritable():
    text = CELL.read_text()
    assert "${{ matrix.base_id || matrix.id }}-partial" in text, (
        "the partial artifact is no longer named by base_id; continuation "
        "shards will upload disjoint partials and resume none of them"
    )
    steps = yaml.safe_load(text)["jobs"]["build"]["steps"]
    partial = next(s for s in steps
                   if "-partial" in str((s.get("with") or {}).get("name", "")))
    assert partial["with"].get("overwrite") is True, (
        "without overwrite the second shard's partial upload fails on the "
        "duplicate name and the third shard resumes stale work"
    )


def test_the_restore_searches_by_base_id():
    text = CELL.read_text()
    assert "--cell-id '${{ matrix.base_id || matrix.id }}'" in text


def _gate_script() -> tuple[str, dict]:
    jobs = _jobs()
    step = jobs["gate"]["steps"][0]
    return step["run"], step["env"]


def test_the_gate_requires_every_occupied_shard(tmp_path):
    """Run the gate's real shell against the case the old logic passed:
    COUNT under 200 (so ceil says one shard) but an occupied, FAILED
    continuation shard."""
    script, _ = _gate_script()
    env = {"PLAN": "success", "COUNT": "2",
           "COUNT_0": "2", "COUNT_1": "2", "COUNT_2": "2",
           "SHARD_0": "success", "SHARD_1": "failure", "SHARD_2": "success"}
    proc = subprocess.run(["bash", "-c", script], env=env,
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode != 0, (
        "gate passed with a failed occupied continuation shard — a green run "
        "whose chain extension silently died"
    )


def test_the_gate_ignores_empty_shards(tmp_path):
    script, _ = _gate_script()
    env = {"PLAN": "success", "COUNT": "2",
           "COUNT_0": "2", "COUNT_1": "0", "COUNT_2": "0",
           "SHARD_0": "success", "SHARD_1": "skipped", "SHARD_2": "skipped"}
    proc = subprocess.run(["bash", "-c", script], env=env,
                          capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr


def test_a_deferred_build_still_uploads_its_partial():
    """The linchpin. A deferred chain exits 0, so its outcome is `success` —
    which the partial upload's allowlist (failure/cancelled) did not cover.
    Without this clause a deferred shard uploads nothing, the next shard
    restores the previous DAY's partial, and the continuation design loses
    exactly the hours it exists to bank. Caught by reading the seam before
    the first live run, the same class as SOURCE_DATE_EPOCH in #464: the
    units were right and the seam was wrong."""
    steps = yaml.safe_load(CELL.read_text())["jobs"]["build"]["steps"]
    partial = next(s for s in steps
                   if "-partial" in str((s.get("with") or {}).get("name", "")))
    cond = partial.get("if", "")
    assert "chain_deferred" in cond, (
        "the partial upload ignores deferral; continuation shards will "
        "resume stale work"
    )
    # Still an allowlist: a cache-hit (outcome `skipped`) must not upload —
    # that regression cost a redundant ~500MB copy per green cell once.
    assert "outcome == 'failure'" in cond and "!=" not in cond
