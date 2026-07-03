%global commit c07644b91e627341452c881392bf417d4dbc0031
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name: libxfce4ui
Version: 4.21.7
Release: 70%{?dist}
Summary: Common UI library for Xfce
License: LGPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/libxfce4ui
Source0: https://gitlab.xfce.org/xfce/libxfce4ui/-/archive/%{commit}/libxfce4ui-%{commit}.tar.gz
BuildRequires: gcc, meson, ninja-build
BuildRequires: gtk3-devel, libxfce4util-devel, xfconf-devel
BuildRequires: libSM-devel
BuildRequires: startup-notification-devel
BuildRequires: libgtop2-devel, libepoxy-devel, libgudev-devel
BuildRequires: gobject-introspection-devel, vala, intltool, gettext
%description
Common UI library for Xfce desktop environment.

%package devel
Summary: Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Headers, pkgconfig, GObject-Introspection typelib, and Vala bindings for
building against libxfce4ui.

%prep
%autosetup -n libxfce4ui-%{commit}

# This commit has fully migrated to meson (no configure.ac/autogen.sh).
%build
%meson
%meson_build

%install
%meson_install

%files
%license COPYING
%{_libdir}/libxfce4ui*.so.*

%files devel
%{_includedir}/xfce4/libxfce4ui/
%{_includedir}/xfce4/libxfce4kbd-private/
%{_libdir}/libxfce4ui*.so
%{_libdir}/libxfce4kbd-private*.so
%{_libdir}/pkgconfig/*.pc
%{_libdir}/girepository-1.0/*.typelib
%{_datadir}/gir-1.0/*.gir
%{_datadir}/vala/vapi/*

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - %{version}-%{release}
- Packaged for the XFCE Wayland stack (tuna-os/github-copr#65)

