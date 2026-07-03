Name: xfce4-wayland
Version: 4.21.0
Release: 1%{?dist}
Summary: Xfce4 Wayland desktop environment
License: GPL-2.0-or-later AND LGPL-2.0-or-later

Requires: xfwl4
Requires: xfce4-panel, xfce4-session, xfdesktop, xfce4-settings
Requires: thunar, xfce4-terminal, xfce4-power-manager
Requires: xfce4-notifyd, xfce4-appfinder
Requires: xfce4-pulseaudio-plugin, xfce4-clipman-plugin
Requires: xfce4-taskmanager, xfce4-screenshooter
Requires: xfce4-sensors-plugin, xfce4-weather-plugin
Requires: xfce4-netload-plugin, xfce4-cpugraph-plugin
Requires: xfce4-datetime-plugin, xfce4-genmon-plugin

%description
Xfce4 desktop environment built for Wayland.
Includes the xfwl4 compositor, panel, session manager,
file manager (thunar), terminal, and essential plugins.

%files
# metapackage - no files

%changelog
* Sat Jun 27 2026 TunaOS Bot <bot@tunaos.org> - 4.21.0-1
- Initial XFCE Wayland metapackage
