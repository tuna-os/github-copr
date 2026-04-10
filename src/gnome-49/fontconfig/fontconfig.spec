%global freetype_version 2.9.1

Summary:	Font configuration and customization library
Name:		fontconfig
Version:	2.17.0
Release:	2%{?dist}
License:	HPND AND LicenseRef-Fedora-Public-Domain AND Unicode-DFS-2016
Source0:	https://src.fedoraproject.org/repo/pkgs/fontconfig/fontconfig-2.17.0.tar.xz/sha512/dd64905c3e0e5c5881df505b8f0bea594bbac5ce145f57aedcd7130978cd285491497198d8f2d6ed26f7b2abb31268dc3ff97aa75ce998b8e57f2d5c75b240b4/fontconfig-2.17.0.tar.xz
Source1:	25-no-bitmap-fedora.conf

Patch0:		%{name}-sleep-less.patch
Patch4:		%{name}-drop-lang-from-pkgkit-format.patch
Patch5:		%{name}-disable-network-required-test.patch
Patch7:		%{name}-fix-crash.patch

BuildRequires:	libxml2-devel
BuildRequires:	freetype-devel >= %{freetype_version}
BuildRequires:	gettext
BuildRequires:	gperf
BuildRequires:	meson
BuildRequires:	ninja-build
BuildRequires:	gcc

Requires:	freetype

%description
Fontconfig is designed to locate fonts within the
system and select them according to requirements specified by
applications.

%package devel
Summary:	Font configuration and customization library devel files
Requires:	%{name}%{?_isa} = %{version}-%{release}
Requires:	pkgconfig
Requires:	freetype-devel >= %{freetype_version}

%description devel
The fontconfig-devel package includes the header files and pkg-config file
needed to compile programs that use fontconfig.

%prep
%autosetup -p1

%build
%meson \
  -Ddoc=disabled \
  -Dtests=disabled \
  -Dcache-build=disabled \
  -Dcache-dir=/usr/lib/fontconfig/cache
%meson_build

%install
%meson_install
install -m 0644 %{SOURCE1} %{buildroot}%{_sysconfdir}/fonts/conf.avail/ || true

%post
%{_bindir}/fc-cache -f &>/dev/null || :

%postun
if [ "$1" = 0 ] ; then
%{_bindir}/fc-cache -f &>/dev/null || :
fi

%files
%license COPYING
%config %{_sysconfdir}/fonts/
%{_datadir}/fontconfig/
%{_datadir}/gettext/its/fontconfig.*
%{_datadir}/locale/*/LC_MESSAGES/fontconfig*.mo
%{_datadir}/xml/fontconfig/
%{_libdir}/libfontconfig.so.*
%{_bindir}/fc-*

%files devel
%{_libdir}/libfontconfig.so
%{_libdir}/pkgconfig/fontconfig.pc
%{_includedir}/fontconfig/

%changelog
* Thu Apr 10 2026 Conductor <james@conductor.local> - 2.17.0-2
- Add -Dcache-dir=/usr/lib/fontconfig/cache so fc-cache writes to persistent
  path; fixes Flatpak apps not discovering host fonts (GH#21)

* Sun Mar 15 2026 Conductor <james@conductor.local> - 2.17.0-1
- Build fontconfig 2.17.0 for EL10 (needed by pango 1.57+)
- Disabled docs, tests, and cache-build for EL10 compatibility
