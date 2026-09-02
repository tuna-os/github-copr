"""gnome-online-accounts must package the two goa-daemon files its own
%files glob does not reach.

Both confirmed real and unconditionally installed against
gitlab.gnome.org/GNOME/gnome-online-accounts at tag 3.58.1:

  * data/meson.build's i18n.merge_file() installs
    org.gnome.goa-daemon.desktop to applications/ with no surrounding
    `if` -- the spec never packaged it at all.
  * data/icons/meson.build's icon_symbolic_data always includes
    org.gnome.goa-daemon-symbolic.svg (only the goa-account-* variants are
    gated behind `if enable_goabackend`) -- the spec's existing
    `%{_datadir}/icons/hicolor/*/apps/goa-*.svg` glob does not match it,
    since the real filename starts with `org.gnome.`, not `goa-`.

Confirmed by an actual build:

    error: Installed (but unpackaged) file(s) found:
       /usr/share/applications/org.gnome.goa-daemon.desktop
       /usr/share/icons/hicolor/symbolic/apps/org.gnome.goa-daemon-symbolic.svg
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "src/gnome-51/gnome-online-accounts/gnome-online-accounts.spec"


def test_the_goa_daemon_desktop_file_is_packaged():
    text = SPEC.read_text(encoding="utf-8")
    assert "%{_datadir}/applications/org.gnome.goa-daemon.desktop" in text, (
        "data/meson.build installs this unconditionally at tag 3.58.1 -- "
        "omitting it fails an actual build with 'Installed (but "
        "unpackaged) file(s) found'"
    )


def test_the_goa_daemon_symbolic_icon_is_packaged():
    text = SPEC.read_text(encoding="utf-8")
    assert "%{_datadir}/icons/hicolor/*/apps/org.gnome.goa-daemon-symbolic.svg" in text, (
        "data/icons/meson.build installs this unconditionally -- the "
        "spec's own goa-*.svg glob does not match its org.gnome.* prefix, "
        "so it needs its own %files line"
    )
