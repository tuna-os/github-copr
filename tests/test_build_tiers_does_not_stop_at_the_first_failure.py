"""One tier's failures must not cancel every tier after it.

The `Build tiers` step runs under `set -e`. A tier exiting non-zero aborted
the loop, so a dispatch yielded exactly one tier no matter how many were
asked for:

    run 31277092125  gnome-01  30 of 33   gnome-02..09 never attempted
    run 31279618402  gnome-02  11 of 14   gnome-03..09 never attempted

A tier's failures rarely block the whole tail -- gnome-02's three were
libglvnd, libheif and samba, and most of what follows does not BuildRequire
any of them. Anything that genuinely does will fail on its own and say so.

The step must still fail when any tier did, or a red run silently goes green,
which is a far worse bug than the one being fixed. Both halves are pinned.
"""

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github/workflows/build-hummingbird-desktops.yml"


def build_tiers_script() -> str:
    steps = yaml.safe_load(WORKFLOW.read_text())["jobs"]["build"]["steps"]
    return next(s for s in steps if s.get("name") == "Build tiers")["run"]


def test_a_failing_tier_does_not_abort_the_loop():
    script = build_tiers_script()
    invocation = re.search(r"\./scripts/build-chain\.sh[^\n]*", script).group(0)
    assert invocation.rstrip().endswith("|| {"), (
        "build-chain.sh is called bare inside the loop; under `set -e` the "
        f"first failing tier aborts every tier after it. Got: {invocation!r}"
    )


def test_the_step_still_fails_when_a_tier_failed():
    """The dangerous half of this change is turning a red run green."""
    script = build_tiers_script()
    assert "rc=1" in script, "no failure is recorded"
    assert re.search(r"exit \"?\$\{?rc\}?\"?", script), (
        "the step does not exit non-zero after a failing tier, so a run with "
        "failed packages would report success"
    )


def test_the_failing_tiers_are_named():
    script = build_tiers_script()
    assert "failed_tiers" in script and "::error::" in script, (
        "failing tiers are not named in the step output; with the loop now "
        "continuing, the summary is the only place the set is visible"
    )


def test_rc_starts_clean():
    assert re.search(r"\brc=0\b", build_tiers_script()), "rc is never initialised"
