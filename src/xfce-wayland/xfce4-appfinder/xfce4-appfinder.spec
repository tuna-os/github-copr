%global commit 1ce6be94d8bc0abdd8fd565a55133a1be90496b8
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name: xfce4-appfinder
Version: 4.21.1
Release: 1%{?dist}
Summary: Application finder for the Xfce desktop environment
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/xfce4-appfinder
Source0: https://gitlab.xfce.org/xfce/xfce4-appfinder/-/archive/%{commit}/xfce4-appfinder-%{commit}.tar.gz

BuildRequires: gcc
BuildRequires: gtk3-devel
BuildRequires: libxfce4ui-devel
BuildRequires: libxfce4util-devel
BuildRequires: garcon-devel
BuildRequires: intltool
BuildRequires: gettext
BuildRequires: meson
BuildRequires: ninja-build

Requires: garcon

%description
Application finder for the Xfce desktop environment.

%prep
%autosetup -n xfce4-appfinder-%{commit}

%build
%meson
%meson_build

%install
%meson_install

%files
%license COPYING
%{_bindir}/xfce4-appfinder
%{_bindir}/xfce4-run
%{_datadir}/applications/*.desktop

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 4.21.1-1
- Initial XFCE Wayland package for TunaOS EL10
