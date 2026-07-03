Name: xfce4-clipman-plugin
Version: 1.7.0
Release: 1%{?dist}
Summary: Clipboard manager panel plugin for the Xfce desktop
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/panel-plugins/xfce4-clipman-plugin
Source0: https://archive.xfce.org/src/panel-plugins/xfce4-clipman-plugin/1.7/xfce4-clipman-plugin-%{version}.tar.xz

BuildRequires: gcc
BuildRequires: gtk3-devel
BuildRequires: libxfce4ui-devel
BuildRequires: libxfce4util-devel
BuildRequires: xfce4-panel-devel
BuildRequires: libXtst-devel
BuildRequires: wayland-devel
BuildRequires: intltool
BuildRequires: gettext
BuildRequires: meson
BuildRequires: ninja-build

Requires: xfce4-panel

%description
Clipboard manager panel plugin for the Xfce desktop environment with
Wayland support.

%prep
%autosetup -n xfce4-clipman-plugin-%{version}

%build
%meson -Dwayland=enabled
%meson_build

%install
%meson_install

%files
%license COPYING
%{_bindir}/xfce4-clipman
%{_bindir}/xfce4-clipman-history
%{_libdir}/xfce4/panel/plugins/libclipman.so
%{_datadir}/xfce4/panel/plugins/*.desktop

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 1.7.1-1
- Initial XFCE Wayland package for TunaOS EL10
