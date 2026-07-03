%global commit 17225e9ff9a4d2de5c23c8225e8abf5cdc1fddd9
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name:           xfce4-session
Version:        4.21.0
Release:        1%{?dist}
Summary:        Session manager for the Xfce desktop environment (Wayland)

License:        GPL-2.0-or-later
URL:            https://gitlab.xfce.org/xfce/xfce4-session
Source0:        https://gitlab.xfce.org/xfce/xfce4-session/-/archive/xfce4-session-4.21.0/xfce4-session-4.21.0.tar.gz

BuildRequires: gcc
BuildRequires:  gtk3-devel
BuildRequires:  libxfce4ui-devel
BuildRequires:  libxfce4util-devel
BuildRequires:  xfconf-devel
BuildRequires:  polkit-devel
BuildRequires:  systemd-devel
BuildRequires:  dbus-devel
BuildRequires:  intltool
BuildRequires:  gettext
BuildRequires:  meson
BuildRequires:  ninja-build

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
%meson
%meson_build

%install
%meson_install

%files
%license COPYING
%{_bindir}/xfce4-session*
%{_bindir}/xfce4-session-logout
%{_datadir}/xsessions/*.desktop
%{_datadir}/wayland-sessions/*.desktop
%{_libexecdir}/xfce4/

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 4.21.0-1
- Initial XFCE Wayland package for TunaOS EL10
