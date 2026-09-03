"""Tests for the Tideforge gate-cell planner.

`scripts/plan_gate_matrix.py` decides which of the ~98 gate cells a diff
actually needs to rebuild, replacing the old build-everything-or-nothing
boolean. Its own docstring names the repo's recurring defect as the silent
skip -- a cell that should have run but didn't (#139, #1080) -- so the rules
that fail toward building (unreadable input, shared file touched, downstream
consumer) are the load-bearing part of this module and are what these tests
pin.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "plan_gate_matrix", ROOT / "scripts" / "plan_gate_matrix.py"
)
assert SPEC and SPEC.loader
pgm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pgm)


# --- is_shared_input ---------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "scripts/tideforge.py",
        "mock/el10-x86_64.cfg",
        ".github/workflows/build-tideforge-supported.yml",
        ".github/actions/render/action.yml",
        "manifests/package-factory.yaml",
        "build-order-gnome51.yml",
    ],
)
def test_shared_input_patterns_match(path: str) -> None:
    assert pgm.is_shared_input(path)


def test_a_recipe_file_is_not_a_shared_input() -> None:
    assert not pgm.is_shared_input("packages/niri/package.yaml")


def test_a_bare_build_order_yml_is_not_matched_only_the_dash_variants_are() -> None:
    assert not pgm.is_shared_input("build-order.yml")


# --- changed_packages ----------------------------------------------------


def test_changed_packages_extracts_recipe_directories() -> None:
    changed = [
        "packages/niri/package.yaml",
        "packages/niri/patches/fix.patch",
        "packages/cosmic-comp/package.yaml",
        "docs/README.md",
    ]
    assert pgm.changed_packages(changed) == {"niri", "cosmic-comp"}


def test_changed_packages_strips_whitespace() -> None:
    assert pgm.changed_packages([" packages/niri/package.yaml \n"]) == {"niri"}


# --- job_packages / job_needs --------------------------------------------


def test_job_packages_reads_matrix_include() -> None:
    job = {
        "strategy": {
            "matrix": {"include": [{"package": "niri", "target": "el10"}, {"package": "cosmic-comp"}]}
        }
    }
    assert pgm.job_packages("niri-rpm", job) == {"niri", "cosmic-comp"}


def test_job_packages_falls_back_to_body_scan_for_dedicated_jobs() -> None:
    job = {"steps": [{"run": "tideforge.py render packages/gtkgreet/package.yaml --target el10"}]}
    assert pgm.job_packages("gtkgreet-rpm", job) == {"gtkgreet"}


def test_job_needs_normalizes_string_to_list() -> None:
    assert pgm.job_needs({"needs": "cosmic-icon-theme-rpm"}) == ["cosmic-icon-theme-rpm"]


def test_job_needs_handles_missing_key() -> None:
    assert pgm.job_needs({}) == []


# --- running_jobs: seeded vs downstream closure --------------------------


def test_running_jobs_seeds_only_the_job_owning_the_changed_recipe() -> None:
    workflow = {
        "jobs": {
            "niri-rpm": {"steps": [{"run": "packages/niri/package.yaml"}]},
            "gtkgreet-rpm": {"steps": [{"run": "packages/gtkgreet/package.yaml"}]},
        }
    }
    seeded, downstream = pgm.running_jobs(workflow, {"niri"})
    assert seeded == {"niri-rpm"}
    assert downstream == set()


def test_running_jobs_pulls_in_the_transitive_consumer() -> None:
    """cosmic-comp-rpm needs cosmic-icon-theme-rpm: a changed icon theme must
    rebuild cosmic-comp even though cosmic-comp's own recipe is untouched."""
    workflow = {
        "jobs": {
            "cosmic-icon-theme-rpm": {"steps": [{"run": "packages/cosmic-icon-theme/package.yaml"}]},
            "cosmic-comp-rpm": {
                "needs": "cosmic-icon-theme-rpm",
                "steps": [{"run": "packages/cosmic-comp/package.yaml"}],
            },
            "unrelated-rpm": {"steps": [{"run": "packages/unrelated/package.yaml"}]},
        }
    }
    seeded, downstream = pgm.running_jobs(workflow, {"cosmic-icon-theme"})
    assert seeded == {"cosmic-icon-theme-rpm"}
    assert downstream == {"cosmic-comp-rpm"}


