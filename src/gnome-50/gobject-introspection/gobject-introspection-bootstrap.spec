Name:           gobject-introspection
Version:        1.86.0
Release:        1%{?dist}
Summary:        Introspection system for GObject-based libraries
License:        GPL-2.0-or-later AND LGPL-2.0-or-later AND MIT
URL:            https://wiki.gnome.org/Projects/GObjectIntrospection
Source0:        https://download.gnome.org/sources/%{name}/1.86/%{name}-%{version}.tar.xz

BuildRequires:  meson
BuildRequires:  gcc
BuildRequires:  flex
BuildRequires:  bison
BuildRequires:  pkgconfig(glib-2.0) >= 2.80.0
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(cairo-gobject)
BuildRequires:  python3-devel
BuildRequires:  python3-mako
BuildRequires:  python3-markdown
BuildRequires:  gtk-doc

%description
GObject Introspection is a project that aims to describe the APIs of
GObject-based libraries.

%package devel
Summary:        Libraries and headers for gobject-introspection
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description devel
Libraries and headers for gobject-introspection.

%prep
%autosetup -n gobject-introspection-%{version}
# Remove glib version constraints from meson.build
python3 -c "
import re
content = open('meson.build').read()
content = re.sub(r\"dependency\((['\\\"][\w.-]+['\\\"]),\s*version:\s*[^,)]+,?\", r\"dependency(\1,\", content)
content = content.replace(\",)\", \")\")
with open('meson.build', 'w') as f: f.write(content)
"

%build
meson setup --prefix=/usr --libdir=/usr/lib64 --buildtype=plain build \
    -Dgtk_doc=true
meson compile -C build

%install
DESTDIR=%{buildroot} meson install -C build

%files
%{_libdir}/libgirepository-1.0.so.1*
%{_libdir}/girepository-1.0/
%{_libdir}/gobject-introspection/
%{_bindir}/g-ir-compiler
%{_bindir}/g-ir-generate
%{_bindir}/g-ir-inspect
%{_bindir}/g-ir-scanner
%{_bindir}/g-ir-annotation-tool
%{_bindir}/g-ir-doc-tool
%{_datadir}/gir-1.0/
%{_datadir}/gobject-introspection-1.0/
%{_mandir}/man1/g-ir-*

%files devel
%{_includedir}/gobject-introspection-1.0/
%{_libdir}/libgirepository-1.0.so
%{_libdir}/pkgconfig/gobject-introspection-1.0.pc
%{_libdir}/pkgconfig/gobject-introspection-no-export-1.0.pc
%{_datadir}/aclocal/introspection.m4
%{_datadir}/gtk-doc/html/gi/

%changelog
* Thu Mar 12 2026 Conductor <james@conductor.local> - 1.86.0-1
- Bootstrap build
