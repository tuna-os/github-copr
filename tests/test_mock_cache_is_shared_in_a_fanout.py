"""A per-package mock cache cannot hit in a fan-out, and evicts what can.

/var/cache/mock is dnf's download cache plus the chroot root cache. Both are
keyed by the mock config, not by the package -- that is what makes them
shareable at all.

Keying per package came from Tideforge, where about 46 leaf packages are
rebuilt over and over and a package's own cache is exactly what you want. A
fan-out inverts the assumption: each of 1248 packages builds ONCE, so a
per-package key cannot hit inside a run, and every job still writes an entry.
Measured on run 31294475023, a single job wrote

    Sent 372724132 of 372724132 (100.0%), 220.6 MBs/sec

372 MB across 1248 jobs is roughly 465 GB of writes against a 10 GB
per-repository cache limit. It evicts continuously, so restore-keys almost
never hit, and it takes the cs10-image entry down with it -- and that one does
hit ("Cache hit occurred on the primary key cs10-image-...").

Dropping the package from the key gives one entry per run rather than 1248,
and every job after the first restores a warm buildroot. Concurrent jobs
racing to save the same key is fine: the first wins, the rest warn.

The default artifact model keeps the per-package key, because the caller it
was written for genuinely rebuilds the same packages.
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
GENERATOR = REPO / "scripts" / "generate-distributed-workflow.py"
WORKFLOW = REPO / ".github" / "workflows" / "build-hummingbird-distributed.yml"

TIERS = [{"name": "layer-00", "packages": [{"path": "src/hummingbird/a"},
                                           {"path": "src/hummingbird/b"}]},
         {"name": "layer-01", "packages": [{"path": "src/hummingbird/c"}]}]


def generate(tmp_path, *extra):
    src = tmp_path / "order.yml"
    src.write_text(yaml.safe_dump({"r2_path": "hummingbird/x", "tiers": TIERS}))
    out = tmp_path / f"wf{'-'.join(extra)}.yml"
    subprocess.run(
        [sys.executable, str(GENERATOR), str(src), str(out),
         "--mock-config", "hummingbird-ci", "--r2-path", "hummingbird/x",
         "--secondary-r2-path", "", "--no-submodules", *extra],
        check=True, capture_output=True, cwd=REPO,
    )
    return yaml.safe_load(out.read_text())


def cache_step(job):
    return [s for s in job["steps"] if s.get("name", "").startswith("Cache mock")][0]


def build_jobs(wf):
    return {n: j for n, j in wf["jobs"].items() if n.startswith("build-")}


def test_the_fanout_shares_one_cache_across_every_package(tmp_path):
    wf = generate(tmp_path, "--r2-state")
    configs = {yaml.safe_dump(cache_step(j)["with"], sort_keys=True)
               for j in build_jobs(wf).values()}
    assert len(configs) == 1, (
        f"{len(configs)} distinct cache configurations; a fan-out builds each "
        "package once, so a per-package key writes an entry that can never be "
        "read back"
    )


def test_the_fanout_key_does_not_mention_the_package(tmp_path):
    wf = generate(tmp_path, "--r2-state")
    for name, job in build_jobs(wf).items():
        key = cache_step(job)["with"]["key"]
        assert "matrix.package" not in key, f"{name} still keys its cache per package: {key}"


def test_the_fanout_still_falls_back_to_an_earlier_run(tmp_path):
    """Without a restore-key the first job of every run starts cold."""
    wf = generate(tmp_path, "--r2-state")
    step = cache_step(build_jobs(wf)["build-layer-00"])
    assert step["with"]["restore-keys"].strip(), "no restore-keys; every run starts cold"
    assert "github.run_id" not in step["with"]["restore-keys"], (
        "the restore-key is pinned to this run, so it can only ever match "
        "entries this run wrote"
    )
    assert "github.run_id" in step["with"]["key"], (
        "without the run id in the primary key, a run cannot refresh the entry"
    )


def test_the_committed_workflow_shares_its_cache():
    wf = yaml.safe_load(WORKFLOW.read_text())
    keys = {cache_step(j)["with"]["key"] for j in build_jobs(wf).values()}
    assert len(keys) == 1, f"the committed workflow has {len(keys)} distinct cache keys"
    assert "matrix.package" not in keys.pop()


def test_the_artifact_model_keeps_its_per_package_cache(tmp_path):
    """The other caller rebuilds the same packages; per-package is right there."""
    wf = generate(tmp_path)
    step = cache_step(build_jobs(wf)["build-layer-00"])
    assert "matrix.package" in step["with"]["key"], (
        "the default path lost its per-package cache; that caller genuinely "
        "rebuilds the same packages and benefits from it"
    )
