"""A dropped dist-git connection must not cost the whole run.

Run 31266605500 imported 9 of 11 bootstrap packages and lost two to
`fatal: the remote end hung up unexpectedly`. The step exits 1 on any failure
and `Build tiers` is `skipped`, so nothing was built at all -- by a network
flake, on packages that exist and had imported fine minutes earlier.

Two packages in eleven is a ~18% per-clone failure rate. The full manifest is
1248 packages.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "import-fedora-distgit.py"

spec = importlib.util.spec_from_file_location("ifd", SCRIPT)
IFD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(IFD)


class FakeResult:
    def __init__(self, returncode, stderr=""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


def runner_returning(*results):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return results[min(len(calls) - 1, len(results) - 1)]

    run.calls = calls
    return run


def test_transient_failure_is_retried_until_it_succeeds(tmp_path):
    run = runner_returning(
        FakeResult(128, "fatal: the remote end hung up unexpectedly"),
        FakeResult(0),
    )
    slept = []
    result = IFD.clone_with_retry(
        "python-hatchling", "rawhide", tmp_path / "co", 3, runner=run, sleeper=slept.append
    )
    assert result.returncode == 0
    assert len(run.calls) == 2
    assert slept == [2]


def test_a_package_that_does_not_exist_is_not_retried(tmp_path):
    run = runner_returning(
        FakeResult(128, "remote: Repository not found\nfatal: repository not found")
    )
    result = IFD.clone_with_retry(
        "python-nope", "rawhide", tmp_path / "co", 3, runner=run, sleeper=lambda _: None
    )
    assert result.returncode == 128
    assert len(run.calls) == 1, "a missing package is deterministic; retrying it is waste"


def test_attempts_are_bounded(tmp_path):
    run = runner_returning(FakeResult(128, "fatal: the remote end hung up unexpectedly"))
    result = IFD.clone_with_retry(
        "python-flaky", "rawhide", tmp_path / "co", 3, runner=run, sleeper=lambda _: None
    )
    assert result.returncode == 128
    assert len(run.calls) == 3


def test_backoff_grows(tmp_path):
    run = runner_returning(FakeResult(128, "fatal: early EOF"))
    slept = []
    IFD.clone_with_retry(
        "python-flaky", "rawhide", tmp_path / "co", 4, runner=run, sleeper=slept.append
    )
    assert slept == [2, 4, 8]


def test_partial_checkout_is_cleared_between_attempts(tmp_path):
    """git refuses to clone into a non-empty directory.

    Without this the retry fails with 'destination path already exists' and a
    transient error is laundered into a permanent one -- which would look like
    the retry is working while making the outcome strictly worse.
    """
    checkout = tmp_path / "co"
    checkout.mkdir()
    (checkout / "partial").write_text("half a clone")
    seen = []

    def run(cmd, **kw):
        seen.append(checkout.exists() and any(checkout.iterdir()))
        return FakeResult(0) if len(seen) == 2 else FakeResult(128, "fatal: early EOF")

    IFD.clone_with_retry(
        "python-x", "rawhide", checkout, 3, runner=run, sleeper=lambda _: None
    )
    assert seen == [False, False], "clone was attempted into a dirty directory"


def test_attempts_of_one_means_no_retry(tmp_path):
    run = runner_returning(FakeResult(128, "fatal: early EOF"))
    IFD.clone_with_retry("p", "rawhide", tmp_path / "co", 1, runner=run, sleeper=lambda _: None)
    assert len(run.calls) == 1


def test_the_workflow_does_not_pin_attempts_to_one():
    workflow = (REPO / ".github/workflows/build-hummingbird-desktops.yml").read_text()
    assert "--clone-attempts 1" not in workflow


def test_permanent_marker_matching_is_case_insensitive():
    assert IFD.clone_is_permanent_failure("remote: Repository NOT FOUND")
    assert not IFD.clone_is_permanent_failure("fatal: the remote end hung up unexpectedly")
