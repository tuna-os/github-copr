Name: xfce4-sensors-plugin
Version: 1.4.5
Release: 1%{?dist}
Summary: Sensors plugin for the Xfce panel
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/panel-plugins/xfce4-sensors-plugin
Source0: https://gitlab.xfce.org/panel-plugins/xfce4-sensors-plugin/-/archive/xfce4-sensors-plugin-1.4.5/xfce4-sensors-plugin-1.4.5.tar.gz
BuildRequires: gtk3-devel, libxfce4ui-devel, libxfce4util-devel, xfce4-panel-devel, lm_sensors-devel, intltool, gettext, autoconf, automake, libtool
Requires: xfce4-panel, lm_sensors
%description
Sensors plugin for the Xfce panel. Displays system sensor information
such as temperatures, voltages, and fan speeds.
%prep
%autosetup -n xfce4-sensors-plugin-%{version}
%build
NOCONFIGURE=1 ./autogen.sh
%configure --disable-gtk-doc
%make_build
%install
%make_install
%files
%license COPYING
%{_libdir}/xfce4/panel/plugins/libsensors.so
%{_datadir}/xfce4/panel/plugins/*.desktop
%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 1.4.5-1
- Initial XFCE Wayland package for TunaOS EL10
