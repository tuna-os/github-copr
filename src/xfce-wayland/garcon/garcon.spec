Name: garcon
Version: 4.20.0
Release: 1%{?dist}
Summary: Xfce menu handling library
License: LGPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/garcon
Source0: https://gitlab.xfce.org/xfce/garcon/-/archive/garcon-4.20.0/garcon-4.20.0.tar.gz
BuildRequires: glib2-devel, libxfce4util-devel
%description
Menu handling library for the Xfce desktop environment.
%prep
%autosetup -n garcon-%{version}
%build
NOCONFIGURE=1 ./autogen.sh
%configure --disable-gtk-doc
%make_build
%install
%make_install
%files
%license COPYING
%{_libdir}/libgarcon*.so.*
