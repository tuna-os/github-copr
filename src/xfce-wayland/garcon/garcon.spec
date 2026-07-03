Name: garcon
Version: 4.20.0
Release: 1%{?dist}
Summary: Xfce menu handling library
License: LGPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/garcon
Source0: https://archive.xfce.org/src/xfce/garcon/4.20/garcon-%{version}.tar.bz2
BuildRequires: glib2-devel, libxfce4util-devel
%description
Menu handling library for the Xfce desktop environment.
%prep
%autosetup -n garcon-%{version}
%build
%configure --disable-gtk-doc
%make_build
%install
%make_install
%files
%license COPYING
%{_libdir}/libgarcon*.so.*
