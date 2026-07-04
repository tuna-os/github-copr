%global commit 465880f67b5705136895bf69c60e2178ad351856
%global shortcommit %(c=%{commit}; echo ${c:0:7})
%global cargo_name xfwl4

Name: xfwl4
Version: 4.21.0
Release: 1%{?dist}
Summary: Wayland compositor for Xfce4
License: GPL-3.0-or-later AND Apache-2.0 AND MIT
URL: https://gitlab.xfce.org/xfce/xfwl4
Source0: https://gitlab.xfce.org/xfce/xfwl4/-/archive/%{commit}/xfwl4-%{commit}.tar.gz

%if 0%{?rhel} >= 10
%global __cargo_requires_buildrequires 1
%endif

BuildRequires: cargo, rust, libdrm-devel, libinput-devel
BuildRequires: libseat-devel, libxkbcommon-devel, pixman-devel
BuildRequires: wayland-devel, wayland-protocols-devel
BuildRequires: gtk3-devel, gdk-pixbuf2-devel, libdisplay-info-devel
BuildRequires: libSM-devel, systemd-devel
BuildRequires: pkgconfig(sm), pkgconfig(libstartup-notification-1.0)
# The xfconf and libxfce4ui Rust binding crates (xfconf-sys,
# libxfce4ui-sys, libxfce4kbd-private-sys) link against these via
# pkg-config — confirmed via the Cargo.lock dependency tree.
BuildRequires: xfconf-devel, libxfce4ui-devel

%description
xfwl4 is a Wayland compositor for Xfce4 built on Smithay/wlroots.
Provides both winit (nested) and TTY (udev+egl) backends.

%prep
%autosetup -n xfwl4-%{commit}

%build
export RUSTFLAGS="-C relocation-model=pic"
cargo build --release %{?_smp_mflags} \
  --no-default-features \
  --features udev,egl,xwayland,smithay/renderer_pixman,smithay/renderer_gl

%install
mkdir -p %{buildroot}%{_bindir}
cp target/release/xfwl4 %{buildroot}%{_bindir}/xfwl4
mkdir -p %{buildroot}%{_datadir}/xfce4/xfwl4
cp resources/defaults %{buildroot}%{_datadir}/xfce4/xfwl4/defaults

%files
%license LICENSE
%{_bindir}/xfwl4
%dir %{_datadir}/xfce4/xfwl4
%{_datadir}/xfce4/xfwl4/defaults

%changelog
* Sat Jun 27 2026 TunaOS Bot <bot@tunaos.org> - 0.1.0-1
- Initial xfwl4 compositor package
