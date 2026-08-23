"""A reusable workflow cannot request more permission than its caller grants.

GitHub rejects the CALLER's whole file when it does, and the message names
the callee:

    Invalid workflow file: .github/workflows/package-factory.yml#L144
    Error calling workflow '.../package-factory-cell.yml@966d9aa'. The
    workflow is requesting 'actions: read', but is only allowed 'actions: none'

This is not a failed run. It is a file that never parses, so nothing plans,
no job appears, and a merge queue has no required workflow to evaluate. It
cost hours of a session on a PR that read `blocked` with every visible check
green and no explanation anywhere in the UI -- and the diagnosis offered
twice was that the merge queue needed a human, which was wrong.

The cause was adding `actions: read` to package-factory-cell.yml so a
timed-out build chain could read its own previous artifacts (#480), without
adding it to package-factory.yml, which calls it.

Nothing else catches this. actionlint does not resolve local `uses:` targets,
yaml lint sees two valid documents, and every other test in this suite reads
one file at a time. The invariant is a RELATION between two files, so it
needs a test that holds both.
"""
from __future__ import annotations

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

# GitHub's own ordering: a caller granting `read` cannot satisfy `write`.
RANK = {"none": 0, "read": 1, "write": 2}


def permissions(document) -> dict:
    declared = (document or {}).get("permissions")
    # `permissions: write-all` / `read-all` are shorthands; neither appears
    # here, and treating an unrecognised shorthand as empty would make this
    # test claim a violation rather than miss one.
    return declared if isinstance(declared, dict) else {}


def local_calls() -> list[tuple[pathlib.Path, str, pathlib.Path]]:
    """Every (caller, job, callee) where a workflow calls one in this repo."""
    calls = []
    for caller in sorted(WORKFLOWS.glob("*.yml")):
        document = yaml.safe_load(caller.read_text(encoding="utf-8")) or {}
        for job_name, job in (document.get("jobs") or {}).items():
            uses = str((job or {}).get("uses") or "")
            if not uses.startswith("./.github/workflows/"):
                continue
            # removeprefix, NOT lstrip("./"): lstrip strips every leading
            # character in the set, so "./.github/..." loses the dot of
            # ".github" and becomes "github/...", which does not exist. The
            # first version of this scan did exactly that and silently found
            # nothing -- reporting no violations because it checked nothing.
            callee = ROOT / uses.removeprefix("./")
            if callee.exists():
                calls.append((caller, job_name, callee))
    return calls


def test_there_is_at_least_one_local_reusable_call_to_check():
    """Guards the test itself: if the discovery breaks, it must not pass by
    finding nothing."""
    assert local_calls(), "no local `uses:` calls found — the scan is broken"


def test_every_caller_grants_what_its_called_workflow_requests():
    violations = []
    for caller, job_name, callee in local_calls():
        caller_doc = yaml.safe_load(caller.read_text(encoding="utf-8")) or {}
        callee_doc = yaml.safe_load(callee.read_text(encoding="utf-8")) or {}
        # A job-level block REPLACES the workflow-level one for that job, so
        # the effective grant is the job's when it declares any.
        job = (caller_doc.get("jobs") or {}).get(job_name) or {}
        granted = permissions(job) or permissions(caller_doc)
        for scope, requested in permissions(callee_doc).items():
            have = granted.get(scope, "none")
            if RANK.get(requested, 0) > RANK.get(have, 0):
                violations.append(
                    f"{caller.name} job `{job_name}` calls {callee.name}, which "
                    f"requests {scope}: {requested} — caller grants {scope}: {have}"
                )
    assert not violations, (
        "GitHub rejects the CALLER's entire file for this, so nothing runs at "
        "all and the failure appears nowhere useful:\n" + "\n".join(violations)
    )


def test_the_factory_caller_grants_actions_read():
    """Named explicitly, because the sweep above would also pass if someone
    removed the resume step instead of granting the permission — and the
    resume is what stops a six-hour cell losing six hours of work."""
    caller = yaml.safe_load(
        (WORKFLOWS / "package-factory.yml").read_text(encoding="utf-8"))
    callee = yaml.safe_load(
        (WORKFLOWS / "package-factory-cell.yml").read_text(encoding="utf-8"))
    assert permissions(callee).get("actions") == "read"
    assert permissions(caller).get("actions") == "read"
