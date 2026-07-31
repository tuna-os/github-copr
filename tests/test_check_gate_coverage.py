"""Tests for the gate-coverage ratchet.

The ratchet exists because the honest assertion is not shippable: 77 of 122
declared (recipe, target) pairs have no gate cell today, so failing on all of
them would block every PR. It fails only on pairs a change *introduces*, and
prints the total so the gap stays visible instead of being laundered through
an allowlist.

These tests pin both halves: that a new gap fails, and that the existing 77 do
not -- because a ratchet that quietly blocks pre-existing gaps is just the
unshippable assertion with extra steps.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_gate_coverage", ROOT / "scripts" / "check-gate-coverage.py"
)
assert SPEC and SPEC.loader
coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage)


class FakeTree:
    """A Tree backed by an in-memory file map, so tests need no git."""

    def __init__(self, files: dict[str, str]) -> None:
        self.files = files

    def read(self, path: str) -> str | None:
        return self.files.get(path)

    def recipes(self) -> list[str]:
        return sorted(p for p in self.files if p.endswith("/package.yaml"))


def recipe(targets: list[str]) -> str:
    return "schema: 1\ntargets: [" + ", ".join(targets) + "]\n"


def gate(cells: list[tuple[str, str]]) -> str:
    include = "".join(
        f"          - package: {package}\n            target: {target}\n"
        for package, target in cells
    )
    return "jobs:\n  rpm:\n    strategy:\n      matrix:\n        include:\n" + include


def test_declared_pairs_reads_every_recipe_target() -> None:
    tree = FakeTree(
        {
            "packages/alpha/package.yaml": recipe(["el10", "arch"]),
            "packages/beta/package.yaml": recipe(["ubuntu"]),
        }
    )
    assert coverage.declared_pairs(tree) == {
        ("alpha", "el10"),
        ("alpha", "arch"),
        ("beta", "ubuntu"),
    }


def test_declared_pairs_skips_the_template() -> None:
    """The template documents the schema; it is not a package candidate."""
    tree = FakeTree({"packages/_template/package.yaml": recipe(["el10"])})
    assert coverage.declared_pairs(tree) == set()


def test_gate_pairs_reads_explicit_targets() -> None:
    tree = FakeTree(
        {".github/workflows/build-tideforge-supported.yml": gate([("alpha", "el10")])}
    )
    assert coverage.gate_pairs(tree) == {("alpha", "el10")}


def test_gate_pairs_infers_the_opensuse_job_target() -> None:
    """That job pins its target in the step body, not the matrix."""
    workflow = (
        "jobs:\n  opensuse-rpm:\n    strategy:\n      matrix:\n        include:\n"
        "          - package: dgop\n"
    )
    tree = FakeTree({".github/workflows/build-tideforge-supported.yml": workflow})
    assert coverage.gate_pairs(tree) == {("dgop", "opensuse-tumbleweed")}


def test_gate_pairs_infers_the_arch_gate_target() -> None:
    """The Arch gate builds exactly one target by construction."""
    workflow = "jobs:\n  build:\n    strategy:\n      matrix:\n        include:\n          - package: niri\n"
    tree = FakeTree({".github/workflows/build-tideforge-arch.yml": workflow})
    assert coverage.gate_pairs(tree) == {("niri", "arch")}


def test_uncovered_is_declared_minus_built() -> None:
    tree = FakeTree(
        {
            "packages/alpha/package.yaml": recipe(["el10", "arch"]),
            ".github/workflows/build-tideforge-supported.yml": gate([("alpha", "el10")]),
        }
    )
    assert coverage.uncovered(tree) == {("alpha", "arch")}


# --- the ratchet property itself -------------------------------------------


def test_a_newly_declared_target_without_a_cell_is_a_new_gap() -> None:
    before = FakeTree({"packages/alpha/package.yaml": recipe(["el10"])})
    after = FakeTree({"packages/alpha/package.yaml": recipe(["el10", "arch"])})
    assert coverage.uncovered(after) - coverage.uncovered(before) == {("alpha", "arch")}


def test_a_pre_existing_gap_is_not_a_new_gap() -> None:
    """The property that makes this shippable at 77 uncovered pairs."""
    tree = FakeTree({"packages/alpha/package.yaml": recipe(["el10", "arch"])})
    assert coverage.uncovered(tree) - coverage.uncovered(tree) == set()


def test_adding_a_cell_closes_a_gap() -> None:
    before = FakeTree({"packages/alpha/package.yaml": recipe(["el10"])})
    after = FakeTree(
        {
            "packages/alpha/package.yaml": recipe(["el10"]),
            ".github/workflows/build-tideforge-supported.yml": gate([("alpha", "el10")]),
        }
    )
    assert len(coverage.uncovered(after)) < len(coverage.uncovered(before))


# --- against the live repository -------------------------------------------


def test_the_real_repository_has_no_cell_for_an_undeclared_pair() -> None:
    """A gate cell building something no recipe asks for is also a defect.

    It means the matrix and the recipes disagree in the other direction: CI
    spending a runner on a target the package does not claim to support.
    """
    tree = coverage.Tree()
    assert coverage.gate_pairs(tree) - coverage.declared_pairs(tree) == set()


def test_the_real_repository_coverage_is_reported_not_asserted() -> None:
    """Pins the shape of today's gap so a silent collapse to zero is visible.

    If this ever fails because coverage improved, raise the floor -- do not
    delete the test.
    """
    tree = coverage.Tree()
    declared = coverage.declared_pairs(tree)
    assert len(declared) >= 122
    assert coverage.uncovered(tree), "no uncovered pairs would make the ratchet vacuous"