def test_running_jobs_closure_is_multi_hop() -> None:
    workflow = {
        "jobs": {
            "a-rpm": {"steps": [{"run": "packages/a/package.yaml"}]},
            "b-rpm": {"needs": "a-rpm", "steps": [{"run": "packages/b/package.yaml"}]},
            "c-rpm": {"needs": "b-rpm", "steps": [{"run": "packages/c/package.yaml"}]},
        }
    }
    seeded, downstream = pgm.running_jobs(workflow, {"a"})
    assert seeded == {"a-rpm"}
    assert downstream == {"b-rpm", "c-rpm"}


# --- recipe_fingerprint ----------------------------------------------------


def test_recipe_fingerprint_is_none_for_a_missing_package_dir(tmp_path: Path) -> None:
    assert pgm.recipe_fingerprint(tmp_path, "does-not-exist", "el10", "img") is None


def test_recipe_fingerprint_changes_when_a_recipe_file_changes(tmp_path: Path) -> None:
    pkg = tmp_path / "packages" / "niri"
    pkg.mkdir(parents=True)
    (pkg / "package.yaml").write_text("version: 1\n")
    before = pgm.recipe_fingerprint(tmp_path, "niri", "el10", "img")
    (pkg / "package.yaml").write_text("version: 2\n")
    after = pgm.recipe_fingerprint(tmp_path, "niri", "el10", "img")
    assert before != after


def test_recipe_fingerprint_is_stable_for_unchanged_inputs(tmp_path: Path) -> None:
    pkg = tmp_path / "packages" / "niri"
    pkg.mkdir(parents=True)
    (pkg / "package.yaml").write_text("version: 1\n")
    assert pgm.recipe_fingerprint(tmp_path, "niri", "el10", "img") == pgm.recipe_fingerprint(
        tmp_path, "niri", "el10", "img"
    )


def test_recipe_fingerprint_differs_by_target_and_image(tmp_path: Path) -> None:
    pkg = tmp_path / "packages" / "niri"
    pkg.mkdir(parents=True)
    (pkg / "package.yaml").write_text("version: 1\n")
    el10 = pgm.recipe_fingerprint(tmp_path, "niri", "el10", "img")
    ubuntu = pgm.recipe_fingerprint(tmp_path, "niri", "ubuntu", "img")
    other_image = pgm.recipe_fingerprint(tmp_path, "niri", "el10", "other-img")
    assert el10 != ubuntu != other_image


# --- plan(): the fail-toward-building rules -------------------------------


SIMPLE_WORKFLOW = {
    "jobs": {
        "niri-rpm": {
            "strategy": {"matrix": {"include": [{"package": "niri", "target": "el10", "image": "i"}]}}
        },
        "gtkgreet-rpm": {
            "strategy": {"matrix": {"include": [{"package": "gtkgreet", "target": "el10", "image": "i"}]}}
        },
    }
}


def test_plan_with_no_diff_information_builds_everything() -> None:
    result = pgm.plan(SIMPLE_WORKFLOW, changed_files=None)
    assert result["_full"] is True
    assert result["jobs"]["niri-rpm"]["run"] is True
    assert result["jobs"]["gtkgreet-rpm"]["run"] is True


def test_plan_seeds_only_the_job_for_the_changed_recipe() -> None:
    result = pgm.plan(SIMPLE_WORKFLOW, changed_files=["packages/niri/package.yaml"])
    assert result["_full"] is False
    assert result["jobs"]["niri-rpm"]["run"] is True
    assert result["jobs"]["gtkgreet-rpm"]["run"] is False
    assert result["jobs"]["gtkgreet-rpm"]["skipped"]


def test_plan_a_shared_input_change_forces_a_full_build() -> None:
    result = pgm.plan(SIMPLE_WORKFLOW, changed_files=["scripts/tideforge.py"])
    assert result["_full"] is True
    assert result["jobs"]["gtkgreet-rpm"]["run"] is True


def test_plan_skips_a_cell_already_proven_by_fingerprint(tmp_path: Path) -> None:
    pkg = tmp_path / "packages" / "niri"
    pkg.mkdir(parents=True)
    (pkg / "package.yaml").write_text("version: 1\n")
    fp = pgm.recipe_fingerprint(tmp_path, "niri", "el10", "i")
    result = pgm.plan(
        SIMPLE_WORKFLOW,
        changed_files=["packages/niri/package.yaml"],
        root=tmp_path,
        proven={fp},
    )
    assert result["jobs"]["niri-rpm"]["run"] is False
    assert result["jobs"]["niri-rpm"]["skipped"][0]["why"].startswith("already proven")


def test_plan_no_changes_at_all_runs_nothing() -> None:
    result = pgm.plan(SIMPLE_WORKFLOW, changed_files=[])
    assert result["jobs"]["niri-rpm"]["run"] is False
    assert result["jobs"]["gtkgreet-rpm"]["run"] is False
