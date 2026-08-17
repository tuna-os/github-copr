"""The aarch64 leg of the Hummingbird desktop factory (tunaOS#1755 §3).

hummingbird's desktop flavors declare linux/arm64, but the only rebuild repo
that has ever existed is repo.tunaos.org/hummingbird/20251124-x86_64/ --
every aarch64 path 404s. `build-aarch64` in build-hummingbird-desktops.yml is
meant to be the smallest faithful mirror of the established x86_64 `build`
job: same manifest, same tiers, same publish/cache mechanics, on a native
aarch64 runner against an aarch64 mock chroot and mock-runner image.

"Faithful mirror" is the thing worth pinning, not the exact text -- these
tests check the properties that made the x86_64 job correct still hold for
its aarch64 sibling, plus the properties that are aarch64-specific by
necessity (a real --image override, a real aarch64 mock config, no name
collisions between the two jobs' artifacts/caches in the same workflow run).

The single most important one: build-fprintd-aarch64.yml already hit the
failure mode this exists to prevent. build-chain.sh's own BUILD_IMAGE default
is the x86_64 mock-runner tag, so a workflow that sets MOCK_RUNNER_IMAGE_*
without ever passing --image pulls an amd64 image onto an arm64 runner and
every package dies with "Exec format error" -- silently arch-mismatched, not
a build failure that names itself.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github/workflows/build-hummingbird-desktops.yml"
FACTORY = REPO / "manifests/package-factory.yaml"
CONTAINERFILE = REPO / "mock/Containerfile"
X86_CFG = REPO / "mock/hummingbird-ci.cfg"
AARCH64_CFG = REPO / "mock/hummingbird-ci-aarch64.cfg"

PUBLISH_STEPS = ("Sign RPMs and publish", "Publish signed rpm-md repository")


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def job(name: str) -> dict:
    return workflow()["jobs"][name]


def steps(job_name: str) -> list:
    return job(job_name)["steps"]


def step(job_name: str, name: str) -> dict:
    return next(s for s in steps(job_name) if s.get("name") == name)


# ── the job exists and is shaped like a real aarch64 build ─────────────────


def test_the_aarch64_job_exists():
    assert "build-aarch64" in workflow()["jobs"]


def test_it_runs_on_a_native_aarch64_runner():
    """Not an emulated x86_64 runner -- ubuntu-24.04-arm is real hardware.

    tunaOS's own reusable-build-image.yml already uses this runner label for
    arm64 (measured fact behind this PR); build-fprintd-aarch64.yml and
    build-mock-runner.yml's build-and-push-aarch64 job use the same label in
    this repo.
    """
    assert job("build-aarch64")["runs-on"] == "ubuntu-24.04-arm"


def test_it_shares_the_plan_jobs_desktop_list():
    """The package list is arch-neutral, so there is no separate aarch64 gap
    measurement to keep in sync -- both jobs fan out over the same desktops.
    """
    build_job = job("build-aarch64")
    needs = build_job["needs"]
    needs = [needs] if isinstance(needs, str) else needs
    assert "plan" in needs
    matrix = build_job["strategy"]["matrix"]
    assert matrix["desktop"] == "${{ fromJson(needs.plan.outputs.desktops) }}"


def test_one_desktop_failing_does_not_cancel_the_others():
    assert job("build-aarch64")["strategy"]["fail-fast"] is False


def test_the_target_axis_matches_the_x86_64_job():
    """Same target name -- it is what makes hummingbird a covered target for
    validate-package-factory.py's gate-coverage check (#139 defect class);
    the aarch64 job must not accidentally invent a second target name that
    check-gate-coverage.py has never heard of.
    """
    assert job("build-aarch64")["strategy"]["matrix"]["target"] == ["hummingbird"]
    assert job("build")["strategy"]["matrix"]["target"] == ["hummingbird"]


# ── the --image bug this whole file exists to prevent ──────────────────────


def test_build_tiers_passes_image_explicitly():
    """build-chain.sh's own default BUILD_IMAGE is the x86_64 tag.

    Setting MOCK_RUNNER_IMAGE_AARCH64 in `env:` is not enough by itself --
    build-chain.sh never reads that variable, only --image. Without it here,
    podman pulls the amd64 image onto this arm64 runner and mock's rebuild
    step fails with "Exec format error" on the very first package, exactly
    as it did for build-fprintd-aarch64.yml before that workflow added the
    same flag (see its own "Build libfprint + fprintd" step comment).
    """
    run = step("build-aarch64", "Build tiers")["run"]
    assert "--image" in run, (
        "Build tiers never passes --image; build-chain.sh will fall back to "
        "its own x86_64 default and pull the wrong architecture"
    )
    assert "MOCK_RUNNER_IMAGE_AARCH64" in run, (
        "--image is present but not wired to the aarch64 tag"
    )


def test_build_tiers_uses_the_aarch64_mock_config():
    run = step("build-aarch64", "Build tiers")["run"]
    assert "-ci-aarch64" in run, (
        "Build tiers does not select an aarch64 mock config; it would reuse "
        "hummingbird-ci (include('/etc/mock/fedora-rawhide-x86_64.cfg')) on "
        "an aarch64 runner"
    )


def test_the_x86_64_jobs_build_step_is_unchanged():
    """The whole point of a separate job: `build` should not need to know
    aarch64 exists. Pin its --image-less invocation so a future edit cannot
    accidentally entangle the two jobs' build steps.
    """
    run = step("build", "Build tiers")["run"]
    assert "--image" not in run, (
        "the x86_64 job now passes --image; if that was intentional, this "
        "test (and its comment) is stale and should be updated, not deleted"
    )


# ── no collisions between two jobs in the same workflow run ────────────────


def test_every_aarch64_artifact_name_is_unique():
    """Two jobs uploading the same artifact name in one workflow run is a
    hard failure in upload-artifact v4+ -- and `build` already uploads
    hummingbird-import-state-<desktop> and hummingbird-rpms-<desktop> in the
    SAME run whenever both jobs execute (the default schedule case).
    """
    x86_64_names = {
        s["with"]["name"]
        for s in steps("build")
        if str(s.get("uses", "")).startswith("actions/upload-artifact")
    }
    aarch64_names = {
        s["with"]["name"]
        for s in steps("build-aarch64")
        if str(s.get("uses", "")).startswith("actions/upload-artifact")
    }
    assert aarch64_names, "the aarch64 job uploads nothing at all"
    for name in aarch64_names:
        assert "matrix.desktop" in name, (
            f"artifact {name!r} is not per-desktop; concurrent desktop jobs "
            "would collide on it"
        )
        assert "aarch64" in name, (
            f"artifact {name!r} does not name its architecture and will "
            "collide with the x86_64 job's artifact of the same desktop"
        )
    # Literal collision check: substitute nothing (the desktop expression is
    # identical in both jobs), so a textual overlap here is a real overlap.
    assert not (x86_64_names & aarch64_names), (
        f"identical artifact name(s) in both jobs: {x86_64_names & aarch64_names}"
    )


def test_the_mock_cache_key_is_scoped_to_this_architecture():
    """A chroot cache is real filesystem content built for one architecture.

    Restoring an aarch64 mock/tar into an x86_64 rebuild (or the reverse) is
    not a cache hit, it is a corrupt buildroot -- the key must not be
    shareable across the two jobs.
    """
    cache_step = next(
        s
        for s in steps("build-aarch64")
        if str(s.get("uses", "")).startswith("actions/cache")
        and s["with"]["path"] == "${{ runner.temp }}/mock-cache"
    )
    key = cache_step["with"]["key"]
    assert "aarch64" in key
    assert "hummingbird-ci-aarch64.cfg" in key, (
        "the mock-chroot cache key does not hash the aarch64 mock config, so "
        "an aarch64-only config edit would not invalidate this leg's cache"
    )
    x86_64_key = step("build", "Cache the mock chroot and its dnf downloads")["with"]["key"]
    assert key != x86_64_key


def test_cache_steps_cannot_fail_the_aarch64_job():
    """Same INCIDENT-repo-wipe-gnome.md-adjacent lesson the x86_64 job
    learned the hard way (test_hummingbird_publish_requires_a_build.py):
    without continue-on-error, a rejected cache key silently skips `Build
    tiers` while the publish steps still run.
    """
    for name in (
        "Cache the mock chroot and its dnf downloads",
        "Cache upstream source tarballs",
    ):
        assert step("build-aarch64", name).get("continue-on-error") is True


# ── the publish guard applies here too ──────────────────────────────────────


@pytest.mark.parametrize("name", PUBLISH_STEPS)
def test_aarch64_publish_requires_the_build_step_to_have_run(name):
    condition = step("build-aarch64", name)["if"]
    assert "steps.build.conclusion != 'skipped'" in condition
    assert "steps.build.conclusion == 'success'" not in condition


@pytest.mark.parametrize("name", PUBLISH_STEPS)
def test_aarch64_publish_refuses_an_empty_result(name):
    assert "steps.progress.outputs.built_rpms != '0'" in step("build-aarch64", name)["if"]


def test_aarch64_progress_runs_even_when_the_build_failed():
    assert "!cancelled()" in step("build-aarch64", "Summarise progress")["if"]


# ── the arch input gates which job(s) a manual dispatch runs ───────────────


def test_a_bare_dispatch_builds_x86_64_only():
    """`arch` defaults to x86_64 so a human debugging one desktop/tier does
    not also kick off an unrelated six-hour aarch64 run.
    """
    inputs = workflow()[True]["workflow_dispatch"]["inputs"]
    assert inputs["arch"]["default"] == "x86_64"


def test_the_scheduled_run_builds_both_architectures():
    """No `inputs` exist on the schedule trigger, so both jobs' `if:` must
    resolve to true when `inputs.arch` is absent, not just when it is
    'x86_64'/'aarch64' -- the `|| 'all'` fallback is what does that.
    """
    assert "|| 'all'" in job("build")["if"]
    assert "|| 'all'" in job("build-aarch64")["if"]


def test_the_two_jobs_if_conditions_are_not_both_skippable_by_the_same_input():
    """arch: x86_64 must not skip both jobs, and arch: aarch64 must not skip
    both jobs -- each condition should name the OTHER architecture as its
    skip trigger, not itself.
    """
    assert "aarch64" in job("build")["if"]
    assert "x86_64" not in job("build")["if"].replace("aarch64", "")
    assert "x86_64" in job("build-aarch64")["if"]


# ── the mock-runner image this job depends on ───────────────────────────────


def test_the_aarch64_mock_runner_image_is_a_distinct_tag():
    """Not a multi-arch manifest fused under :centos-stream-10 --
    build-mock-runner.yml's build-and-push-aarch64 job pushes this as its
    own tag, mirroring the reasoning in that job's own comment: mock's chroot
    content is pulled per-run via use_bootstrap_image, so there is no
    correctness reason to fuse the two, and keeping them separate means an
    aarch64-only rebuild never touches the x86_64 image other workflows
    depend on.
    """
    env = workflow()["env"]
    assert env["MOCK_RUNNER_IMAGE_AARCH64"] == "ghcr.io/tuna-os/mock-runner:centos-stream-10-aarch64"
    assert env["MOCK_RUNNER_IMAGE_AARCH64"] != env["MOCK_RUNNER_IMAGE"]


def test_pull_mock_runner_step_pulls_the_aarch64_tag():
    run = step("build-aarch64", "Pull mock runner")["run"]
    assert "MOCK_RUNNER_IMAGE_AARCH64" in run


# ── the manifest and mock config this job reads ─────────────────────────────


def test_package_factory_declares_hummingbird_aarch64():
    factory = yaml.safe_load(FACTORY.read_text())
    hummingbird = factory["targets"]["hummingbird"]
    assert "aarch64" in hummingbird["architectures"]
    assert "x86_64" in hummingbird["architectures"], (
        "aarch64 must be ADDED, not swapped in for x86_64 -- the established "
        "leg is still live and must keep publishing"
    )
    assert "r2_path_aarch64" in hummingbird, (
        "no separate field for the aarch64 leg's R2 path"
    )


def test_the_established_leg_r2_path_is_unchanged_and_unformatted():
    """r2_path itself must stay the exact literal path it always was.

    build's own R2-path step reads it verbatim, with no .format() call (see
    test_the_resolve_r2_path_steps_agree_with_the_manifest) -- so this field
    can never contain a placeholder like `{arch}` without breaking the
    already-live x86_64 publish path.
    """
    factory = yaml.safe_load(FACTORY.read_text())
    hummingbird = factory["targets"]["hummingbird"]
    assert hummingbird["r2_path"] == "hummingbird/20251124-x86_64"
    assert "{" not in hummingbird["r2_path"]


def test_the_aarch64_r2_path_is_the_expected_sibling_path():
    factory = yaml.safe_load(FACTORY.read_text())
    hummingbird = factory["targets"]["hummingbird"]
    assert hummingbird["r2_path_aarch64"] == "hummingbird/20251124-aarch64"


def test_the_resolve_r2_path_steps_agree_with_the_manifest():
    x86_64_run = step("build", "Resolve the target's R2 path from the package factory manifest")["run"]
    aarch64_run = step("build-aarch64", "Resolve the target's R2 path from the package factory manifest")["run"]
    assert 'target["r2_path"]' in x86_64_run
    assert '.format(' not in x86_64_run, (
        "the x86_64 job's R2-path step must read r2_path verbatim -- it "
        "already publishes the live leg, and no `{arch}` template lives in "
        "that field for it to format"
    )
    assert 'target["r2_path_aarch64"]' in aarch64_run, (
        "the aarch64 job's R2-path step does not read the aarch64-specific "
        "field"
    )


def test_the_aarch64_mock_config_exists():
    assert AARCH64_CFG.exists()


def test_the_aarch64_mock_config_targets_the_aarch64_chroot_template():
    text = AARCH64_CFG.read_text()
    assert "include('/etc/mock/fedora-rawhide-aarch64.cfg')" in text, (
        "this is the load-bearing line: hummingbird-ci.cfg includes "
        "fedora-rawhide-x86_64.cfg, and copying that verbatim onto an "
        "aarch64 runner would build an x86_64 chroot inside qemu instead of "
        "a native aarch64 one"
    )
    assert "config_opts['root'] = 'hummingbird-ci-aarch64'" in text, (
        "the mock config's own root name must match the "
        "--mock-config hummingbird-ci-aarch64 the workflow passes it"
    )


def test_the_aarch64_mock_config_keeps_the_same_repo_priorities():
    """The perl/python/golang/mpich pins are arch-neutral name/version
    splits (measured in hummingbird-ci.cfg's own header) and must carry over
    unchanged, or every desktop tier hits the same failures on aarch64 that
    hummingbird-ci.cfg was written to fix on x86_64.
    """
    x86_64_lines = [
        line
        for line in X86_CFG.read_text().splitlines()
        if line.startswith(("priority=", "includepkgs=", "excludepkgs=", "[")
        )
    ]
    aarch64_lines = [
        line
        for line in AARCH64_CFG.read_text().splitlines()
        if line.startswith(("priority=", "includepkgs=", "excludepkgs=", "[")
        )
    ]
    assert aarch64_lines == x86_64_lines, (
        "the aarch64 mock config's repo sections have drifted from "
        "hummingbird-ci.cfg's; only the base chroot include and root name "
        "should differ"
    )


def test_the_mock_runner_image_bakes_in_the_aarch64_config():
    """A fallback for running the image by hand (build-chain.sh always
    overlays the checked-out mock/ directory at runtime, so this is not load-
    bearing for CI) -- but every other aarch64-capable config in mock/ is
    baked in, and a silently-stale image is exactly the kind of thing #176
    was about.
    """
    text = CONTAINERFILE.read_text()
    assert "COPY hummingbird-ci-aarch64.cfg /etc/mock/hummingbird-ci-aarch64.cfg" in text
