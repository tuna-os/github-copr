"""The convergence workflow's shape is the loop; a wrong `if:` is a runaway.

converge.yml expresses "run until done or stuck" as a chain of measure/wave
jobs. There is no loop construct in Actions, so the control flow IS the `if:`
expressions, and the failure modes are the ones a for-loop cannot have:

  RUNAWAY     a wave whose `if:` does not require the preceding measurement's
              `continue` runs whatever the measurement said -- including after
              `blocked`, which is the verdict that exists to stop it.
  DEAD LOOP   a measurement guarded by `success()` (the default `needs:`
              semantics) never runs after a wave with red shards. A wave with
              red shards is the NORMAL case: one bad package fails its shard
              while its siblings publish, and that published output is exactly
              the movement the next measurement is there to detect.
  NO REPORT   the report is the deliverable of every ending, especially the
              endings nobody is watching. `always()` is what makes a blocked
              run leave something behind instead of a red X.
  SELF-DISPATCH  a workflow_dispatch made with GITHUB_TOKEN does not start a
              new run (GitHub's recursion guard), so a loop written as
              self-dispatch silently runs once. The waves are jobs for that
              reason, and a `gh workflow run` of this same workflow would be
              the regression.
"""
from __future__ import annotations

import pathlib
import re

import pytest
import yaml

REPO = pathlib.Path(__file__).resolve().parent.parent
CONVERGE = REPO / ".github" / "workflows" / "converge.yml"
FANOUT = REPO / ".github" / "workflows" / "build-chain-fanout.yml"

WORKFLOW = yaml.safe_load(CONVERGE.read_text(encoding="utf-8"))
JOBS = WORKFLOW["jobs"]
WAVES = [name for name in JOBS if re.fullmatch(r"wave-\d+", name)]
MEASURES = [name for name in JOBS if re.fullmatch(r"measure-\d+", name)]


def test_there_is_a_measurement_before_every_wave() -> None:
    assert WAVES, "no waves: the loop has nothing to run"
    for wave in WAVES:
        index = wave.split("-")[1]
        assert f"measure-{index}" in MEASURES, (
            f"{wave} has no measure-{index} in front of it, so it dispatches "
            "without knowing whether there is anything left to build"
        )


@pytest.mark.parametrize("wave", WAVES)
def test_a_wave_runs_only_on_its_own_measurements_continue(wave: str) -> None:
    index = wave.split("-")[1]
    condition = JOBS[wave]["if"]
    assert f"needs.measure-{index}.outputs.verdict == 'continue'" in condition, (
        f"{wave} does not require measure-{index} to have said `continue`, so "
        "it would run after `blocked` -- the verdict that exists to stop it"
    )


@pytest.mark.parametrize("measure", MEASURES)
def test_a_measurement_survives_a_wave_with_red_shards(measure: str) -> None:
    """A red shard is the normal case, not a reason to stop measuring."""
    condition = JOBS[measure].get("if")
    if not condition:
        # measure-1 has no upstream wave to survive.
        assert JOBS[measure].get("needs") in (None, []), measure
        return
    assert "!cancelled()" in condition, (
        f"{measure} would be skipped after a wave with any failed shard; the "
        "packages that wave DID publish are exactly the movement it measures"
    )


def test_every_measurement_after_the_first_carries_the_previous_count() -> None:
    """Without it, `blocked` can never be reached: nothing to compare against."""
    for measure in MEASURES:
        index = int(measure.split("-")[1])
        step = next(
            s for s in JOBS[measure]["steps"] if s.get("id") == "decide"
        )
        env = step.get("env", {})
        if index == 1:
            assert "PREVIOUS_REMAINING" not in env, (
                "the first wave has no previous count; passing one makes it "
                "look like a wave that already ran"
            )
        else:
            assert f"measure-{index - 1}.outputs.remaining" in env.get(
                "PREVIOUS_REMAINING", ""
            ), measure


def test_the_report_runs_on_every_ending() -> None:
    condition = JOBS["report"]["if"]
    assert "always()" in condition, (
        "a loop that only reports when it succeeds leaves nothing behind on "
        "the endings worth acting on"
    )


def test_the_loop_does_not_dispatch_itself() -> None:
    text = CONVERGE.read_text(encoding="utf-8")
    for helper in (REPO / ".github" / "scripts").glob("converge-*.sh"):
        text += helper.read_text(encoding="utf-8")
    assert "gh workflow run" not in text, (
        "a workflow_dispatch made with GITHUB_TOKEN does not start a new run, "
        "so a self-dispatching loop runs exactly once and reports nothing"
    )


def test_a_wave_is_the_same_fanout_a_hand_dispatch_runs() -> None:
    """Two definitions of a wave would drift, and only one gets tested."""
    for wave in WAVES:
        assert JOBS[wave]["uses"] == "./.github/workflows/build-chain-fanout.yml"


def test_the_fanout_is_callable_and_still_dispatchable() -> None:
    """Adding workflow_call must not take the hand dispatch away."""
    triggers = yaml.safe_load(FANOUT.read_text(encoding="utf-8"))[True]
    assert "workflow_call" in triggers
    assert "workflow_dispatch" in triggers
    call_inputs = set(triggers["workflow_call"]["inputs"])
    dispatch_inputs = set(triggers["workflow_dispatch"]["inputs"])
    assert call_inputs == dispatch_inputs, (
        "a caller that cannot pass what a hand dispatch passes is a second, "
        f"narrower wave: {call_inputs ^ dispatch_inputs}"
    )


def test_the_waves_inherit_the_publishing_secrets() -> None:
    """A wave that cannot sign or sync builds for nothing."""
    for wave in WAVES:
        assert JOBS[wave].get("secrets") == "inherit", wave


def test_the_loop_does_not_take_the_publish_concurrency_group() -> None:
    """It runs for hours; holding the publishers' group would block them all.

    The waves carry `publish-rpms` themselves, where it is held for the
    minutes a sync takes. A convergence sitting in that group for its whole
    life would serialise every other publisher behind it.
    """
    group = WORKFLOW["concurrency"]["group"]
    assert "publish-rpms" not in group, group
    assert WORKFLOW["concurrency"]["cancel-in-progress"] is False, (
        "cancelling a running convergence mid-wave discards the wave's "
        "unpublished output, which is the loss this whole design avoids"
    )


def test_the_report_can_write_the_issue_it_promises() -> None:
    assert WORKFLOW["permissions"].get("issues") == "write"
