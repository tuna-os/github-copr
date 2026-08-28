"""gtk4's pango floor and libadwaita's gtk4 floor must not go stale again.

Both were pinned below what the packaged release actually needs, which let
the wrong BuildRequires be satisfied instead of failing fast:

  * gtk4.spec pinned pango_version=1.56.0. GTK 4.23.3's own meson.build --
    the exact tag this spec builds -- declares pango_major_req=1,
    pango_minor_req=58 (fetched from gitlab.gnome.org/GNOME/gtk at tag
    4.23.3). Served pango was 1.57, which satisfied the stale 1.56.0 floor,
    so dnf never objected -- gtk4 silently vendored pango as a meson
    subproject instead (the tell: libpangoft2-1.0.so.0.5800.0 in the build
    log) and died under -Werror=unused-but-set-variable in the vendored
    copy. #567 fixed the failure by bumping SYSTEM pango to 1.58.2; this
    guards the spec that should have caught the real requirement itself.

  * libadwaita.spec pinned gtk_version=4.21.1. libadwaita 1.10.beta.1's own
    meson.build -- again the exact tag this spec builds, not main, which
    can have drifted since this beta -- declares
    gtk_min_version = '>= 4.23.1' (fetched from
    gitlab.gnome.org/GNOME/libadwaita at tag 1.10.beta.1).

Both numbers are transcribed from a live upstream fetch at the time this was
written, not derived from anything in this repo -- there is nothing else to
cross-check them against. What this guards is regression: whichever floor a
future spec edit lowers, the corresponding test below catches it before it
can again fall below the version the packaged release actually requires.
"""

from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GTK4_SPEC = ROOT / "src/gnome-51/gtk4/gtk4.spec"
LIBADWAITA_SPEC = ROOT / "src/gnome-51/libadwaita/libadwaita.spec"


def _global_version(spec: pathlib.Path, name: str) -> tuple[int, ...]:
    text = spec.read_text(encoding="utf-8")
    match = re.search(rf"^%global {re.escape(name)}\s+([0-9.]+)", text, re.MULTILINE)
    assert match, f"no %global {name} in {spec}"
    return tuple(int(part) for part in match.group(1).split("."))


def test_gtk4_declares_pangos_real_floor():
    assert _global_version(GTK4_SPEC, "pango_version") >= (1, 58), (
        "GTK 4.23.3's own meson.build requires pango >= 1.58 (pango_major_req=1, "
        "pango_minor_req=58) -- a lower floor here is satisfiable by an older "
        "pango, and gtk4 vendors its own copy instead of failing the BuildRequires"
    )


def test_libadwaita_declares_gtk4s_real_floor():
    assert _global_version(LIBADWAITA_SPEC, "gtk_version") >= (4, 23, 1), (
        "libadwaita 1.10.beta.1's own meson.build requires gtk4 >= 4.23.1 -- a "
        "lower floor here is satisfiable by an older, possibly pango-vendoring gtk4"
    )


@pytest.mark.parametrize(
    "spec,name,stale",
    [
        (GTK4_SPEC, "pango_version", "1.56.0"),
        (LIBADWAITA_SPEC, "gtk_version", "4.21.1"),
    ],
)
def test_the_previously_stale_floor_is_gone(spec, name, stale):
    """The exact values that caused #567's silent vendoring must not come back."""
    text = spec.read_text(encoding="utf-8")
    assert f"%global {name} {stale}" not in text, (
        f"{spec} regressed to the stale {name}={stale} that let gtk4 vendor "
        f"pango instead of failing its BuildRequires"
    )


# Two tools GTK removed between whatever version this spec last built clean
# and 4.23.3, confirmed absent from tools/meson.build and demos/meson.build
# at the exact 4.23.3 tag (no source file, no install rule, no tools/ or
# demos/ subdirectory of that name). A stale %files entry for either fails
# the whole package at the very end of the build with "File not found" --
# reproduced live iterating this chain locally: %files -> gtk4-encode-symbolic-svg
# first, then gtk4-icon-editor plus its org.gtk.Shaper.desktop and
# org.gtk.Shaper*.svg, each one only surfacing after the previous was removed
# and the package rebuilt.
REMOVED_UPSTREAM_FILES = (
    "%{_bindir}/gtk4-encode-symbolic-svg",
    "%{_mandir}/man1/gtk4-encode-symbolic-svg.1*",
    "%{_bindir}/gtk4-icon-editor",
    "%{_datadir}/applications/org.gtk.Shaper.desktop",
    "%{_datadir}/icons/hicolor/*/apps/org.gtk.Shaper*.svg",
)


@pytest.mark.parametrize("stale_file", REMOVED_UPSTREAM_FILES)
def test_gtk4_files_does_not_reference_a_tool_upstream_removed(stale_file):
    text = GTK4_SPEC.read_text(encoding="utf-8")
    assert stale_file not in text, (
        f"{stale_file!r} does not exist in GTK 4.23.3 (verified against "
        f"gitlab.gnome.org/GNOME/gtk tools/meson.build and demos/meson.build "
        f"at that tag) -- referencing it in %files fails the whole package "
        f"build with 'File not found', at the very end of a from-scratch build"
    )
