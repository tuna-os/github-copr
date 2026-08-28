"""gnome-desktop3 must not %files a directory legacy_library=false never creates.

%build passes -Dlegacy_library=false unconditionally -- for every target,
not just EL10 -- so gnome-desktop-debug (the gtk3-era debug helper, only
installed when legacy_library=true) is never produced by ANY build this
spec does. %files guarded the path with `%if !0%{?rhel}` instead of
checking legacy_library, so it was INCLUDED on every non-rhel target --
this spec's own hummingbird-ci mock config among them, where
legacy_library is equally false.

Confirmed by an actual build, iterating the GNOME 51 chain locally:

    error: Directory not found: .../BUILDROOT/usr/libexec/gnome-desktop-debug

A rebuild with the block removed produced gnome-desktop3 51~alpha-1 clean,
with all five subpackages (main, -debuginfo, -debugsource, -devel, -tests).
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "src/gnome-51/gnome-desktop3/gnome-desktop3.spec"


def test_legacy_library_is_unconditionally_false():
    """The premise the %files guard must actually check. If this ever
    becomes conditional, gnome-desktop-debug may exist on SOME targets and
    the guard below would need to track legacy_library again, not %rhel."""
    text = SPEC.read_text(encoding="utf-8")
    assert "-Dlegacy_library=false" in text
    # No %if around the meson invocation's %build block that could make
    # legacy_library vary by target.
    build = text.split("%build", 1)[1].split("%install", 1)[0]
    assert build.count("%if") == 0, (
        "the %build section grew a conditional -- legacy_library may no "
        "longer be unconditionally false, so gnome-desktop-debug's %files "
        "guard needs re-checking against the real condition, not assumed "
        "gone for good"
    )


def test_gnome_desktop_debug_is_never_packaged():
    """It cannot exist on any target this spec builds; packaging it is not
    a matter of getting the %if condition right, there is no condition
    under which %build produces it at all.

    Checks the actual %files directive, not any mention of the name --
    the fix's own explanatory comment names it deliberately, for context.
    """
    text = SPEC.read_text(encoding="utf-8")
    assert "%{_libexecdir}/gnome-desktop-debug" not in text, (
        "gnome-desktop-debug reappeared in gnome-desktop3.spec's %files -- "
        "legacy_library=false is unconditional in %build, so this path "
        "never exists and referencing it in %files fails the build with "
        "'Directory not found', at the very end of a from-scratch build"
    )
