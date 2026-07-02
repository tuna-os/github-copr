Name: xfce4-screenshooter
Version: 1.11.3
Release: 1%{?dist}
Summary: Application to take screenshots (Wayland-ready)
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/apps/xfce4-screenshooter
Source0: https://gitlab.xfce.org/apps/xfce4-screenshooter/-/archive/xfce4-screenshooter-1.11.3/xfce4-screenshooter-1.11.3.tar.gz

BuildRequires: gtk3-devel
BuildRequires: libxfce4ui-devel
BuildRequires: libxfce4util-devel
BuildRequires: xfce4-panel-devel
BuildRequires: libsoup-devel
BuildRequires: gexiv2-devel
BuildRequires: intltool
BuildRequires: gettext
BuildRequires: meson
BuildRequires: ninja-build

Requires: xfce4-panel

%description
Application to take screenshots for the Xfce desktop environment with
Wayland support.

%prep
%autosetup -n xfce4-screenshooter-%{version}

%build
%meson -Dwayland=enabled
%meson_build

%install
%meson_install

%files
%license COPYING
%{_bindir}/xfce4-screenshooter
%{_libdir}/xfce4/panel/plugins/libscreenshooter.so
%{_datadir}/applications/*.desktop
%{_datadir}/xfce4/panel/plugins/*.desktop

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 1.11.3-1
- Initial XFCE Wayland package for TunaOS EL10
