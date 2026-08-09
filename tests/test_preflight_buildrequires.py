"""Knowing which packages cannot build should not require building them.

A tier's job discovers an unsatisfiable BuildRequires only when it reaches it,
which on the 40-layer order can be hours into a run. The answer is knowable
before dispatch: every source package's BuildRequires are in the Rawhide source
index, and every capability anything provides is in the reference index.

Against the current manifest this finds one package in 1248 --
SwayNotificationCenter needs pkgconfig(granite-7), and Rawhide's only granite
provides pkgconfig(granite) and libgranite.so.6.
"""

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def preflight():
    spec = importlib.util.spec_from_file_location(
        "preflight", REPO / "scripts" / "preflight-buildrequires.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROVIDES = {"pkgconfig(gtk4)", "pkgconfig(granite)", "meson", "vala"}
HAVE = {"glibc", "pkgconfig(glib-2.0)"}
SOURCE_INDEX = {
    "good": ["pkgconfig(gtk4)", "meson", "pkgconfig(glib-2.0)"],
    "blocked": ["pkgconfig(gtk4)", "pkgconfig(granite-7)"],
    "very-blocked": ["pkgconfig(granite-7)", "pkgconfig(nonesuch)"],
}


def run(preflight, sources):
    return preflight.unsatisfiable(sources, SOURCE_INDEX, PROVIDES, HAVE)


def test_a_package_whose_buildrequires_all_resolve_is_not_reported(preflight):
    assert run(preflight, ["good"]) == {}


def test_a_capability_nothing_provides_is_reported_against_its_package(preflight):
    assert run(preflight, ["blocked"]) == {"blocked": ["pkgconfig(granite-7)"]}


def test_every_missing_capability_is_listed_not_just_the_first(preflight):
    assert run(preflight, ["very-blocked"]) == {
        "very-blocked": ["pkgconfig(granite-7)", "pkgconfig(nonesuch)"]}


def test_what_the_target_already_ships_is_not_a_blocker(preflight):
    """pkgconfig(glib-2.0) is in `have` and in no provides set."""
    assert "good" not in run(preflight, ["good", "blocked"])


def test_rich_dependencies_are_not_blockers(preflight):
    """rpm resolves `(a or b)` at install time; no provides entry exists."""
    index = {"rich": ["(gtk4 or gtk3)"]}
    assert preflight.unsatisfiable(["rich"], index, PROVIDES, HAVE) == {}


def test_a_package_absent_from_the_source_index_is_not_a_blocker(preflight):
    """No BuildRequires known is not the same as unsatisfiable ones."""
    assert preflight.unsatisfiable(["unknown"], SOURCE_INDEX, PROVIDES, HAVE) == {}
