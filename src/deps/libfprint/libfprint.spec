Name: libfprint
Version: 1.94.8
Release: 1%{?dist}
Summary: Toolkit for fingerprint scanner

# Automatically converted from old format: LGPLv2+ - review is highly recommended.
# Most of the code is LGPL-2.1-or-later
# libfprint/nbis is NIST-PD
License: LGPL-2.1-or-later AND NIST-PD
URL: http://www.freedesktop.org/wiki/Software/fprint/libfprint
Source0: https://gitlab.freedesktop.org/libfprint/libfprint/-/archive/v%{version}/libfprint-v%{version}.tar.gz

BuildRequires: gcc, gcc-c++, git, meson, ninja-build
BuildRequires: openssl-devel
BuildRequires: pkgconfig(glib-2.0) >= 2.50
BuildRequires: pkgconfig(gio-2.0) >= 2.44.0
BuildRequires: pkgconfig(gusb) >= 0.3.0
BuildRequires: pkgconfig(nss)
BuildRequires: pkgconfig(pixman-1)
BuildRequires: libgudev-devel
BuildRequires: systemd
BuildRequires: gobject-introspection-devel

%description
libfprint offers support for consumer fingerprint reader devices. Packaged
here because EL10 does not build it for aarch64 (present on x86_64), which
in turn makes fprintd-pam — a hard dependency of cosmic-greeter — uninstallable
there. Pinned to 1.94.8, the same version already shipping in CentOS Stream
10's own x86_64 repos, so both architectures carry an identical libfprint
rather than introducing version skew.

%package devel
Summary: Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
Headers and pkgconfig files for building applications against libfprint.

%prep
%autosetup -S git -n libfprint-v%{version}

%build
# Fedora's spec builds -Ddrivers=all to cover the virtual image driver used
# by its integration tests; those tests aren't run here (see %%install), so
# the default driver set is enough and keeps the dependency footprint down.
#
# doc and installed-tests default to true in meson_options.txt. gtk-doc is
# deliberately not in BuildRequires (no docs subpackage here), and installed
# tests are never listed in %%files, so both must be turned off explicitly —
# otherwise meson either fails on a missing gtk-doc tool or rpmbuild fails
# its unpackaged-files check on the installed-tests tree.
%meson -Ddoc=false -Dinstalled-tests=false
%meson_build

%install
%meson_install

%ldconfig_scriptlets

# No %%check: libfprint's test suite needs umockdev-recorded device replay
# and a D-Bus session, neither available in the mock chroot — same reason
# every other package in this repo skips tests.

%files
%license COPYING
%doc NEWS THANKS AUTHORS README.md
%{_libdir}/*.so.*
%{_libdir}/girepository-1.0/*.typelib
%{_udevhwdbdir}/60-autosuspend-libfprint-2.hwdb
%{_udevrulesdir}/70-libfprint-2.rules
%{_datadir}/metainfo/org.freedesktop.libfprint.metainfo.xml

%files devel
%doc HACKING.md
%{_includedir}/*
%{_libdir}/*.so
%{_libdir}/pkgconfig/%{name}-2.pc
%{_datadir}/gir-1.0/*.gir

%changelog
* Sun Jul 20 2026 TunaOS Bot <bot@tunaos.org> - 1.94.8-1
- Packaged to unblock cosmic-greeter (fprintd-pam) on EL10 aarch64
