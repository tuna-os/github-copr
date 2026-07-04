%global commit 17225e9ff9a4d2de5c23c8225e8abf5cdc1fddd9
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name:           xfce4-session
Version:        4.21.0
Release:        1%{?dist}
Summary:        Session manager for the Xfce desktop environment (Wayland)

License:        GPL-2.0-or-later
URL:            https://gitlab.xfce.org/xfce/xfce4-session
Source0: https://gitlab.xfce.org/xfce/xfce4-session/-/archive/%{commit}/xfce4-session-%{commit}.tar.gz

BuildRequires: gcc
BuildRequires:  gtk3-devel
BuildRequires:  libxfce4ui-devel
BuildRequires:  libxfce4util-devel
BuildRequires:  libxfce4windowing-devel
BuildRequires:  xfconf-devel
BuildRequires:  polkit-devel
BuildRequires:  systemd-devel
BuildRequires:  dbus-devel
BuildRequires:  intltool
BuildRequires:  gettext
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  gtk-layer-shell-devel

Requires:       polkit
Requires:       dbus

%description
Xfce4-session is the session manager for the Xfce desktop environment.
It is responsible for starting the Xfce desktop, saving and restoring
sessions, and managing logout/shutdown/reboot actions. This build supports
Wayland sessions via the wayland-sessions entry point.

%prep
%autosetup -n xfce4-session-%{commit}

%build
# Wayland-only build (matches this stack's convention elsewhere).
%meson -Dx11=disabled
%meson_build

%install
%meson_install
%find_lang %{name}

%files -f %{name}.lang
%license COPYING
%{_bindir}/xfce4-session*
%{_bindir}/startxfce4
%{_bindir}/xflock4
%{_datadir}/wayland-sessions/*.desktop
%{_datadir}/applications/*.desktop
%{_datadir}/xfce4/labwc/
%{_datadir}/icons/hicolor/*/apps/org.xfce.session.*
%{_datadir}/icons/hicolor/*/actions/xfsm-*.png
%{_datadir}/man/man1/xfce4-session*.1*
%{_datadir}/polkit-1/actions/org.xfce.session.policy
%{_datadir}/xdg-desktop-portal/xfce-portals.conf
%{_sysconfdir}/xdg/xfce4/xinitrc
%{_sysconfdir}/xdg/xfce4/Xft.xrdb
%{_sysconfdir}/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-session.xml
# xfsm-shutdown-helper installs under $libdir (helper_path_prefix defaults
# to $prefix/$libdir), not $libexecdir.
%{_libdir}/xfce4/session/

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 4.21.0-1
- Initial XFCE Wayland package for TunaOS EL10
