Name: xfce4-dev-tools
Version: 4.20.0
Release: 1%{?dist}
Summary: Xfce developer tools (xdt-autogen, m4 macros)
License: GPL-2.0-or-later
URL: https://docs.xfce.org/xfce/xfce4-dev-tools/start
Source0: https://archive.xfce.org/src/xfce/xfce4-dev-tools/4.20/xfce4-dev-tools-%{version}.tar.bz2

BuildRequires: gcc
BuildRequires: make
BuildRequires: glib2-devel
BuildRequires: libxslt
BuildRequires: autoconf automake libtool gettext-devel
Requires: autoconf automake libtool gettext-devel

%description
Autotools helper scripts and m4 macros (xdt-autogen) required to bootstrap
Xfce components built from git snapshots rather than dist tarballs.

%prep
%autosetup -n xfce4-dev-tools-%{version}

%build
%configure
%make_build

%install
%make_install

%files
%license COPYING
%{_bindir}/xdt-*
%{_datadir}/aclocal/*.m4
%{_datadir}/xfce4/dev-tools/
%{_mandir}/man1/xdt-csource.1*

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 4.20.0-1
- Initial package: build-time bootstrap for git-snapshot Xfce components
