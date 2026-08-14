"""Hummingbird ships hdf5-mpich but no mpich; the gap must be bridged.

From run 31732589290, netcdf's builddep failed to resolve:

    - package mpich-4.2.2-10.fc45 from fedora requires
      (python(abi) = 3.15 if python3), but none of the providers can
      be installed

Measured against the hummingbird index itself: it ships hdf5-mpich
(requiring libmpi.so.12(mpich-x86_64)) but NO package named mpich.  The
only provider is Rawhide's, whose rich dep demands python(abi) = 3.15
the moment python3 enters the transaction -- while graphviz/doxygen need
hummingbird's python3 = 3.14 in the SAME transaction.  Unsolvable, so
every package whose builddep touches both doxygen and hdf5-mpich-devel
fails before building anything.

F44's mpich is the same upstream version (4.2.2), provides the exact
libmpi.so.12()(64bit)(mpich-x86_64) hummingbird's hdf5-mpich requires,
and its rich dep is (python(abi) = 3.14 if python3) -- hummingbird's own
interpreter.  Pinning it drops Rawhide's mpich from resolution by name,
the same mechanism the perl/python pins in this config rely on.
"""

from __future__ import annotations

import configparser
import io
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "mock" / "hummingbird-ci.cfg"
MPICH_REPOS = ("fedora-44-mpich", "fedora-44-mpich-updates")
RAWHIDE_PRIORITY = 99


@pytest.fixture(scope="module")
def conf() -> configparser.ConfigParser:
    text = CFG.read_text()
    blocks = re.findall(r'config_opts\[.dnf\.conf.\]\s*\+=\s*"""(.*?)"""', text, re.S)
    assert blocks, "hummingbird-ci.cfg appends no dnf.conf repositories"
    parser = configparser.ConfigParser(strict=False)
    parser.read_file(io.StringIO("\n".join(blocks)))
    return parser


def test_an_mpich_repository_is_pinned(conf) -> None:
    for repo in MPICH_REPOS:
        assert conf.has_section(repo), (
            f"{repo} is gone, so Rawhide's mpich (python 3.15 world) is the "
            "only provider of libmpi.so.12(mpich-x86_64) and every builddep "
            "touching both doxygen and hdf5-mpich-devel fails to resolve"
        )
        assert conf.get(repo, "enabled") == "1", f"{repo} is disabled"


def test_the_pin_is_confined_to_the_mpich_namespace(conf) -> None:
    """includepkgs is the whole safety argument for adding an older Fedora."""
    for repo in MPICH_REPOS:
        globs = [g.strip() for g in conf.get(repo, "includepkgs", fallback="").split(",")]
        globs = [g for g in globs if g]
        assert globs, (
            f"{repo} has no includepkgs, so an entire Fedora 44 -- two releases "
            "of C libraries -- can enter the chroot"
        )
        assert "*" not in globs, f"{repo} includepkgs is unrestricted"
        for glob in globs:
            assert glob.startswith("mpich"), (
                f"{repo} includepkgs carries {glob!r}, which is outside the "
                "mpich namespace this pin exists for"
            )


def test_the_pin_outranks_rawhide_but_never_hummingbird(conf) -> None:
    hummingbird = conf.getint("hummingbird", "priority")
    local = conf.getint("local-build", "priority")
    for repo in MPICH_REPOS:
        pinned = conf.getint(repo, "priority")
        assert pinned > hummingbird, (
            f"{repo} priority {pinned} is at least as good as hummingbird's "
            f"{hummingbird}; if hummingbird ever ships its own mpich it must win"
        )
        assert pinned < RAWHIDE_PRIORITY, (
            f"{repo} priority {pinned} does not beat Rawhide's "
            f"{RAWHIDE_PRIORITY}, so Rawhide's python-3.15 mpich still wins"
        )
        assert local < pinned, "packages this run built must outrank Fedora 44"


def test_the_reason_travels_with_the_config() -> None:
    """A pin with no stated expiry outlives the problem it was added for."""
    text = CFG.read_text()
    assert "hdf5-mpich" in text and "libmpi.so.12" in text, (
        "the config does not record the dependency gap the pin bridges "
        "(hummingbird ships hdf5-mpich but no mpich)"
    )
    assert "python(abi) = 3.15" in text, (
        "the config does not record WHY Rawhide's mpich cannot resolve "
        "(its rich dep conflicts with hummingbird's python3), which is the "
        "load-bearing fact"
    )
    assert "Remove when hummingbird ships its own mpich" in text, (
        "no removal condition, so this outlives the gap"
    )
