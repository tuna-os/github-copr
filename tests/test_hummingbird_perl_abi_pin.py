"""Hummingbird is on perl 5.42.2; Rawhide is on 5.44.0.  Guard the bridge.

This is the python(abi) split again, one interpreter over, and it went
unmitigated until run 31294475023 reached layer-04 and failed thirteen perl
packages at once.  The chain, read out of that run's log rather than guessed:

    Failed to resolve the transaction:
    Problem 1: cannot install both perl-libs-4:5.44.0-527.fc45.x86_64 from
      fedora and perl-libs-4:5.42.2-525.hum1.x86_64 from hummingbird
     - package perl-Unicode-LineBreak-2019.001-28.fc45.x86_64 from fedora
       requires libperl.so.5.44()(64bit), but none of the providers can be
       installed
     - package perl-version-9:0.99.33-522.fc44.x86_64 from fedora-44-python
       is filtered out by exclude filtering

The last line names the fix.  F44 already carries the module the buildroot
wants; `includepkgs=python3-*,flit` was excluding it.

Why F44's modules resolve and Rawhide's cannot, measured against each
repository's own metadata:

    hummingbird perl-libs 5.42.2  provides  libperl.so.5.42
                                            perl(:MODULE_COMPAT_5.42.0)
                                            perl(:MODULE_COMPAT_5.42.1)
                                            perl(:MODULE_COMPAT_5.42.2)
    fedora 44   perl      5.42.1  modules want libperl.so.5.42 / COMPAT_5.42.1  -> OK
    rawhide     perl      5.44.0  modules want libperl.so.5.44 / COMPAT_5.44.0  -> no provider

MODULE_COMPAT is a range here, not a point, which is the property the whole
pin rests on.  166 of the 1248 packages in the build order are perl-*.
"""

from __future__ import annotations

import configparser
import io
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "mock" / "hummingbird-ci.cfg"
PERL_REPOS = ("fedora-44-perl", "fedora-44-perl-updates")
RAWHIDE_PRIORITY = 99


@pytest.fixture(scope="module")
def conf() -> configparser.ConfigParser:
    text = CFG.read_text()
    blocks = re.findall(r'config_opts\[.dnf\.conf.\]\s*\+=\s*"""(.*?)"""', text, re.S)
    assert blocks, "hummingbird-ci.cfg appends no dnf.conf repositories"
    parser = configparser.ConfigParser(strict=False)
    parser.read_file(io.StringIO("\n".join(blocks)))
    return parser


def test_a_perl_542_repository_is_pinned(conf) -> None:
    for repo in PERL_REPOS:
        assert conf.has_section(repo), (
            f"{repo} is gone, so Rawhide's perl 5.44 modules are the only ones "
            "on offer and every perl-* package fails buildroot install"
        )
        assert conf.get(repo, "enabled") == "1", f"{repo} is disabled"


def test_the_pin_is_confined_to_the_perl_namespace(conf) -> None:
    """includepkgs is the whole safety argument for adding an older Fedora."""
    for repo in PERL_REPOS:
        globs = [g.strip() for g in conf.get(repo, "includepkgs", fallback="").split(",")]
        globs = [g for g in globs if g]
        assert globs, (
            f"{repo} has no includepkgs, so an entire Fedora 44 -- two releases "
            "of C libraries -- can enter the chroot"
        )
        assert "*" not in globs, f"{repo} includepkgs is unrestricted"
        for glob in globs:
            assert glob.startswith("perl"), (
                f"{repo} includepkgs carries {glob!r}, which is outside the perl "
                "namespace this pin exists for"
            )


def test_the_interpreter_is_left_to_hummingbird(conf) -> None:
    """Pulling `perl` or `perl-libs` from F44 would swap the interpreter.

    Hummingbird ships both at priority 10 and would win the name anyway, but
    listing them states the intent -- and a later priority change must not
    silently turn F44 into the interpreter.
    """
    for repo in PERL_REPOS:
        globs = [g.strip() for g in conf.get(repo, "includepkgs").split(",")]
        for exact in ("perl", "perl-libs"):
            assert exact not in globs, (
                f"{repo} includes {exact!r} by name; the interpreter must come "
                "from Hummingbird, not Fedora 44"
            )


def test_the_pin_outranks_rawhide_but_never_hummingbird(conf) -> None:
    hummingbird = conf.getint("hummingbird", "priority")
    local = conf.getint("local-build", "priority")
    for repo in PERL_REPOS:
        pinned = conf.getint(repo, "priority")
        assert pinned > hummingbird, (
            f"{repo} priority {pinned} is at least as good as hummingbird's "
            f"{hummingbird}, so F44 could shadow the target's own perl"
        )
        assert pinned < RAWHIDE_PRIORITY, (
            f"{repo} priority {pinned} does not beat Rawhide's "
            f"{RAWHIDE_PRIORITY}, so Rawhide's 5.44 modules still win"
        )
        assert local < pinned, "packages this run built must outrank Fedora 44"


def test_the_reason_travels_with_the_config() -> None:
    """A pin with no stated expiry outlives the problem it was added for."""
    text = CFG.read_text()
    assert "5.44" in text and "5.42" in text, (
        "the config does not record the perl versions the pin bridges"
    )
    assert "MODULE_COMPAT" in text, (
        "the config does not record WHY an F44 module resolves against "
        "Hummingbird's interpreter, which is the load-bearing fact"
    )
    assert "Remove this pin when Hummingbird's own perl" in text, (
        "no removal condition, so this outlives the split"
    )
