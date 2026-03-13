Name:           libicu77
Version:        77.1
Release:        1%{?dist}
Summary:        International Components for Unicode (Bootstrap v77)
License:        MIT and UCD and Public Domain
URL:            http://site.icu-project.org/
Source0:        https://github.com/unicode-org/icu/releases/download/release-77-1/icu4c-77_1-src.tgz

BuildRequires:  gcc-c++
BuildRequires:  make
BuildRequires:  python3
BuildRequires:  autoconf >= 2.72
BuildRequires:  doxygen

%description
Non-conflicting build of ICU 77.1 for mozjs140 bootstrap.

%package devel
Summary:        Development files for libicu77
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description devel
Development files for libicu77.

%prep
%setup -q -n icu
# No config patch needed if we are careful

%build
cd source
chmod +x configure
./configure --prefix=/usr --libdir=/usr/lib64 --disable-samples --disable-tests
make %{?_smp_mflags}

%install
cd source
DESTDIR=%{buildroot} make install

# Remove conflicting files that we don't need for the library
rm -rf %{buildroot}/usr/bin
rm -rf %{buildroot}/usr/sbin
rm -rf %{buildroot}/usr/share/man
rm -rf %{buildroot}/usr/share/icu
rm -rf %{buildroot}/usr/lib64/icu

%files
%{_libdir}/libicu*.so.77*

%files devel
%{_includedir}/unicode
%{_libdir}/libicu*.so
%{_libdir}/pkgconfig/*.pc

%changelog
* Thu Mar 12 2026 Conductor <james@conductor.local> - 77.1-1
- Bootstrap build for mozjs140
