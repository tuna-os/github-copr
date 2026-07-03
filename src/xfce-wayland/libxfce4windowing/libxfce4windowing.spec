Name: libxfce4windowing
Version: 4.20.6
Release: 1%{?dist}
Summary: X11/Wayland windowing abstraction for Xfce
License: LGPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/libxfce4windowing
Source0: https://archive.xfce.org/src/xfce/libxfce4windowing/4.20/libxfce4windowing-%{version}.tar.bz2
BuildRequires: gcc, gtk3-devel, libxfce4util-devel, wayland-devel
BuildRequires: wayland-protocols-devel
%description
Windowing abstraction library for Xfce that handles both X11 and Wayland.
Required by xfce4-panel, xfdesktop, and other Wayland-aware components.
%prep
%autosetup -n libxfce4windowing-%{version}
%build
%meson
%meson_build
%install
%meson_install
%files
%license COPYING
%{_libdir}/libxfce4windowing*.so.*

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - %{version}-%{release}
- Packaged for the XFCE Wayland stack (tuna-os/github-copr#65)

