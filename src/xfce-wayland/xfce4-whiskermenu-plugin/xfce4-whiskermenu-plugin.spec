Name: xfce4-whiskermenu-plugin
Version: 2.10.1
Release: 1%{?dist}
Summary: Whisker menu launcher plugin for the Xfce panel
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/panel-plugins/xfce4-whiskermenu-plugin
Source0: https://archive.xfce.org/src/panel-plugins/xfce4-whiskermenu-plugin/2.10/xfce4-whiskermenu-plugin-%{version}.tar.xz

BuildRequires: gcc
BuildRequires: gcc-c++
BuildRequires: gtk3-devel
BuildRequires: garcon-devel
BuildRequires: xfce4-panel-devel
BuildRequires: libxfce4ui-devel
BuildRequires: exo-devel
BuildRequires: libxfce4util-devel
BuildRequires: xfconf-devel
BuildRequires: accountsservice-devel
BuildRequires: gtk-layer-shell-devel
BuildRequires: gettext
BuildRequires: meson
BuildRequires: ninja-build

Requires: xfce4-panel

%description
Whisker menu launcher plugin for the Xfce panel with Wayland support.

%prep
%autosetup -n xfce4-whiskermenu-plugin-%{version}

%build
%meson
%meson_build

%install
%meson_install
%find_lang %{name}

%files -f %{name}.lang
%license COPYING
%{_bindir}/xfce4-popup-whiskermenu
%{_libdir}/xfce4/panel/plugins/libwhiskermenu.so
%{_datadir}/xfce4/panel/plugins/*.desktop
%{_datadir}/icons/hicolor/*/apps/org.xfce.whiskermenu*

%changelog
* Sat Jul 26 2026 TunaOS Bot <bot@tunaos.org> - 2.10.1-1
- Initial XFCE Wayland package for TunaOS EL10
