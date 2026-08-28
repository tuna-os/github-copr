"""mutter.spec's api version and packaged schemas must match what 51.beta
actually builds and installs -- not what an earlier GNOME cycle did.

Three facts, each verified against gitlab.gnome.org/GNOME/mutter at the
exact tag this spec builds (51.beta), not `main`, which can drift:

  * meson.build hardcodes libmutter_api_version = '51'. The spec's stale
    18 named a %{_libdir}/mutter-18/ directory the build never creates --
    `error: Directory not found: .../usr/lib64/mutter-18` on an actual
    build. Nothing else changed the private lib name; the number IS
    mutter's own release series this cycle, not a smaller sequential
    counter carried from GNOME 50.

  * data/meson.build's schema_xmls installs THREE schemas:
    org.gnome.mutter{,.wayland,.experimental}.gschema.xml. The spec
    packaged only the first two -- confirmed missing by an actual build:
    `error: Installed (but unpackaged) file(s) found:
     /usr/share/glib-2.0/schemas/org.gnome.mutter.experimental.gschema.xml`.

  * mdk/data/meson.build installs a FOURTH schema,
    org.gnome.mutter.devkit.gschema.xml, gated behind %files devkit (which
    corresponds to `if have_devkit: subdir('mdk')` in the top-level
    meson.build). This one is genuinely real and was ALREADY correctly
    packaged -- caught only by iterating a REAL build: a first pass at
    this fix removed it, believing it fictional, because only the
    top-level data/meson.build was checked and mdk/data/meson.build was
    missed. Reintroducing that removal reproduces the exact "Installed
    (but unpackaged)" failure it takes an actual build to see, which is
    why this guard pins it present rather than merely leaving it alone.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "src/gnome-51/mutter/mutter.spec"


def test_api_version_is_51_not_the_stale_18():
    text = SPEC.read_text(encoding="utf-8")
    match = re.search(r"^%global mutter_api_version\s+(\S+)", text, re.MULTILINE)
    assert match, "no %global mutter_api_version in mutter.spec"
    assert match.group(1) == "51", (
        f"mutter_api_version={match.group(1)!r}, but mutter 51.beta's own "
        f"meson.build hardcodes libmutter_api_version = '51' -- a stale "
        f"number here names a %{{_libdir}}/mutter-N/ directory the build "
        f"never creates"
    )


def test_the_experimental_schema_is_packaged():
    text = SPEC.read_text(encoding="utf-8")
    assert "%{_datadir}/glib-2.0/schemas/org.gnome.mutter.experimental.gschema.xml" in text, (
        "data/meson.build installs this schema unconditionally at tag "
        "51.beta -- omitting it from %files fails an actual build with "
        "'Installed (but unpackaged) file(s) found'"
    )


def test_the_devkit_schema_stays_packaged():
    """The one that looked fictional and was not. Guards specifically
    against repeating the mistake this fix's own first draft made."""
    text = SPEC.read_text(encoding="utf-8")
    assert "%{_datadir}/glib-2.0/schemas/org.gnome.mutter.devkit.gschema.xml" in text, (
        "mdk/data/meson.build installs this schema whenever have_devkit is "
        "true (auto-enabled once gtk4 and libadwaita are both present, as "
        "they are in this chain) -- removing it from %files devkit fails "
        "an actual build with 'Installed (but unpackaged) file(s) found', "
        "not 'File not found': it IS produced, just left unpackaged"
    )
