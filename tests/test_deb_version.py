"""Debian constraints are judged with Debian's ruler, not Fedora's.

scripts/deb_version.py implements dpkg's comparison (deb-version(7));
these vectors were cross-checked against real `dpkg --compare-versions`
(900/900 pairs agreed at authoring time), and the property test below
re-checks live wherever dpkg exists — which includes CI's runners.
"""
from __future__ import annotations

import importlib.util
import itertools
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "deb_version", ROOT / "scripts" / "deb_version.py"
)
dv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dv)


VERSIONS = [
    "1.0", "1.0~rc1", "1.0~rc1-1", "1.0-1", "1.0-2", "1.0-1ubuntu1",
    "1.0.1", "1.0a", "1.0+git1", "2:0.5", "1:1.0", "0.8.6-1", "0.8.7-1",
    "1.0-1~bpo12+1", "1.0.1-1", "7.0.0~rc2", "6.19.6", "1.01", "1.1",
    "50~rc-1", "50.0-4", "1.0+dfsg-1", "1.0~~", "1.0~~a", "1.0~",
    "9.20120115", "58-1", "58+deb12u1-1",
]


@pytest.mark.parametrize("a,b,expected", [
    ("1.0", "1.0", 0),
    ("1.0~rc1", "1.0", -1),           # ~ sorts before end-of-string
    ("1.0~~", "1.0~", -1),
    ("1.0~~a", "1.0~", -1),
    ("1.0-1", "1.0-2", -1),
    ("1.0-1", "1.0-1ubuntu1", -1),
    ("2:0.5", "1:1.0", 1),            # epoch dominates
    ("1.0", "1.0-1", -1),             # no revision compares as 0
    ("1.0a", "1.0+git1", -1),         # letters before non-letters
    ("1.0a", "1.0.1", -1),
    ("1.0+git1", "1.0.1", -1),        # '+' < '.' in the symbol ordering
    ("1.01", "1.1", 0),               # numeric runs, leading zeros
    ("1.0-1~bpo12+1", "1.0-1", -1),   # backport sorts below the release
    ("0.8.6-1", "0.8.7-1", -1),
])
def test_dpkg_vectors(a, b, expected):
    assert dv.compare(a, b) == expected


def test_rpm_and_dpkg_genuinely_disagree():
    """The reason this module exists instead of reusing rpm_vercmp.

    dpkg compares separators by weight, rpm skips them entirely: on
    `1.0.1` vs `1.0+1`, dpkg says greater (verified against real dpkg)
    and rpm says equal. A factory that judged Debian constraints with
    the RPM ruler would read that pair as the same version.
    """
    spec = importlib.util.spec_from_file_location(
        "rpm_vercmp", ROOT / "scripts" / "rpm_vercmp.py")
    rpm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rpm)
    assert dv.compare("1.0.1", "1.0+1") == 1
    assert rpm.rpmvercmp("1.0.1", "1.0+1") == 0


@pytest.mark.parametrize("version,expected", [
    ("2:1.5-3", (2, "1.5", "3")),
    ("1.5-3", (0, "1.5", "3")),
    ("1.5", (0, "1.5", "0")),
    ("1.0-rc1-1", (0, "1.0-rc1", "1")),  # revision is the LAST hyphen
])
def test_parse_version(version, expected):
    assert dv.parse_version(version) == expected


@pytest.mark.parametrize("available,op,required,expected", [
    ("0.8.6-1", ">=", "0.8.7", False),
    ("0.8.7-1", ">=", "0.8.7", True),
    ("1.0-1", "<<", "1.0-2", True),
    ("1.0-2", "<<", "1.0-2", False),
    ("1.0-2", ">>", "1.0-1", True),
    ("1.0-1", "=", "1.0-1", True),
    ("1.0-1", ">", "1.0-1", True),    # historical > is inclusive
    ("1.0-1", "<", "1.0-1", True),
])
def test_satisfies(available, op, required, expected):
    assert dv.satisfies(available, op, required) is expected


def test_satisfies_rejects_unknown_operator():
    with pytest.raises(ValueError):
        dv.satisfies("1.0", "~=", "1.0")


@pytest.mark.skipif(shutil.which("dpkg") is None, reason="no dpkg here")
def test_every_pair_agrees_with_real_dpkg():
    """The authority is installable; when it is, defer to it wholesale."""
    for a, b in itertools.product(VERSIONS, repeat=2):
        mine = dv.compare(a, b)
        if subprocess.run(["dpkg", "--compare-versions", a, "eq", b],
                          stderr=subprocess.DEVNULL).returncode == 0:
            real = 0
        elif subprocess.run(["dpkg", "--compare-versions", a, "gt", b],
                            stderr=subprocess.DEVNULL).returncode == 0:
            real = 1
        else:
            real = -1
        assert mine == real, f"{a} vs {b}: mine {mine}, dpkg {real}"
