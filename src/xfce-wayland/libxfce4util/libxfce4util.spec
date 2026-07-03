%global _hardened_build 1

Name:           libxfce4util
Version:        4.20.1
Release:        17%{?dist}
Summary:        Basic utility library for Xfce4

License:        LGPL-2.0-or-later
URL:            https://gitlab.xfce.org/xfce/libxfce4util
Source0: https://archive.xfce.org/src/xfce/libxfce4util/4.20/libxfce4util-%{version}.tar.bz2

%if 0%{?rhel} >= 10
BuildRequires: xfce4-dev-tools
BuildRequires: autoconf automake libtool gettext-devel
BuildRequires:  glib2-devel
BuildRequires:  gobject-introspection-devel
BuildRequires:  vala
BuildRequires:  intltool
BuildRequires:  gettext
BuildRequires:  gtk-doc
%else
BuildRequires:  glib2-devel
BuildRequires:  gobject-introspection-devel
BuildRequires:  vala
BuildRequires:  intltool
%endif

Requires:       glib2%{?_isa}

%description
Basic utility library for the Xfce desktop environment.
Required by all other Xfce components.

%package devel
Summary: Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Headers, pkgconfig, GObject-Introspection typelib, and Vala bindings for
building against libxfce4util.

%prep
%autosetup -n libxfce4util-%{version}

# The dist tarball bundles a configure script generated against an
# older libtool than EL10 ships; its nm-output parsing predates current
# binutils and mis-detects (breaks with a bogus command in the symbol
# pipe). Regenerating against the system libtool fixes it.
%build
autoreconf -fi
%configure --disable-gtk-doc
%make_build

%install
%make_install

%post -p /sbin/ldconfig
%postun -p /sbin/ldconfig

%files
%license COPYING
%doc AUTHORS ChangeLog NEWS
%{_libdir}/libxfce4util.so.*

%files devel
%{_includedir}/xfce4/libxfce4util/
%{_libdir}/libxfce4util.so
%{_libdir}/pkgconfig/libxfce4util*.pc
%{_libdir}/girepository-1.0/Xfce4util*.typelib
%{_datadir}/gir-1.0/Xfce4util*.gir
%{_datadir}/vala/vapi/libxfce4util*.vapi

%changelog
* Sat Jun 27 2026 TunaOS Bot <bot@tunaos.org> - 4.20.1-17
- Initial XFCE Wayland package for TunaOS
