"""Publishing must require that a build actually ran and produced something.

Between 2026-08-09 and 2026-08-14 this workflow compiled zero packages and
published on every run anyway. The mechanism was a chain of individually
reasonable decisions:

    Step 10  Cache the mock chroot     FAILURE   (0s -- comma in the cache key)
    Step 12  Build tiers               skipped   (implicit success() on step 10)
    Step 14  Publish signed repository success   (guarded only by !cancelled())

`!cancelled()` is true for a step that was SKIPPED, so the publish steps fired
for a run that had built nothing, re-signed the seed it had just pulled from
R2, and uploaded it back. Every RPM at
repo.tunaos.org/hummingbird/20251124-x86_64/ carries a file timestamp between
2026-08-07 and 2026-08-09; the four days of runs after that added nothing and
looked, from the outside, exactly like a repository being maintained.

Downstream, tuna-os/tunaOS#1555 read the resulting package set as a partial
rebuild rather than a stalled one -- the failure was invisible precisely
because the pipeline kept publishing.

These tests pin the three properties that make that combination impossible,
and one that stops the runs being evicted before they can execute at all.
"""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github/workflows/build-hummingbird-desktops.yml"

PUBLISH_STEPS = ("Sign RPMs and publish", "Publish signed rpm-md repository")


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def steps() -> list:
    return workflow()["jobs"]["build"]["steps"]


def step(name: str) -> dict:
    return next(s for s in steps() if s.get("name") == name)


# ── A cache must never be able to skip the build ──────────────────────────


@pytest.mark.parametrize(
    "name",
    ["Cache the mock chroot and its dnf downloads", "Cache upstream source tarballs"],
)
def test_cache_steps_cannot_fail_the_job(name):
    """A cache is an optimisation; its failure must cost time, not correctness.

    Without continue-on-error, any error here -- a rejected key, a service
    outage, an exceeded quota -- fails the step, and every later step carrying
    an implicit success() is skipped. `Build tiers` is one of them.
    """
    assert step(name).get("continue-on-error") is True, (
        f"{name!r} can still fail the job, which skips `Build tiers`"
    )


# ── Publishing requires a build that ran and produced output ───────────────


@pytest.mark.parametrize("name", PUBLISH_STEPS)
def test_publish_requires_the_build_step_to_have_run(name):
    """Not 'success' -- 'not skipped'.

    A tier with some failed packages still publishes what built, deliberately:
    that partial publish is what stops hours of built RPMs being thrown away.
    What must not happen is publishing when the build never executed.
    """
    condition = step(name)["if"]
    assert "steps.build.conclusion != 'skipped'" in condition, (
        f"{name!r} can run when `Build tiers` was skipped"
    )
    assert "steps.build.conclusion == 'success'" not in condition, (
        f"{name!r} requires a fully green build, which would discard the "
        "partial publish that exists to protect hours of work"
    )


@pytest.mark.parametrize("name", PUBLISH_STEPS)
def test_publish_refuses_an_empty_result(name):
    """The refuse-to-publish-empty guard, per INCIDENT-repo-wipe-gnome.md.

    Every other R2 writer in this repository adopted this after the GNOME
    wipe. This workflow did not, and republishing an unchanged repository is
    the quiet version of the same failure: nothing is destroyed, but the
    repository reports health it does not have.
    """
    assert "steps.progress.outputs.built_rpms != '0'" in step(name)["if"], (
        f"{name!r} publishes even when the run produced no new RPMs"
    )


def test_the_build_step_is_addressable():
    """The guards above are expressed in terms of `steps.build`."""
    assert step("Build tiers").get("id") == "build"


def test_progress_reports_what_was_built():
    """`built_rpms` is load-bearing for the publish guard, not just a report.

    It is also the number whose absence let a stalled pipeline read as a
    packaging shortfall for four days.
    """
    progress = step("Summarise progress")
    assert progress.get("id") == "progress"
    assert "built_rpms=" in progress["run"], "no built_rpms output is emitted"
    assert "GITHUB_STEP_SUMMARY" in progress["run"], (
        "progress is not surfaced anywhere a human reads"
    )


def test_progress_runs_even_when_the_build_failed():
    """A failed build is exactly when the count matters most."""
    assert "!cancelled()" in step("Summarise progress")["if"]


# ── The run has to be able to start ───────────────────────────────────────


def test_not_triggered_by_push():
    """A push trigger made runs evict each other before they could execute.

    The concurrency group keeps one pending run and cancels the previously
    pending one. Ten consecutive runs between 2026-08-13 18:42 and 2026-08-14
    14:47 were cancelled without executing a step -- which is why the cache-key
    fix that landed inside that window was never exercised.
    """
    triggers = workflow()[True]
    assert "push" not in triggers, (
        "push-triggered runs evict each other out of the concurrency queue"
    )


def test_scheduled_so_it_converges_unattended():
    """The build is incremental: it needs to run repeatedly, not once."""
    triggers = workflow()[True]
    assert "schedule" in triggers, "nothing drives this build on its own"
    assert triggers["schedule"], "the schedule is empty"


def test_publish_still_happens_on_the_scheduled_run():
    """Dropping `push` must not turn every scheduled run into a dry run."""
    for name in PUBLISH_STEPS:
        condition = step(name)["if"]
        assert "github.event_name == 'schedule'" in condition, (
            f"{name!r} no longer publishes on the scheduled run, so the "
            "repository would never converge"
        )
        assert "github.event_name == 'push'" not in condition, (
            f"{name!r} still keys on a push event that can no longer occur"
        )
