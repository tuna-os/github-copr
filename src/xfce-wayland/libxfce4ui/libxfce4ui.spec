%global commit c07644b91e627341452c881392bf417d4dbc0031
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name: libxfce4ui
Version: 4.21.7
Release: 70%{?dist}
Summary: Common UI library for Xfce
License: LGPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/libxfce4ui
Source0: https://gitlab.xfce.org/xfce/libxfce4ui/-/archive/%{commit}/libxfce4ui-%{commit}.tar.gz
BuildRequires: xfce4-dev-tools
BuildRequires: autoconf automake libtool gettext-devel
BuildRequires: gtk3-devel, libxfce4util-devel, xfconf-devel
BuildRequires: gobject-introspection-devel, vala, intltool, gettext
%description
Common UI library for Xfce desktop environment.
%prep
%autosetup -n libxfce4ui-%{commit}
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
