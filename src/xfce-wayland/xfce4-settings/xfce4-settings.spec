%global commit 8e9f1a16f189a27b6d36c444d86a8b220ee90062
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name:           xfce4-settings
Version:        4.21.0
Release:        1%{?dist}
Summary:        Settings manager for the Xfce desktop environment

License:        GPL-2.0-or-later
URL:            https://gitlab.xfce.org/xfce/xfce4-settings
Source0: https://gitlab.xfce.org/xfce/xfce4-settings/-/archive/%{commit}/xfce4-settings-%{commit}.tar.gz

BuildRequires: gcc
BuildRequires:  gtk3-devel
BuildRequires:  libxfce4ui-devel
BuildRequires:  libxfce4util-devel
BuildRequires:  xfconf-devel
BuildRequires:  colord-devel
BuildRequires:  upower-devel
BuildRequires:  intltool
BuildRequires:  gettext
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  garcon-devel
BuildRequires:  gtk-layer-shell-devel
BuildRequires:  wlr-protocols

Requires:       xfconf

%description
Xfce4-settings provides the graphical settings manager for the Xfce desktop
environment. It includes dialogs for configuring accessibility, appearance,
display, keyboard, mouse, MIME types, and more. The settings daemon
xfsettingsd applies preferences at session startup.

%prep
%autosetup -n xfce4-settings-%{commit}

%build
# Wayland-only build (matches this stack's convention elsewhere) — avoids
# needing libnotify/libxklavier/xcursor/xorg-libinput/xrandr X11-only devel.
%meson -Dx11=disabled
%meson_build

%install
%meson_install
%find_lang %{name}

%files -f %{name}.lang
%license COPYING
%{_bindir}/xfce4-settings-manager
%{_bindir}/xfce4-settings-editor
%{_bindir}/xfce4-accessibility-settings
%{_bindir}/xfce4-appearance-settings
%{_bindir}/xfce4-display-settings
%{_bindir}/xfce4-keyboard-settings
%{_bindir}/xfce4-mime-settings
%{_bindir}/xfce4-mouse-settings
%{_bindir}/xfsettingsd
%{_datadir}/applications/*.desktop
%{_datadir}/xfce4/helpers/
%{_datadir}/icons/hicolor/*/apps/*.png
%{_datadir}/icons/hicolor/*/apps/*.svg
%{_datadir}/icons/hicolor/*/devices/*.png
%{_datadir}/icons/hicolor/*/devices/*.svg
%{_libdir}/xfce4/
%{_libdir}/gtk-3.0/modules/*.so
%{_sysconfdir}/xdg/xfce4/
%{_sysconfdir}/xdg/menus/xfce-settings-manager.menu
%{_sysconfdir}/xdg/autostart/*.desktop

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 4.21.0-1
- Initial XFCE Wayland package for TunaOS EL10
