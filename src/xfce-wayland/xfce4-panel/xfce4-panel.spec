%global commit 3467f08522846be0ba294c867f456eaf74274dbd
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name:           xfce4-panel
Version:        4.21.0
Release:        1%{?dist}
Summary:        Panel for the Xfce desktop environment (Wayland-ready)

License:        GPL-2.0-or-later AND LGPL-2.1-or-later
URL:            https://gitlab.xfce.org/xfce/xfce4-panel
Source0:        https://gitlab.xfce.org/xfce/xfce4-panel/-/archive/xfce4-panel-4.21.0/xfce4-panel-4.21.0.tar.gz

BuildRequires:  gtk3-devel
BuildRequires:  libxfce4ui-devel
BuildRequires:  libxfce4util-devel
BuildRequires:  libxfce4windowing-devel
BuildRequires:  garcon-devel
BuildRequires:  gobject-introspection-devel
BuildRequires:  vala
BuildRequires:  intltool
BuildRequires:  gettext
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  gtk-layer-shell-devel

Requires:       libxfce4ui
Requires:       libxfce4windowing
Requires:       garcon
Requires:       gtk-layer-shell

%description
The Xfce4 panel is the taskbar/launcher for the Xfce desktop environment.
This build targets Wayland compositors via gtk-layer-shell and supports
the xfce4-panel 4.21.x development series.

%prep
%autosetup -n xfce4-panel-%{commit}

%build
%meson
%meson_build

%install
%meson_install

%files
%license COPYING
%{_bindir}/xfce4-panel
%{_libdir}/libxfce4panel*.so.*
%{_libdir}/pkgconfig/libxfce4panel-2.0.pc
%{_libdir}/xfce4/panel/
%{_datadir}/applications/*.desktop
%{_datadir}/xfce4/panel/

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 4.21.0-1
- Initial XFCE Wayland package for TunaOS EL10
