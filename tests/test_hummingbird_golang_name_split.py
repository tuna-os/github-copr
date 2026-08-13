"""Hummingbird publishes golang1.26/-bin/-src, never a plain `golang`.

This is not the python(abi)/perl MODULE_COMPAT version split -- it's a NAME
split, and it doesn't fail the transaction cleanly, it hangs the job. Every
one of run 31697678706's five desktop jobs died inside swig's own dnf5
builddep transaction:

    Transaction failed: Rpm transaction failed.
     - file /usr/lib/golang/src/... conflicts between attempted installs of
       golang-src-1.27~rc2-2.fc45.noarch and
       golang1.26-src-1.26.5-0.1.1.hum1.noarch

swig BuildRequires plain `golang`. Hummingbird has no package by that exact
name, so dnf's priority filter -- which drops a NAME entirely from the
losing repo, the mechanism the perl/python pins rely on -- never engages:
`golang` and `golang1.26` are different names, both install, and only their
file layout collides. Nothing in this repo's own build closure needs
golang1.26 by name (the Go-targeting recipes don't even build for
hummingbird/kde), so excluding it from the hummingbird repo is safe: unlike
perl/python, Go produces static binaries with no runtime soname to
version-match, so every `golang` BuildRequires can resolve from Rawhide
alone without an ABI mismatch.
"""

from __future__ import annotations

import configparser
import io
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "mock" / "hummingbird-ci.cfg"


@pytest.fixture(scope="module")
def conf() -> configparser.ConfigParser:
    text = CFG.read_text()
    blocks = re.findall(r'config_opts\[.dnf\.conf.\]\s*\+=\s*"""(.*?)"""', text, re.S)
    assert blocks, "hummingbird-ci.cfg appends no dnf.conf repositories"
    parser = configparser.ConfigParser(strict=False)
    parser.read_file(io.StringIO("\n".join(blocks)))
    return parser


def test_golang1_26_is_excluded_from_the_hummingbird_repo(conf) -> None:
    excludes = [
        g.strip()
        for g in conf.get("hummingbird", "excludepkgs", fallback="").split(",")
        if g.strip()
    ]
    assert excludes, (
        "hummingbird repo has no excludepkgs, so golang1.26* is still an "
        "install candidate alongside Rawhide's golang -- the exact file "
        "conflict that hung run 31697678706"
    )
    assert any(g.startswith("golang1.26") for g in excludes), (
        "excludepkgs does not cover golang1.26 -- the transaction can still "
        "select both golang-src (Rawhide) and golang1.26-src (hummingbird)"
    )


def test_the_exclusion_is_confined_to_golang1_26(conf) -> None:
    """This must not become a blanket exclude that also drops a future
    plain `golang` package Hummingbird might start publishing."""
    excludes = [g.strip() for g in conf.get("hummingbird", "excludepkgs").split(",") if g.strip()]
    assert "*" not in excludes, "hummingbird excludepkgs is unrestricted"
    for glob in excludes:
        assert glob.startswith("golang1.26"), (
            f"hummingbird excludepkgs carries {glob!r}, which is outside the "
            "golang1.26 name-split this exclusion exists for"
        )


def test_hummingbird_still_wins_every_other_package(conf) -> None:
    """The exclusion is scoped to one name family -- it must not lower
    hummingbird's priority or otherwise weaken its claim on everything
    else it ships."""
    assert conf.getint("hummingbird", "priority") == 10, (
        "hummingbird's priority moved; the golang1.26 fix should only add "
        "excludepkgs, not touch priority"
    )


def test_the_reason_travels_with_the_config() -> None:
    """A silent exclude with no citation looks like a typo to the next
    person who reads this file, and invites being 'cleaned up'."""
    text = CFG.read_text()
    assert "31697678706" in text, "the config does not cite the run that surfaced this"
    assert "golang1.26" in text and "golang-src" in text, (
        "the config does not name both sides of the conflicting install"
    )
    assert "static binaries" in text or "no runtime library" in text, (
        "the config does not record WHY excluding golang1.26 is safe -- "
        "that Go binaries carry no soname coupling to the toolchain "
        "version, unlike perl/python -- which is the load-bearing fact "
        "that distinguishes this from the perl/python pins"
    )
