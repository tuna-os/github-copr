Name: libxfce4ui
Version: 4.21.7
Release: 70%{?dist}
Summary: Common UI library for Xfce
License: LGPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/libxfce4ui
Source0: libxfce4ui-%{version}.tar.bz2
BuildRequires: gtk3-devel, libxfce4util-devel, xfconf-devel
BuildRequires: gobject-introspection-devel, vala, intltool, gettext
%description
Common UI library for Xfce desktop environment.
%prep
%autosetup -n libxfce4ui-%{version}
%build
NOCONFIGURE=1 ./autogen.sh
%configure --disable-gtk-doc
%make_build
%install
%make_install
%files
%license COPYING
%{_libdir}/libxfce4ui*.so.*
%{_libdir}/libxfce4ui-%{version}/
