"""The publisher's runs-on path: bigger AWS runners, longer budget, and a
default that changes nothing for existing callers.

Throughput on GitHub-hosted runners is the chain's wall: 4 vCPU means
build-chain.sh's JOBS = nproc/2 = 2 parallel mocks, ~17 packages/hour,
81-85 per leg against ~590 deferred. The AWS pool's 16 vCPU makes that 8
parallel mocks, and self-hosted jobs are not bound by the hosted 6h
ceiling, so one leg can cover what took four.

Everything here is workflow YAML and a RunsOn config -- neither is an
action-key input, so the change re-keys nothing and partials resume.
"""
from __future__ import annotations

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-build-chain-rpms.yml"
SPEC = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
POOL = yaml.safe_load((ROOT / ".github" / "runs-on.yml").read_text(encoding="utf-8"))
BUILD = SPEC["jobs"]["build"]


def test_the_default_is_hosted_so_existing_dispatches_are_unchanged():
    runner = SPEC[True]["workflow_dispatch"]["inputs"]["runner"]
    assert runner["default"] == "hosted"
    assert runner["required"] is False
    assert set(runner["options"]) == {"hosted", "runs-on"}


def test_the_hosted_branch_still_uses_the_planner_runner():
    assert "matrix.runner" in BUILD["runs-on"]
    assert "inputs.runner != 'runs-on'" in BUILD["runs-on"]


def test_the_runs_on_branch_references_pool_runners_that_exist():
    """A label naming a runner absent from .github/runs-on.yml queues
    forever, and there is no cancel tool in this environment."""
    referenced = set(re.findall(r"'(chain-[a-z0-9]+)'", BUILD["runs-on"]))
    assert referenced == {"chain-amd64", "chain-arm64"}
    assert referenced <= set(POOL["runners"]), (
        f"workflow references {referenced - set(POOL['runners'])} "
        "which .github/runs-on.yml does not define")


def test_the_arm_matrix_runner_maps_to_the_arm_pool():
    assert "matrix.runner == 'ubuntu-24.04-arm' && 'chain-arm64'" in BUILD["runs-on"]


@pytest.mark.parametrize("name", ["chain-amd64", "chain-arm64"])
def test_pool_runners_are_sized_for_eight_parallel_mocks(name):
    runner = POOL["runners"][name]
    assert runner["cpu"] == [16], "JOBS = nproc/2 -> 8 needs 16 vCPU"
    # m-family = 4GB/vCPU: eight parallel mock chroots plus podman need the
    # memory headroom; c-family's 2GB/vCPU is what the hosted runners have
    # and mock builds already brush against it at JOBS=2.
    assert all(f.startswith("m") for f in runner["family"]), runner["family"]


def test_the_budget_stretches_only_on_the_runs_on_branch():
    step = next(s for s in BUILD["steps"] if s.get("name") == "Build the cell")
    budget = str(step["env"]["CHAIN_BUDGET_SECONDS"])
    assert "16200" in budget and "34200" in budget
    assert "inputs.runner != 'runs-on'" in budget


def test_budget_fits_inside_the_timeout_with_drain_headroom():
    """The whole point of the soft deadline (#480) is finishing the leg's
    in-flight packages and post-processing BEFORE timeout-minutes tears the
    job down. Both branches must keep >= 60 minutes of headroom."""
    timeout = str(BUILD["timeout-minutes"])
    pairs = {360: 16200, 660: 34200}
    for minutes, budget in pairs.items():
        assert str(minutes) in timeout
        assert minutes * 60 - budget >= 3600, (minutes, budget)
