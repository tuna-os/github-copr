%global commit 91d27e521a5791223915732ec15b701de089a492
%global shortcommit %(c=%{commit}; echo ${c:0:7})
# resources/xfce-wayland-protocols submodule gitlink at %{commit}. It must be
# bumped in lockstep with it: the XML defines the interfaces, requests and
# events src/protocols/*.rs generates its server code from.
%global protocols_commit 55dbf3e3d2a91b525c528c0dd4c1a7805a99364b
%global cargo_name xfwl4
# Rust binaries don't produce the source-file manifest find-debuginfo.sh
# expects for a separate debugsource subpackage (common across cargo-built
# RPMs); debuginfo itself is unaffected.
%undefine _debugsource_packages

Name: xfwl4
Version: 4.21.0
Release: 1%{?dist}
Summary: Wayland compositor for Xfce4
License: GPL-3.0-or-later AND Apache-2.0 AND MIT
URL: https://gitlab.xfce.org/xfce/xfwl4
Source0: https://gitlab.xfce.org/xfce/xfwl4/-/archive/%{commit}/xfwl4-%{commit}.tar.gz
# mock builds run with networking disabled (matches COPR's real isolation),
# but Cargo.toml pulls `smithay` from git — cargo can't fetch that offline.
# Pre-vendored with `cargo vendor` against this exact commit's Cargo.lock
# (crates.io deps + the smithay git dep); see release notes for how it
# was generated if it ever needs regenerating after a Cargo.lock bump.
Source1: https://github.com/tuna-os/tunaos-packages/releases/download/xfwl4-vendor-5c2802c0/vendor.tar.gz
# resources/xfce-wayland-protocols is a git submodule (custom XFCE Wayland
# protocol XML: output-management, input-device-list, etc.) — not included
# in the plain archive tarball, same as any other git submodule. Referenced
# by relative path in src/protocols/*.rs's wayland_scanner::generate_*!
# macros, so it just needs to land at resources/xfce-wayland-protocols/.
Source2: https://gitlab.xfce.org/xfce/xfce-wayland-protocols/-/archive/%{protocols_commit}/xfce-wayland-protocols-%{protocols_commit}.tar.gz

%if 0%{?rhel} >= 10
%global __cargo_requires_buildrequires 1
%endif

BuildRequires: cargo, rust, libdrm-devel, libinput-devel, mesa-libgbm-devel
BuildRequires: libseat-devel, libxkbcommon-devel, pixman-devel
BuildRequires: wayland-devel, wayland-protocols-devel
BuildRequires: gtk3-devel, gdk-pixbuf2-devel, libdisplay-info-devel
BuildRequires: libSM-devel, systemd-devel
BuildRequires: pkgconfig(sm), pkgconfig(libstartup-notification-1.0)
# The xfconf and libxfce4ui Rust binding crates (xfconf-sys,
# libxfce4ui-sys, libxfce4kbd-private-sys) link against these via
# pkg-config — confirmed via the Cargo.lock dependency tree.
BuildRequires: xfconf-devel, libxfce4ui-devel
# Without gettext-devel, gettext-sys's build.rs can't find a usable
# system gettext and falls back to building its own copy of GNU
# gettext from source inside the Rust build — which then fails to
# link against libintl_gettext. gettext-devel makes it use the system
# one (glibc's built-in gettext) instead.
BuildRequires: gettext-devel

%description
xfwl4 is a Wayland compositor for Xfce4 built on Smithay/wlroots.
Provides both winit (nested) and TTY (udev+egl) backends.

%prep
%setup -q -n xfwl4-%{commit}
tar -xzf %{SOURCE1}
mkdir -p resources/xfce-wayland-protocols
tar -xzf %{SOURCE2} --strip-components=1 -C resources/xfce-wayland-protocols
mkdir -p .cargo
cat > .cargo/config.toml <<'EOF'
[source.crates-io]
replace-with = "vendored-sources"

[source."git+https://github.com/smithay/smithay?rev=0a29aecf9e07a2227712ab470b0ab0ee56752272"]
git = "https://github.com/smithay/smithay"
rev = "0a29aecf9e07a2227712ab470b0ab0ee56752272"
replace-with = "vendored-sources"

[source.vendored-sources]
directory = "vendor"

[net]
offline = true
EOF

%build
export RUSTFLAGS="-C relocation-model=pic"
# gettext-sys only skips its from-source build (which fails to link — see
# vendor/gettext-sys/build.rs's try_gettext_system()) when GETTEXT_SYSTEM is
# set; on glibc targets gettext is built into libc, no linking needed at all.
export GETTEXT_SYSTEM=1
cargo build --release --offline %{?_smp_mflags} \
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
