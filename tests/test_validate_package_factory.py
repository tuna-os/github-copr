"""Tests for the package-factory contract validator.

The gate-coverage check exists because openSUSE was a declared target with zero
cells in the Tideforge gate for months (#139). Nothing failed, because nothing
was looking: "never tested" and "passing" were indistinguishable. These tests
assert the check actually distinguishes them, in both directions.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_package_factory", ROOT / "scripts" / "validate-package-factory.py"
)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


DECLARED = {"el10", "ubuntu", "debian", "opensuse-tumbleweed", "arch"}


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


def test_gate_targets_reads_explicit_matrix_keys(tmp_path: Path) -> None:
    workflow = write(
        tmp_path,
        "gate.yml",
        "jobs:\n  rpm:\n    strategy:\n      matrix:\n        include:\n"
        "          - package: uupd\n            target: el10\n"
        "          - package: dgop\n            target: ubuntu\n",
    )
    assert validator.gate_targets([workflow]) == {"el10", "ubuntu"}


def test_gate_targets_reads_render_target_flags(tmp_path: Path) -> None:
    workflow = write(
        tmp_path,
        "gate.yml",
        "run: python3 scripts/tideforge.py render r --target opensuse-tumbleweed --output o\n",
    )
    assert validator.gate_targets([workflow]) == {"opensuse-tumbleweed"}


def test_gate_targets_ignores_the_matrix_expression(tmp_path: Path) -> None:
    """`--target "${{ matrix.target }}"` names no target by itself.

    Its literal values come from that job's `target:` keys. Capturing the
    expression would add a phantom target called "matrix.target" to the set.
    """
    workflow = write(
        tmp_path,
        "gate.yml",
        'run: python3 scripts/tideforge.py render r --target "${{ matrix.target }}"\n',
    )
    assert validator.gate_targets([workflow]) == set()


def test_gate_targets_skips_missing_files(tmp_path: Path) -> None:
    assert validator.gate_targets([tmp_path / "absent.yml"]) == set()


def test_check_gate_coverage_passes_when_every_target_has_a_cell(tmp_path: Path) -> None:
    workflow = write(
        tmp_path,
        "gate.yml",
        "".join(f"        target: {target}\n" for target in sorted(DECLARED)),
    )
    validator.check_gate_coverage(DECLARED, [workflow])


def test_check_gate_coverage_fails_on_a_target_with_zero_cells(tmp_path: Path) -> None:
    """The exact #139 regression: openSUSE declared, exercised nowhere."""
    workflow = write(
        tmp_path,
        "gate.yml",
        "".join(
            f"        target: {target}\n"
            for target in sorted(DECLARED - {"opensuse-tumbleweed"})
        ),
    )
    with pytest.raises(SystemExit):
        validator.check_gate_coverage(DECLARED, [workflow])


def test_the_real_gate_exercises_every_declared_target() -> None:
    """Guards the live workflows, not a fixture.

    This is the assertion that would have failed before #139 and must keep
    failing if a target is ever added to the manifest without cells.
    """
    workflows = ROOT / ".github" / "workflows"
    validator.check_gate_coverage(
        DECLARED,
        [
            workflows / "build-tideforge-supported.yml",
            workflows / "build-tideforge-arch.yml",
        ],
    )
