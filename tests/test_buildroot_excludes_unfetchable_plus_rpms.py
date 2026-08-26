"""The hummingbird buildroot must not resolve to RPMs librepo cannot fetch.

79 RPMs in the factory's hummingbird prefix are stored under a filename
containing a literal '+'. librepo percent-encodes it to %2b and the R2 worker
looks up raw paths, so every one of them 404s. scripts/publish-rpm-wave.sh:31
records that incident and line 101 is the remedy -- it renames '+' to '.' on
publish -- but these files predate the rename and no publish has re-synced
them since.

#548 added [tunaos-hummingbird] to the buildroot, which is what made these
files reachable as build dependencies. Publisher run 32991216265 then failed
on three packages that had never failed before:

    abseil-cpp     Cannot download mingw64-gcc-c%2b%2b-16.1.1-3.1.fc43.x86_64.rpm
    inih           Cannot download mingw64-gcc-c%2b%2b-16.1.1-3.1.fc43.x86_64.rpm
    dejavu-fonts   Cannot download libsigc%2b%2b20-2.12.2-1.fc43.x86_64.rpm

dconf and libuser -- the two #548 set out to fix -- did build. The regression
is narrow and it is this one.

The exclude sends those names back to Rawhide, where they resolved before
#548. It is temporary: publish-rpm-wave.sh renames across the whole
synced-down repo, so the first publish that completes fixes all 79.
"""
from __future__ import annotations

import fnmatch
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIGS = ["mock/hummingbird-ci.cfg", "mock/hummingbird-ci-aarch64.cfg"]

# Measured 2026-08-26 against the served primary.xml (revision 1786989380):
# every distinct package name whose <location href> carries a literal '+'.
# Four of them are the reason a '*+*' name glob is not sufficient on its own.
UNFETCHABLE = [
    "mingw64-gcc-c++", "mingw32-gcc-c++", "ucrt64-gcc-c++",
    "libsigc++20", "libsigc++30", "libxml++30", "dbus-c++",
    "xmlrpc-c-c++", "python3-dns+doh", "python3-lxml+html5",
    "rust-cbindgen+default-devel", "mingw64-libstdc++",
    # '+' in the VERSION (10.2+2.0.2), not the name:
    "libcdio-paranoia", "libcdio-paranoia-devel",
    "libcdio-paranoia-debuginfo", "libcdio-paranoia-debugsource",
]


def repo_block(text: str, name: str) -> str:
    """The body of one .repo section, up to the next section header."""
    match = re.search(rf"^\[{re.escape(name)}\]$(.*?)(?=^\[|\Z)",
                      text, re.M | re.S)
    assert match, f"no [{name}] section"
    return match.group(1)


def excludes(config: str) -> list[str]:
    body = repo_block((ROOT / config).read_text(encoding="utf-8"),
                      "tunaos-hummingbird")
    line = re.search(r"^exclude=(.+)$", body, re.M)
    return line.group(1).split() if line else []


@pytest.mark.parametrize("config", CONFIGS)
def test_the_repo_declares_an_exclude(config):
    assert excludes(config), (
        f"{config}: [tunaos-hummingbird] has no exclude=, so the buildroot "
        "can resolve to an RPM whose filename librepo cannot fetch")


@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.parametrize("name", UNFETCHABLE)
def test_every_unfetchable_name_is_excluded(config, name):
    patterns = excludes(config)
    assert any(fnmatch.fnmatch(name, p) for p in patterns), (
        f"{config}: {name!r} is served only as a '+'-containing filename that "
        f"404s through librepo, and none of {patterns} excludes it")


@pytest.mark.parametrize("config", CONFIGS)
def test_the_exclude_does_not_swallow_the_whole_repo(config):
    """`exclude=*` would 'fix' this by making #548 a no-op -- the buildroot
    would stop seeing gobject-introspection and vala too, and dconf would go
    straight back to failing."""
    patterns = excludes(config)
    assert "*" not in patterns, f"{config}: exclude=* disables the repo"
    for keep in ("gobject-introspection", "vala", "gobject-introspection-devel",
                 "gtest-devel", "gmock-devel"):
        assert not any(fnmatch.fnmatch(keep, p) for p in patterns), (
            f"{config}: {keep!r} is what #548 exists to serve, but {patterns} "
            "excludes it")


def test_both_arches_agree():
    """#529 shipped a fix to one arch config and left its twin behind."""
    assert excludes(CONFIGS[0]) == excludes(CONFIGS[1])


def test_the_name_glob_alone_would_be_insufficient():
    """Guards the second pattern. libcdio-paranoia's '+' is in its version,
    so dropping the 'libcdio-paranoia*' pattern must leave it uncovered --
    without this, someone trims the exclude to '*+*' and the four subpackages
    silently start failing again."""
    missed = [n for n in UNFETCHABLE if not fnmatch.fnmatch(n, "*+*")]
    assert missed, "no name in the list lacks '+', so the second pattern is untested"
    assert all(m.startswith("libcdio-paranoia") for m in missed), missed
