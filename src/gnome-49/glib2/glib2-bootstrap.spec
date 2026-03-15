Name:           glib2
Version:        2.86.4
Release:        1%{?dist}
Summary:        A library of handy utility functions
License:        LGPL-2.1-or-later
URL:            https://www.gtk.org
Source0:        https://download.gnome.org/sources/glib/2.86/glib-%{version}.tar.xz

BuildRequires:  meson
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  gettext
BuildRequires:  pkgconfig(libpcre2-8)
BuildRequires:  pkgconfig(libffi)
BuildRequires:  pkgconfig(zlib)
BuildRequires:  pkgconfig(mount)
BuildRequires:  python3-devel
BuildRequires:  python3-docutils

Obsoletes:      glib2 < %{version}
Provides:       glib2 = %{version}-%{release}

%description
GLib is the low-level core library that forms the basis for projects such as
GNOME and GTK. (Bootstrap build)

%package devel
Summary:        Development files for glib2
Requires:       %{name}%{?_isa} = %{version}-%{release}
Obsoletes:      glib2-devel < %{version}
Provides:       glib2-devel = %{version}-%{release}

%description devel
Development files for glib2.

%prep
%autosetup -n glib-%{version}

%build
meson setup --prefix=/usr --libdir=/usr/lib64 --buildtype=plain build \
    -Dglib_debug=disabled \
    -Ddocumentation=false \
    -Dinstalled_tests=false \
    -Dintrospection=disabled
meson compile -C build

%install
DESTDIR=%{buildroot} meson install -C build

%files
/usr/bin/*
/usr/lib64/*.so*
/usr/lib64/pkgconfig/*.pc
/usr/include/*
/usr/share/locale/*/LC_MESSAGES/*.mo
/usr/share/glib-2.0/*
/usr/lib64/glib-2.0/include/*
/usr/libexec/gio-launch-desktop
/usr/share/aclocal/*.m4
/usr/share/bash-completion/completions/*
/usr/share/gdb/auto-load/usr/lib64/*.py
/usr/share/gettext/its/gschema.*

%files devel
# Combined for bootstrap

%changelog
* Sun Mar 15 2026 James <james@example.com> - 2.86.4-1
- Bootstrap build for GNOME 49 project (F43 version)
