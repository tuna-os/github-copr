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
            patterns.extend(line.group(1).split())
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
