Name: exo
Version: 4.21.0
Release: 1%{?dist}
Summary: Application development library for the Xfce desktop environment
License: LGPL-2.1-or-later AND GPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/exo
# Use the official release tarball, not a GitLab git-archive URL — git
# archives don't include the generated configure script (autotools doesn't
# track it in git), so %%configure would fail with "No such file".
Source0: https://archive.xfce.org/src/xfce/exo/4.21/exo-%{version}.tar.bz2

BuildRequires: gcc
BuildRequires: make
BuildRequires: gtk3-devel
BuildRequires: libxfce4util-devel
BuildRequires: libxfce4ui-devel
BuildRequires: intltool
BuildRequires: gettext

%description
Exo is an extension library to GTK+/GLib used by several Xfce applications
(e.g. xfce4-screenshooter) providing helper widgets, MIME/URL-opening
utilities, and the exo-open/exo-desktop-item-edit helper tools. Not
packaged upstream for EL10 — built from source here, pinned to the
exo-4.21.0 tag.

%package devel
Summary: Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Headers and pkgconfig files for building against libexo-2.

%prep
%autosetup -n exo-%{version}

%build
%configure
%make_build

%install
%make_install
%find_lang %{name}

%post -p /sbin/ldconfig
%postun -p /sbin/ldconfig

%files -f %{name}.lang
%license COPYING COPYING.LIB
%{_bindir}/exo-open
%{_bindir}/exo-desktop-item-edit
%{_libdir}/libexo-2.so.*
%{_datadir}/man/man1/*
%{_datadir}/pixmaps/exo/

%files devel
%{_includedir}/exo-2/
%{_libdir}/libexo-2.so
%{_libdir}/pkgconfig/exo-2.pc
%doc %{_datadir}/gtk-doc/html/exo-2/

%changelog
* Sat Jul 04 2026 TunaOS Bot <bot@tunaos.org> - 4.21.0-1
- Initial package, needed by xfce4-screenshooter (not on EL10/EPEL/CRB)
