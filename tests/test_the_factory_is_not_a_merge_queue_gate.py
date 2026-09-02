"""A 2.5-hour build must not be a gate on a 1-hour queue.

Package Factory builds cells; a src/-touching PR rebuilds them from zero and
takes about two and a half hours. The merge queue's CI timeout is about one.
So every src/-touching PR was evicted on every attempt, however green it was
on its own head -- #545, then #567 three times in one night (23:38Z, 00:44Z
and 01:44Z on 2026-08-28, each ending CI_TIMEOUT).

It could not even reuse the work: GitHub scopes the Actions cache by ref, so
a run on refs/heads/gh-readonly-queue/... cannot read what the PR's run on
refs/pull/N/merge wrote. The queue rebuilt all 673 packages from scratch to
re-test a base that had usually not moved, since the PR gate already builds
refs/pull/N/merge -- the merge result.

THE COUPLING THIS FILE EXISTS TO PROTECT
========================================

Dropping the merge_group trigger is safe ONLY while no Package Factory job is
a required status check. lint.yml's own header records what happens otherwise,
measured the hard way:

    A workflow that does not listen for merge_group never runs, the six
    checks never report, and every queued PR sits in AWAITING_CHECKS until
    the queue's 60-minute timeout ejects it. Measured: enabling the queue
    with no merge_group trigger stalled the queue immediately and blocked
    all merges until the queue was disabled again.

That is a repo-settings fact this test cannot read. What it CAN pin is the
other half of the contract: the workflow that does carry the required checks
must keep listening for merge_group, so the queue always has something that
reports. If someone ever makes a factory job required again, they must
restore the trigger here too -- and the failure mode is a stalled queue, not
a red test, which is exactly why it is written down.
"""

from __future__ import annotations

import pathlib

import pytest

yaml = pytest.importorskip("yaml")

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
FACTORY = WORKFLOWS / "package-factory.yml"
LINT = WORKFLOWS / "lint.yml"


def triggers(path: pathlib.Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    # PyYAML resolves a bare `on:` key to the boolean True (the YAML 1.1
    # "y/yes/on" rule), so the trigger block is not under the string "on".
    return data.get("on") or data.get(True) or {}


def test_the_factory_does_not_run_on_the_merge_queue():
    assert "merge_group" not in triggers(FACTORY), (
        "a ~2.5h cell build behind a ~1h queue timeout is a gate that cannot "
        "pass: #567 was evicted three times in one night with CI_TIMEOUT"
    )


def test_the_factory_still_gates_pull_requests():
    """Removing the queue run must not remove the SIGNAL.

    The PR gate builds refs/pull/N/merge, which is the merge result -- the
    thing the queue run was re-testing. Losing it would trade a slow gate for
    no gate.
    """
    assert "pull_request" in triggers(FACTORY)


def test_the_required_checks_still_report_to_the_queue():
    """The other half of the coupling in this module's docstring.

    Whatever carries main's required checks MUST emit on merge_group, or
    every queued PR sits in AWAITING_CHECKS until the timeout ejects it --
    measured, and it blocked all merges until the queue was disabled.
    """
    on = triggers(LINT)
    assert "merge_group" in on, (
        "lint.yml carries required-checks; without merge_group the queue "
        "stalls on every PR"
    )


def test_the_required_checks_are_not_path_filtered_on_pull_request():
    """A path-filtered required check is unmergeable-forever by another route:
    the filter misses, the workflow never runs, the check never reports.

    main was in exactly that state once, requiring a job whose workflow was
    filtered to src/gnome-50/**; nothing could merge, including the fix.
    """
    on = triggers(LINT)
    assert on.get("pull_request") in (None, {}), (
        f"lint.yml pull_request must stay unfiltered, got {on.get('pull_request')!r}"
    )


def test_the_rollup_still_covers_every_fast_job():
    """`required-checks` is the single stable check branch protection points
    at, so it must aggregate the fast jobs rather than drift behind them."""
    data = yaml.safe_load(LINT.read_text(encoding="utf-8"))
    jobs = data["jobs"]
    rollup = jobs["required-checks"]
    fast = {name for name in jobs if name != "required-checks"}
    assert set(rollup["needs"]) == fast, (
        f"required-checks needs {sorted(rollup['needs'])} but lint.yml "
        f"defines {sorted(fast)} -- a job outside the roll-up is not required"
    )
    assert str(rollup.get("if", "")).strip() == "always()", (
        "without always() a failed member SKIPS the roll-up, and a skipped "
        "required check reports success"
    )
