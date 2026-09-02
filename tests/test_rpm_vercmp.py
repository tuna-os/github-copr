"""The version-comparison primitive behaves exactly like librpm.

Vectors carried over from the sandogasa-rpmvercmp crate
(slopfest/sandogasa, Apache-2.0 OR MIT), which implements librpm's
rpmvercmp() including ``~``/``^``. Getting any of these wrong turns a
version-aware gap or staleness check into quiet misinformation — a
package read as fresh that is stale, or a constraint read as satisfied
that mock will reject hours into a chain.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "rpm_vercmp", ROOT / "scripts" / "rpm_vercmp.py"
)
vc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vc)


@pytest.mark.parametrize("a,b,expected", [
    # equal / numeric / segment-count basics
    ("1.0", "1.0", 0),
    ("1.1", "1.2", -1),
    ("1.2", "1.1", 1),
    ("1.10", "1.9", 1),
    ("1.9", "1.10", -1),
    ("1.0a", "1.01", -1),
    ("1.01", "1.0a", 1),
    ("1.0a", "1.0b", -1),
    ("1.0b", "1.0a", 1),
    ("1.0.0", "1.0", 1),
    ("1.0", "1.0.0", -1),
    ("1.01", "1.1", 0),
    ("", "", 0),
    ("1.0", "", 1),
    ("", "1.0", -1),
    # ~ pre-release
    ("1.0~rc1", "1.0", -1),
    ("1.0", "1.0~rc1", 1),
    ("1.0~rc1", "1.0~rc2", -1),
    ("1.0~rc2", "1.0~rc1", 1),
    ("6.19~rc6", "6.19", -1),
    ("6.19~rc6", "6.19.6", -1),
    ("6.19", "6.19.6", -1),
    # ^ post-release snapshot
    ("1.0^post1", "1.0", 1),
    ("1.0^post1", "1.0.1", -1),
    ("1.0^post1", "1.0^post2", -1),
    ("1.0~rc1", "1.0^post1", -1),
    # real-world kernel shapes
    ("6.19.6", "6.19~rc6", 1),
    ("6.18.16", "6.18.3", 1),
    ("7.0.0", "5.7.9", 1),
    ("10.0", "9.0", 1),
    ("7.0.0~rc2", "6.19.6", 1),
])
def test_rpmvercmp_matches_librpm(a, b, expected):
    assert vc.rpmvercmp(a, b) == expected


@pytest.mark.parametrize("a,b,expected", [
    ("1.0-1", "2.0-1", -1),
    ("2.0-1", "1.0-1", 1),
    ("2:1.0-1", "1:2.0-1", 1),
    ("1:2.0-1", "2:1.0-1", -1),
    ("1.0-1.fc41", "1.0-2.fc41", -1),
    ("1.0-2.fc41", "1.0-1.fc41", 1),
    ("5.14.0", "5.16.0", -1),
    ("5.16.0", "5.14.0", 1),
    ("1.5.0-3.el9", "1.6.3-1.fc44", -1),
    ("GLIBC_2.28", "GLIBC_2.38", -1),
    ("GLIBC_2.38", "GLIBC_2.28", 1),
])
def test_compare_evr(a, b, expected):
    assert vc.compare_evr(a, b) == expected


@pytest.mark.parametrize("evr,expected", [
    ("2:1.5.0-3.el9", (2, "1.5.0", "3.el9")),
    ("1.5.0-3.el9", (0, "1.5.0", "3.el9")),
    ("5.16.0", (0, "5.16.0", None)),
])
def test_parse_evr(evr, expected):
    assert vc.parse_evr(evr) == expected


def test_satisfies_the_libnotify_case():
    """The #480 defect, as a constraint check.

    gnome-settings-daemon needs libnotify >= 0.8.7; the buildroot
    resolved 0.8.6. That must read as unsatisfied — and 0.8.7-1.el10
    must satisfy it despite the requirement carrying no release.
    """
    assert not vc.satisfies("0.8.6-2.el10", ">=", "0.8.7")
    assert vc.satisfies("0.8.7-1.el10", ">=", "0.8.7")
    assert vc.satisfies("0.8.8-1.el10", ">=", "0.8.7")


@pytest.mark.parametrize("available,op,required,expected", [
    ("1.0-1.el10", "=", "1.0", True),      # no release in requirement
    ("1.0-1.el10", "=", "1.0-2.el10", False),
    ("1.0-2.el10", ">", "1.0-1.el10", True),
    ("1.0~rc1-1.el10", ">=", "1.0", False),  # pre-release is older
    ("2:0.9-1.el10", ">=", "1.0", True),     # epoch dominates
    ("1.0-1.el10", "<=", "1.0", True),
    ("1.1-1.el10", "<", "1.0", False),
])
def test_satisfies_range_semantics(available, op, required, expected):
    assert vc.satisfies(available, op, required) is expected


def test_satisfies_rejects_unknown_operator():
    with pytest.raises(ValueError):
        vc.satisfies("1.0", "~=", "1.0")
