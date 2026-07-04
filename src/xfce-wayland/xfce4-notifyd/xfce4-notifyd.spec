Name: xfce4-notifyd
Version: 0.9.7
Release: 1%{?dist}
Summary: Notification daemon for the Xfce desktop environment
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/apps/xfce4-notifyd
Source0: https://archive.xfce.org/src/apps/xfce4-notifyd/0.9/xfce4-notifyd-%{version}.tar.bz2

BuildRequires: gcc
BuildRequires: gtk3-devel
BuildRequires: libxfce4ui-devel
BuildRequires: libxfce4util-devel
BuildRequires: xfconf-devel
BuildRequires: libnotify-devel
BuildRequires: sqlite-devel
BuildRequires: systemd-devel
# meson.build's dependency('systemd') needs the top-level systemd.pc, which
# ships in the systemd package itself, not systemd-devel.
BuildRequires: systemd
BuildRequires: gtk-layer-shell-devel
BuildRequires: xfce4-panel-devel
BuildRequires: libcanberra-devel
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
%find_lang %{name}

%files -f %{name}.lang
%license COPYING
%{_libdir}/xfce4/notifyd/xfce4-notifyd
%{_bindir}/xfce4-notifyd-config
%{_libdir}/xfce4/panel/plugins/libnotification-plugin.so
%{_datadir}/xfce4/panel/plugins/*.desktop
%{_datadir}/applications/*.desktop
%{_sysconfdir}/xdg/autostart/*.desktop
%{_datadir}/dbus-1/services/*.service
%{_prefix}/lib/systemd/user/xfce4-notifyd.service
%{_datadir}/icons/hicolor/*/apps/*.png
%{_datadir}/icons/hicolor/scalable/apps/*.svg
%{_datadir}/icons/hicolor/scalable/status/*.svg
%{_datadir}/man/man1/*
%{_datadir}/themes/

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 0.9.7-1
- Initial XFCE Wayland package for TunaOS EL10
