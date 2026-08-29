"""gdm.spec must not carry build dependencies GDM itself dropped upstream.

Our copy of gdm.spec was hand-maintained since GNOME 51 packaging started
(#320) and had drifted from Fedora Rawhide's own gdm.spec in ways nobody
had re-checked since -- unlike the sibling GNOME 51 packages that already
got a from-Rawhide refork this session (xdg-desktop-portal, flatpak,
glib2, gnome-control-center, etc.).

Fetched Rawhide's live spec (src.fedoraproject.org/rpms/gdm/raw/rawhide)
and diffed it fully against ours. Two concrete pieces of staleness:

1. `%define gtk3_version 2.99.2`, `BuildRequires: pkgconfig(gtk+-3.0) >=
   %{gtk3_version}`, and the `%if !0%{?rhel} BuildRequires:
   pkgconfig(libcanberra-gtk3) %endif` block are all gone from Rawhide's
   current spec (read in full, not just diffed). Cross-checked against
   gitlab.gnome.org/GNOME/gdm's meson.build (main branch, fetched live,
   323 lines): there is no "gtk" or "canberra" token anywhere in it --
   GDM no longer builds any GTK3 UI itself (the greeter is gnome-shell's
   job; gdm's own X11 fallback UI was removed when it went wayland-only).
   These BuildRequires were pure drift with no effect other than pulling
   in a dependency the build no longer touches. A real local build with
   them removed (build-chain.sh, podman+mock, hummingbird-ci/.fc43)
   produced all 5 expected RPMs.

2. The hand-rolled `meson setup ... ; ninja -C _build` / `ninja -C _build
   install` in %build/%install predates the %meson/%meson_build/
   %meson_install macro family that Rawhide's current spec uses instead
   (same options, same behavior, already proven working elsewhere in this
   tree -- gnome-online-accounts, xdg-desktop-portal).

What did NOT change, because Rawhide's own spec still carries them
unmodified byte-for-byte (diffed against the live fetch):
  - all three downstream patches (Honor-initial-setup-being-disabled,
    data-add-system-dconf-databases, Add-headless-session-files)
  - org.gnome.login-screen.gschema.override and gdm.sysusers
  - the #580 el10-compat Requires fix (93305ee) -- Rawhide has no concept
    of gnome50-el10-compat at all, so there is nothing to adopt from it;
    the gap this fix closed is hummingbird-local and stays hummingbird-local
  - the %files pam.d glob (35bee73) -- kept over Rawhide's literal file
    enumeration (which has grown from six names to ten since this glob
    was written); the built RPM was inspected directly (`rpm -qlp`) and
    all ten of Rawhide's current names are covered by the glob as-is
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "src/gnome-51/gdm/gdm.spec"


def _spec_text() -> str:
    return SPEC.read_text(encoding="utf-8")


def test_no_gtk3_build_dependency():
    text = _spec_text()
    assert "gtk+-3.0" not in text, (
        "gdm.spec still requires pkgconfig(gtk+-3.0) -- GDM dropped its "
        "GTK3 usage entirely (verified against gitlab.gnome.org/GNOME/gdm "
        "meson.build, which has no gtk/canberra references at all)"
    )
    assert "libcanberra-gtk3" not in text, (
        "gdm.spec still requires pkgconfig(libcanberra-gtk3), a GTK3-era "
        "dependency GDM no longer builds against"
    )
    assert "gtk3_version" not in text, (
        "gdm.spec still defines an unused gtk3_version macro"
    )


def test_build_install_use_the_standard_meson_macros():
    text = _spec_text()
    assert "%meson " in text or "%meson\n" in text, (
        "gdm.spec should use the %meson macro (matches Rawhide's current "
        "spec) instead of a hand-rolled `meson setup` invocation"
    )
    assert "%meson_build" in text
    assert "%meson_install" in text
    assert "ninja -C" not in text, (
        "gdm.spec still hand-invokes ninja instead of using "
        "%meson_build/%meson_install"
    )


def test_all_three_downstream_patches_are_kept():
    text = _spec_text()
    patches = [
        "0001-Honor-initial-setup-being-disabled-by-distro-install.patch",
        "0001-data-add-system-dconf-databases-to-gdm-profile.patch",
        "0001-Add-headless-session-files.patch",
    ]
    for patch in patches:
        assert patch in text, (
            f"{patch} should still be applied -- Fedora Rawhide's own "
            "gdm.spec still carries this patch unmodified"
        )
        assert (ROOT / "src/gnome-51/gdm" / patch).exists(), (
            f"{patch} is referenced by the spec but missing from the tree"
        )


def test_el10_compat_fix_from_pr_580_survives():
    """#580 (93305ee) made gnome50-el10-compat conditional on %{?rhel}
    because it only exists in build-order-gnome51.yml's deps, not
    build-order-hummingbird-desktops.yml, and was breaking dnf5 builddep
    on the hummingbird (Fedora Rawhide) target unconditionally. Rawhide's
    own spec has no equivalent -- gnome50-el10-compat is a hummingbird/
    EL10-only package -- so there is nothing upstream to adopt instead;
    the explicit guard must stay.
    """
    text = _spec_text()
    assert "gnome50-el10-compat" in text
    assert "%if 0%{?rhel}\nRequires:       gnome50-el10-compat\n%endif" in text, (
        "the gnome50-el10-compat Requires must stay guarded behind "
        "%{?rhel}, or it will again break dnf5 builddep on hummingbird"
    )
