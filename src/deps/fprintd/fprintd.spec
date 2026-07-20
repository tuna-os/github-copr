Name: fprintd
Version: 1.94.5
Release: 1%{?dist}
Summary: D-Bus service for Fingerprint reader access

# man page is GFDL-1.1-or-later
License: GPL-2.0-or-later AND GFDL-1.1-or-later
URL: http://www.freedesktop.org/wiki/Software/fprint/fprintd
Source0: https://gitlab.freedesktop.org/libfprint/fprintd/-/archive/v%{version}/fprintd-v%{version}.tar.gz

BuildRequires: gcc, gcc-c++, git, meson, ninja-build
BuildRequires: pam-devel
BuildRequires: libfprint-devel >= 1.94.0
BuildRequires: polkit-devel
BuildRequires: gettext
BuildRequires: perl-podlators
BuildRequires: pkgconfig(libsystemd)
BuildRequires: pkgconfig(systemd)

%description
D-Bus service to access fingerprint readers. Packaged here, alongside
libfprint in this same repo, because EL10 does not build either for
aarch64 — present on x86_64 only — which makes cosmic-greeter (which hard
requires the fprintd-pam subpackage) uninstallable there. Pinned to
1.94.5, the same version already shipping in CentOS Stream 10's own
x86_64 repos, so both architectures carry an identical fprintd rather
than introducing version skew.

%package pam
Summary: PAM module for fingerprint authentication
Requires: %{name} = %{version}-%{release}
# Note that we obsolete pam_fprint, but as the configuration
# is different, it will be mentioned in the release notes
Provides: pam_fprint = %{version}-%{release}
Obsoletes: pam_fprint < 0.2-3
Requires(postun): authselect >= 0.3

License: GPL-2.0-or-later

%description pam
PAM module that uses the fprintd D-Bus service for fingerprint
authentication. This is the actual dependency cosmic-greeter needs.

%package devel
Summary: Development files for %{name}
Requires: %{name} = %{version}-%{release}
# dbus interfaces are GPL-2.0-or-later
# documentation is GFDL-1.1-or-later
License: GPL-2.0-or-later AND GFDL-1.1-or-later
BuildArch: noarch

%description devel
Development documentation for fprintd, the D-Bus service for
fingerprint readers access.

%prep
%autosetup -S git -n %{name}-v%{version}

%build
# gtk_doc defaults to false in meson_options.txt (unlike Fedora's spec,
# which turns it on for its -devel doc subpackage); left off here since
# nothing downstream needs the generated docs, only the compositor/greeter
# binary — keeps gtk-doc off the BuildRequires list entirely.
%meson -Dgtk_doc=false -Dpam=true -Dpam_modules_dir=%{_libdir}/security
%meson_build

%install
%meson_install
mkdir -p %{buildroot}%{_localstatedir}/lib/fprint

%find_lang %{name}

# No %%check: fprintd's test suite needs python3-dbusmock + python3-libpamtest
# to simulate a live D-Bus session and a PAM stack, neither meaningful in the
# mock chroot — same reason every other package in this repo skips tests.

%postun pam
if [ $1 -eq 0 ]; then
  /bin/authselect disable-feature with-fingerprint || :
fi

%files -f %{name}.lang
%doc README COPYING AUTHORS TODO
%{_bindir}/fprintd-*
%{_libexecdir}/fprintd
# FIXME This file should be marked as config when it does something useful
%{_sysconfdir}/fprintd.conf
%{_datadir}/dbus-1/system.d/net.reactivated.Fprint.conf
%{_datadir}/dbus-1/system-services/net.reactivated.Fprint.service
%{_unitdir}/fprintd.service
%{_datadir}/polkit-1/actions/net.reactivated.fprint.device.policy
%attr(0700, -, -) %{_localstatedir}/lib/fprint
%{_mandir}/man1/fprintd.1.gz

%files pam
%doc pam/README
%{_libdir}/security/pam_fprintd.so
%{_mandir}/man8/pam_fprintd.8.gz

%files devel
%{_datadir}/dbus-1/interfaces/net.reactivated.Fprint.Device.xml
%{_datadir}/dbus-1/interfaces/net.reactivated.Fprint.Manager.xml

%changelog
* Sun Jul 20 2026 TunaOS Bot <bot@tunaos.org> - 1.94.5-1
- Packaged to unblock cosmic-greeter (fprintd-pam) on EL10 aarch64
