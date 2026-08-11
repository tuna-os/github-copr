# python3-evdev for EL10 — dependency of input-remapper (#122, #126).
#
# input-remapper declares `evdev` and nothing on EL10 provides it.  Checked
# against real repository metadata: absent from CentOS Stream 10 BaseOS,
# AppStream and CRB, and 0 matches in EPEL 10's primary.xml.zst.
#
# VERSION PIN (1.9.2, deliberately not 1.9.3):
#   1.9.3  build-requires setuptools>=77.0   (PEP 639 license metadata)
#   1.9.2  build-requires setuptools>=61.0   (file-based license)
# EL10 ships python3-setuptools 69.0.3, so 1.9.3 cannot build here.
# Do not bump past 1.9.2 until EL10 has setuptools 77 or newer.
#
# BUILD METHOD (setup.py, not pip wheel):
#   pip wheel requires the `wheel` Python package for bdist_wheel, and EL10
#   has no python3-wheel RPM.  setup.py build + setup.py install compiles the
#   three C extensions (_input, _uinput, _ecodes) without needing wheel.

Name:           python3-evdev
Version:        1.9.2
Release:        1%{?dist}
Summary:        Python bindings to the Linux input handling subsystem

License:        BSD-3-Clause
URL:            https://github.com/gvalkov/python-evdev
Source0:        https://github.com/gvalkov/python-evdev/archive/refs/tags/v%{version}.tar.gz#/python-evdev-%{version}.tar.gz

BuildRequires:  gcc
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  kernel-headers

Requires:       python3

%description
Bindings for the Linux input subsystem, exposing evdev devices, event codes
and uinput.  Required by input-remapper, which EL10 cannot otherwise provide.

%prep
%autosetup -n python-evdev-%{version}

%build
# setup.py build compiles three C extensions (_input, _uinput, _ecodes).
# ecodes.c is generated at build time by genecodes_c.py reading the kernel
# input headers — hence the kernel-headers BuildRequires.
python3 setup.py build

%install
python3 setup.py install --root %{buildroot} --prefix %{_prefix} --skip-build

%files
%license LICENSE
%{python3_sitearch}/evdev/
%{python3_sitearch}/evdev-*.egg-info/

%changelog
* Tue Aug 12 2025 TunaOS Bot <bot@tunaos.org> - 1.9.2-1
- Initial package: Python evdev bindings for EL10 (#126)
