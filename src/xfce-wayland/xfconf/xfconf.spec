%global commit a6f0a7aa9073f9d8a0935cee73c0da52b6e49660
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name: xfconf
Version: 4.21.2
Release: 6%{?dist}
Summary: Xfce configuration daemon and library
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/xfconf
Source0: https://gitlab.xfce.org/xfce/xfconf/-/archive/%{commit}/xfconf-%{commit}.tar.gz
BuildRequires: xfce4-dev-tools
BuildRequires: autoconf automake libtool gettext-devel
BuildRequires: glib2-devel, dbus-devel, libxfce4util-devel
BuildRequires: gobject-introspection-devel, vala, intltool, gettext
%description
Xfce configuration daemon and library. Required by all Xfce components.
%prep
%autosetup -n xfconf-%{commit}
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

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - %{version}-%{release}
- Packaged for the XFCE Wayland stack (tuna-os/github-copr#65)

