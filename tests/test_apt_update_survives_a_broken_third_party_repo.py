"""A 403 from a repo we never use must not fail a build job.

GitHub's Ubuntu runner image ships apt sources for packages.microsoft.com --
azure-cli and the Microsoft prod repo -- that this project does not use. When
one of them returns 403, `apt-get update` exits 100, and because the step is

    sudo apt-get update -q && sudo apt-get install -y -q ...

under `bash -e`, the whole job dies before it builds anything. Observed on run
31294475023, job 93199440461:

    E: Failed to fetch https://packages.microsoft.com/repos/azure-cli/...
       403  Forbidden [IP: 13.107.246.41 443]
    E: The repository '...' is no longer signed.
    ##[error]Process completed with exit code 100.

The package there was libid3tag, which never got as far as being built. At
1248 jobs a transient 403 on somebody else's mirror would take out a random
subset of the run every time.

`update` may now fail; `install` may not. If the packages genuinely cannot be
resolved, apt-get install still exits non-zero and the job still fails -- which
is the distinction that matters, because swallowing that would turn a broken
runner into a silently incomplete build.
"""

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "build-hummingbird-distributed.yml"


@pytest.fixture(scope="module")
def apt_steps():
    wf = yaml.safe_load(WORKFLOW.read_text())
    found = []
    for job_name, job in wf["jobs"].items():
        for step in job.get("steps", []):
            if "apt-get" in str(step.get("run", "")):
                found.append((job_name, step["run"]))
    return found


def test_there_are_apt_steps_to_check(apt_steps):
    assert apt_steps, "no apt-get steps found; the fixture is wrong"


def test_no_step_chains_update_into_install(apt_steps):
    for job_name, run in apt_steps:
        assert "apt-get update -q && sudo apt-get install" not in run, (
            f"{job_name} still fails the whole job when any configured apt "
            "repository returns an error, including ones the runner image "
            "ships and this project never uses"
        )


def test_update_is_allowed_to_fail(apt_steps):
    for job_name, run in apt_steps:
        update = [l for l in run.split("\n") if "apt-get update" in l]
        assert update, f"{job_name} installs without updating"
        assert any("|| true" in l for l in update), (
            f"{job_name} lets a third-party repo failure kill the job: {update}"
        )


def test_install_is_not_allowed_to_fail(apt_steps):
    """Swallowing this would turn a broken runner into a silent partial build."""
    for job_name, run in apt_steps:
        install = [l for l in run.split("\n") if "apt-get install" in l]
        assert install, f"{job_name} updates but never installs"
        for line in install:
            assert "|| true" not in line and "|| :" not in line, (
                f"{job_name} ignores a failed install: {line}"
            )


def test_update_is_retried_before_giving_up(apt_steps):
    """The 403 was transient; one retry costs seconds and usually clears it."""
    for job_name, run in apt_steps:
        update = [l for l in run.split("\n") if "apt-get update" in l][0]
        assert update.count("apt-get update") >= 2, (
            f"{job_name} gives up on the first failure: {update}"
        )
