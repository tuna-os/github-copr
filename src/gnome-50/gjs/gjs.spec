%global glib2_version 2.68.0
%global gobject_introspection_version 1.72.0
%global mozjs140_version 140.1.0

%bcond_with tests

Name:           gjs
Version:        1.87.90
Release:        1%{?dist}
Summary:        Javascript Bindings for GNOME

# The following files contain code from Mozilla which
# is triple licensed under MPL-1.1/GPL-2.0-or-later/LGPL-2.1-or-later:
# The console module (modules/console.c)
# Stack printer (gjs/stack.c)
# modules/esm/_encoding/util.js and few other things are MIT
# modules/script/tweener/equations.js is BSD-3-Clause
License:        MIT AND BSD-3-Clause AND (MIT OR LGPL-2.0-or-later) AND (MPL-1.1 OR GPL-2.0-or-later OR LGPL-2.1-or-later)
URL:            https://wiki.gnome.org/Projects/Gjs
Source0:        https://download.gnome.org/sources/%{name}/1.87/%{name}-%{version}.tar.xz

BuildRequires:  gcc-c++
BuildRequires:  meson
BuildRequires:  dbus-daemon
BuildRequires:  gettext
BuildRequires:  readline-devel
BuildRequires:  pkgconfig(cairo-gobject)
BuildRequires:  pkgconfig(gio-2.0) >= %{glib2_version}
BuildRequires:  pkgconfig(gobject-introspection-1.0) >= %{gobject_introspection_version}
BuildRequires:  pkgconfig(gtk4)
BuildRequires:  pkgconfig(mozjs-140) >= %{mozjs140_version}
BuildRequires:  pkgconfig(sysprof-capture-4)

%if %{with tests}
BuildRequires:  gtk3
BuildRequires:  /usr/bin/dbus-run-session
BuildRequires:  dbus-x11
BuildRequires:  mesa-dri-drivers
BuildRequires:  mutter
BuildRequires:  xwayland-run
%endif

Requires: glib2%{?_isa} >= %{glib2_version}
Requires: gobject-introspection%{?_isa} >= %{gobject_introspection_version}
Requires: mozjs140%{?_isa} >= %{mozjs140_version}

%description
Gjs allows using GNOME libraries from Javascript. It's based on the
Spidermonkey Javascript engine from Mozilla and the GObject introspection
framework.

%package devel
Summary: Development package for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Files for development with %{name}.

%package tests
Summary: Tests for the gjs package
# installed-tests/js/modules/encodings.json is BSD-3-Clause
License: MIT AND (MIT OR LGPL-2.0-or-later) AND BSD-3-Clause
Requires: %{name}%{?_isa} = %{version}-%{release}

%if %{with tests}
%description tests
The gjs-tests package contains tests that can be used to verify
the functionality of the installed gjs package.
%else
%description tests
Tests are disabled.
%endif

%prep
%autosetup -p1

%build
meson setup --prefix=/usr --libdir=/usr/lib64 --buildtype=plain build
meson compile -C build

%install
DESTDIR=%{buildroot} meson install -C build

%ldconfig_scriptlets

%files
%exclude %{_libdir}/debug/
%exclude %{_libexecdir}/installed-tests/
%exclude %{_datadir}/installed-tests/
%license COPYING
%doc README.md
%{_bindir}/gjs
%{_bindir}/gjs-console
%{_libdir}/libgjs.so.*
%{_libdir}/gjs/
%dir %{_datadir}/gjs-1.0
%dir %{_datadir}/gjs-1.0/lsan
%dir %{_datadir}/gjs-1.0/valgrind
%{_datadir}/gjs-1.0/lsan/lsan.supp
%{_datadir}/gjs-1.0/valgrind/gjs.supp
%{_datadir}/glib-2.0/schemas/org.gnome.GjsTest.gschema.xml

%files devel
%dir %{_includedir}/gjs-1.0
%{_includedir}/gjs-1.0/*
%{_libdir}/libgjs.so
%{_libdir}/pkgconfig/gjs-1.0.pc

%changelog
* Thu Mar 12 2026 Conductor <james@conductor.local> - 1.87.90-1
- Clean build for GNOME 50 against mozjs140
