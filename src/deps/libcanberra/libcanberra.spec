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

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
Development files (headers, pkg-config file) for libcanberra.

%package        gtk3
Summary:        Virtual compatibility package for libcanberra-gtk3
Provides:       libcanberra-gtk3 = %{version}-%{release}
Provides:       libcanberra-gtk3%{?_isa} = %{version}-%{release}
# Fake the library provide to satisfy hard links in base packages like EDS
Provides:       libcanberra-gtk3.so.0()(64bit)
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    gtk3
This is a virtual compatibility package to satisfy dependencies on libcanberra-gtk3
without actually installing GTK3 libraries. Note that applications attempting
to use GTK3 sound hooks may fail to find the expected symbols.

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

# Create a symlink so that apps looking for the gtk3 version at least find the base library
# This is the "Option C" hack
ln -s libcanberra.so.0.2.5 %{buildroot}%{_libdir}/libcanberra-gtk3.so.0

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
%{_datadir}/vala/vapi/libcanberra.vapi

%files gtk3
%{_libdir}/libcanberra-gtk3.so.0

%changelog
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 0.30-100
- Option C: Virtual provides for libcanberra-gtk3 to satisfy system deps
- Fake libcanberra-gtk3.so.0 with a symlink to base libcanberra
- Bump release to 100 to override system package
