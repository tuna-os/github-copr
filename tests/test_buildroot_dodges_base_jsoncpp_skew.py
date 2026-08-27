"""Two buildroot repo-set fixes, both found by the resolution simulator in
one pass, hours before a build would have found the first of them.

JSONCPP SKEW. The base compose bumped jsoncpp to libjsoncpp.so.27 while
every cmake it ships still requires libjsoncpp.so.26 -- rebuild-in-flight
skew, appearing between ~17:00Z and ~23:25Z on 2026-08-26. cmake thereby
became uninstallable, taking 211 of 673 build-order packages with it.
Rawhide has NOT bumped: its jsoncpp/.so.26 + cmake pair is coherent. The
dodge is to exclude jsoncpp* from BOTH the base (so Rawhide's provider
survives name-masking) and our own repo (whose jsoncpp is also .so.27 at
priority 11 and would otherwise reinstate the block). Only jsoncpp-devel
requires .so.27 in either repo, and it leaves with its provider.

MINGW SPLIT-BRAIN. #551's '+'-glob excluded mingw{32,64}-gcc-c++ from our
repo but left the rest of our mingw toolchain visible. dnf priorities then
split the toolchain: our mingw32-gcc (priority 11) masks Rawhide's, while
Rawhide's mingw32-gcc-c++ -- the only c++ compiler left -- requires
mingw32-gcc = 16.1.1-3.fc45 EXACTLY and resolves our fc43 build instead.
abseil-cpp and inih fail again, one leg after #551 fixed their previous
failure. Excluding the whole family (mingw*, ucrt64-*) keeps Rawhide's
toolchain internally coherent, exactly as before #548 added this repo.
"""
from __future__ import annotations

import fnmatch
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIGS = ["mock/hummingbird-ci.cfg", "mock/hummingbird-ci-aarch64.cfg"]


def section_field(config: str, section: str, *keys: str) -> list[str]:
    text = (ROOT / config).read_text(encoding="utf-8")
    match = re.search(rf"^\[{re.escape(section)}\]$(.*?)(?=^\[|\Z)",
                      text, re.M | re.S)
    assert match, f"{config}: no [{section}]"
    patterns = []
    for key in keys:
        line = re.search(rf"^{key}=(.+)$", match.group(1), re.M)
        if line:
            # exclude= is whitespace-separated; includepkgs= is comma-separated
            patterns.extend(line.group(1).replace(",", " ").split())
    return patterns


@pytest.mark.parametrize("config", CONFIGS)
def test_base_jsoncpp_is_excluded_so_rawhides_survives(config):
    patterns = section_field(config, "hummingbird", "excludepkgs")
    for name in ("jsoncpp", "jsoncpp-devel"):
        assert any(fnmatch.fnmatch(name, p) for p in patterns), (
            f"{config}: base {name!r} not excluded -- its .so.27 masks "
            f"Rawhide's .so.26 provider and cmake cannot install")


@pytest.mark.parametrize("config", CONFIGS)
def test_our_jsoncpp_is_excluded_too(config):
    """With only the base's excluded, OUR jsoncpp (priority 11, also .so.27)
    wins the name against Rawhide (99) and reinstates the very block."""
    patterns = section_field(config, "tunaos-hummingbird", "exclude")
    assert any(fnmatch.fnmatch("jsoncpp", p) for p in patterns), config


@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.parametrize("name", [
    "mingw32-gcc", "mingw64-gcc", "mingw32-filesystem", "mingw64-filesystem",
    "mingw32-libstdc++", "ucrt64-gcc-c++",
])
def test_the_whole_mingw_family_leaves_together(config, name):
    """Half a toolchain is worse than none: any surviving member masks its
    Rawhide twin and breaks Rawhide's exact-version internal requires."""
    patterns = section_field(config, "tunaos-hummingbird", "exclude")
    assert any(fnmatch.fnmatch(name, p) for p in patterns), (
        f"{config}: {name!r} survives and splits the toolchain across repos")


@pytest.mark.parametrize("config", CONFIGS)
def test_the_base_exclude_stays_narrow(config):
    """excludepkgs=* on the BASE would hand the whole OS to Rawhide."""
    patterns = section_field(config, "hummingbird", "excludepkgs")
    assert "*" not in patterns
    for keep in ("python3", "glib2", "openssl-libs", "cmake"):
        assert not any(fnmatch.fnmatch(keep, p) for p in patterns), (
            f"{config}: {keep!r} must keep coming from the base")


def test_both_arches_agree():
    for section, keys in (("hummingbird", ("excludepkgs",)),
                          ("tunaos-hummingbird", ("exclude",))):
        assert section_field(CONFIGS[0], section, *keys) == \
            section_field(CONFIGS[1], section, *keys)


