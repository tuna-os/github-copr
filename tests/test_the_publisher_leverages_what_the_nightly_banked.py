"""A publish dispatch must not rebuild from zero what the nightly already built.

publish-build-chain-rpms.yml builds its cells in its own run and publishes
same-run. Before this, its build job had NO action-cache restore and NO
partial resume: a chain the nightly had COMPLETED was rebuilt for hours, and
a chain the nightly had DEFERRED restarted at tier 0. Nightly convergence
never transferred to publication -- the two workflows shared a repository and
nothing else.

The bridge is the action key. It only bridges if both workflows compute the
SAME key, which is why the publish planner now carries dependency_tree,
target_queue, track and series: omitting them made the publisher's key hash
empty strings where the nightly hashed real values ("stable"), and the cache
could never hit across the two.
"""

from __future__ import annotations

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUB = ROOT / ".github" / "workflows" / "publish-build-chain-rpms.yml"
CELL = ROOT / ".github" / "workflows" / "package-factory-cell.yml"
PLANNER = ROOT / "scripts" / "plan-build-chain-publish.py"


def build_steps() -> list[dict]:
    return yaml.safe_load(PUB.read_text())["jobs"]["build"]["steps"]


def step(fragment: str) -> dict:
    for s in build_steps():
        if fragment in (s.get("name") or "") or fragment in (s.get("uses") or ""):
            return s
    raise AssertionError(f"publisher build job has no step matching {fragment!r}")


def test_the_publisher_restores_the_action_cache():
    s = step("tideforge-action-cache")
    assert s["with"]["operation"] == "restore"


def test_the_publisher_resumes_partials():
    s = step("Resume from a previous attempt")
    assert "restore-partial-chain-output.py" in s["run"]


def test_a_cache_hit_skips_the_rebuild():
    s = step("Build the cell")
    assert "hit != 'true'" in s.get("if", ""), (
        "a completed chain is rebuilt for hours despite a verified cache hit"
    )


def test_the_keys_can_actually_match():
    """The bridge is only real if both workflows hash the same inputs."""
    pub_identity = step("Resolve immutable inputs")["run"]
    for flag in ("--dependency-tree", "--target-queue", "--track", "--series",
                 "native-key", "--source-date-epoch"):
        assert flag in pub_identity, f"publisher key omits {flag}"
    assert "--format=%at" in pub_identity, (
        "publisher dates with committer time; the nightly uses author time, "
        "so every rebase would split the keys and unbridge the cache"
    )
    planner = PLANNER.read_text()
    for field in ('"dependency_tree"', '"target_queue"', '"track"', '"series"'):
        assert field in planner, (
            f"publish planner drops {field}; the publisher hashes an empty "
            "string where the nightly hashes a real value and never hits"
        )


def test_restored_paths_match_the_nightly_cache_layout():
    """Both sides must cache/restore the same trio, or an Arch-style
    package-info.txt regression recurs on the publish side."""
    pub = step("tideforge-action-cache")["with"]["path"]
    cell_steps = yaml.safe_load(CELL.read_text())["jobs"]["build"]["steps"]
    cell = next(s for s in cell_steps
                if "tideforge-action-cache" in (s.get("uses") or "")
                and (s.get("with") or {}).get("operation") == "restore")
    def names(block: str) -> set[str]:
        return {line.strip().rsplit("/", 1)[-1] for line in block.splitlines() if line.strip()}
    assert names(pub) == names(cell["with"]["path"])
