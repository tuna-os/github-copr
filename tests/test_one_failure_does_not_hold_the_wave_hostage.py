"""A failed package must not stop the built ones from publishing.

Legs 32914264044, 32991216265 and 33022688689 each built 81-85 packages,
failed 1-3, and published NOTHING: the wave upload carried no `if:`, so the
build step's failure skipped it, the publish job (default success gating)
skipped in turn, and the next leg rebuilt the same packages against an
unchanged served index. Accumulation (#544) is impossible under that wiring
regardless of how well the chain itself banks partials.

Asserted here:

  * the wave upload runs `always()` — a chain that failed one package out of
    674 still banked the rest, and those bytes are the whole point;
  * it warns rather than errors on an empty wave — a cell torn down before
    its first RPM must surface the BUILD failure, not an upload failure;
  * the publish job runs unless the run was cancelled — `!cancelled()`
    because a torn-down run must not race a fresh dispatch for the bucket,
    `plan.result == 'success'` because without the planner there is no
    matrix to publish;
  * the partial-banking upload keeps its own conditions — publishing the
    wave and banking the resume state are different guarantees and one must
    not absorb the other.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "publish-build-chain-rpms.yml"


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def build_job(workflow):
    return workflow["jobs"]["build"]


@pytest.fixture(scope="module")
def wave_upload(build_job):
    steps = [
        s for s in build_job["steps"]
        if "upload-artifact" in str(s.get("uses", ""))
        and "publish-rpm-" in str(s.get("with", {}).get("name", ""))
    ]
    assert len(steps) == 1, "exactly one wave upload expected"
    return steps[0]


def test_the_wave_uploads_even_when_a_package_failed(wave_upload):
    assert "always()" in str(wave_upload.get("if", "")), (
        "no always(): one failed package skips the upload, starves publish, "
        "and the same packages rebuild every leg against a frozen index"
    )


def test_an_empty_wave_warns_instead_of_masking_the_build_failure(wave_upload):
    assert wave_upload["with"]["if-no-files-found"] == "warn"


def test_publish_runs_on_a_red_build(workflow):
    cond = str(workflow["jobs"]["publish"].get("if", ""))
    assert "!cancelled()" in cond, (
        "publish must run when build is red (the wave holds what DID build) "
        "but never on a cancelled run racing a fresh dispatch for the bucket"
    )
    assert "needs.plan.result == 'success'" in cond


def test_publish_does_not_run_unconditionally(workflow):
    cond = str(workflow["jobs"]["publish"].get("if", ""))
    assert "always()" not in cond, (
        "always() would publish even from a cancelled run — the exact "
        "two-publishers-one-bucket shape of #124"
    )


def test_partial_banking_keeps_its_own_conditions(build_job):
    partials = [
        s for s in build_job["steps"]
        if "-partial" in str(s.get("with", {}).get("name", ""))
    ]
    assert len(partials) == 1
    cond = str(partials[0].get("if", ""))
    assert "always()" in cond
    assert "steps.build.outcome" in cond, (
        "the partial's allowlist must survive: it exists so a cache hit does "
        "not upload a redundant copy, and that logic is separate from the wave"
    )