@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.parametrize("name", ["wayland-protocols-devel", "wayland-protocols"])
def test_stale_wayland_protocols_is_excluded(config, name):
    """Our served wayland-protocols-devel is 1.47-2.fc43 and at priority 11
    it masks Rawhide's 1.49; gtk4 and mutter BuildRequire >= 1.48, so the
    stale copy blocks exactly the two packages GNOME 51 hangs on."""
    patterns = section_field(config, "tunaos-hummingbird", "exclude")
    assert any(fnmatch.fnmatch(name, p) for p in patterns), (
        f"{config}: stale {name!r} survives and starves gtk4/mutter of "
        f"pkgconfig(wayland-protocols) >= 1.48")


@pytest.mark.parametrize("config", CONFIGS)
def test_stale_docutils_is_excluded(config):
    """Our served python3-docutils 0.23-1.fc43 masks F44's 0.22.4 while
    python3-sphinx requires python3.14dist(docutils) < 0.23~~ -- our copy
    fails the upper bound and every sphinx consumer blocks on it."""
    patterns = section_field(config, "tunaos-hummingbird", "exclude")
    assert any(fnmatch.fnmatch("python3-docutils", p) for p in patterns), (
        f"{config}: stale 'python3-docutils' survives, fails sphinx's "
        f"docutils < 0.23~~ bound, and blocks ~17 sources")


@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.parametrize("name", ["python3-sphinx", "python3-gobject", "wayland-devel"])
def test_new_excludes_do_not_overreach(config, name):
    """The two new globs must hit only the stale pair -- not sphinx itself,
    not unrelated wayland-* or python3-* names."""
    patterns = section_field(config, "tunaos-hummingbird", "exclude")
    assert not any(fnmatch.fnmatch(name, p) for p in patterns), (
        f"{config}: exclude glob overreaches onto {name!r}")


@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.parametrize("name", [
    "libultrahdr", "libultrahdr-devel", "signon", "signon-qt6-devel",
    "stb_image-devel", "quickshell", "rapidjson-devel", "transfig",
    "usbmuxd", "vpnc", "aribb24", "libmpcdec", "musepack-tools",
    "poly2tri", "accounts-qml-module-qt6",
])
def test_the_caret_version_families_are_excluded(config, name):
    """50 served RPMs carry '^' in their VERSION; librepo requests %5E, the
    R2 worker looks up the raw path, 404. The '*+*' name glob cannot catch a
    version-side character, so the 14 affected name families are listed --
    leg 33022688689 failed dejavu-fonts on exactly libultrahdr-1.4.0^....rpm."""
    patterns = section_field(config, "tunaos-hummingbird", "exclude")
    assert any(fnmatch.fnmatch(name, p) for p in patterns), (
        f"{config}: {name!r} still advertised but unfetchable (%5E lookup)")


@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.parametrize("name", ["rapidcheck", "usbutils", "librsvg2"])
def test_caret_family_globs_do_not_overreach(config, name):
    patterns = section_field(config, "tunaos-hummingbird", "exclude")
    assert not any(fnmatch.fnmatch(name, p) for p in patterns), (
        f"{config}: caret-family glob overreaches onto {name!r}")


@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.parametrize("name", [
    "asciidoc", "go-vendor-tools", "xwayland-run", "blueprint-compiler",
    "marshalparser", "xcb-proto", "lirc-devel", "glad2", "python3-glad2",
])
def test_python315_buildtools_are_pinned_to_f44(config, name):
    """Rawhide is mid python-3.15 transition: these build tools require
    python(abi) = 3.15, which no repo in the set provides. Their F44 builds
    run on python 3.14 (which the base serves), so they are pinned via
    includepkgs -- the same pattern as the python3-*/perl-*/mpich* pins.
    Measured with the simulator: 630 -> 642 OK, 12 sources unblocked, no
    regressions."""
    patterns = section_field(config, "fedora-44-python", "includepkgs")
    assert any(fnmatch.fnmatch(name, p) for p in patterns), (
        f"{config}: {name!r} not pinned -- its Rawhide build needs "
        f"python(abi) = 3.15 and blocks its consumers")


@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.parametrize("name", ["opencv-devel", "openexr", "fontforge", "gnuplot"])
def test_dead_end_f44_pins_stay_out(config, name):
    """Verified NOT to help before being left out: F44 opencv needs F44's
    OpenEXR, which the base's newer openexr masks by name; F44 fontforge
    needs the old libxml2.so.2 the base no longer ships; F44 gnuplot did
    not unblock leptonica. Pinning them would mask working Rawhide copies
    for nothing."""
    patterns = section_field(config, "fedora-44-python", "includepkgs")
    assert not any(fnmatch.fnmatch(name, p) for p in patterns), (
        f"{config}: {name!r} pinned despite being a verified dead end")
