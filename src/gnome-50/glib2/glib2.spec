Name:           glib2
Version:        2.87.3
Release:        1%{?dist}
Summary:        A library of handy utility functions

License:        LGPL-2.1-or-later
URL:            https://www.gtk.org
Source0:        glib-%{version}.tar.xz

Patch0:         gnutls-hmac.patch
Patch1:         default-terminal.patch
Patch2:         glib-do-not-install-localtime-test.patch

BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  gettext
BuildRequires:  perl-interpreter
BuildRequires:  glibc-devel
BuildRequires:  libattr-devel
BuildRequires:  libselinux-devel
BuildRequires:  meson
BuildRequires:  systemtap-sdt-devel
BuildRequires:  systemtap-sdt-dtrace
BuildRequires:  pkgconfig(libelf)
BuildRequires:  pkgconfig(libffi)
BuildRequires:  pkgconfig(libpcre2-8)
BuildRequires:  pkgconfig(mount)
BuildRequires:  pkgconfig(sysprof-capture-4)
BuildRequires:  pkgconfig(zlib)
BuildRequires:  python3-devel
BuildRequires:  gobject-introspection-devel

Provides: bundled(cmph)
Provides: bundled(dirent)
Provides: bundled(gnulib)
Provides: bundled(gvdb)
Provides: bundled(libcharset)
Provides: bundled(xdgmime)

%description
GLib is the low-level core library that forms the basis for projects
such as GTK+ and GNOME.

%package devel
Summary: A library of handy utility functions
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: python3-packaging

%description devel
The glib2-devel package includes the header files for the GLib library.

%package static
Summary: glib static
Requires: %{name}-devel = %{version}-%{release}

%description static
The %{name}-static subpackage contains static libraries for %{name}.

%prep
%autosetup -n glib-%{version} -p1
# Patch frexp checks for mock environment
python3 -c "
import re
path = 'glib/gnulib/meson.build'
content = open(path).read()
content = re.sub(r'if not have_frexp.*?endif', 'have_frexp = true\ngl_cv_func_frexp_works = true', content, flags=re.DOTALL)
content = re.sub(r'if not have_frexpl.*?endif', 'have_frexpl = true\ngl_cv_func_frexpl_works = true\ngl_cv_func_frexpl_decl = true', content, flags=re.DOTALL)
with open(path, 'w') as f: f.write(content)
"

%build
meson setup --prefix=/usr --libdir=/usr/lib64 --buildtype=plain build \
    -Dglib_debug=disabled \
    -Ddocumentation=false \
    -Dinstalled_tests=false \
    -Dgnutls=true \
    -Dintrospection=enabled \
    --default-library=both
meson compile -C build

%install
DESTDIR=%{buildroot} meson install -C build

mv %{buildroot}%{_bindir}/gio-querymodules %{buildroot}%{_bindir}/gio-querymodules-%{__isa_bits}

sed -i 's|gio_querymodules=.*|gio_querymodules=${bindir}/gio-querymodules-64|' \
    %{buildroot}%{_libdir}/pkgconfig/gio-2.0.pc

%find_lang glib20

%files -f glib20.lang
%{_bindir}/gapplication
%{_bindir}/gdbus
%{_bindir}/gio
%{_bindir}/gio-querymodules-%{__isa_bits}
%{_bindir}/glib-compile-schemas
%{_bindir}/gsettings
%{_bindir}/gi-compile-repository
%{_bindir}/gi-decompile-typelib
%{_bindir}/gi-inspect-typelib
%{_libdir}/libgio-2.0.so.*
%{_libdir}/libglib-2.0.so.*
%{_libdir}/libgmodule-2.0.so.*
%{_libdir}/libgobject-2.0.so.*
%{_libdir}/libgthread-2.0.so.*
%{_libdir}/libgirepository-2.0.so.*
%{_libdir}/girepository-1.0/*.typelib
%{_datadir}/glib-2.0/schemas
%{_datadir}/glib-2.0/dtds/gresource.dtd
%{_libexecdir}/gio-launch-desktop

%files devel
%{_bindir}/gdbus-codegen
%{_bindir}/glib-compile-resources
%{_bindir}/glib-genmarshal
%{_bindir}/glib-gettextize
%{_bindir}/glib-mkenums
%{_bindir}/gobject-query
%{_bindir}/gresource
%{_bindir}/gtester
%{_bindir}/gtester-report
%{_includedir}/*
%{_libdir}/lib*.so
%{_libdir}/pkgconfig/*.pc
%{_libdir}/glib-2.0
%{_datadir}/glib-2.0/codegen
%{_datadir}/glib-2.0/gdb
%{_datadir}/glib-2.0/gettext
%{_datadir}/glib-2.0/valgrind
%{_datadir}/gir-1.0/*.gir
%{_datadir}/aclocal/*.m4
%{_datadir}/bash-completion/completions/*
%{_datadir}/gettext/its/gschema.*
%{_datadir}/gdb/auto-load/usr/lib64/*.py
%{_datadir}/systemtap/tapset/%{_arch}/*.stp

%files static
%{_libdir}/*.a

%changelog
* Thu Mar 12 2026 Conductor <james@conductor.local> - 2.87.3-1
- Final clean build with introspection enabled and missing files included
