"""At Hummingbird scale the repository cannot travel as a GitHub artifact.

The generator's original model hands the whole repository from tier to tier as
an artifact: every build runner downloads it. That is O(repo x packages-in-tier)
and it was fine at the scale it was written for.

Hummingbird's repository is over a gigabyte and gnome-00 is 108 packages, so a
single tier would move on the order of a hundred gigabytes of artifact traffic
in order to distribute a few hundred megabytes of RPMs.

--r2-state seeds each runner from R2 instead, which is O(1) per runner and
about two minutes -- a cost the sequential workflow already pays once. The
barrier is unchanged, so correctness is unchanged: a tier's runners start only
after the previous tier's consolidate job has published.
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
GENERATOR = REPO / "scripts" / "generate-distributed-workflow.py"
MANIFEST = REPO / "build-order-hummingbird-desktops.yml"


def generate(tmp_path, *extra):
    order = yaml.safe_load(MANIFEST.read_text())
    slice_ = [t for t in order["tiers"] if t["name"].startswith(("bootstrap", "gnome"))]
    src = tmp_path / "order.yml"
    src.write_text(yaml.safe_dump({"r2_path": order["r2_path"], "tiers": slice_}, sort_keys=False))
    out = tmp_path / "wf.yml"
    subprocess.run(
        [sys.executable, str(GENERATOR), str(src), str(out),
         "--mock-config", "hummingbird-ci",
         "--r2-path", order["r2_path"], "--secondary-r2-path", "",
         "--no-submodules", *extra],
        check=True, capture_output=True, cwd=REPO,
    )
    return yaml.safe_load(out.read_text())


def step_names(job):
    return [s.get("name") or s.get("uses") for s in job["steps"]]


def test_r2_state_never_moves_the_repository_as_an_artifact(tmp_path):
    wf = generate(tmp_path, "--r2-state")
    for name, job in wf["jobs"].items():
        for step in job["steps"]:
            if str(step.get("uses", "")).startswith("actions/download-artifact"):
                pattern = str(step.get("with", {}).get("pattern", ""))
                artifact = str(step.get("with", {}).get("name", ""))
                assert pattern.startswith("rpms-") or artifact.startswith("rpms-"), (
                    f"{name} downloads {artifact or pattern!r}; under --r2-state only a "
                    "tier's new rpms may travel as artifacts, never the repository"
                )


def test_without_the_flag_the_original_artifact_model_is_untouched(tmp_path):
    """The generator has another caller; this must be opt-in."""
    wf = generate(tmp_path)
    assert "Download previous repo" in step_names(wf["jobs"]["build-gnome-00"])


def test_every_build_runner_seeds_itself(tmp_path):
    wf = generate(tmp_path, "--r2-state")
    for name, job in wf["jobs"].items():
        if name.startswith("build-"):
            assert "Seed local repo from R2" in step_names(job), f"{name} has no repository"


def test_the_barrier_between_tiers_survives(tmp_path):
    """Correctness rests on this: tier N must wait for tier N-1 to publish."""
    wf = generate(tmp_path, "--r2-state")
    tiers = [t["name"] for t in yaml.safe_load(MANIFEST.read_text())["tiers"]
             if t["name"].startswith(("bootstrap", "gnome"))]
    for previous, current in zip(tiers, tiers[1:]):
        assert wf["jobs"][f"build-{current}"]["needs"] == f"consolidate-{previous}", (
            f"build-{current} does not wait for consolidate-{previous}; its packages "
            "would build against a repository missing the tier they depend on"
        )


def test_the_matrix_covers_every_package_in_the_tier(tmp_path):
    """A silently short matrix looks exactly like a complete one."""
    wf = generate(tmp_path, "--r2-state")
    order = yaml.safe_load(MANIFEST.read_text())
    for tier in order["tiers"]:
        if not tier["name"].startswith(("bootstrap", "gnome")):
            continue
        matrix = wf["jobs"][f"build-{tier['name']}"]["strategy"]["matrix"]["package"]
        assert len(matrix) == len(tier["packages"]), (
            f"{tier['name']}: matrix has {len(matrix)} cells for "
            f"{len(tier['packages'])} packages"
        )


def test_a_failing_package_does_not_cancel_its_tier(tmp_path):
    wf = generate(tmp_path, "--r2-state")
    for name, job in wf["jobs"].items():
        if name.startswith("build-"):
            assert job["strategy"]["fail-fast"] is False, (
                f"{name} is fail-fast; one package failing would cancel every "
                "other package in the tier mid-build"
            )


def test_tiers_publish_with_copy_not_sync(tmp_path):
    """sync would delete what earlier tiers published."""
    wf = generate(tmp_path, "--r2-state")
    publish = next(s for s in wf["jobs"]["consolidate-gnome-00"]["steps"]
                   if s.get("name") == "Publish this tier to R2")
    assert "rclone copy" in publish["run"]
    assert "rclone sync" not in publish["run"]


def test_one_r2_endpoint_secret_across_the_whole_workflow(tmp_path):
    """Two secrets for one endpoint means whichever is unset fails at runtime.

    The seed and publish jobs built their endpoint from CLOUDFLARE_ACCOUNT_ID
    while every per-tier job used R2_ENDPOINT. In a 158-job workflow that
    surfaces as two unrelated-looking jobs dying two minutes in, long after the
    change that caused it.

    R2_ENDPOINT is the one the existing Hummingbird workflow publishes with.
    """
    wf = generate(tmp_path, "--r2-state")
    text = yaml.safe_dump(wf)
    assert "CLOUDFLARE_ACCOUNT_ID" not in text, (
        "some job still builds its R2 endpoint from CLOUDFLARE_ACCOUNT_ID; "
        "under --r2-state every job must use R2_ENDPOINT"
    )
    assert "secrets.R2_ENDPOINT" in text


def test_the_default_still_uses_the_account_id_form(tmp_path):
    """The other caller's secrets are not ours to change."""
    wf = generate(tmp_path)
    assert "CLOUDFLARE_ACCOUNT_ID" in yaml.safe_dump(wf)
