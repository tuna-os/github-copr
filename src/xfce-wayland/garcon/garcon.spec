Name: garcon
Version: 4.20.0
Release: 1%{?dist}
Summary: Xfce menu handling library
License: LGPL-2.0-or-later
URL: https://gitlab.xfce.org/xfce/garcon
Source0: https://archive.xfce.org/src/xfce/garcon/4.20/garcon-%{version}.tar.bz2
BuildRequires: xfce4-dev-tools
BuildRequires: autoconf automake libtool gettext-devel gtk-doc
BuildRequires: glib2-devel, libxfce4util-devel
BuildRequires: gtk3-devel, libxfce4ui-devel
%description
Menu handling library for the Xfce desktop environment.

%package devel
Summary: Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Headers and pkgconfig files for building against garcon.

%prep
%autosetup -n garcon-%{version}
# The dist tarball bundles a configure script generated against an
# older libtool than EL10 ships; its nm-output parsing predates current
# binutils and mis-detects (breaks with a bogus command in the symbol
# pipe). Regenerating against the system libtool fixes it.
%build
autoreconf -fi
%configure --disable-gtk-doc
%make_build
%install
%make_install
%find_lang %{name}

%files -f %{name}.lang
%license COPYING
%{_libdir}/libgarcon*.so.*
%{_sysconfdir}/xdg/menus/xfce-applications.menu
%{_datadir}/desktop-directories/*.directory
%{_datadir}/icons/hicolor/*/apps/org.xfce.garcon.png

%files devel
%{_includedir}/garcon-1/
%{_includedir}/garcon-gtk3-1/
%{_libdir}/libgarcon*.so
%{_libdir}/pkgconfig/*.pc
%doc %{_datadir}/gtk-doc/

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - %{version}-%{release}
- Packaged for the XFCE Wayland stack (tuna-os/github-copr#65)

