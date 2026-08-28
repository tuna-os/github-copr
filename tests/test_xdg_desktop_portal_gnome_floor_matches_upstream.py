"""xdg-desktop-portal-gnome's floor on xdg-desktop-portal must not go stale again.

xdg-desktop-portal-gnome's own src/meson.build -- the exact tag this spec
builds -- declares dependency('xdg-desktop-portal', version: '>= 1.21.1')
(fetched from gitlab.gnome.org/GNOME/xdg-desktop-portal-gnome at tag
51.alpha). xdg-desktop-portal-gnome.spec's own BuildRequires floor
(%global xdg_desktop_portal_version) was stale at 1.19.1, so dnf5 builddep
happily satisfied it with the xdg-desktop-portal package this chain had
already built at 1.21.0 -- one patch release short. rpmbuild never checks
that floor against what meson itself demands, so the build got all the way
to %build before meson's own version check failed it:

    src/meson.build:4:25: ERROR: Dependency lookup for xdg-desktop-portal
    with method 'pkg-config' failed: Invalid version, need
    'xdg-desktop-portal' ['>= 1.21.1'] found '1.21.0'.

Fixed by bumping BOTH: xdg-desktop-portal.spec's own Version to 1.21.1 (a
real released tag -- github.com/flatpak/xdg-desktop-portal/releases/tag/1.21.1
-- not an arbitrary bump), and xdg-desktop-portal-gnome.spec's floor to match.
Verified by a real rebuild of each, in that order (the newer xdg-desktop-portal
has to actually land in the local repo before xdg-desktop-portal-gnome's
builddep can resolve it).
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
PORTAL_SPEC = ROOT / "src/gnome-51/xdg-desktop-portal/xdg-desktop-portal.spec"
PORTAL_GNOME_SPEC = ROOT / "src/gnome-51/xdg-desktop-portal-gnome/xdg-desktop-portal-gnome.spec"


def _version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def _spec_version(spec: pathlib.Path) -> tuple[int, ...]:
    text = spec.read_text(encoding="utf-8")
    match = re.search(r"^Version:\s*([0-9.]+)", text, re.MULTILINE)
    assert match, f"no Version: in {spec}"
    return _version_tuple(match.group(1))


def _global_version(spec: pathlib.Path, name: str) -> tuple[int, ...]:
    text = spec.read_text(encoding="utf-8")
    match = re.search(rf"^%global {re.escape(name)}\s+([0-9.]+)", text, re.MULTILINE)
    assert match, f"no %global {name} in {spec}"
    return _version_tuple(match.group(1))


def test_xdg_desktop_portal_gnome_declares_the_real_floor():
    assert _global_version(PORTAL_GNOME_SPEC, "xdg_desktop_portal_version") >= (1, 21, 1), (
        "xdg-desktop-portal-gnome 51.alpha's own src/meson.build requires "
        "xdg-desktop-portal >= 1.21.1 -- a lower floor here is satisfiable by "
        "an older xdg-desktop-portal build, and meson's own version check "
        "fails %build instead of dnf5 builddep catching it early"
    )


def test_xdg_desktop_portal_itself_meets_that_floor():
    assert _spec_version(PORTAL_SPEC) >= (1, 21, 1), (
        "xdg-desktop-portal.spec must actually build a release that "
        "satisfies xdg-desktop-portal-gnome's real floor -- 1.21.0 is one "
        "patch release short of the 1.21.1 that upstream requires"
    )


def test_the_previously_stale_floor_is_gone():
    """The exact value that caused the meson version-check failure must not
    come back."""
    text = PORTAL_GNOME_SPEC.read_text(encoding="utf-8")
    assert "%global xdg_desktop_portal_version 1.19.1" not in text, (
        "xdg-desktop-portal-gnome.spec regressed to the stale "
        "xdg_desktop_portal_version=1.19.1 that let dnf5 builddep satisfy "
        "the BuildRequires with an xdg-desktop-portal too old for meson's "
        "own version check"
    )
