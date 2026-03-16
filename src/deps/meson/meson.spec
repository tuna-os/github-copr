Name:           meson
Version:        1.10.1
Release:        2%{?dist}
Summary:        High productivity build system
License:        Apache-2.0
URL:            https://mesonbuild.com
Source0:        https://github.com/mesonbuild/meson/releases/download/%{version}/meson-%{version}.tar.gz
Source1:        macros.meson
BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
Requires:       python3
Requires:       ninja-build

%description
Meson is an open source build system meant to be both extremely fast, and,
even more importantly, as user friendly as possible.

%prep
%autosetup -n meson-%{version}

%build
%py3_build

%install
%py3_install
install -Dpm 644 %{SOURCE1} %{buildroot}%{_rpmconfigdir}/macros.d/macros.meson

%files
%{_bindir}/meson
%{python3_sitelib}/mesonbuild/
%{python3_sitelib}/meson-*.egg-info/
%{_datadir}/polkit-1/actions/com.mesonbuild.install.policy
%{_mandir}/man1/meson.1*
%{_rpmconfigdir}/macros.d/macros.meson

%changelog
* Mon Mar 16 2026 James <james@example.com> - 1.10.1-2
- Add RPM macros to fix build failures in downstream packages.

* Thu Mar 12 2026 Conductor <james@conductor.local> - 1.10.1-1
- Minimal bootstrap build
