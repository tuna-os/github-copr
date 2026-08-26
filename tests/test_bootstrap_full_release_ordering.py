"""A full build must outrank the bootstrap build it replaces.

glib2 and gobject-introspection are each built TWICE in a GNOME build
order: once from a `-bootstrap.spec` (no introspection, a stub -devel)
to break the glib<->g-i cycle, then again from the real spec once the
bootstrap g-i exists. Tier order alone does not make the second build
happen: build-chain.sh skips any package whose exact NVR it has already
produced, so if the full spec carries the SAME version-release as the
bootstrap spec, the full build is silently skipped and the bootstrap's
stub stays in the local repo.

That is not hypothetical. The GNOME 51.beta bump reset both glib2 specs
to 2.89.4-1. Tier 7 (glib2-full) was skipped, the 6.7KB bootstrap
glib2-devel -- which ships no gir files -- remained, and every package
that generates introspection data died on

    Couldn't find include 'GObject-2.0.gir'

25 packages failed: the whole src/deps introspection layer and every
GNOME 51 module downstream of it. Nothing in the run said "skipped";
the chain reported a green tier 7 by doing nothing at all.

The other tracks encode the rule by accident (gnome-49 glib2 is 1 then
2, gnome-50 is 1 then 4). This makes it a property instead.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "rpm_vercmp", ROOT / "scripts" / "rpm_vercmp.py")
vercmp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vercmp)

# rpmautospec computes this at build time and it is always ahead of a
# hand-written integer release, so a pair that differs this way cannot
# collide. Compared literally it would look "equal", which it is not.
AUTORELEASE = "%autorelease"


def evr_of(spec: Path) -> tuple[str, str]:
    text = spec.read_text(encoding="utf-8")
    version = re.search(r"^Version:\s*(\S+)", text, re.M)
    release = re.search(r"^Release:\s*(\S+)", text, re.M)
    assert version and release, f"{spec} has no Version/Release"
    return version.group(1), release.group(1).replace("%{?dist}", "")


def bootstrap_pairs() -> list[tuple[Path, Path, Path]]:
    """(build order, bootstrap spec, full spec) for every doubly-built package."""
    pairs = []
    for order_path in sorted(ROOT.glob("build-order*.yml")):
        order = yaml.safe_load(order_path.read_text(encoding="utf-8")) or {}
        by_path: dict[str, list[dict]] = {}
        for tier in order.get("tiers") or []:
            for pkg in tier.get("packages") or []:
                if "path" in pkg:
                    by_path.setdefault(pkg["path"], []).append(pkg)
        for pkg_path, entries in by_path.items():
            overrides = [e for e in entries if e.get("spec_override")]
            plain = [e for e in entries if not e.get("spec_override")]
            if not overrides or not plain:
                continue
            directory = ROOT / pkg_path
            for override in overrides:
                boot = directory / override["spec_override"]
                full = directory / f"{directory.name}.spec"
                if boot.is_file() and full.is_file():
                    pairs.append((order_path, boot, full))
    return pairs


def test_the_pairs_are_actually_found() -> None:
    """A discovery bug would make every assertion below vacuous."""
    pairs = bootstrap_pairs()
    assert pairs, "no bootstrap/full pairs discovered -- the check is asleep"
    assert any("glib2" in str(full) for _, _, full in pairs)


@pytest.mark.parametrize(
    "order,boot,full",
    bootstrap_pairs(),
    ids=lambda value: value.name if isinstance(value, Path) else str(value),
)
def test_the_full_build_outranks_its_bootstrap(
        order: Path, boot: Path, full: Path) -> None:
    boot_evr, full_evr = evr_of(boot), evr_of(full)
    assert boot_evr[0] == full_evr[0], (
        f"{boot.name} and {full.name} build different versions "
        f"({boot_evr[0]} vs {full_evr[0]}); the full build cannot replace the "
        "bootstrap it is supposed to supersede"
    )
    if full_evr[1] == AUTORELEASE:
        return
    boot_full = f"{boot_evr[0]}-{boot_evr[1]}"
    full_full = f"{full_evr[0]}-{full_evr[1]}"
    assert vercmp.compare_evr(full_full, boot_full) > 0, (
        f"{full.relative_to(ROOT)} is {full_full}, not newer than "
        f"{boot.relative_to(ROOT)} at {boot_full}. build-chain.sh skips a "
        "package whose exact NVR already exists, so the full build will be "
        "SKIPPED and the bootstrap's stub -devel (no gir files) will stay in "
        "the buildroot -- every introspection-generating package downstream "
        "then fails on a missing GObject-2.0.gir."
    )
