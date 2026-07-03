Name: garcon
Version: 4.20.0
Release: 1%{?dist}
Summary: Xfce menu handling library
License: LGPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/garcon
Source0: https://archive.xfce.org/src/xfce/garcon/4.20/garcon-%{version}.tar.bz2
BuildRequires: autoconf automake libtool gettext-devel
BuildRequires: glib2-devel, libxfce4util-devel
%description
Menu handling library for the Xfce desktop environment.
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
