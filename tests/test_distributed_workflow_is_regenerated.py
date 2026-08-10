"""The committed workflow is generated, and nothing checked that it still was.

.github/workflows/build-hummingbird-distributed.yml has no human-edited lines:
it is whatever scripts/generate-distributed-workflow.py emits for
build-order-hummingbird-desktops.yml. Nothing enforced that, so a fix to the
generator could pass its own tests, be merged, and never reach a single runner
-- the workflow that actually dispatches would still be the old text.

This test also serves as the record of how to regenerate it, which until now
lived only in commit messages. REGENERATE is the command; if this test fails,
run it.
"""

import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "build-hummingbird-distributed.yml"

ARGS = [
    "scripts/generate-distributed-workflow.py",
    "build-order-hummingbird-desktops.yml",
    ".github/workflows/build-hummingbird-distributed.yml",
    "--name", "Build Hummingbird desktops (distributed)",
    "--mock-config", "hummingbird-ci",
    "--r2-path", "hummingbird/20251124-x86_64",
    "--secondary-r2-path", "",
    "--no-submodules",
    "--r2-state",
]

REGENERATE = "python3 " + " ".join(
    f'"{a}"' if (" " in a or a == "") else a for a in ARGS
)


def test_committed_workflow_matches_its_generator(tmp_path):
    out = tmp_path / "regenerated.yml"
    args = list(ARGS)
    args[2] = str(out)
    subprocess.run([sys.executable, *args], check=True, capture_output=True, cwd=REPO)

    # Compared parsed, not byte for byte. The committed file was emitted by one
    # PyYAML and CI runs another, and the emitter is free to choose quoting and
    # block style differently between versions. What has to hold is that the
    # workflow GitHub would run is the workflow the generator describes; a byte
    # comparison would also fail on an emitter upgrade, which is drift in the
    # test rather than in the tree.
    expected = yaml.safe_load(out.read_text())
    actual = yaml.safe_load(WORKFLOW.read_text())

    assert actual == expected, (
        "the committed distributed workflow is not what the generator emits.\n"
        "A generator change that never reaches this file changes nothing about "
        "what runs on a dispatch.\n\n"
        f"Regenerate with:\n\n    {REGENERATE}\n"
        + _first_difference(actual, expected)
    )


def _first_difference(actual, expected):
    """Point at the job and step that differ, rather than dumping 158 jobs."""
    if set(actual.get("jobs", {})) != set(expected.get("jobs", {})):
        only_committed = sorted(set(actual["jobs"]) - set(expected["jobs"]))
        only_generated = sorted(set(expected["jobs"]) - set(actual["jobs"]))
        return (f"\njobs only in the committed file: {only_committed}"
                f"\njobs only in the generated one: {only_generated}\n")
    for name in actual.get("jobs", {}):
        a, e = actual["jobs"][name], expected["jobs"][name]
        if a == e:
            continue
        for step_a, step_e in zip(a.get("steps", []), e.get("steps", [])):
            if step_a != step_e:
                return (f"\nfirst difference is in job {name!r}, step "
                        f"{step_a.get('name') or step_a.get('uses')!r}:\n"
                        f"  committed: {step_a}\n  generated: {step_e}\n")
        return f"\nfirst differing job: {name!r}\n"
    return ""
