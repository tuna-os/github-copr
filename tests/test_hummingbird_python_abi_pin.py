"""Hummingbird is on Python 3.14; Rawhide is on 3.15.  Guard the pin that bridges them.

`mock/hummingbird-ci.cfg` layers Fedora Rawhide under Hummingbird's own
repository, which is right for everything except Python: Hummingbird ships
python3-3.14.6 and has not followed Rawhide through the 3.15 rebuild.  Every
noarch Python module carries `Requires: python(abi) = <x.y>`, so Rawhide's
modules cannot be installed beside Hummingbird's interpreter.  Measured
2026-08-08 against Rawhide's own index, 8919 of its 66644 binary packages
transitively need `python(abi) = 3.15`.

That is what fails the eight python-* packages of tier niri-00 (runs
31231968581, 31242725235, 31248093019): `%pyproject_buildrequires` emits e.g.
`python3dist(flit-core)`, the only provider is Rawhide's 3.15 build, and the
transaction cannot resolve.

Fedora 44 is the release whose interpreter is python3-3.14.6 — the same
upstream version Hummingbird ships.  It is pinned for the Python namespace
only.  Two properties make that safe, and both are asserted here:

* `includepkgs` confines the repository, so no F44 C library can enter the
  chroot and the glibc / libxml2 / openssl soname split recorded in
  docs/hummingbird-desktop-gap.md Finding 3 is untouched;
* the priority sits strictly between Hummingbird's and Rawhide's, so F44 beats
  Rawhide's 3.15 modules but can never shadow Hummingbird's own interpreter,
  setuptools, pip, packaging or pytest.
"""
from __future__ import annotations

import configparser
import fnmatch
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "mock/hummingbird-ci.cfg"

# mock's fedora-rawhide-x86_64.cfg leaves its repos at dnf's default priority.
RAWHIDE_PRIORITY = 99

PINNED = ("fedora-44-python", "fedora-44-python-updates")

# Names the pin must never be able to supply.  Every one is a package where
# Hummingbird and Fedora 44 differ by a soname or a symbol version, so pulling
# the F44 build into the chroot would produce RPMs that do not run on the
# target.  Sources: docs/hummingbird-desktop-gap.md Findings 1 and 3.
FORBIDDEN = (
    "glibc",
    "libxml2",
    "openssl",
    "openssl-libs",
    "fontconfig",
    "glib2",
    "systemd",
    "gcc",
    "rust",
    "gtk4",
    "qt6-qtbase",
    "python3",
)


def dnf_conf() -> configparser.ConfigParser:
    """Parse the .repo stanzas this config appends to dnf.conf."""
    text = CONFIG.read_text()
    blocks = re.findall(r'config_opts\[.dnf\.conf.\]\s*\+=\s*"""(.*?)"""', text, re.S)
    assert blocks, "hummingbird-ci.cfg appends no dnf.conf repositories"
    parser = configparser.ConfigParser()
    parser.read_string("\n".join(blocks))
    return parser


@pytest.fixture(scope="module")
def conf() -> configparser.ConfigParser:
    return dnf_conf()


def test_a_python_314_repository_is_pinned(conf) -> None:
    """Without it every %pyproject_buildrequires resolves a 3.15 backend."""
    for repo in PINNED:
        assert conf.has_section(repo), (
            f"{repo} is gone from mock/hummingbird-ci.cfg, so the only provider "
            f"of python3dist(flit-core), python3dist(hatchling), "
            f"python3dist(poetry-core) and python3dist(cython) is Rawhide's "
            f"Python 3.15 build, which cannot install beside Hummingbird's 3.14"
        )
        assert conf.get(repo, "enabled") == "1", f"{repo} is disabled"


def test_the_pin_is_confined_to_the_python_namespace(conf) -> None:
    """includepkgs is the whole safety argument for adding an older Fedora."""
    for repo in PINNED:
        raw = conf.get(repo, "includepkgs", fallback="").strip()
        assert raw, (
            f"{repo} has no includepkgs, so an entire Fedora 44 — two releases "
            f"of build tools behind the target — can satisfy any BuildRequires "
            f"Hummingbird happens to miss"
        )
        globs = [g.strip() for g in raw.split(",") if g.strip()]
        assert "*" not in globs, f"{repo} includepkgs is unrestricted"
        for name in FORBIDDEN:
            matched = [g for g in globs if fnmatch.fnmatchcase(name, g)]
            assert not matched, (
                f"{repo} includepkgs {matched} would let Fedora 44's {name} "
                f"into the buildroot; Hummingbird and F44 differ there by a "
                f"soname or symbol version (gap doc, Findings 1 and 3)"
            )


def test_the_pin_outranks_rawhide_but_never_hummingbird(conf) -> None:
    """Priority order is what keeps the interpreter Hummingbird's own."""
    hummingbird = conf.getint("hummingbird", "priority")
    local = conf.getint("local-build", "priority")
    for repo in PINNED:
        pinned = conf.getint(repo, "priority")
        assert pinned > hummingbird, (
            f"{repo} priority {pinned} is at least as good as hummingbird's "
            f"{hummingbird}; dnf would drop Hummingbird's python3, setuptools "
            f"and pip in favour of Fedora 44's older builds"
        )
        assert pinned < RAWHIDE_PRIORITY, (
            f"{repo} priority {pinned} does not beat Rawhide's default "
            f"{RAWHIDE_PRIORITY}, so dnf keeps choosing the Python 3.15 "
            f"modules that cannot be installed"
        )
        assert local < pinned, (
            "packages this run already built must keep winning over Fedora 44"
        )


def test_the_pin_records_why_it_exists_and_when_to_drop_it() -> None:
    """A version pin with no stated expiry outlives its reason."""
    text = CONFIG.read_text()
    assert "3.15" in text and "3.14" in text, (
        "the config does not name the two Python versions it is bridging"
    )
    assert "Remove this pin" in text, (
        "nothing in the config says when the Fedora 44 pin stops being correct "
        "— it must go when Hummingbird's own python3 reaches 3.15, or it will "
        "silently build 3.14 modules for a 3.15 target"
    )
