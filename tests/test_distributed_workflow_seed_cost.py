"""The seed step was most of every job in the fan-out.

Run 31291311136 was the first fan-out to build green end to end. Its
bootstrap-01 jobs took about four and a half minutes each, and the timings say
where that went:

    03:02:31 -> 03:02:47   curl | sudo bash, installing rclone       16s
    03:02:47 -> 03:04:35   rclone copy + createrepo_c, silently     108s
    03:04:36 -> 03:05:54   the actual package build                  78s

Two thirds of the job was not the build. Both halves of the overhead are
avoidable:

* rclone came from ``curl | sudo bash`` -- a zip download, an unzip and a man
  page install -- in a job that was already running ``apt-get update &&
  apt-get install``. Ubuntu ships rclone, so it costs nothing to add it there.
  Sixteen seconds is small until you multiply it by 1255 build jobs, 78 of
  which sit on the critical path along with 78 consolidate jobs.

* rclone's defaults (4 transfers, 8 checkers, paginated listing) suit a handful
  of large files. This repository is a few thousand small RPMs, so the transfer
  is dominated by per-object round trips rather than by bandwidth.

The 108 seconds were logged with no output at all, so the split between the
transfer and the createrepo_c after it is unknown. --stats is part of this
change for that reason: the next run says which half is left to attack.
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
GENERATOR = REPO / "scripts" / "generate-distributed-workflow.py"
MANIFEST = REPO / "build-order-hummingbird-desktops.yml"


@pytest.fixture(scope="module")
def workflow(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("seed-cost")
    order = yaml.safe_load(MANIFEST.read_text())
    slice_ = [t for t in order["tiers"] if t["name"].startswith("bootstrap")]
    src = tmp_path / "order.yml"
    src.write_text(yaml.safe_dump({"r2_path": order["r2_path"], "tiers": slice_}, sort_keys=False))
    out = tmp_path / "wf.yml"
    subprocess.run(
        [sys.executable, str(GENERATOR), str(src), str(out),
         "--mock-config", "hummingbird-ci",
         "--r2-path", order["r2_path"], "--secondary-r2-path", "",
         "--no-submodules", "--r2-state"],
        check=True, capture_output=True, cwd=REPO,
    )
    return yaml.safe_load(out.read_text())


def runs(workflow):
    """Every run: script in the workflow, as (job name, step name, script)."""
    for job_name, job in workflow["jobs"].items():
        for step in job["steps"]:
            if "run" in step:
                yield job_name, step.get("name", "<unnamed>"), step["run"]


def test_no_job_installs_rclone_by_downloading_it(workflow):
    offenders = [(j, s) for j, s, r in runs(workflow) if "rclone.org/install.sh" in r]
    assert offenders == [], (
        f"{len(offenders)} step(s) still install rclone over the network: {offenders}. "
        "That is sixteen seconds per job, and every one of these jobs already "
        "runs apt-get, which can install rclone for free."
    )


def test_every_job_that_runs_rclone_installs_it(workflow):
    for job_name, job in workflow["jobs"].items():
        scripts = [s["run"] for s in job["steps"] if "run" in s]
        if not any("rclone " in s for s in scripts):
            continue
        assert any("apt-get install" in s and " rclone" in s for s in scripts), (
            f"{job_name} runs rclone but never installs it; dropping the "
            "curl|bash installs must not leave a job without the binary"
        )


@pytest.mark.parametrize("flag", ["--transfers 32", "--checkers 64", "--fast-list"])
def test_whole_repo_transfers_are_parallelised(workflow, flag):
    """Only the transfers that move the repository need the flags."""
    whole_repo = [
        (j, s, r) for j, s, r in runs(workflow)
        if "rclone copy" in r or "rclone sync" in r
    ]
    assert whole_repo, "no rclone transfer found at all; the fixture is wrong"
    for job_name, step_name, script in whole_repo:
        for line in script.split("\n"):
            if not line.startswith(("rclone copy ", "rclone sync ")):
                continue
            if "copyto" in line or "public.gpg" in line or "install.sh" in line:
                continue  # single small files; parallelism is irrelevant
            assert flag in line, (
                f"{job_name} / {step_name} moves the repository without {flag}:\n"
                f"    {line}\n"
                "rclone's defaults are tuned for a few large files, not for a "
                "few thousand small RPMs."
            )


def test_repository_transfers_report_their_stats(workflow):
    """108 silent seconds is a measurement you cannot act on."""
    for job_name, step_name, script in runs(workflow):
        for line in script.split("\n"):
            if not line.startswith(("rclone copy ", "rclone sync ")):
                continue
            if "copyto" in line or "public.gpg" in line or "install.sh" in line:
                continue
            assert "--stats" in line, (
                f"{job_name} / {step_name} moves the repository without --stats:\n"
                f"    {line}\n"
                "The first fan-out logged nothing for the whole transfer, which "
                "left no way to tell the transfer from the createrepo_c after it."
            )


def test_the_seed_still_seeds(workflow):
    """Speed work must not quietly drop the thing being made faster."""
    seed = [r for j, s, r in runs(workflow)
            if j.startswith("build-") and s == "Seed local repo from R2"]
    assert seed, "build jobs no longer seed from R2"
    for script in seed:
        assert 'rclone copy "r2:' in script and "local-repo/" in script
        assert "createrepo_c local-repo" in script, (
            "the seeded repo still needs metadata before mock can use it"
        )
