Name:           libcanberra
Version:        0.30
Release:        100%{?dist}
Summary:        Portable sound event library

License:        LGPL-2.1-or-later
URL:            http://0pointer.de/lennart/projects/libcanberra/
Source0:        https://0pointer.de/lennart/projects/libcanberra/libcanberra-%{version}.tar.xz

BuildRequires:  gcc
BuildRequires:  libtool
BuildRequires:  libtool-ltdl-devel
BuildRequires:  gettext-devel
BuildRequires:  pkgconfig(alsa)
BuildRequires:  pkgconfig(libpulse)
BuildRequires:  pkgconfig(vorbisfile)
BuildRequires:  pkgconfig(tdb)

%description
libcanberra is a simple abstract interface for playing event sounds.
It implements the XDG Sound Theme and Name Specifications.

This package is built without GTK2/GTK3 modules to avoid the gtk3
dependency chain on EL10 where gtk3 has been removed.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
Development files (headers, pkg-config file) for libcanberra.
This package does not require libcanberra-gtk3.

%prep
%autosetup -p1

%build
%configure \
    --disable-static \
    --disable-gtk-doc \
    --disable-gtk \
    --disable-gtk3 \
    --with-builtin=dso

%make_build

%install
%make_install
find %{buildroot} -name '*.la' -delete

# Remove the gtk2/gtk3 modules (not built, but just in case)
rm -f %{buildroot}%{_libdir}/libcanberra-gtk*.so*
rm -f %{buildroot}%{_libdir}/pkgconfig/libcanberra-gtk*.pc
rm -f %{buildroot}%{_libdir}/gtk-*/modules/libcanberra-gtk-module.so

%ldconfig_scriptlets

%files
%license LGPL
%doc README
%{_libdir}/libcanberra.so.0{,.*}
# Plugins built with --with-builtin=dso
%{_libdir}/libcanberra-0.30/

%files devel
%{_includedir}/canberra.h
%{_libdir}/libcanberra.so
%{_libdir}/pkgconfig/libcanberra.pc
%{_datadir}/gtk-doc/html/libcanberra/

%changelog
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 0.30-1
- Build without gtk2/gtk3 modules for EL10 compatibility
  (EL10 libcanberra-devel has broken dep on libcanberra-gtk3 which needs gtk3)
