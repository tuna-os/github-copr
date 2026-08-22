"""The deb publisher must build, publish and verify both architectures.

It did not. The build matrix was `runs-on: ubuntu-latest` with no arch key at
all, so every deb ever published was amd64 -- confirmed against the served
indexes, where all 5 ubuntu and 8 debian-sid entries read
`Architecture: amd64`.

The factory gates BOTH arches, so this was not cosmetic:
tideforge-quickshell-ubuntu-arm64 reported `libcpptrace-dev NOT AVAILABLE` and
died at build-dep resolution, while the amd64 cell resolved 1.0.4-1 from the
same published index and went on to compile. debian-arm64 was unaffected only
because Debian sid ships libcpptrace-dev for arm64 itself -- which is why the
gap read as an ubuntu recipe problem for several rounds.

The verify job is widened for the reason it exists: publishing an architecture
nothing ever installs is precisely the #179 shape it was added to prevent.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-tideforge-debs.yml"

ARCHES = {"amd64", "arm64"}


@pytest.fixture(scope="module")
def jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


@pytest.mark.parametrize("job", ["build", "verify"])
def test_the_job_covers_both_architectures(jobs, job):
    assert set(jobs[job]["strategy"]["matrix"]["arch"]) == ARCHES, job


@pytest.mark.parametrize("job", ["build", "verify"])
def test_each_architecture_runs_on_its_own_native_runner(jobs, job):
    """No qemu: a cross-built deb is not what these targets install, and an
    arm64 runner is what makes the build native."""
    runners = {
        entry["arch"]: entry["runner"]
        for entry in jobs[job]["strategy"]["matrix"]["include"]
        if "arch" in entry
    }
    assert set(runners) == ARCHES, (job, runners)
    assert "arm" in runners["arm64"], runners
    assert "arm" not in runners["amd64"], runners
    assert jobs[job]["runs-on"] == "${{ matrix.runner }}", job


def test_the_uploaded_artifact_name_carries_the_architecture(jobs):
    """Without the arch in the NAME the two arches collide on one artifact and
    one silently wins."""
    upload = next(
        step for step in jobs["build"]["steps"]
        if str(step.get("uses", "")).startswith("actions/upload-artifact")
    )
    assert "${{ matrix.arch }}" in upload["with"]["name"], upload["with"]["name"]


def test_the_publish_job_still_collects_every_architecture(jobs):
    """The download globs the distro prefix and merges, so both arches land in
    one pool and apt-ftparchive writes a single flat Packages -- correct for a
    flat repo, since apt selects on the Architecture field. If the pattern ever
    narrows past the distro, an arch would be dropped silently."""
    download = next(
        step for step in jobs["publish"]["steps"]
        if str(step.get("uses", "")).startswith("actions/download-artifact")
    )
    assert download["with"]["pattern"] == "publish-deb-${{ matrix.distro }}-*"
    assert download["with"]["merge-multiple"] is True


def test_the_publisher_never_hardcodes_a_single_runner_again(jobs):
    """The root cause was a literal runner with no arch dimension."""
    for job in ("build", "verify"):
        assert jobs[job]["runs-on"] != "ubuntu-latest", job
