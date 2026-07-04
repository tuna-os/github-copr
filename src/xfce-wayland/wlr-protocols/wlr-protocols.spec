%global commit 4264185db3b7e961e7f157e1cc4fd0ab75137568
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name: wlr-protocols
Version: 0
Release: 1.%{shortcommit}%{?dist}
Summary: Wayland protocols designed for use in wlroots (and other compositors)
License: MIT
URL: https://gitlab.freedesktop.org/wlroots/wlr-protocols
Source0: https://gitlab.freedesktop.org/wlroots/wlr-protocols/-/archive/%{commit}/wlr-protocols-%{commit}.tar.gz
BuildArch: noarch
BuildRequires: make

%description
Wayland protocol XML definitions designed for use in wlroots-based
compositors. Pinned to the exact commit xfce4-settings' protocols/
wlr-protocols git submodule references (this repo builds from plain
source tarballs, so submodules aren't available — this package
provides the same pkg-config-discoverable data wlr-protocols.pc
points at instead).

%prep
%autosetup -n wlr-protocols-%{commit}

%build
make wlr-protocols.pc

%install
%make_install

%files
%{_datadir}/pkgconfig/wlr-protocols.pc
%{_datadir}/wlr-protocols/

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 0-1
- Initial package, pinned to xfce4-settings' wlr-protocols submodule commit
