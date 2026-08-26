"""A rebuilt fix must not ship under the NVR of the thing it replaces.

libunwind-devel's aarch64 build was broken: its libunwind.so.8 carried four
undefined `__aarch64_*` symbols and no libgcc_s in NEEDED, so every consumer
died at load (#469). The recipe fix — `LIBS: -lgcc_s` — changes the bytes and
nothing else.

The broken build is published as **libunwind-devel-1.8.1-1.el10** at
rpm/el10/aarch64. Republishing the fix at release 1 would have put a second,
different artifact into the world under an identical name-version-release:
dnf would report no upgrade, anyone already holding the broken one would keep
it, and the repository would contain two builds claiming to be the same thing.

That is why the wave was not dispatched before this bump. The publisher was
ready and the fix was merged; the version was the blocker, and publishing
would have looked successful while changing nothing for consumers.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "packages" / "libunwind-devel" / "package.yaml"

# What rpm/el10/aarch64 served on 2026-08-22, measured from its primary.xml.
PUBLISHED_BROKEN_RELEASE = 1


def recipe() -> dict:
    return yaml.safe_load(RECIPE.read_text(encoding="utf-8"))


def test_the_release_moved_past_the_broken_publish():
    assert int(recipe()["release"]) > PUBLISHED_BROKEN_RELEASE


def test_the_version_did_not_change():
    """A release bump, not a version bump: the sources are identical, only the
    link line changed. Moving the version would misreport what was fixed."""
    assert str(recipe()["version"]) == "1.8.1"


def test_the_fix_the_bump_exists_for_is_still_there():
    """A bumped release carrying the unfixed build would be worse than no bump
    at all — it would advertise a fix that is not present."""
    assert recipe()["build"]["environment"]["LIBS"] == "-lgcc_s"


def test_the_aarch64_prefix_has_an_anti_wipe_floor():
    """rpm/el10/aarch64 serves 39 packages. The publisher's sync-down ends in
    `|| true`, so without a floor a failed download syncs up only the new
    packages and deletes the rest (#124)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "plan_rpm_publish", ROOT / "scripts" / "plan-rpm-publish.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    aarch64 = module.BESPOKE["el10"]["aarch64"]
    assert aarch64.get("min_rpms", 0) > 0, "a populated prefix must have a floor"
    assert aarch64["min_rpms"] < 39, "a floor at or above the current count blocks every publish"


def test_every_populated_bespoke_prefix_has_a_floor():
    """The general rule, so the next prefix to gain content is not left open."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "plan_rpm_publish", ROOT / "scripts" / "plan-rpm-publish.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for target, arches in module.BESPOKE.items():
        for arch, override in arches.items():
            assert "min_rpms" in override, (
                f"{target}/{arch} has a bespoke prefix but no min_rpms — state the "
                f"floor explicitly, even if 0 for a genuinely empty prefix"
            )
