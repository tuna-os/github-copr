"""One failing package used to throw away the entire run.

A tier's matrix job fails if any of its packages failed -- fail-fast: false
keeps the siblings running, but the job's own conclusion is still failure.
`needs` treats that as a stop sign, so the consolidate was skipped, so the next
tier was skipped, and so on to the end: every remaining tier and the publish.

Rebuilding 1248 Rawhide packages will always turn up some that do not build.
One is already known before the first dispatch: SwayNotificationCenter
BuildRequires pkgconfig(granite-7) and Rawhide ships Granite 6, providing only
pkgconfig(granite) and libgranite.so.6. Under the old graph that single package
would have stopped 35 layers and published nothing.

So the barrier publishes what did build and the chain carries on. Packages
downstream of a failure fail on their own missing dependency, which is the
report you want -- every failure in one pass, rather than one per re-dispatch.
The run still ends red, because a run's conclusion is failure if any job
failed, whatever the jobs after it do.

The one predecessor whose failure must still stop everything is seed-repo:
without the seeded repository there is nothing to build against.
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
GENERATOR = REPO / "scripts" / "generate-distributed-workflow.py"
WORKFLOW = REPO / ".github" / "workflows" / "build-hummingbird-distributed.yml"
RUNS_ANYWAY = "${{ !cancelled() }}"


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(WORKFLOW.read_text())


def test_every_consolidate_runs_even_when_the_tier_had_failures(workflow):
    ungated = [n for n, j in workflow["jobs"].items()
               if n.startswith("consolidate-") and j.get("if") != RUNS_ANYWAY]
    assert not ungated, (
        f"{len(ungated)} consolidate jobs stop the chain on a single failed "
        f"package: {ungated[:5]}"
    )


def test_every_tier_after_the_first_starts_even_if_the_last_one_had_failures(workflow):
    ungated = [n for n, j in workflow["jobs"].items()
               if n.startswith("build-")
               and j["needs"] != "seed-repo"
               and j.get("if") != RUNS_ANYWAY]
    assert not ungated, f"these tiers are skipped after any earlier failure: {ungated[:5]}"


def test_publish_still_signs_what_the_run_did_build(workflow):
    assert workflow["jobs"]["publish"].get("if") == RUNS_ANYWAY


def test_a_failed_seed_still_stops_everything(workflow):
    """There is nothing to build against, so carrying on would be noise."""
    seeded = [n for n, j in workflow["jobs"].items()
              if j.get("needs") == "seed-repo"]
    assert seeded, "no job depends on seed-repo"
    for name in seeded:
        assert "if" not in workflow["jobs"][name], (
            f"{name} would run even when the repository failed to seed"
        )
    assert "if" not in workflow["jobs"]["seed-repo"]


def test_the_chain_is_unbroken_from_seed_to_publish(workflow):
    """A guard that let a job run is useless if the graph no longer connects."""
    jobs = workflow["jobs"]
    seen, node = [], "publish"
    while True:
        seen.append(node)
        if node == "seed-repo":
            break
        needs = jobs[node].get("needs")
        needs = [needs] if isinstance(needs, str) else needs
        assert needs, f"{node} has no predecessor and is not seed-repo"
        node = needs[0]
        assert len(seen) < len(jobs) + 2, "cycle in the job graph"
    assert seen[-1] == "seed-repo"
    # seed -> 40 tiers x (build, consolidate) -> publish, following one edge each
    assert len(seen) >= 40, f"chain is only {len(seen)} long: {seen}"


def test_guards_survive_regeneration(tmp_path):
    src = tmp_path / "order.yml"
    src.write_text(yaml.safe_dump({"r2_path": "hummingbird/x", "tiers": [
        {"name": "layer-00", "packages": [{"path": "src/hummingbird/a"}]},
        {"name": "layer-01", "packages": [{"path": "src/hummingbird/b"}]},
    ]}))
    out = tmp_path / "wf.yml"
    subprocess.run(
        [sys.executable, str(GENERATOR), str(src), str(out),
         "--mock-config", "hummingbird-ci", "--r2-path", "hummingbird/x",
         "--secondary-r2-path", "", "--no-submodules", "--r2-state"],
        check=True, capture_output=True, cwd=REPO,
    )
    wf = yaml.safe_load(out.read_text())
    assert wf["jobs"]["consolidate-layer-00"]["if"] == RUNS_ANYWAY
    assert wf["jobs"]["build-layer-01"]["if"] == RUNS_ANYWAY
    assert "if" not in wf["jobs"]["build-layer-00"]
