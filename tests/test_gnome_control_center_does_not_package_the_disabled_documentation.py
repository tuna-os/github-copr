"""gnome-control-center's %build doc flag and %files man page must agree.

meson.build only enters `subdir('man')` -- where gnome-control-center.1 is
built -- via `if get_option('documentation')`. meson_options.txt defaults
that option to false. The original bug (#580) was a spec that passed
`-Ddocumentation=false` unconditionally in %build while still %files-ing
`%{_mandir}/man1/gnome-control-center.1*`, so the man page was never
produced by any build this spec did, and rpmbuild died with:

    error: File not found: .../BUILDROOT/usr/share/man/man1/gnome-control-center.1*

The fix #580 landed was narrower than "documentation must stay off forever":
it was "the %build flag and the %files entry must not disagree". This test's
own predecessor said as much in its own docstring -- "if this ever becomes
[enabled], the man page would need its own %files line again". Rawhide's
current spec (fetched live and forked here) does exactly that: it turned
documentation on, because man/meson.build only needs xsltproc + the plain
(non-namespaced) docbook stylesheets -- both already in this spec's
BuildRequires (docbook-style-xsl, libxslt; see
test_docbook_man_pages_name_the_right_stylesheets.py, which independently
confirms gnome-control-center probes the non-namespaced xsl/current URI and
is correct with docbook-style-xsl) -- and confirmed by a real hummingbird-ci
mock build producing and packaging gnome-control-center.1 cleanly.

So the invariant this guards is the agreement, not the 2026-era answer:
whichever way -Ddocumentation is set, the %files man-page line must be
present if and only if the flag says the man page will actually be built.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "src/gnome-51/gnome-control-center/gnome-control-center.spec"

MAN_PAGE_LINE = "%{_mandir}/man1/gnome-control-center.1*"


def _documentation_flag(build_section: str) -> bool:
    match = re.search(r"-Ddocumentation=(true|false)", build_section)
    assert match, "no -Ddocumentation=true|false found in %build"
    return match.group(1) == "true"


def test_documentation_flag_and_man_page_packaging_agree():
    text = SPEC.read_text(encoding="utf-8")
    build_section = text.split("%build", 1)[1].split("%install", 1)[0]
    files_section = text.split("%files ", 1)[1]

    documentation_enabled = _documentation_flag(build_section)
    man_page_packaged = MAN_PAGE_LINE in files_section

    assert documentation_enabled == man_page_packaged, (
        "the %build -Ddocumentation flag and the %files man-page entry have "
        "gone out of sync -- man/meson.build only builds "
        "gnome-control-center.1 when documentation is enabled, so %files "
        "must package it exactly when the flag is true, and never when it "
        "is false (rpmbuild fails %files with 'File not found' either way "
        "it disagrees)"
    )


def test_documentation_flag_is_not_conditional_on_a_target():
    """The premise both directions rely on: `-Ddocumentation` must be the
    same on every target this spec builds, or the %files line above would
    need to become conditional too (guarded on the real condition) instead
    of being a flat present/absent check."""
    text = SPEC.read_text(encoding="utf-8")
    build_section = text.split("%build", 1)[1].split("%install", 1)[0]
    assert build_section.count("-Ddocumentation=") == 1, (
        "expected exactly one -Ddocumentation= setting in %build; if a "
        "target now needs a different value, this test and the %files "
        "check above both need to learn the real condition"
    )
