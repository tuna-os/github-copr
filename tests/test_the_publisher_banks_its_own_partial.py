"""A six-hour publisher run that is torn down must not lose its chain.

`publish-build-chain-rpms.yml` exists to resume the nightly's banked partial
and extend it. Until now it could only ever READ one. Its single upload is the
success artifact, which carries no `always()`, so a run that exhausted its
360-minute `timeout-minutes` uploaded nothing — and the next run resumed from
whatever the nightly had last banked, as if those six hours had not happened.

That is the other half of why the chain does not accumulate. The first half
was the epoch: the publisher derived it from paths including the manifest
while `package-factory-cell.yml` (post-#529) did not, so their action keys
disagreed by 35 hours of commit time and every partial was rejected as "action
key differs". Fixing only the key would let the publisher accept a partial it
still could not produce.

Every rule asserted here was learned in package-factory-cell.yml and is copied
rather than re-derived:

  * `always()`, because a timeout tears the job down and it is the only
    condition GitHub documents as still running steps then;
  * an outcome ALLOWLIST, because `!= 'success'` also fires on an exact cache
    hit — where the build never ran — and uploads a redundant copy the size of
    the real artifact;
  * `chain_deferred`, because the soft deadline exits 0 and would otherwise
    look like a clean finish.

The `id: build` test is the one that matters most. Without it every condition
above reads `steps.build.outcome` on a step that has no id, evaluates empty,
and the upload silently never runs — configured, reviewed, and inert.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / ".github" / "workflows" / "publish-build-chain-rpms.yml"
CELL = ROOT / ".github" / "workflows" / "package-factory-cell.yml"
RESTORE = ROOT / "scripts" / "restore-partial-chain-output.py"


def build_steps() -> list[dict]:
    return yaml.safe_load(PUBLISHER.read_text(encoding="utf-8"))["jobs"]["build"]["steps"]


def partial_upload() -> dict:
    for step in build_steps():
        with_ = step.get("with") or {}
        if "upload-artifact" in str(step.get("uses", "")) and str(
            with_.get("name", "")
        ).endswith("-partial"):
            return step
    raise AssertionError("the publisher has no partial upload step")


def test_the_publisher_uploads_a_partial_at_all():
    assert partial_upload()


def test_the_build_step_has_an_id_or_every_condition_is_inert():
    """`steps.build.outcome` on a step with no id evaluates to empty."""
    named = [s for s in build_steps() if s.get("name") == "Build the cell"]
    assert named, "the build step was renamed; this file no longer measures it"
    assert named[0].get("id") == "build", (
        "the partial upload conditions read steps.build.*, which is empty "
        "unless the step declares `id: build` — the upload would never run"
    )


def test_it_survives_a_timeout_teardown():
    assert "always()" in partial_upload()["if"], (
        "a job that exhausts timeout-minutes is torn down; only always() is "
        "documented as still running steps then"
    )


def test_the_outcome_test_is_an_allowlist_not_a_denylist():
    """`!= 'success'` also fires on a cache hit, where the build never ran."""
    condition = partial_upload()["if"]
    assert "!=" not in condition, (
        "a denylist admits every future outcome value, which is how `skipped` "
        "got in and uploaded a redundant copy of every cached cell"
    )
    for outcome in ("failure", "cancelled"):
        assert f"steps.build.outcome == '{outcome}'" in condition


def test_a_deferred_chain_also_banks():
    """The soft deadline exits 0, so the outcome is `success`."""
    assert "steps.build.outputs.chain_deferred == 'true'" in partial_upload()["if"]


def test_the_name_is_what_the_resume_step_queries():
    """Read and write must agree, or the upload is written where nothing looks.

    restore-partial-chain-output.py builds the artifact name as
    f"{cell_id}-partial", and this job passes --cell-id matrix.id.
    """
    assert '-partial"' in RESTORE.read_text(encoding="utf-8")
    assert partial_upload()["with"]["name"] == "${{ matrix.id }}-partial"
    body = PUBLISHER.read_text(encoding="utf-8")
    assert "--cell-id '${{ matrix.id }}'" in body


def test_it_overwrites_rather_than_failing_on_the_shared_name():
    """One partial per family cell; each run replaces the previous."""
    assert partial_upload()["with"]["overwrite"] is True


def test_it_carries_the_action_key_the_next_resume_checks():
    """A partial with no recorded key is rejected as unverifiable."""
    paths = partial_upload()["with"]["path"]
    assert "action-key.txt" in paths
    assert "artifacts/" in paths


def test_a_missing_directory_warns_rather_than_failing_the_job():
    """A cell that died before creating it would otherwise replace the real
    error with an upload error."""
    assert partial_upload()["with"]["if-no-files-found"] == "warn"


def test_the_success_upload_is_left_alone():
    """Guard the guard: the deliverable must still be uploaded on success."""
    names = [
        (s.get("with") or {}).get("name")
        for s in build_steps()
        if "upload-artifact" in str(s.get("uses", ""))
    ]
    assert "publish-rpm-${{ matrix.id }}" in names


def test_the_rules_match_the_workflow_they_were_copied_from():
    """Drift guard: if the cell runner's allowlist changes, this should too."""
    cell_body = CELL.read_text(encoding="utf-8")
    cell_conditions = re.findall(r"steps\.build\.outcome == '(\w+)'", cell_body)
    assert set(cell_conditions) >= {"failure", "cancelled"}, (
        "package-factory-cell.yml's allowlist changed shape; re-check this one"
    )
