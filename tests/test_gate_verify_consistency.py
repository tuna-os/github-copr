"""Cross-check the gate's hand-written verification against the recipes.

Every gate cell today carries `smoke` and `install_name` as matrix keys. The
recipes now carry the same values in a `verify:` block. Until the gate is
switched over to read them, the two must agree exactly -- otherwise the
switchover would silently change what is asserted, which is the failure mode
this whole line of work exists to prevent (#139).

These tests are what make the switchover a pure deletion: when the matrix keys
go away, this file proves nothing was lost in the move.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tideforge", ROOT / "scripts" / "tideforge.py")
assert SPEC and SPEC.loader
tideforge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tideforge)

GATES = [
    ROOT / ".github" / "workflows" / "build-tideforge-supported.yml",
    ROOT / ".github" / "workflows" / "build-tideforge-arch.yml",
]


def gate_cells() -> list[dict]:
    """Every matrix cell that asserts something, with the target it asserts on."""
    cells = []
    for gate in GATES:
        workflow = yaml.safe_load(gate.read_text())
        for job_name, job in workflow["jobs"].items():
            for cell in job.get("strategy", {}).get("matrix", {}).get("include", []):
                if "smoke" not in cell and "install_name" not in cell:
                    continue
                # The Arch gate has one target by construction; the openSUSE job
                # pins its target in the step body rather than the matrix.
                target = cell.get("target")
                if target is None:
                    target = "opensuse-tumbleweed" if "opensuse" in job_name else "arch"
                cells.append({**cell, "target": target, "job": job_name})
    return cells


def recipe_for(package: str) -> dict:
    return yaml.safe_load((ROOT / "packages" / package / "package.yaml").read_text())


CELLS = gate_cells()


def test_the_gate_actually_has_cells() -> None:
    """A zero-length cell list would make every test below vacuously pass."""
    assert len(CELLS) >= 39


@pytest.mark.parametrize("cell", CELLS, ids=lambda c: f"{c['package']}-{c['target']}")
def test_every_gate_cell_matches_its_recipe(cell: dict) -> None:
    recipe = recipe_for(cell["package"])
    resolved = tideforge.verify_metadata(recipe, cell["target"])

    if "smoke" in cell:
        assert resolved["smoke"] == cell["smoke"], (
            f"{cell['package']} ({cell['target']}): recipe verify.smoke differs from "
            "the gate cell. Switching the gate over would change what is asserted."
        )
    if "install_name" in cell:
        assert resolved["install_name"] == cell["install_name"], (
            f"{cell['package']} ({cell['target']}): recipe verify.install_name differs "
            "from the gate cell."
        )


@pytest.mark.parametrize("cell", CELLS, ids=lambda c: f"{c['package']}-{c['target']}")
def test_every_gate_cell_has_a_recipe_verify_block(cell: dict) -> None:
    recipe = recipe_for(cell["package"])
    assert recipe.get("verify"), (
        f"{cell['package']} is exercised by the gate but its recipe has no verify: "
        "block, so the cell could not be derived from the recipe."
    )


def test_xfconf_keeps_its_per_target_install_name() -> None:
    """The one genuine divergence, asserted by name so it cannot be flattened.

    xfconf renders as `xfconf` on el10 and `libxfconf-0-4` on the deb targets.
    A refactor that collapsed install_name to a single value would still pass
    every other test here, because xfconf is the only package that differs.
    """
    recipe = recipe_for("xfconf")
    assert tideforge.verify_metadata(recipe, "el10")["install_name"] == "xfconf"
    assert tideforge.verify_metadata(recipe, "ubuntu")["install_name"] == "libxfconf-0-4"
    assert tideforge.verify_metadata(recipe, "debian")["install_name"] == "libxfconf-0-4"


def test_install_name_defaults_to_the_recipe_name() -> None:
    assert tideforge.verify_metadata({"name": "dgop", "verify": {"smoke": "x"}}, "el10")[
        "install_name"
    ] == "dgop"


def test_validate_rejects_a_mistyped_verify_block() -> None:
    """A silently-ignored typo is the same defect class as a missing cell."""
    recipe = {"name": "x", "targets": ["el10"], "verify": {"smoke": "y", "smoek": "z"}}
    with pytest.raises(SystemExit):
        tideforge.validate_verify(recipe)


def test_validate_rejects_an_override_for_an_unenabled_target() -> None:
    recipe = {
        "name": "x",
        "targets": ["el10"],
        "verify": {"smoke": "y", "targets": {"ubuntu": {"install_name": "z"}}},
    }
    with pytest.raises(SystemExit):
        tideforge.validate_verify(recipe)


def test_validate_rejects_an_empty_smoke() -> None:
    with pytest.raises(SystemExit):
        tideforge.validate_verify({"name": "x", "targets": ["el10"], "verify": {"smoke": "  "}})


# --- packages the gate builds outside a matrix include ----------------------


DEDICATED_JOB_PACKAGES = {
    "niri",
    "quickshell",
    "gtkgreet",
    "cpptrace-devel",
    "iio-niri",
    "dms",
    "dms-cli",
    "dms-greeter",
}


def _coverage_module():
    spec = importlib.util.spec_from_file_location(
        "check_gate_coverage", ROOT / "scripts" / "check-gate-coverage.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_package_the_gate_builds_has_a_verify_block() -> None:
    """Not just the matrix-include cells.

    The tests above walk `include:` cells only, which is how seven packages
    built by dedicated jobs -- quickshell, gtkgreet, cpptrace-devel, iio-niri
    and the dms stack -- ended up with no verify block at all while this file
    claimed the gate was fully cross-checked. Assert against real coverage
    instead of against one job shape.
    """
    coverage = _coverage_module()
    # rpm-payload builds its cells without installing them -- there is no clean
    # container and no smoke test to run, so those packages correctly have no
    # verify block. Assert against packages the gate *installs*.
    payload_only = {
        package
        for package, _ in coverage.gate_pairs(coverage.Tree())
        if package not in {cell["package"] for cell in CELLS}
        and package not in DEDICATED_JOB_PACKAGES
    }
    installed = {
        package for package, _ in coverage.gate_pairs(coverage.Tree())
    } - payload_only
    missing = sorted(
        package
        for package in installed
        if not (yaml.safe_load((ROOT / "packages" / package / "package.yaml").read_text()) or {}).get("verify")
    )
    assert not missing, f"gate-installed packages with no verify: block: {missing}"


def test_niri_carries_its_full_session_contract() -> None:
    """niri --help alone would pass with every session file missing.

    The el10 job asserts the compositor binary *and* the five session
    integration assets. A weaker recipe-side contract would silently drop them
    when the gate switches over -- and a niri that no display manager can
    discover is the flounder:niri failure repeating.
    """
    smoke = tideforge.verify_metadata(recipe_for("niri"), "el10")["smoke"]
    for asset in (
        "/usr/bin/niri-session",
        "/usr/share/wayland-sessions/niri.desktop",
        "/usr/share/xdg-desktop-portal/niri-portals.conf",
        "/usr/lib/systemd/user/niri.service",
        "/usr/lib/systemd/user/niri-shutdown.target",
    ):
        assert asset in smoke, f"niri verify.smoke does not assert {asset}"
