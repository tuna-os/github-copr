Name: xfce4-notifyd
Version: 0.9.7
Release: 1%{?dist}
Summary: Notification daemon for the Xfce desktop environment
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/apps/xfce4-notifyd
Source0: https://gitlab.xfce.org/apps/xfce4-notifyd/-/archive/xfce4-notifyd-0.9.7/xfce4-notifyd-0.9.7.tar.gz

BuildRequires: gtk3-devel
BuildRequires: libxfce4ui-devel
BuildRequires: libxfce4util-devel
BuildRequires: xfconf-devel
BuildRequires: libnotify-devel
BuildRequires: sqlite-devel
BuildRequires: systemd-devel
BuildRequires: gtk-layer-shell-devel
BuildRequires: intltool
BuildRequires: gettext
BuildRequires: meson
BuildRequires: ninja-build

Requires: gtk-layer-shell

%description
Notification daemon for the Xfce desktop environment with Wayland support
via gtk-layer-shell.

%prep
%autosetup -n xfce4-notifyd-%{version}

%build
%meson -Dwayland=enabled
%meson_build

%install
%meson_install

%files
%license COPYING
%{_libexecdir}/xfce4/notifyd/xfce4-notifyd
%{_datadir}/applications/*.desktop
%{_datadir}/dbus-1/services/*.service
%{_datadir}/xfce4/notifyd/

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 0.9.7-1
- Initial XFCE Wayland package for TunaOS EL10
