"""Tiering once over every desktop makes tiers far wider than the cap allows.

The per-desktop orders never produced a tier bigger than 108. One order over
all five desktops produces layer-15 at 251 packages, and GitHub generates at
most 256 jobs from a matrix -- five packages of headroom before the workflow
stops scheduling at all.

A tier's packages have no edges between them; that is what being in one tier
means. So an oversized tier is split into sibling matrix jobs that share one
`needs` and feed one consolidate barrier. It costs no extra round.
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
GENERATOR = REPO / "scripts" / "generate-distributed-workflow.py"
WORKFLOW = REPO / ".github" / "workflows" / "build-hummingbird-distributed.yml"
GITHUB_MATRIX_CAP = 256


def generate(tmp_path, tiers):
    src = tmp_path / "order.yml"
    src.write_text(yaml.safe_dump({"r2_path": "hummingbird/x", "tiers": tiers}))
    out = tmp_path / "wf.yml"
    subprocess.run(
        [sys.executable, str(GENERATOR), str(src), str(out),
         "--mock-config", "hummingbird-ci", "--r2-path", "hummingbird/x",
         "--secondary-r2-path", "", "--no-submodules", "--r2-state"],
        check=True, capture_output=True, cwd=REPO,
    )
    return yaml.safe_load(out.read_text())


def tier_of(n, size):
    return {"name": n, "packages": [{"path": f"src/hummingbird/p{i}"} for i in range(size)]}


@pytest.fixture(scope="module")
def committed():
    return yaml.safe_load(WORKFLOW.read_text())


def matrices(wf):
    return {n: j["strategy"]["matrix"]["package"]
            for n, j in wf["jobs"].items() if n.startswith("build-")}


def test_no_matrix_in_the_committed_workflow_can_exceed_the_cap(committed):
    over = {n: len(p) for n, p in matrices(committed).items() if len(p) >= GITHUB_MATRIX_CAP}
    assert not over, (
        f"{over} would not schedule: GitHub generates at most "
        f"{GITHUB_MATRIX_CAP} jobs from one matrix"
    )


def test_a_tier_under_the_limit_stays_one_job(tmp_path):
    wf = generate(tmp_path, [tier_of("layer-00", 10)])
    assert sorted(matrices(wf)) == ["build-layer-00"]
    assert wf["jobs"]["consolidate-layer-00"]["needs"] == "build-layer-00"


def test_an_oversized_tier_splits_into_siblings_of_one_barrier(tmp_path):
    wf = generate(tmp_path, [tier_of("layer-00", 5), tier_of("layer-01", 260)])
    split = sorted(n for n in matrices(wf) if n.startswith("build-layer-01"))
    assert split == ["build-layer-01-00", "build-layer-01-01"]

    # siblings, not a longer chain: same predecessor, one shared barrier
    assert {wf["jobs"][n]["needs"] for n in split} == {"consolidate-layer-00"}
    assert sorted(wf["jobs"]["consolidate-layer-01"]["needs"]) == split

    # and the next tier still waits on that one barrier
    assert wf["jobs"]["consolidate-layer-01"]["needs"] != []


def test_splitting_loses_no_package(tmp_path):
    wf = generate(tmp_path, [tier_of("layer-00", 260)])
    cells = [p for n, m in matrices(wf).items() if n.startswith("build-layer-00") for p in m]
    assert len(cells) == 260
    assert len(set(cells)) == 260


def test_split_chunks_do_not_collide_on_artifact_names(tmp_path):
    """Both chunks index their matrix from zero, so without the chunk number
    every chunk would upload rpms-<tier>-0 and race."""
    wf = generate(tmp_path, [tier_of("layer-00", 260)])
    uploads = []
    for name, job in wf["jobs"].items():
        if not name.startswith("build-layer-00"):
            continue
        step = [s for s in job["steps"] if "upload-artifact" in str(s.get("uses", ""))][0]
        uploads.append(step["with"]["name"])
    assert len(set(uploads)) == len(uploads), f"artifact names collide: {uploads}"

    pattern = [s for s in wf["jobs"]["consolidate-layer-00"]["steps"]
               if "download-artifact" in str(s.get("uses", ""))][0]["with"]["pattern"]
    for name in uploads:
        prefix = pattern.rstrip("*")
        assert name.startswith(prefix), (
            f"consolidate collects {pattern!r} but a chunk uploads {name!r}"
        )
