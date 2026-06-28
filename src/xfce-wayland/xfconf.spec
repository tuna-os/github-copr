Name: xfconf
Version: 4.21.2
Release: 6%{?dist}
Summary: Xfce configuration daemon and library
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/xfconf
Source0: https://gitlab.xfce.org/xfce/xfconf/-/archive/xfconf-4.21.2/xfconf-4.21.2.tar.gz
BuildRequires: glib2-devel, dbus-devel, libxfce4util-devel
BuildRequires: gobject-introspection-devel, vala, intltool, gettext
%description
Xfce configuration daemon and library. Required by all Xfce components.
%prep
%autosetup -n xfconf-%{version}
%build
NOCONFIGURE=1 ./autogen.sh
%configure --disable-gtk-doc
%make_build
%install
%make_install
%files
%license COPYING
%{_libdir}/libxfconf*.so.*
%{_bindir}/xfconfd
%{_bindir}/xfconf-query
