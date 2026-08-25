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


@pytest.fixture(scope="module")
def vercmp():
    spec = importlib.util.spec_from_file_location(
        "rpm_vercmp", REPO / "scripts" / "rpm_vercmp.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_libnotify_class_is_caught_before_dispatch(preflight, vercmp):
    """#480, as a preflight verdict instead of a 2.5-hour mock run.

    gnome-settings-daemon needs libnotify >= 0.8.7; libnotify exists in
    the target AND the reference, at 0.8.3 and 0.8.6. Presence said
    "satisfied"; the constraint says no, and the report names the best
    version anything offers so the reader sees the distance.
    """
    versioned = {"gnome-settings-daemon": [("libnotify", ">=", "0:0.8.7")]}
    available = {"libnotify": {"0:0.8.3-5.el10", "0:0.8.6-1.el10"}}
    blocked = preflight.version_blocked(
        ["gnome-settings-daemon"], versioned, available, vercmp)
    assert list(blocked) == ["gnome-settings-daemon"]
    assert blocked["gnome-settings-daemon"] == [
        "libnotify >= 0:0.8.7 (best available 0:0.8.6-1.el10)"]


def test_a_satisfying_provider_anywhere_clears_the_constraint(preflight, vercmp):
    versioned = {"gsd": [("libnotify", ">=", "0:0.8.7")]}
    available = {"libnotify": {"0:0.8.6-1.el10", "0:0.8.7-1.el10"}}
    assert preflight.version_blocked(["gsd"], versioned, available, vercmp) == {}


def test_an_unversioned_provider_is_not_judged(preflight, vercmp):
    """A capability provided without a version cannot fail a constraint.

    Judging it would manufacture false blockers for every soname-style
    provide; absence from available_evr means "cannot say", and "cannot
    say" must not read as "blocked".
    """
    versioned = {"gsd": [("libnotify", ">=", "0:0.8.7")]}
    assert preflight.version_blocked(["gsd"], versioned, {}, vercmp) == {}


RUNTIME_REFERENCE = {
    "packages": {
        # gtkgreet is built by the set and Requires greetd -- which is
        # neither in the target nor built. The #480 xfce shape.
        "gtkgreet": {"srpm": "gtkgreet-0.8-1.fc45.src.rpm",
                     "requires": ["greetd", "glibc", "libwayland-client.so.0"]},
        # xfconf's requires all resolve: glibc from the target,
        # libxfce4util from the build set itself.
        "xfconf": {"srpm": "xfconf-4.20.0-1.fc45.src.rpm",
                   "requires": ["glibc", "libxfce4util.so.7", "(sqlite if x)"]},
        "libxfce4util": {"srpm": "libxfce4util-4.20.0-1.fc45.src.rpm",
                         "requires": ["glibc"]},
        # greetd exists in the reference, but its source is NOT in the
        # build set -- being installable in Rawhide helps nobody here.
        "greetd": {"srpm": "greetd-0.10.3-1.fc45.src.rpm",
                   "requires": []},
    },
    "provides": {
        "libwayland-client.so.0": {"wayland"},
        "libxfce4util.so.7": {"libxfce4util"},
        "greetd": {"greetd"},
    },
}


def test_a_runtime_require_outside_target_and_buildset_is_reported(preflight):
    """The reference is the buildroot, not the install environment."""
    missing = preflight.runtime_unsatisfied(
        ["gtkgreet", "xfconf", "libxfce4util"], RUNTIME_REFERENCE,
        have={"glibc", "libwayland-client.so.0"})
    assert missing == {"gtkgreet": ["greetd"]}


def test_the_buildsets_own_provides_count_as_available(preflight):
    """xfconf needs libxfce4util.so.7, which the build set itself makes."""
    missing = preflight.runtime_unsatisfied(
        ["xfconf", "libxfce4util"], RUNTIME_REFERENCE, have={"glibc"})
    assert "xfconf" not in missing


def test_adding_the_provider_source_closes_the_runtime_gap(preflight):
    """The fix the report is asking for, verified to be the fix."""
    missing = preflight.runtime_unsatisfied(
        ["gtkgreet", "greetd"], RUNTIME_REFERENCE,
        have={"glibc", "libwayland-client.so.0"})
    assert missing == {}
