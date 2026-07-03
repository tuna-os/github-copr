Name: xfce4-weather-plugin
Version: 0.11.3
Release: 1%{?dist}
Summary: Weather plugin for the Xfce panel
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/panel-plugins/xfce4-weather-plugin
Source0: https://archive.xfce.org/src/panel-plugins/xfce4-weather-plugin/0.11/xfce4-weather-plugin-0.11.3.tar.bz2
BuildRequires: gtk3-devel, libxfce4ui-devel, libxfce4util-devel, xfce4-panel-devel, libsoup-devel, upower-devel, intltool, gettext, meson, ninja-build
Requires: xfce4-panel
%description
Weather plugin for the Xfce panel. Displays current weather conditions
and forecasts using online weather services.
%prep
%autosetup -n xfce4-weather-plugin-%{version}
%build
%meson
%meson_build
%install
%meson_install
%files
%license COPYING
%{_libdir}/xfce4/panel/plugins/libweather.so
%{_datadir}/xfce4/panel/plugins/*.desktop
%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 0.11.2-1
- Initial XFCE Wayland package for TunaOS EL10
