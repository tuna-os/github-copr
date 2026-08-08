"""The gate dispatcher: scripts/plan_gate_matrix.py.

The gate declares 98 cells (84 supported + 14 arch) behind ONE boolean, so
editing a single recipe rebuilds 97 bit-identical artifacts.  This plans the
run instead.

Everything here is written against the dangerous direction.  A dispatcher's
failure mode is not "built too much", it is the silent skip -- the declared
target no cell exercised (#139), the wishlist that made every missing package
optional (#1080).  So the fail-open paths get as much coverage as the happy
one, and the downstream-closure tests exist because the first implementation
DID drop cosmic-comp-deb: it was pulled in correctly by the `needs:` closure
and then filtered right back out by a "your own recipe is unchanged" rule that
must not apply to a job whose whole reason for running is somebody else's
rebuilt artifact.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from plan_gate_matrix import (  # noqa: E402
    changed_packages,
    is_shared_input,
    plan,
    recipe_fingerprint,
    running_jobs,
)

SUPPORTED = ROOT / ".github" / "workflows" / "build-tideforge-supported.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(SUPPORTED.read_text())


def running(result) -> set[str]:
    return {n for n, e in result["jobs"].items() if e["run"]}


def cells(result) -> int:
    total = 0
    for entry in result["jobs"].values():
        if entry["matrix"] is not None:
            total += len(entry["matrix"]["include"])
        elif entry["run"]:
            total += 1
    return total


# ── fail open ──────────────────────────────────────────────────────────────

def test_no_diff_information_builds_everything(workflow):
    """push/dispatch/schedule carry no usable base -- never trim those."""
    result = plan(workflow, changed_files=None, root=ROOT)
    assert result["_full"] is True
    assert running(result) == set(workflow["jobs"])


@pytest.mark.parametrize(
    "path",
    [
        "scripts/tideforge.py",
        "scripts/build-chain.sh",
        "mock/centos-stream-10-local.cfg",
        ".github/workflows/build-tideforge-supported.yml",
        ".github/actions/tideforge-source-cache/action.yml",
        "manifests/package-factory.yaml",
        "build-order-xfce.yml",
    ],
)
def test_shared_inputs_force_a_full_build(workflow, path):
    """These feed every cell; trimming after one changes is the silent skip."""
    assert is_shared_input(path)
    result = plan(workflow, [path], root=ROOT)
    assert result["_full"] is True
    assert cells(result) == cells(plan(workflow, None, root=ROOT))


def test_an_unrelated_change_builds_nothing(workflow):
    result = plan(workflow, ["README.md", "docs/whatever.md"], root=ROOT)
    assert cells(result) == 0
    assert running(result) == set()


def test_a_missing_recipe_directory_cannot_be_proven(tmp_path):
    """No recipe on disk -> no fingerprint -> the cell must build."""
    assert recipe_fingerprint(tmp_path, "does-not-exist", "el10", "img") is None


# ── the trimming itself ────────────────────────────────────────────────────

def test_changed_packages_reads_the_recipe_directory():
    assert changed_packages(["packages/uupd/package.yaml"]) == {"uupd"}
    assert changed_packages(["packages/niri/patches/x.patch"]) == {"niri"}
    assert changed_packages(["README.md"]) == set()


def test_one_leaf_recipe_trims_the_run_hard(workflow):
    full = cells(plan(workflow, None, root=ROOT))
    result = plan(workflow, ["packages/uupd/package.yaml"], root=ROOT)
    assert 0 < cells(result) < full / 2, "a leaf recipe should not rebuild the world"


def test_a_seeded_matrix_job_drops_its_other_cells(workflow):
    result = plan(workflow, ["packages/uupd/package.yaml"], root=ROOT)
    rpm = result["jobs"]["rpm"]
    packages = {c["package"] for c in rpm["matrix"]["include"]}
    assert packages == {"uupd"}


# ── downstream closure: the part that broke ────────────────────────────────

def test_a_producer_change_drags_its_consumers(workflow):
    """cosmic-icon-theme feeds cosmic-comp and cosmic-bg, on both rpm and deb."""
    result = plan(workflow, ["packages/cosmic-icon-theme/package.yaml"], root=ROOT)
    live = running(result)
    for consumer in ("cosmic-comp-rpm", "cosmic-bg-rpm", "cosmic-comp-deb", "cosmic-icon-theme-deb"):
        assert consumer in live, f"{consumer} consumes the changed artifact and must rebuild"


def test_downstream_jobs_keep_all_their_cells(workflow):
    """The regression that shipped in the first draft.

    cosmic-comp-deb's own recipe is untouched -- that is precisely why it is
    downstream -- so a 'recipe unchanged' filter silently emptied its matrix
    and the job vanished after the closure had already included it.
    """
    result = plan(workflow, ["packages/cosmic-icon-theme/package.yaml"], root=ROOT)
    entry = result["jobs"]["cosmic-comp-deb"]
    declared = workflow["jobs"]["cosmic-comp-deb"]["strategy"]["matrix"]["include"]
    assert entry["run"] is True
    assert len(entry["matrix"]["include"]) == len(declared)


def test_transitive_closure_reaches_two_hops(workflow):
    """quickshell-rpm needs cpptrace-rpm; dms-stack-rpm needs quickshell-rpm."""
    seeded, downstream = running_jobs(workflow, {"cpptrace-devel"})
    assert "cpptrace-rpm" in seeded
    assert {"quickshell-rpm", "dms-stack-rpm"} <= downstream


# ── phase 2: fingerprints ──────────────────────────────────────────────────

def test_fingerprint_is_stable_and_target_scoped(workflow):
    a = recipe_fingerprint(ROOT, "uupd", "el10", "img")
    b = recipe_fingerprint(ROOT, "uupd", "el10", "img")
    c = recipe_fingerprint(ROOT, "uupd", "debian", "img")
    d = recipe_fingerprint(ROOT, "uupd", "el10", "other-image")
    assert a and a == b
    assert a != c, "the same recipe on another target is a different proof"
    assert a != d, "a different toolchain image is a different proof"


def test_fingerprint_follows_the_recipe_contents(tmp_path):
    pkg = tmp_path / "packages" / "demo"
    pkg.mkdir(parents=True)
    (pkg / "package.yaml").write_text("version: 1\n")
    before = recipe_fingerprint(tmp_path, "demo", "el10", "img")
    (pkg / "package.yaml").write_text("version: 2\n")
    assert recipe_fingerprint(tmp_path, "demo", "el10", "img") != before


def test_fingerprint_follows_shared_renderer_files(tmp_path):
    pkg = tmp_path / "packages" / "demo"
    pkg.mkdir(parents=True)
    (pkg / "package.yaml").write_text("version: 1\n")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "tideforge.py").write_text("# v1\n")
    before = recipe_fingerprint(tmp_path, "demo", "el10", "img")
    (scripts / "tideforge.py").write_text("# v2\n")
    assert recipe_fingerprint(tmp_path, "demo", "el10", "img") != before, (
        "a renderer change must invalidate every previously-proven fingerprint"
    )


def test_a_proven_fingerprint_drops_only_that_cell(workflow):
    result = plan(workflow, ["packages/uupd/package.yaml"], root=ROOT)
    kept = result["jobs"]["rpm"]["matrix"]["include"]
    assert kept, "precondition: uupd has an rpm cell"
    cell = kept[0]
    fp = recipe_fingerprint(ROOT, cell["package"], cell.get("target", ""), cell.get("image", ""))
    assert fp
    pruned = plan(workflow, ["packages/uupd/package.yaml"], root=ROOT, proven={fp})
    assert cell not in pruned["jobs"]["rpm"]["matrix"]["include"]


def test_an_unknown_proven_set_prunes_nothing(workflow):
    base = plan(workflow, ["packages/uupd/package.yaml"], root=ROOT)
    same = plan(workflow, ["packages/uupd/package.yaml"], root=ROOT, proven={"deadbeef" * 8})
    assert cells(same) == cells(base)


def test_every_skip_carries_a_reason(workflow):
    result = plan(workflow, ["packages/uupd/package.yaml"], root=ROOT)
    for entry in result["jobs"].values():
        for skip in entry["skipped"]:
            assert skip["why"], "a skip without a reason is a silent skip"


# ── wiring: the plan must actually be consumed, and safely ─────────────────

WIRED_JOBS = {
    "gtkgreet-rpm", "cpptrace-rpm", "quickshell-rpm", "niri-rpm", "iio-niri-rpm",
    "dms-stack-rpm", "cosmic-icon-theme-rpm", "cosmic-comp-rpm", "cosmic-bg-rpm",
}


def test_the_plan_job_exists_and_outputs_every_wired_job(workflow):
    plan_job = workflow["jobs"].get("plan")
    assert plan_job, "the dispatcher job is gone; the wiring below is decoration"
    outputs = plan_job.get("outputs", {})
    for job in WIRED_JOBS:
        assert f"{job.replace('-', '_')}_run" in outputs, f"plan does not publish a verdict for {job}"


@pytest.mark.parametrize("job", sorted(WIRED_JOBS))
def test_wired_jobs_gate_on_the_plan(workflow, job):
    spec = workflow["jobs"][job]
    assert "plan" in spec["needs"], f"{job} reads the plan's output but does not need it"
    assert f"needs.plan.outputs.{job.replace('-', '_')}_run == 'true'" in spec["if"]


def test_every_matrix_free_build_job_is_wired(workflow):
    """A new dedicated job must not silently miss the dispatcher.

    Missing wiring only costs runner minutes, but the reverse mistake -- a job
    wired to an output the plan never publishes -- evaluates to an empty string
    and skips the job forever.  Both directions are caught here.
    """
    from plan_gate_matrix import job_packages
    infra = {"detect-changes", "plan", "tideforge-gate", "rpm-payload"}
    for name, spec in workflow["jobs"].items():
        if name in infra:
            continue
        has_matrix = bool((spec.get("strategy") or {}).get("matrix", {}).get("include"))
        if has_matrix or not job_packages(name, spec):
            continue
        assert name in WIRED_JOBS, f"{name} builds a recipe, has no matrix, and is not wired to the plan"


def test_the_aggregate_gate_accepts_planned_skips(workflow):
    """Trimming a job makes it 'skipped'; the gate must not call that failure.

    Read the step's `run:` script straight off the parsed job -- re-dumping it
    to YAML escapes the quotes and the substring silently never matches, which
    is a test that passes for the wrong reason.
    """
    scripts = " ".join(step.get("run", "") for step in workflow["jobs"]["tideforge-gate"]["steps"])
    assert 'result != "skipped"' in scripts, (
        "the gate still demands success from every job, so any trimmed job turns the PR red"
    )


def test_the_gate_still_waits_on_every_build_job(workflow):
    """Trimming must never remove a job from the gate's needs list.

    That list is what makes accepting 'skipped' safe: a real failure is visible
    to the gate directly, so a dependent's skip can never launder it.
    """
    needs = set(workflow["jobs"]["tideforge-gate"]["needs"])
    for name, spec in workflow["jobs"].items():
        if name in {"detect-changes", "tideforge-gate"}:
            continue
        if (spec.get("strategy") or {}).get("matrix", {}).get("include") or name in WIRED_JOBS or name == "rpm-payload":
            assert name in needs, f"{name} builds but the gate does not wait on it"
