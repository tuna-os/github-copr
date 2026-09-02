"""gnome-shell's %build option and %files list must match gnome-shell 51.beta's real build.

Two distinct bugs surfaced iterating this chain locally, one after the
other (fixing the first only exposed the second):

  1. %build passed `-Dextensions_app=false`. gnome-shell 51.beta's own
     meson.options (fetched from gitlab.gnome.org/GNOME/gnome-shell at that
     tag) has no such option -- it was renamed to `extensions_tool`
     (default true), which gates building the `gnome-extensions` CLI tool
     (subproject('extensions-tool', ...) in meson.build). The spec's own
     %files already expects that tool to exist (%{_bindir}/gnome-extensions,
     its bash-completion, its man page, plus a comment "for gnome-extensions
     CLI tool"), so the old flag was wrong on both the option name and the
     value. Failed with:
       meson.build:1:0: ERROR: Unknown option: "extensions_app".

  2. Once past that, %files was missing org.gnome.Shell.CalendarServer.desktop.
     data/meson.build installs it unconditionally -- unlike
     org.gnome.Shell.PortalHelper.desktop, which IS gated behind
     have_portal_helper and correctly wrapped in %if %{portal_helper}
     elsewhere in this same spec. Failed with:
       error: Installed (but unpackaged) file(s) found:
          /usr/share/applications/org.gnome.Shell.CalendarServer.desktop

Both independently cross-checked against Fedora's rawhide dist-git spec
(src.fedoraproject.org/rpms/gnome-shell/raw/rawhide/f/gnome-shell.spec),
which reaches the same place from a different angle: it never sets
extensions_tool/extensions_app at all (relying on the upstream default,
same effect as fix 1), and lists CalendarServer.desktop unconditionally in
%files, exactly where fix 2 puts it.

Verified by a real, from-scratch rebuild after both fixes: gnome-shell
51~beta-1 built clean with all subpackages.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "src/gnome-51/gnome-shell/gnome-shell.spec"


def test_extensions_tool_is_enabled_and_the_old_option_name_is_gone():
    text = SPEC.read_text(encoding="utf-8")
    assert "-Dextensions_tool=true" in text, (
        "gnome-shell 51.beta's meson.options renamed extensions_app to "
        "extensions_tool -- omitting/disabling it fails meson configure "
        "with 'Unknown option: extensions_app', or (if reverted to the "
        "renamed-but-false form) silently skips building the "
        "gnome-extensions CLI tool that %files expects to exist"
    )
    assert "extensions_app" not in text, (
        "extensions_app reappeared -- gnome-shell 51.beta has no such "
        "meson option, it was renamed to extensions_tool"
    )


def test_calendarserver_desktop_is_packaged_unconditionally():
    text = SPEC.read_text(encoding="utf-8")
    assert "%{_datadir}/applications/org.gnome.Shell.CalendarServer.desktop" in text, (
        "data/meson.build installs this file unconditionally at gnome-shell "
        "51.beta -- omitting it fails the build with 'Installed (but "
        "unpackaged) file(s) found'"
    )
    # It must NOT be inside the portal_helper conditional block -- that only
    # gates the separate PortalHelper desktop/service/icons.
    portal_block = text[text.index("%if %{portal_helper}"):text.index("%endif", text.index("%if %{portal_helper}"))]
    assert "CalendarServer" not in portal_block, (
        "org.gnome.Shell.CalendarServer.desktop must be packaged "
        "unconditionally, not gated behind %if %{portal_helper} -- "
        "data/meson.build installs it regardless of have_portal_helper"
    )
