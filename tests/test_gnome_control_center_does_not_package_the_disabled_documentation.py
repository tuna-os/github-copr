"""gnome-control-center must not %files a man page -Ddocumentation=false never builds.

meson.build only enters `subdir('man')` -- where gnome-control-center.1 is
built -- via `if get_option('documentation')`. meson_options.txt defaults
that option to false, and %build passes -Ddocumentation=false explicitly and
unconditionally, for every target. So this man page is never produced by
ANY build this spec does, yet %files packaged it behind `%if !0%{?rhel}`
(true on every non-rhel target, including this spec's own hummingbird-ci
build).

Confirmed by an actual build, iterating the GNOME 51 chain locally:

    error: File not found: .../BUILDROOT/usr/share/man/man1/gnome-control-center.1*

A rebuild with the block removed produced gnome-control-center 51~beta-1
clean.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "src/gnome-51/gnome-control-center/gnome-control-center.spec"


def test_documentation_option_is_unconditionally_false():
    """The premise the %files omission relies on. If this ever becomes
    conditional, the man page may exist on SOME targets and would need its
    own %files line again, guarded on the real condition."""
    text = SPEC.read_text(encoding="utf-8")
    assert "-Ddocumentation=false" in text
    build = text.split("%build", 1)[1].split("%install", 1)[0]
    assert build.count("%if") == 0, (
        "the %build section grew a conditional -- documentation may no "
        "longer be unconditionally false, so the man page may need "
        "packaging again on some target"
    )


def test_the_man_page_is_never_packaged():
    text = SPEC.read_text(encoding="utf-8")
    assert "man1/gnome-control-center.1" not in text, (
        "gnome-control-center.1 reappeared in %files -- -Ddocumentation=false "
        "is unconditional in %build, so man/meson.build's subdir is never "
        "entered and this path never exists; referencing it fails the build "
        "with 'File not found'"
    )
