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

    expected = out.read_text()
    actual = WORKFLOW.read_text()
    assert actual == expected, (
        "the committed distributed workflow is not what the generator emits.\n"
        "A generator change that never reaches this file changes nothing about "
        "what runs on a dispatch.\n\n"
        f"Regenerate with:\n\n    {REGENERATE}\n"
    )
