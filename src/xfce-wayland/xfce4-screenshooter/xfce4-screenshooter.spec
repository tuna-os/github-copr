Name: xfce4-screenshooter
Version: 1.11.1
Release: 1%{?dist}
Summary: Application to take screenshots (Wayland-ready)
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/apps/xfce4-screenshooter
Source0: https://archive.xfce.org/src/apps/xfce4-screenshooter/1.11/xfce4-screenshooter-1.11.1.tar.bz2

BuildRequires: gcc
BuildRequires: gtk3-devel
BuildRequires: libxfce4ui-devel
BuildRequires: libxfce4util-devel
BuildRequires: xfce4-panel-devel
BuildRequires: exo-devel
# libsoup and gexiv2 aren't build dependencies of this version — libsoup was
# dropped upstream (see NEWS), and gexiv2 isn't referenced anywhere in the
# source at all; both were stale guesses.
BuildRequires: intltool
BuildRequires: gettext

Requires: xfce4-panel

%description
Application to take screenshots for the Xfce desktop environment with
Wayland support. This version (1.11.1) predates the meson-based build
system used elsewhere in this stack — it's autotools (configure/make).

%prep
%autosetup -n xfce4-screenshooter-%{version}

%build
%configure
%make_build

%install
%make_install
%find_lang %{name}

%files -f %{name}.lang
%license COPYING
%{_bindir}/xfce4-screenshooter
%{_libdir}/xfce4/panel/plugins/libscreenshooterplugin.so
%{_libexecdir}/xfce4/screenshooter/
%{_datadir}/applications/*.desktop
%{_datadir}/xfce4/panel/plugins/*.desktop
%{_datadir}/icons/hicolor/*/apps/org.xfce.screenshooter.*
%{_datadir}/man/man1/*
%{_datadir}/metainfo/*.xml

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 1.11.3-1
- Initial XFCE Wayland package for TunaOS EL10
