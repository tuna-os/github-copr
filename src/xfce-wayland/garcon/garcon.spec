Name: garcon
Version: 4.20.0
Release: 1%{?dist}
Summary: Xfce menu handling library
License: LGPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/garcon
Source0: https://archive.xfce.org/src/xfce/garcon/4.20/garcon-%{version}.tar.bz2
BuildRequires: xfce4-dev-tools
BuildRequires: autoconf automake libtool gettext-devel gtk-doc
BuildRequires: glib2-devel, libxfce4util-devel
BuildRequires: gtk3-devel, libxfce4ui-devel
%description
Menu handling library for the Xfce desktop environment.

%package devel
Summary: Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Headers and pkgconfig files for building against garcon.

%prep
%autosetup -n garcon-%{version}
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
%files
%license COPYING
%{_libdir}/libgarcon*.so.*

%files devel
%{_includedir}/xfce4/garcon-1/
%{_libdir}/libgarcon*.so
%{_libdir}/pkgconfig/*.pc

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - %{version}-%{release}
- Packaged for the XFCE Wayland stack (tuna-os/github-copr#65)

