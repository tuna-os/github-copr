%global commit f6e83d2c95a7adf58cf62b5b69c50ac11a51a2d9
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name: xfce4-power-manager
Version: 4.21.1
Release: 1%{?dist}
Summary: Power manager for the Xfce desktop environment (Wayland)
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/xfce4-power-manager
Source0: https://gitlab.xfce.org/xfce/xfce4-power-manager/-/archive/%{commit}/xfce4-power-manager-%{commit}.tar.gz

BuildRequires: gtk3-devel
BuildRequires: libxfce4ui-devel
BuildRequires: libxfce4util-devel
BuildRequires: libxfce4windowing-devel
BuildRequires: xfconf-devel
BuildRequires: xfce4-panel-devel
BuildRequires: upower-devel
BuildRequires: polkit-devel
BuildRequires: wayland-devel
BuildRequires: wayland-protocols-devel
BuildRequires: intltool
BuildRequires: gettext
BuildRequires: meson
BuildRequires: ninja-build

Requires: upower
Requires: polkit
Requires: libxfce4windowing

%description
Power manager for the Xfce desktop environment with Wayland support.

%prep
%autosetup -n xfce4-power-manager-%{commit}

%build
%meson -Dwayland=enabled
%meson_build

%install
%meson_install

%files
%license COPYING
%{_bindir}/xfce4-power-manager
%{_bindir}/xfce4-power-manager-settings
%{_libexecdir}/xfce4/xfce4-power-manager
%{_datadir}/applications/*.desktop

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 4.21.1-1
- Initial XFCE Wayland package for TunaOS EL10
