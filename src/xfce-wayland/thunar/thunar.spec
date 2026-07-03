%global commit eec4d04e10c66f0a537961f63b435755ef357bf2
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name:           thunar
Version:        4.21.0
Release:        1%{?dist}
Summary:        File manager for the Xfce desktop environment (Wayland)

License:        GPL-2.0-or-later AND LGPL-2.1-or-later
URL:            https://gitlab.xfce.org/xfce/thunar
Source0: https://gitlab.xfce.org/xfce/thunar/-/archive/%{commit}/thunar-%{commit}.tar.gz

BuildRequires: gcc
BuildRequires:  gtk3-devel
BuildRequires:  libxfce4ui-devel
BuildRequires:  libxfce4util-devel
BuildRequires:  garcon-devel
BuildRequires:  xfconf-devel
BuildRequires:  libnotify-devel
BuildRequires:  intltool
BuildRequires:  gettext
BuildRequires:  meson
BuildRequires:  ninja-build

%description
Thunar is the file manager for the Xfce desktop environment. It is designed
to be fast and easy to use. This build is compiled with X11 support disabled
(-Dx11=disabled) for use in pure Wayland sessions on TunaOS EL10.

%package devel
Summary: Development files for %{name} (thunarx plugin API)
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Headers and pkgconfig files for building Thunar (thunarx) plugins.

%prep
%autosetup -n thunar-%{commit}

%build
%meson -Dx11=disabled
%meson_build

%install
%meson_install

%post -p /sbin/ldconfig
%postun -p /sbin/ldconfig

%files
%license COPYING
%{_bindir}/thunar
%{_bindir}/Thunar
%{_bindir}/thunar-bulk-rename
%{_libdir}/libthunar*.so.*
%{_libdir}/thunarx-3/
%{_datadir}/applications/*.desktop

%files devel
%{_includedir}/thunarx-3/
%{_libdir}/pkgconfig/thunarx-3.pc

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 4.21.0-1
- Initial XFCE Wayland package for TunaOS EL10
