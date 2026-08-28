%global glib2_version 2.80
%global gtk4_version 4.14
%global vte291_version 0.77
%global json_glib_version 1.6
%global libadwaita_version 1.6
%global libportal_gtk4_version 0.7.1

# Genuine delta vs Rawhide: compute the tarball/major version ourselves
# instead of relying on %%gnome_tarball_version / %%gnome_major_version
# (defined by Fedora's redhat-rpm-config macros.gnome). Same output, no
# dependency on an external macro file we don't control the availability
# of on every buildroot this repo targets.
%global tarball_version %%(echo %%{version} | tr '~' '.')
%global major_version %%(echo %%{tarball_version} | cut -d "." -f 1)

Name:		ptyxis
Version:	50.1
Release:	%autorelease
Summary:	A container oriented terminal for GNOME

License:	GPL-2.0-or-later AND GPL-3.0-or-later AND LGPL-3.0-or-later AND LGPL-2.0-or-later AND CC0-1.0
URL:		https://gitlab.gnome.org/chergert/ptyxis
Source0:	https://download.gnome.org/sources/%{name}/%{major_version}/%{name}-%{tarball_version}.tar.xz
# Fedora branding-flavored gschema override (a11y on, dark theme by default).
# Kept under its upstream Fedora name and installed byte-identical to
# Rawhide's own Source1/%%files entries: its content isn't Fedora-branded
# (no logos/colors, just sane defaults we also want), so renaming it would
# only create a permanent divergence to re-reconcile on every future sync
# for no functional gain.
Source1:	org.gnome.Ptyxis.fedora.gschema.override

BuildRequires:	pkgconfig(gio-unix-2.0) >= %{glib2_version}
BuildRequires:	pkgconfig(gtk4) >= %{gtk4_version}
BuildRequires:	pkgconfig(vte-2.91-gtk4) >= %{vte291_version}
BuildRequires:	pkgconfig(libadwaita-1) >= %{libadwaita_version}
BuildRequires:  pkgconfig(libportal-gtk4) >= %{libportal_gtk4_version}
BuildRequires:	pkgconfig(json-glib-1.0) >= %{json_glib_version}
BuildRequires:	desktop-file-utils
BuildRequires:	gcc
# Genuine delta vs Rawhide: msgfmt (from gettext) is pulled in transitively
# on Fedora's own buildroot, but was added here deliberately in the
# original EL10 fork (8e40c19: "provides msgfmt; implicit on Fedora, absent
# on EL10") for a real observed gap on a real EL10 chroot. The active
# hummingbird-ci config happens to be Rawhide-based today so the gap isn't
# currently exercised, but this spec's own %check/%files don't guarantee
# that stays true, and a missing msgfmt fails silently -- %find_lang just
# emits an empty .lang file instead of erroring, so the build would still
# go green while shipping zero translations. Same call this repo already
# made for flatpak's redundant gcc/gcc-c++ BRs: zero-cost to keep, real
# cost to drop and be wrong.
BuildRequires:	gettext
BuildRequires:	itstool
BuildRequires:	meson
BuildRequires:	/usr/bin/appstream-util

Requires:	hicolor-icon-theme

# https://fedoraproject.org/wiki/Changes/EncourageI686LeafRemoval
ExcludeArch:	%{ix86}

%description
Ptyxis is a container oriented terminal that provides transparent support for
container systems like Podman, Distrobox, and Toolbx. It also has robust
support for user profiles.


%prep
# Genuine delta vs Rawhide: same check %%gnome_check_version performs
# (alpha/beta/rc must use a tilde, not a dot, in Version), spelled out so
# %%prep doesn't depend on macros.gnome being present -- see the
# tarball/major_version comment above for why we don't lean on that file.
if [ `echo "%{version}" | grep -cE "\.alpha|\.beta|\.rc"` = "1" ]; then echo "Error: Use tilde in Version field in front of alpha/beta/rc; checked '%{version}'" 1>&2; exit 1; fi

%autosetup -p1 -n %{name}-%{tarball_version}


%build
# Genuine delta vs Rawhide: explicit meson invocation instead of the
# %%meson/%%meson_build macros. This spec already did it this way before
# this fork, matching the same fix applied to glib2, gjs and gtk4 in this
# repo (see their %%changelog) after %%meson_build's internal job-control
# (`fg`) tripped "fg: no job control" on non-interactive COPR builders.
# xdg-desktop-portal went the other way and adopted %%meson_build cleanly
# under our own mock+podman build-chain.sh, so that failure mode may be
# COPR-specific rather than universal -- but the explicit form here is
# already verified working end-to-end (real build, %%check passing), so
# there's no reason to trade a working, portable build step for a macro
# whose safety in every environment this repo might build under is
# unconfirmed.
meson setup --prefix=%{_prefix} --libdir=%{_libdir} --buildtype=plain build -Dgeneric=terminal
meson compile -C build


%install
DESTDIR=%{buildroot} meson install -C build
install -p %{SOURCE1} %{buildroot}%{_datadir}/glib-2.0/schemas
%find_lang %{name} --with-gnome


%check
appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/org.gnome.Ptyxis.metainfo.xml
desktop-file-validate %{buildroot}%{_datadir}/applications/org.gnome.Ptyxis.desktop


%files -f %{name}.lang
%doc README.md NEWS
%license COPYING
%{_bindir}/ptyxis
%{_libexecdir}/ptyxis-agent
%{_metainfodir}/org.gnome.Ptyxis.metainfo.xml
%{_datadir}/applications/org.gnome.Ptyxis.desktop
%dir %{_datadir}/dbus-1
%dir %{_datadir}/dbus-1/services
%{_datadir}/dbus-1/services/org.gnome.Ptyxis.service
%{_datadir}/glib-2.0/schemas/org.gnome.Ptyxis.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.Ptyxis.fedora.gschema.override
%{_datadir}/icons/hicolor/*/*/*.svg
%{_mandir}/man1/ptyxis.1*

%changelog
%autochangelog
