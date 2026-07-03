%global commit a6f0a7aa9073f9d8a0935cee73c0da52b6e49660
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name: xfconf
Version: 4.21.2
Release: 6%{?dist}
Summary: Xfce configuration daemon and library
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/xfconf
Source0: https://gitlab.xfce.org/xfce/xfconf/-/archive/%{commit}/xfconf-%{commit}.tar.gz
BuildRequires: gcc, meson, ninja-build
BuildRequires: glib2-devel, dbus-devel, libxfce4util-devel
BuildRequires: gobject-introspection-devel, vala, intltool, gettext
%description
Xfce configuration daemon and library. Required by all Xfce components.

%package devel
Summary: Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Headers, pkgconfig, GObject-Introspection typelib, and Vala bindings for
building against xfconf.

%prep
%autosetup -n xfconf-%{commit}

# This commit has fully migrated to meson (no configure.ac/autogen.sh at
# all) — xfce4-dev-tools/autotools BuildRequires from the old spec are
# gone; gtk-doc defaults to false in meson_options.txt already.
%build
%meson
%meson_build

%install
%meson_install

%files
%license COPYING
%{_libdir}/libxfconf*.so.*
%{_libdir}/xfce4/xfconf/xfconfd
%{_bindir}/xfconf-query
%{_prefix}/lib/systemd/user/xfconfd.service
%{_datadir}/dbus-1/services/*.service

%files devel
%{_includedir}/xfce4/xfconf/
%{_libdir}/libxfconf*.so
%{_libdir}/pkgconfig/*.pc
%{_libdir}/girepository-1.0/*.typelib
%{_datadir}/gir-1.0/*.gir
%{_datadir}/vala/vapi/*

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - %{version}-%{release}
- Packaged for the XFCE Wayland stack (tuna-os/github-copr#65)

